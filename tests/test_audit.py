import json, tempfile, unittest
from pathlib import Path
import obsidian_manager as om

class AuditTests(unittest.TestCase):
    def test_version_tuple(self):
        self.assertGreaterEqual(om.version_tuple("1.13.7"), om.MIN_CLI)
        self.assertLess(om.version_tuple("1.11.9"), om.MIN_CLI)
    def test_manifest_and_enabled_inventory(self):
        with tempfile.TemporaryDirectory() as d:
            vault=Path(d); cfg=vault/".obsidian"; plugins=cfg/"plugins"
            p=plugins/"sample"; p.mkdir(parents=True)
            (p/"manifest.json").write_text(json.dumps({"id":"sample","name":"Sample","version":"1.0"}))
            cfg.mkdir(exist_ok=True)
            (cfg/"community-plugins.json").write_text(json.dumps(["sample"]))
            self.assertEqual(json.loads((cfg/"community-plugins.json").read_text()), ["sample"])
            self.assertTrue((p/"manifest.json").is_file())

if __name__ == "__main__": unittest.main()
