"""Stable, timestamp-aligned 8–48h cloud forecast from cached Meteonomiqs data.

Missing cloud measurements stay null; stale hourly data never falls back to
hourly[0]. All supplied timestamps are UTC-aware.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .timing import index_for_time, parse_utc


def cloud_forecast(hourly: list[dict], now: datetime, hours: int = 48) -> list[dict]:
    """Return available provider hourly rows, capped at 48 distinct hours."""
    hours = min(48, max(1, int(hours)))
    idx = index_for_time(hourly, now)
    if idx is None:
        return []
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    now = now.astimezone(timezone.utc)
    result: list[dict] = []
    seen: set[datetime] = set()
    # Current interval counts as the first of N hours.
    first = parse_utc(hourly[idx].get("from"))
    if first is None:
        return []
    deadline = first + timedelta(hours=hours)
    for row in hourly[idx:]:
        if not isinstance(row, dict):
            continue
        start = parse_utc(row.get("from"))
        end = parse_utc(row.get("to"))
        if start is None or end is None or end <= start:
            continue
        if start >= deadline:
            break
        if end <= now or start in seen:
            continue
        seen.add(start)
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
    """Preserve the existing eight-hour sensor interface."""
    return cloud_forecast(hourly, now, 8)
