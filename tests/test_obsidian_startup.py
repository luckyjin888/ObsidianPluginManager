import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import obsidian_manager as om


class ObsidianStartupTests(unittest.TestCase):
    def test_running_app_is_not_launched_again(self):
        with patch.object(om, "obsidian_is_running", return_value=True):
            with patch.object(om.subprocess, "Popen") as popen:
                self.assertTrue(om.launch_obsidian(Path("/Applications/Obsidian.app")))
                popen.assert_not_called()

    def test_macos_launch_uses_open_application(self):
        with patch.object(om, "obsidian_is_running", return_value=False):
            with patch.object(om.platform, "system", return_value="Darwin"):
                with patch.object(om.subprocess, "Popen") as popen:
                    self.assertTrue(om.launch_obsidian(Path("/Applications/Obsidian.app")))
                    popen.assert_called_once_with(["open", "-a", str(Path("/Applications/Obsidian.app"))])

    def test_cli_check_retries_while_app_is_starting(self):
        responses = [
            SimpleNamespace(returncode=1, stdout="", stderr="The CLI is unable to find Obsidian."),
            SimpleNamespace(returncode=0, stdout="help output", stderr=""),
        ]
        with patch.object(om.subprocess, "run", side_effect=responses):
            with patch.object(om.time, "monotonic", side_effect=[0, 0]):
                with patch.object(om.time, "sleep") as sleep:
                    self.assertTrue(om.check_cli_available("/fake/obsidian", wait_timeout=5))
                    sleep.assert_called_once_with(1)

    def test_active_vault_path_reads_cli_output_without_guessing(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            response = SimpleNamespace(returncode=0, stdout=f"path {vault}\n", stderr="")
            with patch.object(om.subprocess, "run", return_value=response):
                self.assertEqual(om.active_vault_path("/fake/obsidian"), vault.resolve())

    def test_active_vault_path_retries_until_vault_is_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            responses = [
                SimpleNamespace(returncode=0, stdout="path /not/ready/yet\n", stderr=""),
                SimpleNamespace(returncode=0, stdout=f"path {vault}\n", stderr=""),
            ]
            with patch.object(om.subprocess, "run", side_effect=responses):
                with patch.object(om.time, "monotonic", side_effect=[0, 0]):
                    with patch.object(om.time, "sleep") as sleep:
                        self.assertEqual(
                            om.active_vault_path("/fake/obsidian", wait_timeout=5),
                            vault.resolve(),
                        )
                        sleep.assert_called_once_with(1)

    def test_active_vault_path_returns_none_for_unknown_path(self):
        response = SimpleNamespace(returncode=0, stdout="path /not/a/real/vault\n", stderr="")
        with patch.object(om.subprocess, "run", return_value=response):
            self.assertIsNone(om.active_vault_path("/fake/obsidian"))

    def test_wait_for_plugin_enabled_retries_until_file_updates(self):
        with tempfile.TemporaryDirectory() as tmp:
            enabled = Path(tmp) / "community-plugins.json"
            enabled.write_text('["obsidian-git"]', encoding="utf-8")

            def appear_later(_seconds):
                enabled.write_text('["obsidian-git", "quickadd"]', encoding="utf-8")

            with patch.object(om.time, "monotonic", side_effect=[0, 0, 0]):
                with patch.object(om.time, "sleep", side_effect=appear_later) as sleep:
                    self.assertTrue(om.wait_for_plugin_enabled(enabled, "quickadd", wait_timeout=5))
            sleep.assert_called_once_with(0.5)

    def test_wait_for_plugin_enabled_times_out_without_false_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            enabled = Path(tmp) / "community-plugins.json"
            enabled.write_text('["obsidian-git"]', encoding="utf-8")
            with patch.object(om.time, "monotonic", side_effect=[0, 5]):
                with patch.object(om.time, "sleep") as sleep:
                    self.assertFalse(om.wait_for_plugin_enabled(enabled, "quickadd", wait_timeout=5))
            sleep.assert_not_called()

    def test_plugin_batch_rejects_empty_enabled_plugin_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            enabled = vault / ".obsidian" / "community-plugins.json"
            enabled.parent.mkdir(parents=True)
            enabled.write_text('[""]', encoding="utf-8")
            with patch.object(om.shutil, "which", return_value="/fake/obsidian"):
                with patch.object(om, "say") as say:
                    om.offer_obsidian_plugins(vault)
            messages = "\n".join(str(call.args[0]) for call in say.call_args_list)
            self.assertIn("格式异常", messages)

    def test_plugin_manager_stops_on_invalid_manifest_before_selection(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            manifest = vault / ".obsidian" / "plugins" / "quickadd" / "manifest.json"
            manifest.parent.mkdir(parents=True)
            manifest.write_text('{"id":"wrong-plugin"}', encoding="utf-8")
            enabled = vault / ".obsidian" / "community-plugins.json"
            enabled.write_text("[]", encoding="utf-8")
            with patch.object(om.shutil, "which", return_value="/fake/obsidian"):
                with patch.object(om, "select_numbered") as select:
                    with patch.object(om, "say") as say:
                        om.offer_obsidian_plugins(vault)
            select.assert_not_called()
            output = "\n".join(str(call.args[0]) for call in say.call_args_list)
            self.assertIn("插件 ID 不匹配", output)
            self.assertIn("已停止插件管理", output)

    def test_vault_chooser_uses_official_obsidian_uri(self):
        with patch.object(om.platform, "system", return_value="Darwin"):
            with patch.object(om.subprocess, "Popen") as popen:
                self.assertTrue(om.open_vault_chooser())
                popen.assert_called_once_with(["open", "obsidian://choose-vault"])

    def test_missing_app_still_allows_manual_local_vault_audit(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            with patch.object(om.platform, "system", return_value="Linux"):
                with patch.object(om, "find_obsidian", return_value=None):
                    with patch.object(om, "ask", return_value=str(vault)):
                        with patch.object(om, "ensure_vault_plugin_dirs", return_value=True):
                            with patch.object(om, "audit_plugins") as audit:
                                with patch.object(om, "offer_obsidian_plugins") as manage:
                                    with patch.object(om, "say"):
                                        self.assertEqual(om.main(), 0)
            audit.assert_called_once_with(vault.resolve())
            manage.assert_not_called()


if __name__ == "__main__":
    unittest.main()
