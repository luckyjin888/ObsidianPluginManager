import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import quickadd_shortcuts as qs
import obsidian_hotkeys as oh
import obsidian_manager as om


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

    def test_symlinked_plugins_parent_is_rejected_before_reading_plugin(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / "vault"
            outside = Path(tmp) / "outside"
            vault.mkdir()
            outside.mkdir()
            (vault / ".obsidian").mkdir()
            try:
                (vault / ".obsidian" / "plugins").symlink_to(outside, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("directory symlinks are unavailable on this platform")
            messages = []
            result = qs.configure_quickadd_shortcuts(
                vault, "obsidian", lambda _: True, messages.append
            )
            self.assertFalse(result)
            self.assertTrue(any("符号链接/越界路径" in message for message in messages))
            self.assertFalse((outside / "quickadd").exists())

    def test_missing_quickadd_is_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            messages = []
            result = qs.configure_quickadd_shortcuts(
                Path(tmp), "obsidian", lambda _: True, messages.append
            )
            self.assertFalse(result)
            self.assertTrue(any("尚未安装" in x for x in messages))

    def test_quickadd_below_safe_import_version_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault, plugin = self.make_vault(tmp)
            (plugin / "manifest.json").write_text(
                json.dumps({"id": "quickadd", "version": "2.29.9"}), encoding="utf-8"
            )
            messages = []
            confirm = Mock(return_value=True)
            result = qs.configure_quickadd_shortcuts(
                vault, "obsidian", confirm, messages.append
            )
            self.assertFalse(result)
            confirm.assert_not_called()
            self.assertTrue(any("2.30.0" in message for message in messages))

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



class ObsidianProcessStateTests(unittest.TestCase):
    def test_process_probe_error_returns_unknown(self):
        with patch.object(om.platform, "system", return_value="Darwin"):
            with patch.object(om.subprocess, "run", side_effect=OSError("pgrep unavailable")):
                self.assertIsNone(om.obsidian_is_running())

    def test_unexpected_pgrep_exit_code_returns_unknown(self):
        from types import SimpleNamespace
        with patch.object(om.platform, "system", return_value="Linux"):
            with patch.object(om.subprocess, "run", return_value=SimpleNamespace(returncode=2, stdout="", stderr="permission denied")):
                self.assertIsNone(om.obsidian_is_running())

    def test_successful_no_match_probe_confirms_closed(self):
        from types import SimpleNamespace
        with patch.object(om.platform, "system", return_value="Linux"):
            with patch.object(om.subprocess, "run", return_value=SimpleNamespace(returncode=1, stdout="", stderr="")):
                self.assertFalse(om.obsidian_is_running())

    def test_windows_process_probe_confirms_closed_without_localized_text(self):
        from types import SimpleNamespace
        with patch.object(om.platform, "system", return_value="Windows"):
            with patch.object(om.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout="", stderr="")) as run:
                self.assertFalse(om.obsidian_is_running())
                self.assertIn("powershell.exe", run.call_args.args[0][0])

    def test_windows_process_probe_detects_numeric_pid(self):
        from types import SimpleNamespace
        with patch.object(om.platform, "system", return_value="Windows"):
            with patch.object(om.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout="1234\\r\\n", stderr="")):
                self.assertTrue(om.obsidian_is_running())

    def test_windows_process_probe_failure_returns_unknown(self):
        with patch.object(om.platform, "system", return_value="Windows"):
            with patch.object(om.subprocess, "run", side_effect=OSError("powershell unavailable")):
                self.assertIsNone(om.obsidian_is_running())

    def test_unknown_process_state_prevents_hotkey_write(self):
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as tmp:
            vault, plugin = QuickAddInstallerTests().make_vault(tmp)
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
                        ask=lambda _: "", is_running=lambda: None
                    )
            self.assertFalse(result)
            self.assertFalse((vault / ".obsidian" / "hotkeys.json").exists())
            self.assertTrue(any("状态未知" in message for message in messages))


class AtomicHotkeyWriterTests(unittest.TestCase):
    def test_atomic_writer_saves_json_and_cleans_temporary_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "hotkeys.json"
            qs._atomic_write_json(target, {"quickadd:choice:test": []})
            self.assertEqual(json.loads(target.read_text(encoding="utf-8")), {"quickadd:choice:test": []})
            self.assertEqual(list(Path(tmp).glob(".opm-*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
