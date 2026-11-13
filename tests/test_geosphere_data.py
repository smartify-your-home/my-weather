"""Offline regression tests for the GeoSphere solar forecast bridge.

No Home Assistant installation or live external API is required.
"""

from datetime import datetime, timedelta, timezone
import importlib.util
from pathlib import Path
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "custom_components/my_weather/geosphere_data.py"
spec = importlib.util.spec_from_file_location("geosphere_data", SOURCE)
data = importlib.util.module_from_spec(spec)
spec.loader.exec_module(data)


def fixture(ghi=(0, 400, 800), clouds=(90, 40, None)):
    return {
        "reference_time": "2026-11-13T06:00:00Z",
        "timestamps": [
            "2026-11-13T07:00:00Z",
            "2026-11-13T08:00:00Z",
            "2026-11-13T09:00:00Z",
        ],
        "features": [{"properties": {"parameters": {
            "ssrd": {"unit": "W m-2", "data": list(ghi)},
            "tcc": {"unit": "%", "data": list(clouds)},
        }}}],
    }


class TestGeoSphereData(unittest.TestCase):
    def test_watts_not_cumulative(self):
        parsed = data.parse_geosphere_forecast(fixture())
        values = [row["ghi_w_m2"] for row in parsed["forecast"]]
        self.assertEqual(values, [0, 400, 800])
        self.assertEqual(parsed["dataset"], "nwp-v2-1h-1km")

    def test_utc_intervals_and_partial_energy(self):
        parsed = data.parse_geosphere_forecast(fixture())
        now = datetime(2026, 11, 13, 7, 30, tzinfo=timezone.utc)
        rows = data.upcoming_rows(parsed, now)
        self.assertEqual(len(rows), 2)
        self.assertEqual(data.current_row(parsed, now)["ghi_w_m2"], 400)
        # 400 W/m² for 30 min + 800 W/m² for 60 min.
        self.assertEqual(data.remaining_energy_kwh_m2(rows, now), 1.0)

    def test_expired_forecast_never_rolls_over_to_first_row(self):
        parsed = data.parse_geosphere_forecast(fixture())
        now = datetime(2026, 11, 13, 11, tzinfo=timezone.utc)
        self.assertEqual(data.upcoming_rows(parsed, now), [])
        self.assertIsNone(data.current_row(parsed, now))
        self.assertIsNone(data.remaining_energy_kwh_m2([], now))

    def test_missing_clouds_are_null_not_clear_sky(self):
        parsed = data.parse_geosphere_forecast(fixture())
        self.assertIsNone(parsed["forecast"][2]["cloud_coverage"])
        self.assertEqual(parsed["forecast"][0]["cloud_coverage"], 90)

    def test_invalid_response_cannot_replace_snapshot(self):
        bad = fixture()
        bad["features"][0]["properties"]["parameters"]["ssrd"]["data"] = [3]
        with self.assertRaises(ValueError):
            data.parse_geosphere_forecast(bad)

    def test_all_missing_rejected(self):
        with self.assertRaises(ValueError):
            data.parse_geosphere_forecast(fixture((None, None, None), (None, None, None)))

    def test_timezone_aware(self):
        parsed = data.parse_geosphere_forecast(fixture())
        now = datetime(2026, 11, 13, 9, 30, tzinfo=timezone(timedelta(hours=1)))
        self.assertEqual(len(data.upcoming_rows(parsed, now)), 1)

    def test_reject_bogus_values(self):
        parsed = data.parse_geosphere_forecast(fixture((None, -10, 3000), (-1, 101, 25)))
        self.assertIsNone(parsed["forecast"][1]["ghi_w_m2"])
        self.assertIsNone(parsed["forecast"][0]["cloud_coverage"])
        self.assertEqual(parsed["forecast"][2]["cloud_coverage"], 25.0)


if __name__ == "__main__":
    unittest.main()
