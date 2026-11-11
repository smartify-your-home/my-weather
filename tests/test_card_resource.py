"""Offline tests for the cloud chart Lovelace resource registration."""
import asyncio
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components/my_weather"
spec = importlib.util.spec_from_file_location("my_weather_card_resource", COMPONENT / "card_resource.py")
card_resource = importlib.util.module_from_spec(spec)
spec.loader.exec_module(card_resource)
CARD_PATH = card_resource.CARD_PATH


class Resources:
    """Minimal stand-in for Home Assistant's ResourceStorageCollection."""

    def __init__(self, items=()):
        self.items = [dict(i) for i in items]
        self.loaded = False
        self.touched_before_load = False
        self._n = 0

    async def async_get_info(self):
        self.loaded = True

    def async_items(self):
        self.touched_before_load |= not self.loaded
        return list(self.items)

    async def async_create_item(self, data):
        self.touched_before_load |= not self.loaded
        self._n += 1
        self.items.append({"id": f"new{self._n}", "url": data["url"], "type": data["res_type"]})

    async def async_update_item(self, item_id, data):
        for item in self.items:
            if item["id"] == item_id:
                item.update(url=data["url"], type=data["res_type"])

    async def async_delete_item(self, item_id):
        self.items = [i for i in self.items if i["id"] != item_id]


class Hass:
    def __init__(self, lovelace=None):
        self.data = {} if lovelace is None else {"lovelace": lovelace}


class Lovelace:
    def __init__(self, resources):
        self.resources = resources


def ours(res):
    return [(i["url"], i["type"]) for i in res.items if i["url"].split("?")[0] == CARD_PATH]


class CardResourceTests(unittest.IsolatedAsyncioTestCase):
    async def test_creates_once_and_loads_storage_first(self):
        res = Resources([{"id": "x", "url": "/local/other.js", "type": "module"}])
        hass = Hass(Lovelace(res))
        url = card_resource.card_url("1.0.0")
        self.assertTrue(await card_resource.async_ensure_lovelace_resource(hass, url))
        self.assertTrue(await card_resource.async_ensure_lovelace_resource(hass, url))
        self.assertEqual(ours(res), [(url, "module")])
        self.assertFalse(res.touched_before_load)
        self.assertEqual(len(res.items), 2)

    async def test_updates_version_and_removes_only_own_duplicates(self):
        res = Resources([
            {"id": "a", "url": f"{CARD_PATH}?v=old", "type": "js"},
            {"id": "b", "url": CARD_PATH, "type": "module"},
            {"id": "c", "url": "/local/other.js", "type": "module"},
        ])
        url = card_resource.card_url("2.0.0")
        self.assertTrue(await card_resource.async_ensure_lovelace_resource(Hass(Lovelace(res)), url))
        self.assertEqual(ours(res), [(url, "module")])
        self.assertIn("/local/other.js", [i["url"] for i in res.items])

    async def test_dict_style_lovelace_data(self):
        res = Resources()
        url = card_resource.card_url("1.0.0")
        self.assertTrue(await card_resource.async_ensure_lovelace_resource(Hass({"resources": res}), url))
        self.assertEqual(ours(res), [(url, "module")])

    async def test_no_lovelace_or_yaml_mode_returns_false(self):
        url = card_resource.card_url("1.0.0")
        self.assertFalse(await card_resource.async_ensure_lovelace_resource(Hass(), url))
        yaml_resources = type("ResourceYAMLCollection", (), {"async_items": lambda self: []})()
        self.assertFalse(await card_resource.async_ensure_lovelace_resource(Hass(Lovelace(yaml_resources)), url))

    async def test_retry_waits_for_late_lovelace_without_fallback(self):
        hass = Hass()
        res = Resources()
        calls = []
        url = card_resource.card_url("late")
        task = asyncio.create_task(card_resource.async_register_card(
            hass, url, extra_js_fallback=lambda *a: calls.append(a), delay=0.01))
        await asyncio.sleep(0.02)
        hass.data["lovelace"] = Lovelace(res)
        self.assertTrue(await task)
        self.assertEqual(ours(res), [(url, "module")])
        self.assertEqual(calls, [])

    async def test_yaml_mode_falls_back_to_extra_js_after_retries(self):
        hass = Hass()
        calls = []
        url = card_resource.card_url("yaml")
        self.assertFalse(await card_resource.async_register_card(
            hass, url, extra_js_fallback=lambda h, u: calls.append((h, u)), attempts=3, delay=0))
        self.assertEqual(calls, [(hass, url)])

    async def test_storage_error_does_not_raise(self):
        class Broken(Resources):
            async def async_get_info(self):
                raise RuntimeError("storage unavailable")

        with self.assertLogs(card_resource._LOGGER, level="WARNING"):
            self.assertFalse(await card_resource.async_register_card(
                Hass(Lovelace(Broken())), card_resource.card_url("x"), attempts=2, delay=0))


class SetupSourceTests(unittest.TestCase):
    def test_extra_js_is_only_used_as_fallback(self):
        source = (COMPONENT / "__init__.py").read_text(encoding="utf-8")
        self.assertEqual(source.count("add_extra_js_url("), 1)
        self.assertIn("extra_js_fallback=_extra_js_fallback", source)
        self.assertIn("EVENT_HOMEASSISTANT_STARTED", source)

    def test_static_path_matches_resource_path(self):
        self.assertEqual(CARD_PATH, "/my_weather/my-weather-cloud-8h-card.js")
        self.assertTrue((COMPONENT / "www" / "my-weather-cloud-8h-card.js").is_file())


if __name__ == "__main__":
    unittest.main()
