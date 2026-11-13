"""Home Assistant sensors for optional GeoSphere C-LAEF solar forecasts."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, PERCENTAGE
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .geosphere_data import (
    as_utc,
    current_row,
    remaining_energy_kwh_m2,
    upcoming_rows,
)

ATTRIBUTION = "GeoSphere Austria, CC BY 4.0 (data.hub.geosphere.at)"


class GeoSphereSolarSensor(CoordinatorEntity, SensorEntity):
    """A distinct GeoSphere entity; legacy Meteonomiqs IDs stay unchanged."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = False

    def __init__(self, coordinator, entry, kind):
        super().__init__(coordinator)
        self.kind = kind
        self._attr_unique_id = f"{entry.entry_id}_geosphere_{kind}"
        if kind == "ghi":
            self._attr_name = "GeoSphere Solar Radiation GHI"
            self._attr_icon = "mdi:white-balance-sunny"
            self._attr_native_unit_of_measurement = "W/m²"
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif kind == "cloud_60h":
            self._attr_name = "GeoSphere Cloud Forecast 60h"
            self._attr_icon = "mdi:weather-partly-cloudy"
            self._attr_native_unit_of_measurement = PERCENTAGE
        elif kind == "energy_60h":
            self._attr_name = "GeoSphere Solar Irradiation 60h"
            self._attr_icon = "mdi:solar-power"
            self._attr_native_unit_of_measurement = "kWh/m²"
        elif kind == "model_run":
            self._attr_name = "GeoSphere Model Run"
            self._attr_icon = "mdi:clock-outline"
            self._attr_device_class = SensorDeviceClass.TIMESTAMP
            self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def _forecast(self):
        return upcoming_rows(self.coordinator.data, dt_util.utcnow(), 60)

    @property
    def available(self):
        # Preserve still-valid cached hours during a temporary API outage.
        # Once forecast expires, return unavailable rather than stale hour 0.
        return bool(self._forecast)

    @property
    def native_value(self):
        if self.kind == "ghi":
            row = current_row(self.coordinator.data, dt_util.utcnow())
            return round(row["ghi_w_m2"], 1) if row and row["ghi_w_m2"] is not None else None
        if self.kind == "cloud_60h":
            values = [row["cloud_coverage"] for row in self._forecast
                      if row["cloud_coverage"] is not None]
            return round(sum(values) / len(values), 1) if values else None
        if self.kind == "energy_60h":
            return remaining_energy_kwh_m2(self._forecast, dt_util.utcnow())
        if self.kind == "model_run":
            return as_utc((self.coordinator.data or {}).get("model_run"))
        return None

    @property
    def extra_state_attributes(self):
        data = self.coordinator.data or {}
        forecast = self._forecast
        attrs = {
            "source": "GeoSphere Austria C-LAEF",
            "dataset": "nwp-v2-1h-1km",
            "model_run": data.get("model_run"),
            "last_api_update": (
                self.coordinator.last_successful_update.isoformat()
                if self.coordinator.last_successful_update else None
            ),
            "license": "CC BY 4.0",
            "source_url": "https://data.hub.geosphere.at/dataset/nwp-v2-1h-1km",
        }
        if self.kind in ("cloud_60h", "energy_60h"):
            attrs.update({
                "forecast": forecast,
                "forecast_hours": len(forecast),
                "valid_cloud_hours": sum(
                    row["cloud_coverage"] is not None for row in forecast
                ),
                "valid_solar_hours": sum(
                    row["ghi_w_m2"] is not None for row in forecast
                ),
                "max_forecast_hours": 60,
                "irradiance_unit": "W/m²",
                "energy_unit": "kWh/m²",
            })
        return attrs
