import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import obsidian_manager


class ObsidianCliGuidanceTests(unittest.TestCase):
    def test_detects_cli_disabled_message_in_stderr(self):
        result = SimpleNamespace(stdout="", stderr="Command line interface is not enabled.")
        self.assertTrue(obsidian_manager.is_cli_not_enabled(result))

    def test_detects_cli_disabled_message_in_stdout_case_insensitively(self):
        result = SimpleNamespace(stdout="Please turn it on in Settings > General > Advanced.", stderr="")
        self.assertTrue(obsidian_manager.is_cli_not_enabled(result))

    def test_does_not_classify_unrelated_cli_errors_as_disabled(self):
        result = SimpleNamespace(stdout="", stderr="Vault not found.")
        self.assertFalse(obsidian_manager.is_cli_not_enabled(result))

    def test_handles_missing_output_attributes(self):
        self.assertFalse(obsidian_manager.is_cli_not_enabled(object()))

    @patch("obsidian_manager.subprocess.run")
    def test_preflight_runs_help_and_accepts_success(self, run):
        run.return_value = SimpleNamespace(stdout="Obsidian CLI help", stderr="", returncode=0)
        self.assertTrue(obsidian_manager.check_cli_available("/fake/obsidian"))
        run.assert_called_once_with(
            ["/fake/obsidian", "help"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
            check=False,
        )

    @patch("obsidian_manager.explain_cli_not_enabled")
    @patch("obsidian_manager.subprocess.run")
    def test_preflight_shows_guide_when_cli_is_disabled(self, run, guide):
        run.return_value = SimpleNamespace(
            stdout="",
            stderr="Command line interface is not enabled. Please turn it on in Settings > General > Advanced.",
            returncode=1,
        )
        self.assertFalse(obsidian_manager.check_cli_available("/fake/obsidian"))
        guide.assert_called_once_with()

    @patch("obsidian_manager.explain_cli_not_enabled")
    @patch("obsidian_manager.subprocess.run")
    def test_preflight_does_not_misclassify_other_errors(self, run, guide):
        run.return_value = SimpleNamespace(stdout="", stderr="Vault not found.", returncode=1)
        self.assertFalse(obsidian_manager.check_cli_available("/fake/obsidian"))
        guide.assert_not_called()

    @patch("obsidian_manager.subprocess.Popen")
    @patch("obsidian_manager.platform.system", return_value="Darwin")
    @patch("obsidian_manager.Path.is_file", return_value=True)
    @patch("obsidian_manager.subprocess.run")
    @patch("obsidian_manager.shutil.which", return_value="/usr/bin/chafa")
    @patch("obsidian_manager.say")
    def test_diagram_shows_terminal_and_original_image_together(
        self, say, which, run, is_file, system, popen
    ):
        run.return_value = SimpleNamespace(stdout="terminal image", stderr="", returncode=0)
        obsidian_manager.display_cli_setup_diagram(Path("/repo/guide.svg"))
        run.assert_called_once()
        self.assertIn("--size", run.call_args.args[0])
        self.assertIn("terminal image", [str(call.args[0]) for call in say.call_args_list])
        popen.assert_called_once_with(["open", str(Path("/repo/guide.svg"))])

    @patch("obsidian_manager.subprocess.Popen")
    @patch("obsidian_manager.platform.system", return_value="Darwin")
    @patch("obsidian_manager.Path.is_file", return_value=True)
    @patch("obsidian_manager.subprocess.run")
    @patch("obsidian_manager.shutil.which", return_value=None)
    @patch("obsidian_manager.say")
    def test_diagram_falls_back_to_ascii_and_opens_original_svg(
        self, say, which, run, is_file, system, popen
    ):
        obsidian_manager.display_cli_setup_diagram(Path("/repo/guide.svg"))
        run.assert_not_called()
        popen.assert_called_once_with(["open", str(Path("/repo/guide.svg"))])
        output = "\\n".join(str(call.args[0]) for call in say.call_args_list)
        self.assertIn("Obsidian · 设置", output)
        self.assertIn("命令行界面", output)

    @patch("obsidian_manager.ask")
    @patch("obsidian_manager.explain_cli_not_enabled")
    @patch("obsidian_manager.subprocess.run")
    @patch("obsidian_manager.shutil.which", return_value="/fake/obsidian")
    @patch("obsidian_manager.app_version", return_value="1.13.7")
    @patch("obsidian_manager.find_obsidian", return_value=Path("/Applications/Obsidian.app"))
    @patch("obsidian_manager.platform.system", return_value="Darwin")
    def test_main_stops_before_vault_prompt_when_cli_is_disabled(
        self, system, find_app, version, which, run, guide, ask
    ):
        run.return_value = SimpleNamespace(
            stdout="",
            stderr="Command line interface is not enabled.",
            returncode=1,
        )
        self.assertEqual(obsidian_manager.main(), 0)
        guide.assert_called_once_with()
        ask.assert_not_called()


if __name__ == "__main__":
    unittest.main()
