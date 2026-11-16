import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import quickadd_shortcuts as qs


class QuickAddPackageTests(unittest.TestCase):
    def test_package_has_three_command_enabled_capture_choices(self):
        package = qs.build_package()
        self.assertEqual(package["schemaVersion"], 1)
        self.assertEqual(len(package["choices"]), 3)
        for item in package["choices"]:
            choice = item["choice"]
            self.assertEqual(choice["type"], "Capture")
            self.assertTrue(choice["command"])
            self.assertTrue(choice["captureToActiveFile"])
            self.assertEqual(choice["activeFileWritePosition"], "cursor")
            self.assertIn("{{CURSOR}}", choice["format"]["format"])
        self.assertEqual(package["assets"], [])

    def test_hotkey_plan_adds_three_bindings(self):
        planned, additions = qs._plan_hotkeys({})
        self.assertEqual(len(additions), 3)
        self.assertEqual(planned["quickadd:choice:opm-insert-code-block"][0],
                         {"modifiers": ["Mod", "Shift"], "key": "C"})

    def test_hotkey_plan_is_idempotent(self):
        planned, additions = qs._plan_hotkeys({})
        planned_again, additions_again = qs._plan_hotkeys(planned)
        self.assertEqual(additions_again, [])
        self.assertEqual(planned_again, planned)

    def test_hotkey_conflict_stops_without_mutating_input(self):
        existing = {
            "another-plugin:open-command": [
                {"modifiers": ["Shift", "Mod"], "key": "C"}
            ]
        }
        before = json.loads(json.dumps(existing))
        with self.assertRaisesRegex(RuntimeError, "已被"):
            qs._plan_hotkeys(existing)
        self.assertEqual(existing, before)

    def test_same_binding_on_our_command_is_not_a_conflict(self):
        existing = {
            "quickadd:choice:opm-insert-code-block": [
                {"modifiers": ["Mod", "Shift"], "key": "C"}
            ]
        }
        planned, additions = qs._plan_hotkeys(existing)
        self.assertEqual(len(additions), 2)
        self.assertEqual(planned["quickadd:choice:opm-insert-code-block"], existing[
            "quickadd:choice:opm-insert-code-block"
        ])


class QuickAddInstallerTests(unittest.TestCase):
    def make_vault(self, root):
        vault = Path(root)
        plugin = vault / ".obsidian" / "plugins" / "quickadd"
        plugin.mkdir(parents=True)
        (plugin / "manifest.json").write_text(
            json.dumps({"id": "quickadd", "version": "2.33.1"}), encoding="utf-8"
        )
        (vault / ".obsidian" / "community-plugins.json").write_text(
            '["quickadd"]', encoding="utf-8"
        )
        return vault, plugin

    def test_missing_quickadd_is_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            messages = []
            result = qs.configure_quickadd_shortcuts(
                Path(tmp), "obsidian", lambda _: True, messages.append
            )
            self.assertFalse(result)
            self.assertTrue(any("尚未安装" in x for x in messages))

    def test_decline_does_not_write_any_configuration(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault, plugin = self.make_vault(tmp)
            (plugin / "data.json").write_text('{"choices":[]}', encoding="utf-8")
            messages = []
            result = qs.configure_quickadd_shortcuts(
                vault, "obsidian", lambda _: False, messages.append
            )
            self.assertFalse(result)
            self.assertEqual(json.loads((plugin / "data.json").read_text())["choices"], [])
            self.assertFalse((vault / ".obsidian" / "hotkeys.json").exists())

    def test_existing_hotkey_conflict_stops_before_confirmation(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault, plugin = self.make_vault(tmp)
            (plugin / "data.json").write_text('{"choices":[]}', encoding="utf-8")
            hotkeys = vault / ".obsidian" / "hotkeys.json"
            hotkeys.write_text(json.dumps({
                "some-plugin:command": [
                    {"modifiers": ["Mod", "Shift"], "key": "P"}
                ]
            }), encoding="utf-8")
            confirm = Mock(return_value=True)
            messages = []
            result = qs.configure_quickadd_shortcuts(vault, "obsidian", confirm, messages.append)
            self.assertFalse(result)
            confirm.assert_not_called()
            self.assertIn("some-plugin:command", hotkeys.read_text())

    def test_partial_existing_choices_are_not_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault, plugin = self.make_vault(tmp)
            (plugin / "data.json").write_text(json.dumps({
                "choices": [{"id": "opm-insert-code-block", "name": "Insert Code Block"}]
            }), encoding="utf-8")
            messages = []
            result = qs.configure_quickadd_shortcuts(
                vault, "obsidian", lambda _: True, messages.append
            )
            self.assertFalse(result)
            self.assertTrue(any("只存在部分快捷选项" in x for x in messages))


if __name__ == "__main__":
    unittest.main()
