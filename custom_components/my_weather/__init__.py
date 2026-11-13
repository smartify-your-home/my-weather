from __future__ import annotations

import logging
from pathlib import Path
from homeassistant.config_entries import ConfigEntry, ConfigEntryNotReady
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import CoreState, HomeAssistant, ServiceCall, callback
from homeassistant.helpers.event import async_track_time_change
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    PLATFORMS,
    CONF_API_KEY,
    CONF_API_KEYS,
    CONF_API_KEY_SECRETS,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_LANGUAGE,
    CONF_UPDATE_TIMES,
    CONF_GEOSPHERE_SOLAR,
    DEFAULT_GEOSPHERE_SOLAR,
)
from .card_resource import CARD_PATH, async_register_card, card_url
from .coordinator import MeteonomiqsDataUpdateCoordinator
from .geosphere_solar import GeoSphereSolarCoordinator
from .secrets import async_load_fixed_secret_keys, SecretKeyError
from .timing import prefetch_hour_slot, publication_target

_LOGGER = logging.getLogger(__name__)


def _extra_js_fallback(hass: HomeAssistant, url: str) -> None:
    """Lovelace YAML mode only: no storage resource can be created."""
    from homeassistant.components.frontend import add_extra_js_url

    add_extra_js_url(hass, url)


@callback
def _schedule_card_registration(hass: HomeAssistant, url: str) -> None:
    """Register the card resource in the event loop once Home Assistant runs.

    Listeners that call hass.async_* MUST be @callback (a plain def would run
    in an executor thread). Retries happen inside one background task.
    """
    @callback
    def _start(_event=None) -> None:
        hass.async_create_background_task(
            async_register_card(hass, url, extra_js_fallback=_extra_js_fallback),
            f"{DOMAIN}_card_resource",
        )

    if hass.state is CoreState.running:
        _start()
    else:
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _start)


