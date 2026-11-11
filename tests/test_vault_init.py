import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import obsidian_manager as om


class VaultDirectoryInitializationTests(unittest.TestCase):
    def test_automatically_creates_both_missing_directories_without_prompt(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / "Company-Hub"
            vault.mkdir()
            with patch("builtins.input", side_effect=AssertionError("unexpected prompt")):
                self.assertTrue(om.ensure_vault_plugin_dirs(vault))
            self.assertTrue((vault / ".obsidian").is_dir())
            self.assertTrue((vault / ".obsidian" / "plugins").is_dir())
            self.assertEqual(list((vault / ".obsidian" / "plugins").iterdir()), [])

    def test_automatically_creates_plugins_inside_existing_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            (vault / ".obsidian").mkdir()
            with patch("builtins.input", side_effect=AssertionError("unexpected prompt")):
                self.assertTrue(om.ensure_vault_plugin_dirs(vault))
            self.assertTrue((vault / ".obsidian" / "plugins").is_dir())

    def test_existing_directories_need_no_confirmation_and_are_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            plugins = vault / ".obsidian" / "plugins"
            plugins.mkdir(parents=True)
            marker = plugins / "keep.txt"
            marker.write_text("do not overwrite", encoding="utf-8")
            with patch("builtins.input", side_effect=AssertionError("unexpected prompt")):
                self.assertTrue(om.ensure_vault_plugin_dirs(vault))
            self.assertEqual(marker.read_text(encoding="utf-8"), "do not overwrite")

    def test_rejects_non_directory_vault(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / "not-a-folder"
            vault.write_text("x", encoding="utf-8")
            self.assertFalse(om.ensure_vault_plugin_dirs(vault))

    def test_rejects_config_path_that_is_a_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            (vault / ".obsidian").write_text("keep", encoding="utf-8")
            self.assertFalse(om.ensure_vault_plugin_dirs(vault))
            self.assertEqual((vault / ".obsidian").read_text(encoding="utf-8"), "keep")


if __name__ == "__main__":
    unittest.main()
