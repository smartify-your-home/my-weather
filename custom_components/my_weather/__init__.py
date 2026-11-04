from __future__ import annotations

import logging
from datetime import timedelta
from homeassistant.config_entries import ConfigEntry, ConfigEntryNotReady
from homeassistant.core import HomeAssistant, ServiceCall
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
)
from .coordinator import MeteonomiqsDataUpdateCoordinator
from .secrets import async_load_secret_keys, SecretKeyError

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict):
    """YAML setup not used."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    _LOGGER.debug("MY_WEATHER: async_setup_entry START – id=%s", entry.entry_id)

    hass.data.setdefault(DOMAIN, {})

    # Existing plaintext API keys are supported for backwards compatibility.
    # Named secrets take priority and are never written into the config entry.
    secret_names = entry.options.get(
        CONF_API_KEY_SECRETS, entry.data.get(CONF_API_KEY_SECRETS, []),
    )
    if secret_names:
        try:
            api_keys = await async_load_secret_keys(hass, secret_names)
        except SecretKeyError as err:
            raise ConfigEntryNotReady(
                "Meteonomiqs: cannot resolve configured secrets.yaml API key names"
            ) from err
    else:
        api_keys = entry.data.get(CONF_API_KEYS)
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
        target = dt_util.as_utc(now) + timedelta(minutes=5)
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
        unsub_schedules.append(async_track_time_change(
            hass, prefetch_before_hour, hour=(hour - 1) % 24, minute=55, second=0,
        ))
        unsub_schedules.append(async_track_time_change(
            hass, publish_on_hour, hour=hour, minute=0, second=0,
        ))

    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
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
                coord = data.get("coordinator")
                if coord:
                    await coord.async_request_refresh()

        hass.services.async_register(
            DOMAIN,
            "update",
            handle_manual_update,
        )

        _LOGGER.debug("MY_WEATHER: Service my_weather.update registered")

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
        entry.async_unload()

        # Remove service if this was the last entry
        if not hass.data[DOMAIN]:
            hass.services.async_remove(DOMAIN, "update")
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
