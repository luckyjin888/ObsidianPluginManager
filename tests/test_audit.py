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

def test_malformed_enabled_entries_do_not_crash_inventory(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            cfg = vault / ".obsidian"
            plugin = cfg / "plugins" / "sample"
            plugin.mkdir(parents=True)
            (plugin / "manifest.json").write_text(
                json.dumps({"id": "sample", "name": "Sample"}), encoding="utf-8"
            )
            (cfg / "community-plugins.json").write_text(
                json.dumps(["sample", {"bad": "unhashable"}, ["nested"], ""]),
                encoding="utf-8",
            )
            from contextlib import redirect_stdout
            import io
            output = io.StringIO()
            with patch.object(om, "fetch_registry", return_value={}), redirect_stdout(output):
                om.audit_plugins(vault)
            self.assertIn("非字符串/空值", output.getvalue())
            self.assertIn("状态：启用", output.getvalue())

    def test_non_list_enabled_config_marks_state_unknown(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            cfg = vault / ".obsidian"
            plugin = cfg / "plugins" / "sample"
            plugin.mkdir(parents=True)
            (plugin / "manifest.json").write_text(
                json.dumps({"id": "sample"}), encoding="utf-8"
            )
            (cfg / "community-plugins.json").write_text(
                json.dumps({"unexpected": "object"}), encoding="utf-8"
            )
            from contextlib import redirect_stdout
            import io
            output = io.StringIO()
            with patch.object(om, "fetch_registry", return_value={}), redirect_stdout(output):
                om.audit_plugins(vault)
            self.assertIn("状态：未知", output.getvalue())

    def test_scanner_reports_file_limit_and_uses_stable_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for index in reversed(range(502)):
                (root / f"{index:03}.js").write_text(
                    "fetch('/example')" if index == 0 else "const value = 1;",
                    encoding="utf-8",
                )
            findings, stats = om.scan_source(root, max_files=500)
            self.assertEqual(stats["discovered"], 502)
            self.assertEqual(stats["scanned"], 500)
            self.assertEqual(stats["skipped"], 2)
            self.assertTrue(any(filename == "000.js" for _, filename, _ in findings))

    def test_scanner_reports_oversized_file_instead_of_silent_skip(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "large.js").write_text("x" * 20, encoding="utf-8")
            findings, stats = om.scan_source(root, max_file_size=10)
            self.assertEqual(findings, [])
            self.assertEqual(stats["scanned"], 0)
            self.assertEqual(stats["skipped"], 1)
            self.assertTrue(any("超过单文件大小上限" in item for item in stats["errors"]))
