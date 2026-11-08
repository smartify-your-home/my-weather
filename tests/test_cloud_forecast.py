"""Regression tests for 8h cloud bridge, including stale-cache handling."""
import unittest
from datetime import datetime, timedelta, timezone
import importlib.util
from pathlib import Path
import sys
import types

root = Path(__file__).resolve().parents[1] / "custom_components/my_weather"
package = types.ModuleType("my_weather_test")
package.__path__ = [str(root)]
sys.modules["my_weather_test"] = package
for name in ("timing", "cloud_forecast"):
    spec = importlib.util.spec_from_file_location(f"my_weather_test.{name}", root / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
cloud_forecast_8h = sys.modules["my_weather_test.cloud_forecast"].cloud_forecast_8h
cloud_forecast = sys.modules["my_weather_test.cloud_forecast"].cloud_forecast


class CloudForecastTests(unittest.TestCase):
    def test_eight_values_and_missing_clouds(self):
        origin = datetime(2026, 11, 8, 10, tzinfo=timezone.utc)
        rows = [
            {"from": (origin + timedelta(hours=i)).isoformat(),
             "to": (origin + timedelta(hours=i + 1)).isoformat(),
             "clouds": {"eights": i if i < 8 else 8}}
            for i in range(10)
        ]
        rows[3]["clouds"] = {}
        values = cloud_forecast_8h(rows, origin + timedelta(minutes=10))
        self.assertEqual(len(values), 8)
        self.assertEqual(values[0]["cloud_coverage"], 0)
        self.assertEqual(values[2]["cloud_coverage"], 25)
        self.assertIsNone(values[3]["cloud_coverage"])
        self.assertEqual(values[7]["cloud_coverage"], 88)


    def test_48h_forecast_is_bounded_and_preserves_8h_sensor(self):
        origin = datetime(2026, 11, 8, 10, tzinfo=timezone.utc)
        rows = [{"from": (origin + timedelta(hours=i)).isoformat(),
                 "to": (origin + timedelta(hours=i + 1)).isoformat(),
                 "clouds": {"eights": i % 9}} for i in range(72)]
        full = cloud_forecast(rows, origin + timedelta(minutes=10), 48)
        self.assertEqual(len(full), 48)
        self.assertEqual(full[-1]["datetime"], (origin + timedelta(hours=47)).isoformat())
        self.assertEqual(len(cloud_forecast_8h(rows, origin)), 8)

    def test_short_api_response_and_unknown_clouds(self):
        origin = datetime(2026, 11, 8, 10, tzinfo=timezone.utc)
        rows = [{"from": (origin + timedelta(hours=i)).isoformat(),
                 "to": (origin + timedelta(hours=i + 1)).isoformat(),
                 "clouds": {} if i == 4 else {"eights": 3}} for i in range(19)]
        result = cloud_forecast(rows, origin, 48)
        self.assertEqual(len(result), 19)
        self.assertIsNone(result[4]["cloud_coverage"])
        self.assertEqual(len([r for r in result if r["cloud_coverage"] is not None]), 18)
        self.assertEqual(cloud_forecast(rows, origin + timedelta(days=7), 48), [])

    def test_stale_cache_never_falls_back_to_first_hour(self):
        origin = datetime(2026, 11, 8, 10, tzinfo=timezone.utc)
        rows = [{"from": origin.isoformat(),
                 "to": (origin + timedelta(hours=1)).isoformat(),
                 "clouds": {"eights": 8}}]
        self.assertEqual(cloud_forecast_8h(rows, origin + timedelta(days=1)), [])

    def test_timezone_offset_finds_correct_interval(self):
        origin = datetime(2026, 11, 8, 10, tzinfo=timezone.utc)
        row = {"from": origin.isoformat(),
               "to": (origin + timedelta(hours=1)).isoformat(),
               "clouds": {"eights": 4}}
        self.assertEqual(cloud_forecast_8h([row], datetime.fromisoformat("2026-11-08T11:30:00+01:00"))[0]["cloud_coverage"], 50)

    def test_invalid_percentage_is_unknown(self):
        origin = datetime(2026, 11, 8, 10, tzinfo=timezone.utc)
        row = {"from": origin.isoformat(),
               "to": (origin + timedelta(hours=1)).isoformat(),
               "clouds": {"eights": 12}}
        self.assertIsNone(cloud_forecast_8h([row], origin)[0]["cloud_coverage"])


if __name__ == "__main__":
    unittest.main()
