"""Pure forecast-time helpers, kept separate for deterministic regression tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone


def parse_utc(value: str | None) -> datetime | None:
    """Parse an ISO timestamp, preserving explicit offsets. Assume UTC if naive."""
    if not value or not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def index_for_time(hourly: list[dict], now: datetime) -> int | None:
    """Return the interval containing now; NEVER fall back to item 0."""
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    now = now.astimezone(timezone.utc)
    for idx, row in enumerate(hourly):
        if not isinstance(row, dict):
            continue
        start, end = parse_utc(row.get("from")), parse_utc(row.get("to"))
        if start is not None and end is not None and start <= now < end:
            return idx
    return None


def prefetch_hour_slot(publication_hour: int) -> tuple[int, int]:
    """Return local wall-clock hour and minute for a five-minute early fetch."""
    if not 0 <= publication_hour <= 23:
        raise ValueError("Full-hour slot outside 0–23")
    return ((publication_hour - 1) % 24, 55)


def publication_target(fetch_time: datetime) -> datetime:
    """Return the UTC instant five minutes after the scheduled fetch."""
    if fetch_time.tzinfo is None:
        raise ValueError("Expected timezone-aware time")
    return fetch_time.astimezone(timezone.utc) + timedelta(minutes=5)
