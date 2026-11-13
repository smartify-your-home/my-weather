"""Offline checks for GeoSphere 60h Home Assistant entities and scheduler wiring.

Mock HA's small sensor interface so this runs without a live installation.
"""
from datetime import datetime, timedelta, timezone
import ast
import importlib.util
from pathlib import Path
import sys
import types
from unittest import TestCase, main
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1] / "custom_components/my_weather"
NOW = datetime(2026, 11, 13, 8, 30, tzinfo=timezone.utc)


def stub_module(name, **attrs):
    module = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(module, key, value)
    return module


def load_sensor():
    class CoordinatorEntity:
        def __init__(self, coordinator):
            self.coordinator = coordinator

    dt = stub_module("homeassistant.util.dt", utcnow=lambda: NOW)
    fake = {
        "homeassistant": stub_module("homeassistant"),
        "homeassistant.components": stub_module("homeassistant.components"),
        "homeassistant.components.sensor": stub_module(
            "homeassistant.components.sensor",
            SensorEntity=type("SensorEntity", (), {}),
            SensorDeviceClass=type("SensorDeviceClass", (), {"TIMESTAMP": "timestamp"}),
            SensorStateClass=type("SensorStateClass", (), {"MEASUREMENT": "measurement"}),
        ),
        "homeassistant.const": stub_module(
            "homeassistant.const",
            EntityCategory=type("EntityCategory", (), {"DIAGNOSTIC": "diagnostic"}),
            PERCENTAGE="%",
        ),
        "homeassistant.helpers": stub_module("homeassistant.helpers"),
        "homeassistant.helpers.update_coordinator": stub_module(
            "homeassistant.helpers.update_coordinator",
            CoordinatorEntity=CoordinatorEntity,
        ),
        "homeassistant.util": stub_module("homeassistant.util", dt=dt),
        "homeassistant.util.dt": dt,
        "geosphere_sensor_offline_pkg": stub_module("geosphere_sensor_offline_pkg"),
    }
    fake["geosphere_sensor_offline_pkg"].__path__ = [str(ROOT)]
    with patch.dict(sys.modules, fake):
        spec = importlib.util.spec_from_file_location(
            "geosphere_sensor_offline_pkg.geosphere_sensor", ROOT / "geosphere_sensor.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod


class GeoSphereEntitiesTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_sensor()

    def setUp(self):
        rows = [
            {
                "datetime": (NOW - timedelta(minutes=30)).isoformat(),
                "end": (NOW + timedelta(minutes=30)).isoformat(),
                "ghi_w_m2": 300,
                "cloud_coverage": 60,
            },
            {
                "datetime": (NOW + timedelta(minutes=30)).isoformat(),
                "end": (NOW + timedelta(minutes=90)).isoformat(),
                "ghi_w_m2": 600,
                "cloud_coverage": 40,
            },
        ]
        self.coordinator = types.SimpleNamespace(
            data={"forecast": rows, "model_run": NOW.isoformat()},
            last_successful_update=NOW,
        )
        self.entry = types.SimpleNamespace(entry_id="offline-test")

    def sensor(self, kind):
        return self.module.GeoSphereSolarSensor(self.coordinator, self.entry, kind)

    def test_cloud_60h_exposes_average_and_forecast(self):
        sensor = self.sensor("cloud_60h")
        self.assertTrue(sensor.available)
        self.assertEqual(sensor.native_value, 50)
        self.assertEqual(sensor.extra_state_attributes["forecast_hours"], 2)
        self.assertEqual(sensor.extra_state_attributes["valid_cloud_hours"], 2)
        self.assertEqual(sensor.extra_state_attributes["irradiance_unit"], "W/m²")
        self.assertEqual(sensor.extra_state_attributes["source"], "GeoSphere Austria C-LAEF")

    def test_solar_60h_exposes_energy_and_forecast(self):
        sensor = self.sensor("energy_60h")
        self.assertEqual(sensor.native_value, 0.75)
        self.assertEqual(len(sensor.extra_state_attributes["forecast"]), 2)
        self.assertEqual(sensor.extra_state_attributes["max_forecast_hours"], 60)

    def test_ghi_and_model_run(self):
        self.assertEqual(self.sensor("ghi").native_value, 300)
        self.assertEqual(self.sensor("model_run").native_value, NOW)

    def test_missing_forecast_does_not_appear_as_zero(self):
        self.coordinator.data["forecast"] = []
        self.assertFalse(self.sensor("cloud_60h").available)
        self.assertIsNone(self.sensor("cloud_60h").native_value)
        self.assertIsNone(self.sensor("energy_60h").native_value)

    def test_no_48h_branch_left_for_new_sensors(self):
        code = (ROOT / "geosphere_sensor.py").read_text(encoding="utf-8")
        self.assertNotIn('self.kind == "cloud_48h"', code)
        self.assertNotIn('self.kind == "energy_48h"', code)
        self.assertNotIn('self.kind in ("cloud_48h"', code)

    def test_hourly_tick_preserves_poll_schedule_and_shutdown_is_awaited(self):
        source = (ROOT / "geosphere_solar.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        coordinator = next(x for x in tree.body if isinstance(x, ast.ClassDef)
                           and x.name == "GeoSphereSolarCoordinator")
        tick = next(x for x in coordinator.body if isinstance(x, ast.FunctionDef)
                    and x.name == "_on_time_tick")
        calls = [n.func.attr for n in ast.walk(tick) if isinstance(n, ast.Call)
                 and isinstance(n.func, ast.Attribute)]
        self.assertIn("async_update_listeners", calls)
        self.assertNotIn("async_set_updated_data", calls)
        shutdown = next(x for x in coordinator.body if isinstance(x, ast.AsyncFunctionDef)
                        and x.name == "async_shutdown")
        self.assertTrue(any(isinstance(n, ast.Await) for n in ast.walk(shutdown)))
        init_source = (ROOT / "__init__.py").read_text(encoding="utf-8")
        self.assertIn("await solar.async_shutdown()", init_source)


if __name__ == "__main__":
    main()
