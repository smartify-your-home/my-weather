from __future__ import annotations

import logging
from datetime import timedelta

from aiohttp import ClientTimeout
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import dt as dt_util
from .weather import map_condition_from_state

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

    @staticmethod
    def _parse_utc(value):
        """Parse an API timestamp without overwriting an existing UTC offset."""
        parsed = dt_util.parse_datetime(value) if value else None
        if parsed is None:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt_util.UTC)
        return dt_util.as_utc(parsed)

    @classmethod
    def _index_for_time(cls, hourly, now):
        """Find the actual hour by timestamps, never by a guessed array position."""
        for index, hour in enumerate(hourly):
            if not isinstance(hour, dict):
                continue
            start = cls._parse_utc(hour.get("from"))
            end = cls._parse_utc(hour.get("to"))
            if start is not None and end is not None and start <= now < end:
                return index
        return None

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
        # Grace period: when a fetch is expected shortly after the hourly boundary,
        # avoid publishing yesterday's forecast shift and a fresh provider revision
        # as two separate transitions. A fresh API snapshot bypasses this delay.
        if old_index is not None and new_index is not None and new_index > old_index:
            target_start = self._parse_utc(hourly[new_index].get("from"))
            now = dt_util.utcnow()
            if (target_start is not None
                    and target_start <= now < target_start + timedelta(minutes=10)
                    and (self.last_successful_update is None
                         or self.last_successful_update < target_start)):
                return False
        updated = dict(self.data)
        updated["current_index"] = new_index
        updated["current"] = hourly[new_index] if new_index is not None else None
        self.data = updated
        self.async_set_updated_data(updated)
        return True

    async def _async_tick_recalculate_current_index(self, now):
        self._recalculate_current_index()

    async def _async_update_data(self):
        await self._async_load_stats()
        now = dt_util.utcnow()
        url = f"{API_BASE}/forecast/{self.latitude}/{self.longitude}"

        if now.month != self.current_month:
            self.current_month = now.month
            self.monthly_call_counter = 0

        session = async_get_clientsession(self.hass)
        attempts = 0
        max_attempts = max(1, len(self.api_keys))
        raw = None

        while attempts < max_attempts:
            headers = {
                "x-api-key": self.api_key,
                "Accept": "application/json",
                "Accept-Language": LANG_MAP.get(self.language, "en-US"),
            }
            try:
                async with session.get(url, headers=headers, timeout=ClientTimeout(total=20)) as resp:
                    if resp.status == 429:
                        attempts += 1
                        self._switch_api_key()
                        continue
                    if resp.status != 200:
                        raise UpdateFailed(f"HTTP {resp.status}")
                    raw = await resp.json()
                    break
            except Exception as err:
                raise UpdateFailed(f"Meteonomiqs fetch error: {err}")

        if raw is None:
            raise UpdateFailed("Meteonomiqs: all API keys returned HTTP 429")

        self.monthly_call_counter += 1
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
        # Publish a coherent snapshot only after the whole response is validated.
        self.last_successful_update = now
        self.data = new_data
        await self._async_save_stats()
        return new_data
