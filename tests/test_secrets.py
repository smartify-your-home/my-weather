"""Tests for named API key loading without an installed Home Assistant core."""

import importlib.util
from pathlib import Path
import sys
import tempfile
import types
import unittest

sys.modules.setdefault("homeassistant", types.ModuleType("homeassistant"))
core = sys.modules.setdefault("homeassistant.core", types.ModuleType("homeassistant.core"))
core.HomeAssistant = type("HomeAssistant", (), {})

source = Path(__file__).resolve().parents[1] / "custom_components/my_weather/secrets.py"
spec = importlib.util.spec_from_file_location("my_weather_secrets_test", source)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class SecretKeyTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / "secrets.yaml"
        self.path.write_text("weather_1: ABC123\nweather_2: DEF456\n", encoding="utf-8")

    def tearDown(self):
        self.directory.cleanup()

    def test_multiple_keys_in_order(self):
        self.assertEqual(
            module.load_secret_keys(str(self.path), ["weather_2", "weather_1"]),
            ["DEF456", "ABC123"],
        )

    def test_missing_secret_does_not_expose_values(self):
        with self.assertRaises(module.SecretKeyError) as error:
            module.load_secret_keys(str(self.path), ["does_not_exist"])
        self.assertNotIn("ABC123", str(error.exception))

    def test_duplicate_keys_deduplicated(self):
        self.path.write_text("weather_1: ABC123\nweather_2: ABC123\n", encoding="utf-8")
        self.assertEqual(module.load_secret_keys(str(self.path), ["weather_1", "weather_2"]), ["ABC123"])

    def test_one_fixed_key(self):
        self.path.write_text("my_weather_api_1: ABC123\n", encoding="utf-8")
        self.assertEqual(module.load_fixed_secret_keys(str(self.path)), ["ABC123"])

    def test_two_fixed_keys_with_missing_gap(self):
        self.path.write_text("my_weather_api_1: ABC123\nmy_weather_api_3: DEF456\n", encoding="utf-8")
        self.assertEqual(module.load_fixed_secret_keys(str(self.path)), ["ABC123", "DEF456"])

    def test_four_fixed_keys(self):
        self.path.write_text(
            "my_weather_api_1: FIRST\nmy_weather_api_2: SECOND\n"
            "my_weather_api_3: THIRD\nmy_weather_api_4: FOURTH\n",
            encoding="utf-8",
        )
        self.assertEqual(
            module.load_fixed_secret_keys(str(self.path)),
            ["FIRST", "SECOND", "THIRD", "FOURTH"],
        )

    def test_missing_fixed_file_is_optional(self):
        self.path.unlink()
        self.assertEqual(module.load_fixed_secret_keys(str(self.path)), [])

    def test_present_but_empty_fixed_key_fails(self):
        self.path.write_text("my_weather_api_1: ABC123\nmy_weather_api_2: ''\n", encoding="utf-8")
        with self.assertRaises(module.SecretKeyError):
            module.load_fixed_secret_keys(str(self.path))

    def test_duplicate_fixed_key_values(self):
        self.path.write_text("my_weather_api_1: ABC123\nmy_weather_api_2: ABC123\n", encoding="utf-8")
        self.assertEqual(module.load_fixed_secret_keys(str(self.path)), ["ABC123"])

    def test_too_many_secrets_rejected(self):
        with self.assertRaises(module.SecretKeyError):
            module.load_secret_keys(str(self.path), ["one", "two", "three", "four", "five"])

    def test_path_like_name_rejected(self):
        with self.assertRaises(module.SecretKeyError):
            module.load_secret_keys(str(self.path), ["../../secrets.yaml"])


if __name__ == "__main__":
    unittest.main()