async def async_setup(hass: HomeAssistant, config: dict):
    """YAML setup not used."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    _LOGGER.debug("MY_WEATHER: async_setup_entry START – id=%s", entry.entry_id)

    hass.data.setdefault(DOMAIN, {})

    # Fixed secret slots are preferred when present. Missing slots are optional.
    try:
        api_keys = await async_load_fixed_secret_keys(hass)
    except SecretKeyError as err:
        raise ConfigEntryNotReady(
            "Meteonomiqs: invalid fixed API key in secrets.yaml"
        ) from err
    if not api_keys:
        # Keep older manually configured entries working unchanged.
        api_keys = entry.data.get(CONF_API_KEYS) or []
        if not api_keys:
            legacy = entry.data.get(CONF_API_KEY)
            api_keys = [legacy] if legacy else []

    if not api_keys:
        raise ConfigEntryNotReady("Meteonomiqs: No API keys configured")

    latitude = entry.data.get(CONF_LATITUDE)
    longitude = entry.data.get(CONF_LONGITUDE)
    language = entry.data.get(CONF_LANGUAGE, "en")

    # Create coordinator
    coordinator = MeteonomiqsDataUpdateCoordinator(
        hass,
        api_keys,
        latitude,
        longitude,
        language,
    )

    # Initial refresh (uses cache if valid)
    await coordinator.async_config_entry_first_refresh()
    _LOGGER.debug("MY_WEATHER: First refresh finished")

    # A scheduled refresh is optional; manual refresh remains independent.
    unsub_schedules = []

    async def prefetch_before_hour(now):
        """Read forecast five minutes before the configured publication hour."""
        target = publication_target(now)
        try:
            await coordinator.async_prefetch(target)
        except Exception:
            _LOGGER.exception("MY_WEATHER: scheduled forecast prefetch failed")

    async def publish_on_hour(now):
        """Switch cached forecast hour and pending API data at one boundary."""
        target = dt_util.as_utc(now)
        if not coordinator.async_publish_staged(target):
            coordinator._recalculate_current_index()

    for slot in entry.options.get(CONF_UPDATE_TIMES, []):
        try:
            hour, minute = (int(part) for part in slot.split(":"))
            if not (0 <= hour <= 23 and minute == 0):
                raise ValueError("scheduled times must be full hours")
        except (ValueError, AttributeError):
            _LOGGER.warning("MY_WEATHER: ignoring invalid publication time %r", slot)
            continue
        prefetch_hour, prefetch_minute = prefetch_hour_slot(hour)
        unsub_schedules.append(async_track_time_change(
            hass, prefetch_before_hour, hour=prefetch_hour, minute=prefetch_minute, second=0,
        ))
        unsub_schedules.append(async_track_time_change(
            hass, publish_on_hour, hour=hour, minute=0, second=0,
        ))

    solar_coordinator = None
    if entry.options.get(CONF_GEOSPHERE_SOLAR, DEFAULT_GEOSPHERE_SOLAR):
        solar_coordinator = GeoSphereSolarCoordinator(hass, entry)
        await solar_coordinator.async_initialize()

    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "solar_coordinator": solar_coordinator,
        "unsub_schedules": unsub_schedules,
    }
    entry.async_on_unload(entry.add_update_listener(async_update_options))

    # -------------------------------------------------
    # Register manual update service (ONLY ONCE)
    # -------------------------------------------------
    if not hass.services.has_service(DOMAIN, "update"):

        async def handle_manual_update(call: ServiceCall):
            # Optional: support future multi-entry updates
            for data in hass.data.get(DOMAIN, {}).values():
                if not isinstance(data, dict):
                    continue
                coord = data.get("coordinator")
                if coord:
                    await coord.async_request_refresh()

        hass.services.async_register(
            DOMAIN,
            "update",
            handle_manual_update,
        )

        _LOGGER.debug("MY_WEATHER: Service my_weather.update registered")

    # GeoSphere manual refresh is independent of Meteonomiqs key quotas.
    if not hass.services.has_service(DOMAIN, "update_solar"):

        async def handle_solar_update(call: ServiceCall):
            for data in hass.data.get(DOMAIN, {}).values():
                if isinstance(data, dict) and data.get("solar_coordinator"):
                    await data["solar_coordinator"].async_request_refresh()

        hass.services.async_register(DOMAIN, "update_solar", handle_solar_update)

    # Provide the standalone cloud chart without third-party Lovelace cards.
    # The sensor is available even in headless Home Assistant installations.
    # The card is registered as a Lovelace resource, NOT via add_extra_js_url
    # (see card_resource.py for the reason); extra JS is only the YAML-mode fallback.
    if not hass.data[DOMAIN].get("_cloud_card_registered"):
        try:
            from homeassistant.components.http import StaticPathConfig
            from homeassistant.loader import async_get_integration

            if getattr(hass, "http", None) is not None:
                card_path = Path(__file__).parent / "www" / "my-weather-cloud-8h-card.js"
                await hass.http.async_register_static_paths([
                    StaticPathConfig(CARD_PATH, str(card_path), False)
                ])
                version = (await async_get_integration(hass, DOMAIN)).version
                _schedule_card_registration(hass, card_url(str(version)))
                hass.data[DOMAIN]["_cloud_card_registered"] = True
        except (ImportError, OSError, RuntimeError):
            _LOGGER.warning("MY_WEATHER: cloud chart registration unavailable", exc_info=True)

    # Forward platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _LOGGER.debug("MY_WEATHER: async_setup_entry END — Platforms forwarded")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    _LOGGER.debug("MY_WEATHER: async_unload_entry for %s", entry.entry_id)

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        data = hass.data[DOMAIN].pop(entry.entry_id, {})
        for unsub in data.get("unsub_schedules", []):
            unsub()
        if coordinator := data.get("coordinator"):
            coordinator.async_shutdown()
        if solar := data.get("solar_coordinator"):
            await solar.async_shutdown()
        # Home Assistant owns ConfigEntry unloading; do not recursively unload it.

        # Remove service if this was the last entry
        if not any(isinstance(value, dict) and "coordinator" in value
                   for value in hass.data[DOMAIN].values()):
            hass.services.async_remove(DOMAIN, "update")
            if hass.services.has_service(DOMAIN, "update_solar"):
                hass.services.async_remove(DOMAIN, "update_solar")
            _LOGGER.debug("MY_WEATHER: Service my_weather.update removed")

    return unload_ok


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old entries to the new api_keys list format."""
    _LOGGER.debug("MY_WEATHER: Migrating config entry from v%s", entry.version)

    if entry.version < 3:
        data = dict(entry.data)

        # Legacy: single api_key -> api_keys list
        if CONF_API_KEYS not in data:
            legacy = data.get(CONF_API_KEY)
            if legacy:
                # allow comma/newline separated too
                raw = str(legacy)
                parts = []
                for chunk in raw.replace(";", ",").splitlines():
                    parts.extend([p.strip() for p in chunk.split(",")])
                keys = [p for p in parts if p]
                # de-duplicate preserve order, max 4
                seen = set()
                out = []
                for k in keys:
                    if k not in seen:
                        seen.add(k)
                        out.append(k)
                data[CONF_API_KEYS] = out[:4]
            else:
                data[CONF_API_KEYS] = []

        # Keep CONF_API_KEY for backwards compatibility? Remove to avoid confusion.
        data.pop(CONF_API_KEY, None)

        hass.config_entries.async_update_entry(entry, data=data, version=3)
        _LOGGER.info("MY_WEATHER: Migration to v3 successful")

    return True


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry):
    """Apply changed scheduled fetch times without duplicate timers."""
    await hass.config_entries.async_reload(entry.entry_id)
