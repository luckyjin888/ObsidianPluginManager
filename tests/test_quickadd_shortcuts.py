import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import quickadd_shortcuts as qs
import obsidian_hotkeys as oh


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

    def test_cli_default_hotkey_conflict_stops_setup(self):
        with self.assertRaisesRegex(RuntimeError, "Obsidian 命令"):
            qs._plan_hotkeys({}, {("core:command", "c+mod+shift")})


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
            with patch.object(qs, "read_active_hotkeys", return_value=set()):
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
            with patch.object(qs, "read_active_hotkeys", return_value=set()):
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
            with patch.object(qs, "read_active_hotkeys", return_value=set()):
                result = qs.configure_quickadd_shortcuts(
                    vault, "obsidian", lambda _: True, messages.append
                )
            self.assertFalse(result)
            self.assertTrue(any("只存在部分快捷选项" in x for x in messages))

    def test_does_not_write_hotkeys_while_obsidian_is_running(self):
        from types import SimpleNamespace

        with tempfile.TemporaryDirectory() as tmp:
            vault, plugin = self.make_vault(tmp)
            data_path = plugin / "data.json"
            data_path.write_text('{"choices":[]}', encoding="utf-8")
            messages = []

            def fake_cli(args, **kwargs):
                if "quickadd:package-import" in args:
                    package = qs.build_package()
                    data_path.write_text(json.dumps({
                        "choices": [entry["choice"] for entry in package["choices"]]
                    }), encoding="utf-8")
                return SimpleNamespace(returncode=0, stdout="", stderr="")

            with patch.object(qs, "read_active_hotkeys", return_value=set()):
                with patch.object(qs.subprocess, "run", side_effect=fake_cli):
                    result = qs.configure_quickadd_shortcuts(
                        vault, "obsidian", lambda _: True, messages.append,
                        ask=lambda _: "", is_running=lambda: True
                    )
            self.assertFalse(result)
            self.assertFalse((vault / ".obsidian" / "hotkeys.json").exists())
            self.assertTrue(any("仍在运行" in message for message in messages))


class ObsidianHotkeyParsingTests(unittest.TestCase):
    def test_normalises_macos_display_hotkey(self):
        self.assertEqual(oh.normalise_hotkey("⌘⇧C"), "c+mod+shift")

    def test_parses_command_records(self):
        parsed = oh.parse_hotkeys_json(json.dumps([
            {"id": "editor:toggle-bold", "hotkeys": ["⌘B"]},
            {"id": "another:command", "hotkey": {"modifiers": ["Mod", "Shift"], "key": "J"}},
        ]))
        self.assertIn(("editor:toggle-bold", "b+mod"), parsed)
        self.assertIn(("another:command", "j+mod+shift"), parsed)

    def test_parses_id_to_bindings_map(self):
        parsed = oh.parse_hotkeys_json(json.dumps({
            "another:command": [{"modifiers": ["Mod", "Shift"], "key": "P"}]
        }))
        self.assertIn(("another:command", "mod+p+shift"), parsed)

    def test_rejects_unrecognised_nonempty_payload(self):
        with self.assertRaisesRegex(ValueError, "无法识别"):
            oh.parse_hotkeys_json('{"unexpected":true}')


if __name__ == "__main__":
    unittest.main()
