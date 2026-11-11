"""Register the bundled cloud chart as a Lovelace resource.

The card must NOT be loaded through ``frontend.add_extra_js_url`` by default:
extra JS sits in the ``<head>`` of Home Assistant's index.html and races with
the frontend's scoped-custom-element-registry polyfill. If the card defines its
element first, the polyfilled registry never learns about it
(``customElements.get()`` stays empty, ``whenDefined()`` never resolves) and the
dashboard permanently shows "Configuration error / Custom element doesn't
exist" until the page is reloaded. Lovelace resources are loaded by the
frontend itself, i.e. always after the polyfill.

This module deliberately has no top-level Home Assistant imports so it can be
tested offline.
"""
from __future__ import annotations

import asyncio
import logging

_LOGGER = logging.getLogger(__name__)

CARD_PATH = "/my_weather/my-weather-cloud-8h-card.js"
RESOURCE_ATTEMPTS = 6


def card_url(version: str) -> str:
    """Versioned URL; the query string changes with every release."""
    return f"{CARD_PATH}?v={version}"


def _storage_resources(hass):
    """Return the storage-mode Lovelace resource collection, or None."""
    lovelace = hass.data.get("lovelace")
    if lovelace is None:
        return None
    resources = (
        lovelace.get("resources") if isinstance(lovelace, dict)
        else getattr(lovelace, "resources", None)
    )
    # YAML-mode collections are read-only and have no async_create_item.
    if resources is None or not hasattr(resources, "async_create_item"):
        return None
    return resources


async def async_ensure_lovelace_resource(hass, url: str) -> bool:
    """Create or update our module resource. False = not possible (yet)."""
    resources = _storage_resources(hass)
    if resources is None:
        return False
    # REQUIRED: resource storage is lazy-loaded. Touching items before it is
    # loaded could overwrite the user's existing resources.
    if hasattr(resources, "async_get_info"):
        await resources.async_get_info()
    ours = [
        item for item in resources.async_items()
        if str(item.get("url", "")).split("?", 1)[0] == CARD_PATH
    ]
    if not ours:
        await resources.async_create_item({"res_type": "module", "url": url})
        _LOGGER.info("MY_WEATHER: cloud chart resource registered: %s", url)
        return True
    first, *duplicates = ours
    if first.get("url") != url or first.get("type") != "module":
        await resources.async_update_item(first["id"], {"res_type": "module", "url": url})
    for item in duplicates:
        await resources.async_delete_item(item["id"])
    return True


async def async_register_card(
    hass, url: str, *, extra_js_fallback=None,
    attempts: int = RESOURCE_ATTEMPTS, delay: float = 2.0,
) -> bool:
    """Register the resource; Lovelace may finish starting later, so retry.

    If no storage-mode resource can be created (Lovelace YAML mode), fall back
    to ``extra_js_fallback(hass, url)`` so the card stays available.
    """
    for attempt in range(1, attempts + 1):
        try:
            if await async_ensure_lovelace_resource(hass, url):
                return True
        except Exception:  # noqa: BLE001 - never break integration setup
            _LOGGER.warning(
                "MY_WEATHER: cloud chart resource registration failed (%s/%s)",
                attempt, attempts, exc_info=True,
            )
        if attempt < attempts:
            await asyncio.sleep(delay * attempt)
    if extra_js_fallback is not None:
        try:
            extra_js_fallback(hass, url)
        except Exception:  # noqa: BLE001
            _LOGGER.error("MY_WEATHER: cloud chart could not be registered: %s", url, exc_info=True)
            return False
        _LOGGER.warning(
            "MY_WEATHER: cloud chart could not be registered as a Lovelace resource "
            "(YAML mode?). It is loaded through the frontend instead; for reliable "
            "loading add it manually as a resource: %s (type: module)", url,
        )
    return False
