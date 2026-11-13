"""Pure parsing helpers for GeoSphere Austria C-LAEF solar forecasts.

The native nwp-v2-1h-1km 'ssrd' field is an hourly-mean W/m²
(not the cumulative Ws/m² 'grad' field used by the retired model).
GeoSphere timestamps refer to the END of the preceding forecast hour.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import math


def as_utc(value: str | None) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _number(value, low: float, high: float):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if not math.isfinite(value) or not low <= value <= high:
        return None
    return float(value)


def parse_geosphere_forecast(payload: dict) -> dict:
    """Parse one location; reject malformed/incomplete responses atomically.

    Missing individual readings stay None; they must never become zero.
    """
    if not isinstance(payload, dict):
        raise ValueError("GeoSphere: expected a GeoJSON object")
    timestamps = payload.get("timestamps")
    features = payload.get("features")
    if not isinstance(timestamps, list) or not timestamps:
        raise ValueError("GeoSphere: no timestamps")
    if not isinstance(features, list) or len(features) != 1:
        raise ValueError("GeoSphere: expected exactly one location")
    properties = features[0].get("properties") if isinstance(features[0], dict) else None
    params = properties.get("parameters") if isinstance(properties, dict) else None
    if not isinstance(params, dict) or "ssrd" not in params or "tcc" not in params:
        raise ValueError("GeoSphere: missing ssrd/tcc parameters")

    def column(name):
        item = params[name]
        values = item.get("data") if isinstance(item, dict) else None
        if not isinstance(values, list) or len(values) != len(timestamps):
            raise ValueError(f"GeoSphere: invalid {name} series length")
        return values

    radiation = column("ssrd")
    clouds = column("tcc")
    forecast = []
    previous_end = None
    good_radiation = 0
    good_clouds = 0
    for stamp, radiation_raw, cloud_raw in zip(timestamps, radiation, clouds):
        end = as_utc(stamp)
        if end is None or (previous_end is not None and end <= previous_end):
            raise ValueError("GeoSphere: invalid/non-monotonic hourly timestamps")
        previous_end = end
        ghi = _number(radiation_raw, 0, 1800)
        cloud = _number(cloud_raw, 0, 100)
        good_radiation += ghi is not None
        good_clouds += cloud is not None
        forecast.append({
            "datetime": (end - timedelta(hours=1)).isoformat(),
            "end": end.isoformat(),
            "ghi_w_m2": ghi,
            "cloud_coverage": cloud,
        })
    if not good_radiation and not good_clouds:
        raise ValueError("GeoSphere: no valid solar/cloud readings")
    return {
        "forecast": forecast,
        "model_run": payload.get("reference_time"),
        "source": "GeoSphere Austria C-LAEF",
        "dataset": "nwp-v2-1h-1km",
    }


def upcoming_rows(data: dict | None, now: datetime, limit: int = 48) -> list[dict]:
    """Only real future intervals; never fall back to expired hour zero."""
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    now = now.astimezone(timezone.utc)
    rows = (data or {}).get("forecast") or []
    return [row for row in rows if (as_utc(row.get("end")) or now) > now][:limit]


def current_row(data: dict | None, now: datetime) -> dict | None:
    for row in upcoming_rows(data, now, 2):
        start = as_utc(row.get("datetime"))
        end = as_utc(row.get("end"))
        if start is not None and end is not None and start <= now < end:
            return row
    return None


def remaining_energy_kwh_m2(rows: list[dict], now: datetime) -> float | None:
    """Integrate valid remaining intervals, including the current fractional hour."""
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    now = now.astimezone(timezone.utc)
    total = 0.0
    valid = False
    for row in rows:
        ghi = row.get("ghi_w_m2")
        start = as_utc(row.get("datetime"))
        end = as_utc(row.get("end"))
        if not isinstance(ghi, (int, float)) or start is None or end is None:
            continue
        hours = max(0.0, (end - max(start, now)).total_seconds() / 3600)
        total += ghi * hours / 1000.0
        valid = True
    return round(total, 3) if valid else None
