from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from aiohttp import ClientTimeout
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import dt as dt_util
from .weather import map_condition_from_state
from .timing import index_for_time, parse_utc

from .const import API_BASE, LANG_MAP

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1

class MeteonomiqsDataUpdateCoordinator(DataUpdateCoordinator):
    """Meteonomiqs Update Coordinator."""

    def __init__(self, hass, api_keys, latitude, longitude, language):
        super().__init__(
            hass,
            _LOGGER,
            name="MeteonomiqsDataUpdateCoordinator",
            update_interval=None,
        )

        self.hass = hass
        self.api_keys = list(api_keys)
        self._current_key_index = 0
        self.latitude = latitude
        self.longitude = longitude
        self.language = language

        self.last_successful_update = None
        self.monthly_call_counter = 0
        self.current_month = dt_util.utcnow().month
        self.data = None
        self._fetch_lock = asyncio.Lock()
        self._pending_snapshot = None
        self._pending_target = None

        lat_key = self._normalize(latitude)
        lon_key = self._normalize(longitude)

        self._store = Store(
            hass,
            STORAGE_VERSION,
            f"my_weather_stats_{lat_key}_{lon_key}",
        )
        self._stats_loaded = False

        self._unsub_index_tick = async_track_time_interval(
            hass,
            self._async_tick_recalculate_current_index,
            timedelta(minutes=1),
        )

    def async_shutdown(self):
        """Remove the periodic cache index tracker on unload."""
        if self._unsub_index_tick:
            self._unsub_index_tick()
            self._unsub_index_tick = None

    @staticmethod
    def _normalize(value):
        try:
            return f"{float(value):.4f}"
        except Exception:
            return str(value)

    @property
    def api_key(self) -> str:
        return self.api_keys[self._current_key_index]

    @property
    def current_key_index(self) -> int:
        return self._current_key_index

    def _switch_api_key(self) -> None:
        """Rotate keys without invalidating published forecast data or the cache."""
        self._current_key_index = (self._current_key_index + 1) % len(self.api_keys)
        _LOGGER.warning("Meteonomiqs: HTTP 429; switching to API key %s", self._current_key_index + 1)

    _parse_utc = staticmethod(parse_utc)
    _index_for_time = staticmethod(index_for_time)

    async def _async_load_stats(self):
        if self._stats_loaded:
            return
        stored = await self._store.async_load()
        if stored:
            self.monthly_call_counter = stored.get("monthly_call_counter", 0)
            self.current_month = stored.get("current_month", self.current_month)
            ts = stored.get("last_successful_update")
            if ts:
                try:
                    self.last_successful_update = dt_util.parse_datetime(ts)
                except Exception:
                    self.last_successful_update = None
            self.data = stored.get("last_data")
        self._stats_loaded = True
        if self.data:
            self._recalculate_current_index()

    async def _async_save_stats(self):
        await self._store.async_save({
            "monthly_call_counter": self.monthly_call_counter,
            "current_month": self.current_month,
            "last_successful_update": (
                self.last_successful_update.isoformat()
                if self.last_successful_update else None
            ),
            "last_data": self.data,
        })

    async def async_config_entry_first_refresh(self):
        await self._async_load_stats()
        if self.data and self.last_successful_update:
            _LOGGER.info("Meteonomiqs: using cached data on startup")
            self.async_set_updated_data(self.data)
            return
        await super().async_config_entry_first_refresh()

    def _recalculate_current_index(self) -> bool:
        if not self.data:
            return False
        hourly = self.data.get("hourly") or []
        new_index = self._index_for_time(hourly, dt_util.utcnow())
        # Never publish hourly[0] as an arbitrary fallback if the cache is stale.
        old_index = self.data.get("current_index")
        if old_index == new_index:
            return False
        # At a scheduled full hour the staged response is published as one update.
        if self._pending_target and dt_util.utcnow() >= self._pending_target:
            if self.async_publish_staged(self._pending_target):
                return True
        updated = dict(self.data)
        updated["current_index"] = new_index
        updated["current"] = hourly[new_index] if new_index is not None else None
        self.data = updated
        self.async_set_updated_data(updated)
        return True

    async def _async_tick_recalculate_current_index(self, now):
        self._recalculate_current_index()

    def async_publish_staged(self, target):
        """Publish a complete snapshot only at or after its scheduled boundary."""
        if self._pending_snapshot is None or self._pending_target != target:
            return False
        if dt_util.utcnow() < target:
            return False
        snapshot = self._pending_snapshot
        self._pending_snapshot = None
        self._pending_target = None
        index = self._index_for_time(snapshot["hourly"], dt_util.utcnow())
        snapshot = dict(snapshot, current_index=index,
                        current=snapshot["hourly"][index] if index is not None else None)
        self.data = snapshot
        self.async_set_updated_data(snapshot)
        self.hass.async_create_task(self._async_save_stats())
        return True

    async def async_prefetch(self, target):
        """Fetch before the scheduled full hour, but do not change sensors."""
        await self._async_load_stats()
        async with self._fetch_lock:
            snapshot = await self._fetch_snapshot()
            self._pending_snapshot = snapshot
            self._pending_target = target
            # If the API response is late, publish as soon as it arrives.
            if dt_util.utcnow() >= target:
                self.async_publish_staged(target)

    async def _async_update_data(self):
        await self._async_load_stats()
        async with self._fetch_lock:
            snapshot = await self._fetch_snapshot()
            # Manual service updates win over any waiting scheduled snapshot.
            self._pending_snapshot = None
            self._pending_target = None
            self.data = snapshot
            await self._async_save_stats()
            return snapshot

    async def _fetch_snapshot(self):
        """Build and validate a fresh forecast without publishing partial data."""
        now = dt_util.utcnow()
        url = f"{API_BASE}/forecast/{self.latitude}/{self.longitude}"

        if now.month != self.current_month:
            self.current_month = now.month
            self.monthly_call_counter = 0

        session = async_get_clientsession(self.hass)
        # Try each configured key at most once. 401/403 deny access for this
        # key; 429 means its quota has been reached. Never disclose key values.
        statuses = []
        raw = None
        for attempt in range(len(self.api_keys)):
            key_number = self._current_key_index + 1
            headers = {
                "x-api-key": self.api_key,
                "Accept": "application/json",
                "Accept-Language": LANG_MAP.get(self.language, "en-US"),
            }
            try:
                async with session.get(url, headers=headers, timeout=ClientTimeout(total=20)) as resp:
                    if resp.status in (401, 403, 429):
                        statuses.append(resp.status)
                        _LOGGER.warning(
                            "Meteonomiqs: API key slot %d rejected (HTTP %d); %s",
                            key_number,
                            resp.status,
                            "trying next key" if attempt + 1 < len(self.api_keys)
                            else "no more configured keys",
                        )
                        if attempt + 1 < len(self.api_keys):
                            self._current_key_index = (
                                self._current_key_index + 1
                            ) % len(self.api_keys)
                        continue
                    if resp.status != 200:
                        raise UpdateFailed(
                            f"Meteonomiqs forecast API returned HTTP {resp.status}"
                        )
                    raw = await resp.json()
                    break
            except UpdateFailed:
                raise
            except Exception as err:
                # Do not include headers, request object or API key in logs.
                _LOGGER.warning("Meteonomiqs: request failed (%s)", type(err).__name__)
                raise UpdateFailed(
                    "Meteonomiqs forecast request failed"
                ) from err

        if raw is None:
            codes = ", ".join(str(code) for code in statuses)
            raise UpdateFailed(
                f"Meteonomiqs forecast access denied for all {len(self.api_keys)} "
                f"configured API key(s) (HTTP responses: {codes}). "
                "Check secret values and forecast API permissions."
            )

        if not isinstance(raw, dict):
            raise UpdateFailed("Meteonomiqs: unexpected API response format")
        hourly = raw.get("hourly") if isinstance(raw.get("hourly"), list) else []

        if not hourly or not any(isinstance(h, dict) and self._parse_utc(h.get("from")) and self._parse_utc(h.get("to")) for h in hourly):
            raise UpdateFailed("Meteonomiqs: response contains no valid hourly forecast")
        current_index = self._index_for_time(hourly, now)

        daily_map = {}
        for h in hourly:
            d = h.get("date")
            if d: daily_map.setdefault(d, []).append(h)

        WEIGHTS = {
            "clear-night": 0, "sunny": 4, "partlycloudy": 5, 
            "rainy": 3, "snowy": 3, "cloudy": 2, "fog": 1, "windy": 1
        }

        daily_list = []
        for d, hours in sorted(daily_map.items()):
            temps = [h.get("temperature", {}).get("avg") for h in hours if isinstance(h.get("temperature", {}).get("avg"), (int, float))]
            
            # Zustands-Logik
            hour_conditions = [
                map_condition_from_state(h.get("weather", {}).get("state"), False)
                for h in hours
            ]
            scores = {}
            for cond in hour_conditions:
                weight = WEIGHTS.get(cond, 1)
                scores[cond] = scores.get(cond, 0) + weight
            best_condition = max(scores, key=scores.get) if scores else "cloudy"

            # Niederschlag & Bewölkung
            prec_sum = sum(h.get("prec", {}).get("sum", 0.0) or h.get("prec", {}).get("amount", 0.0) for h in hours)
            cloud_vals = [h.get("clouds", {}).get("eights", 0) * 12.5 for h in hours if h.get("clouds", {}).get("eights") is not None]
            avg_clouds = round(sum(cloud_vals) / len(cloud_vals), 1) if cloud_vals else 0

            # Wind & Böen Aggregation (KORREKTUR)
            wind_avgs = [h.get("wind", {}).get("avg") for h in hours if isinstance(h.get("wind", {}).get("avg"), (int, float))]
            # Sammle alle Böen-Werte der Stunden
            gust_vals = [h.get("wind", {}).get("gusts", {}).get("value") for h in hours if h.get("wind", {}).get("gusts", {}).get("value") is not None]
            max_gust = max(gust_vals) if gust_vals else 0
            # Check ob IRGENDEINE Stunde eine Warnung hat
            is_significant = any(h.get("wind", {}).get("significantWind") for h in hours)

            daily_list.append({
                "date": d,
                "temperature": {
                    "min": min(temps) if temps else None,
                    "max": max(temps) if temps else None,
                },
                "prec": {"sum": round(prec_sum, 2)},
                "clouds": {"avg": avg_clouds},
                "weather": {
                    "state": best_condition
                },
                "wind": {
                    "avg": round(sum(wind_avgs) / len(wind_avgs), 1) if wind_avgs else 0,
                    "significantWind": is_significant,
                    "gusts": {"value": max_gust} # Exakt so wie in der sensor.py erwartet
                }
            })

        new_data = {
            "raw": raw,
            "hourly": hourly,
            "current": hourly[current_index] if current_index is not None else None,
            "current_index": current_index,
            "daily": daily_list,
        }
        # Save counters without replacing the published cached forecast.
        self.last_successful_update = now
        self.monthly_call_counter += 1
        await self._async_save_stats()
        return new_data
