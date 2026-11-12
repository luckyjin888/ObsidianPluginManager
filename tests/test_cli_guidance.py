import unittest
from types import SimpleNamespace

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


if __name__ == "__main__":
    unittest.main()
