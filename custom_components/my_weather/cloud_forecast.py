"""Stable configurable 8–48 hour cloud forecast for Home Assistant and SEP.

All time comparisons use UTC; output timestamps carry offsets. Missing cloud
measurements stay null and are never silently converted to clear sky.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from .timing import index_for_time, parse_utc


def cloud_forecast_8h(hourly: list[dict], now: datetime) -> list[dict]:
    """Eight current/future hourly slots, aligned to the API's valid intervals."""
    idx = index_for_time(hourly, now)
    if idx is None:
        return []
    result = []
    for row in hourly[idx:]:
        if not isinstance(row, dict):
            continue
        start = parse_utc(row.get("from"))
        end = parse_utc(row.get("to"))
        if start is None or end is None or end <= start:
            continue
        # Reject distant/irregular cache slots; no invented sunshine for gaps.
        if start >= now + timedelta(hours=hours) or end <= now:
            continue
        eights = (row.get("clouds") or {}).get("eights")
        coverage = None
        if isinstance(eights, (int, float)) and not isinstance(eights, bool) and 0 <= eights <= 8:
            coverage = round(eights * 12.5)
        result.append({
            "datetime": start.isoformat(),
            "end": end.isoformat(),
            "cloud_coverage": coverage,
        })
        if len(result) == hours:
            break
    return result


def cloud_forecast_8h(hourly: list[dict], now: datetime) -> list[dict]:
    """Preserved legacy 8h sensor contract and timestamp alignment."""
    return cloud_forecast(hourly, now, 8)
