"""Optional, independent GeoSphere Austria C-LAEF solar data coordinator."""

from __future__ import annotations

from datetime import timedelta
import logging

from aiohttp import ClientTimeout
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .geosphere_data import as_utc, parse_geosphere_forecast, upcoming_rows

_LOGGER = logging.getLogger(__name__)
GEOSPHERE_URL = (
    "https://dataset.api.hub.geosphere.at/v1/timeseries/forecast/nwp-v2-1h-1km"
)
SOLAR_REFRESH_INTERVAL = timedelta(hours=3)


class GeoSphereSolarCoordinator(DataUpdateCoordinator):
    """Fetch solar forecasts separately from Meteonomiqs and its API quota."""

    def __init__(self, hass, entry):
        super().__init__(
            hass,
            _LOGGER,
            name="GeoSphereSolarCoordinator",
            update_interval=SOLAR_REFRESH_INTERVAL,
        )
        self.latitude = entry.data["latitude"]
        self.longitude = entry.data["longitude"]
        self.last_successful_update = None
        self._store = Store(hass, 1, f"my_weather_geosphere_{entry.entry_id}")

    async def async_initialize(self):
        """Reuse a recent snapshot across restarts without an unnecessary fetch."""
        try:
            stored = await self._store.async_load()
            if isinstance(stored, dict) and isinstance(stored.get("data"), dict):
                cached = stored["data"]
                if isinstance(cached.get("forecast"), list) and cached["forecast"]:
                    self.async_set_updated_data(cached)
                    self.last_successful_update = as_utc(stored.get("last_update"))
        except (ValueError, TypeError, OSError):
            _LOGGER.warning("GeoSphere: stored solar forecast could not be loaded")

        now = dt_util.utcnow()
        if (
            self.last_successful_update is None
            or now - self.last_successful_update >= SOLAR_REFRESH_INTERVAL
            or not upcoming_rows(self.data, now, 1)
        ):
            # A GeoSphere outage must never prevent Meteonomiqs setup.
            await self.async_refresh()

    async def _async_update_data(self):
        try:
            session = async_get_clientsession(self.hass)
            params = {
                "parameters": "ssrd,tcc",
                "lat_lon": f"{self.latitude},{self.longitude}",
                "output_format": "geojson",
            }
            async with session.get(
                GEOSPHERE_URL,
                params=params,
                headers={"Accept": "application/json"},
                timeout=ClientTimeout(total=25),
            ) as response:
                if response.status != 200:
                    raise ValueError(f"HTTP {response.status}")
                parsed = parse_geosphere_forecast(await response.json())

            now = dt_util.utcnow()
            self.last_successful_update = now
            try:
                await self._store.async_save({
                    "last_update": now.isoformat(),
                    "data": parsed,
                })
            except (OSError, ValueError):
                _LOGGER.warning("GeoSphere: could not persist solar forecast cache")
            return parsed
        except Exception as err:
            # Never clear a previously published forecast or disrupt Meteonomiqs.
            _LOGGER.warning(
                "GeoSphere solar forecast request failed (%s)", type(err).__name__
            )
            if self.data and upcoming_rows(self.data, dt_util.utcnow(), 1):
                return self.data
            raise UpdateFailed(
                "GeoSphere solar forecast unavailable; keeping Meteonomiqs unaffected"
            ) from err
