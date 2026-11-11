import tempfile
import unittest
from pathlib import Path

import obsidian_manager as om


class VaultDirectoryInitializationTests(unittest.TestCase):
    def test_creates_both_missing_directories_without_prompting(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / "Company-Hub"
            vault.mkdir()
            self.assertTrue(om.ensure_vault_plugin_dirs(vault))
            self.assertTrue((vault / ".obsidian").is_dir())
            self.assertTrue((vault / ".obsidian" / "plugins").is_dir())
            self.assertEqual(list((vault / ".obsidian" / "plugins").iterdir()), [])

    def test_creates_only_missing_plugins_directory_and_preserves_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            config = vault / ".obsidian"
            config.mkdir()
            marker = config / "appearance.json"
            marker.write_text('{"theme":"obsidian"}', encoding="utf-8")
            self.assertTrue(om.ensure_vault_plugin_dirs(vault))
            self.assertTrue((config / "plugins").is_dir())
            self.assertEqual(marker.read_text(encoding="utf-8"), '{"theme":"obsidian"}')

    def test_existing_directories_and_files_are_preserved_without_prompting(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            plugins = vault / ".obsidian" / "plugins"
            plugins.mkdir(parents=True)
            marker = plugins / "keep.txt"
            marker.write_text("do not overwrite", encoding="utf-8")
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
            (vault / ".obsidian").write_text("not a directory", encoding="utf-8")
            self.assertFalse(om.ensure_vault_plugin_dirs(vault))

    def test_rejects_plugins_path_that_is_a_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            config = vault / ".obsidian"
            config.mkdir()
            (config / "plugins").write_text("not a directory", encoding="utf-8")
            self.assertFalse(om.ensure_vault_plugin_dirs(vault))


if __name__ == "__main__":
    unittest.main()
