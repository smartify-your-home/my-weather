"""Key rotation is restricted to authorization and quota failures."""

import importlib.util
from pathlib import Path
import unittest

source = Path(__file__).resolve().parents[1] / "custom_components/my_weather/api_errors.py"
spec = importlib.util.spec_from_file_location("api_errors_test", source)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class KeyFailoverTests(unittest.TestCase):
    def test_key_failover_statuses(self):
        for status in (401, 403, 429):
            with self.subTest(status=status):
                self.assertTrue(module.should_try_other_key(status))

    def test_other_errors_do_not_rotate_keys(self):
        for status in (200, 400, 404, 500, 502, 503):
            with self.subTest(status=status):
                self.assertFalse(module.should_try_other_key(status))


if __name__ == "__main__":
    unittest.main()
