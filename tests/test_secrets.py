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

    def test_too_many_secrets_rejected(self):
        with self.assertRaises(module.SecretKeyError):
            module.load_secret_keys(str(self.path), ["one", "two", "three", "four", "five"])

    def test_path_like_name_rejected(self):
        with self.assertRaises(module.SecretKeyError):
            module.load_secret_keys(str(self.path), ["../../secrets.yaml"])


if __name__ == "__main__":
    unittest.main()
