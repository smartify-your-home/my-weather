"""Forecast hour and prefetch boundary regression tests."""

import importlib.util
from pathlib import Path
import unittest
from datetime import datetime, timezone, timedelta

source = Path(__file__).resolve().parents[1] / "custom_components/my_weather/timing.py"
spec = importlib.util.spec_from_file_location("my_weather_timing_test", source)
timing = importlib.util.module_from_spec(spec)
spec.loader.exec_module(timing)


class ForecastTimingTests(unittest.TestCase):
    def setUp(self):
        self.hours = [
            {"from": "2026-11-04T13:00:00+01:00", "to": "2026-11-04T14:00:00+01:00"},
            {"from": "2026-11-04T14:00:00+01:00", "to": "2026-11-04T15:00:00+01:00"},
            {"from": "2026-11-04T15:00:00+01:00", "to": "2026-11-04T16:00:00+01:00"},
        ]

    def test_hour_shifts_exactly_at_boundary(self):
        self.assertEqual(timing.index_for_time(self.hours, datetime(2026,11,4,12,59,59,tzinfo=timezone.utc)), 0)
        self.assertEqual(timing.index_for_time(self.hours, datetime(2026,11,4,13,0,0,tzinfo=timezone.utc)), 1)

    def test_hour_plus_two_becomes_plus_one_same_data(self):
        before = timing.index_for_time(self.hours, datetime(2026,11,4,12,59,tzinfo=timezone.utc))
        after = timing.index_for_time(self.hours, datetime(2026,11,4,13,0,tzinfo=timezone.utc))
        self.assertEqual(self.hours[before + 2], self.hours[after + 1])

    def test_stale_cache_has_no_incorrect_index_zero(self):
        self.assertIsNone(timing.index_for_time(self.hours, datetime(2026,11,5,tzinfo=timezone.utc)))

    def test_offset_not_replaced_by_utc(self):
        self.assertEqual(timing.parse_utc("2026-11-04T14:00:00+01:00"), datetime(2026,11,4,13,tzinfo=timezone.utc))

    def test_dst_fall_back_hours_are_distinct(self):
        hours = [
            {"from":"2026-10-25T02:00:00+02:00", "to":"2026-10-25T02:00:00+01:00"},
            {"from":"2026-10-25T02:00:00+01:00", "to":"2026-10-25T03:00:00+01:00"},
        ]
        self.assertEqual(timing.index_for_time(hours, datetime(2026,10,25,0,30,tzinfo=timezone.utc)),0)
        self.assertEqual(timing.index_for_time(hours, datetime(2026,10,25,1,30,tzinfo=timezone.utc)),1)

    def test_prefetch_midnight_wraps(self):
        self.assertEqual(timing.prefetch_hour_slot(0), (23,55))
        self.assertEqual(timing.prefetch_hour_slot(14), (13,55))

    def test_prefetch_target_utc_crosses_midnight(self):
        start = datetime(2026,11,4,23,55,tzinfo=timezone.utc)
        self.assertEqual(timing.publication_target(start), datetime(2026,11,5,0,0,tzinfo=timezone.utc))

    def test_malformed_timestamps_return_none(self):
        self.assertIsNone(timing.parse_utc("not a date"))


if __name__ == "__main__":
    unittest.main()
