"""Read named Meteonomiqs API keys from the fixed Home Assistant secrets.yaml."""

from __future__ import annotations

from pathlib import Path
import re
import yaml

from homeassistant.core import HomeAssistant

SECRET_NAME_PATTERN = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]*$")


class SecretKeyError(ValueError):
    """Invalid or missing API-key reference (never include a secret value)."""


def load_secret_keys(path: str, names: list[str]) -> list[str]:
    """Resolve up to four named strings from secrets.yaml, with no path input from UI."""
    if not 1 <= len(names) <= 4:
        raise SecretKeyError("Configure between one and four secret references")
    if any(not SECRET_NAME_PATTERN.fullmatch(n) for n in names):
        raise SecretKeyError("Invalid secret reference name")
    try:
        with Path(path).open("r", encoding="utf-8") as handle:
            values = yaml.safe_load(handle) or {}
    except (OSError, yaml.YAMLError) as err:
        raise SecretKeyError("Cannot read secrets.yaml") from err
    if not isinstance(values, dict):
        raise SecretKeyError("secrets.yaml must contain a mapping")
    missing = [name for name in names if not isinstance(values.get(name), str) or not values[name].strip()]
    if missing:
        raise SecretKeyError("Missing or empty secrets.yaml entry: " + ", ".join(missing))
    keys = [values[name].strip() for name in names]
    return list(dict.fromkeys(keys))


async def async_load_secret_keys(hass: HomeAssistant, names: list[str]) -> list[str]:
    """Read secrets from disk outside the Home Assistant event loop."""
    return await hass.async_add_executor_job(
        load_secret_keys, hass.config.path("secrets.yaml"), names
    )
