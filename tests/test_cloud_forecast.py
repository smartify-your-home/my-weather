"""Regression tests for 8h cloud bridge, including stale-cache handling."""
import unittest
from datetime import datetime, timedelta, timezone
from custom_components.my_weather.cloud_forecast import cloud_forecast_8h


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
