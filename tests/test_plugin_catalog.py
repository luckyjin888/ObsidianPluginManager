import copy
import json
import unittest

from tools.validate_plugin_catalog import validate_catalog


class PluginCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from pathlib import Path
        cls.catalog = json.loads(
            (Path(__file__).resolve().parents[1] / "shared" / "plugin-catalog.json").read_text(encoding="utf-8")
        )

    def test_catalog_is_valid(self):
        self.assertEqual(validate_catalog(self.catalog), [])

    def test_catalog_has_unique_plugin_ids(self):
        ids = [plugin["id"] for plugin in self.catalog["plugins"]]
        self.assertEqual(len(ids), len(set(ids)))

    def test_each_plugin_defines_all_five_platforms(self):
        expected = {"windows", "macos", "ios", "ipados", "android"}
        for plugin in self.catalog["plugins"]:
            self.assertEqual(set(plugin["platforms"]), expected)

    def test_advanced_audio_recorder_is_catalogued_without_claiming_verified_platforms(self):
        plugin = next(p for p in self.catalog["plugins"] if p["id"] == "advanced-audio-recorder")
        self.assertEqual(plugin["upstream_url"], "https://github.com/akhmialeuski/advanced-audio-recorder")
        self.assertEqual(plugin["license"], "MIT")
        self.assertTrue(all(record["status"] == "declared_unverified" for record in plugin["platforms"].values()))

    def test_manifest_false_does_not_mark_mobile_as_verified(self):
        for plugin in self.catalog["plugins"]:
            if plugin["manifest_is_desktop_only"] is False:
                for platform in ("ios", "ipados", "android"):
                    self.assertNotEqual(plugin["platforms"][platform]["status"], "verified")

    def test_verified_status_requires_device_evidence(self):
        broken = copy.deepcopy(self.catalog)
        broken["plugins"][0]["platforms"]["ios"] = {
            "status": "verified",
            "evidence": "Claimed verified without device record."
        }
        self.assertTrue(any("verified status requires" in e for e in validate_catalog(broken)))

    def test_duplicate_plugin_ids_are_rejected(self):
        broken = copy.deepcopy(self.catalog)
        broken["plugins"].append(copy.deepcopy(broken["plugins"][0]))
        self.assertTrue(any("duplicate plugin id" in e for e in validate_catalog(broken)))

    def test_unknown_platforms_are_rejected(self):
        broken = copy.deepcopy(self.catalog)
        broken["plugins"][0]["platforms"]["linux"] = {"status": "unknown", "evidence": "test"}
        self.assertTrue(any("must define exactly" in e for e in validate_catalog(broken)))


if __name__ == "__main__":
    unittest.main()
