"""Repository consistency tests (no running Home Assistant required)."""

import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components/my_weather"


class IntegrationStructureTests(unittest.TestCase):
    def test_all_supported_locales_have_identical_fields(self):
        base = json.loads((COMPONENT / "strings.json").read_text(encoding="utf-8"))
        base_user = set(base["config"]["step"]["user"]["data"])
        base_opts = set(base["options"]["step"]["init"]["data"])
        self.assertEqual(base_opts, {f"update_time_{i}" for i in range(1, 5)})
        self.assertFalse(any("api_secret_" in field for field in base_user))
        for language in ("de", "en", "fr", "it", "es"):
            with self.subTest(language=language):
                translation = json.loads((COMPONENT / "translations" / f"{language}.json").read_text(encoding="utf-8"))
                self.assertEqual(set(translation["config"]["step"]["user"]["data"]), base_user)
                self.assertEqual(set(translation["options"]["step"]["init"]["data"]), base_opts)
                self.assertIn("invalid_time", translation["options"]["error"])

    def test_required_release_files_present(self):
        for filename in ("README.md", "AGENTS.md", "CHANGELOG.md", "CONTRIBUTING.md", "SECURITY.md", ".gitignore"):
            with self.subTest(filename=filename):
                self.assertTrue((ROOT / filename).is_file())
        self.assertIn("update:", (COMPONENT / "services.yaml").read_text(encoding="utf-8"))

    def test_manifest_and_hacs_are_consistent(self):
        manifest = json.loads((COMPONENT / "manifest.json").read_text(encoding="utf-8"))
        hacs = json.loads((ROOT / "hacs.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["domain"], "my_weather")
        self.assertTrue(manifest["config_flow"])
        self.assertEqual(manifest["version"], "0.1.3.1")
        self.assertTrue(hacs["render_readme"])


if __name__ == "__main__":
    unittest.main()
