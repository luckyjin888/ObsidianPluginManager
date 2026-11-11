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

    def test_rejects_plugins_path_that_is_a_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            plugins = vault / ".obsidian" / "plugins"
            plugins.parent.mkdir(parents=True)
            plugins.write_text("keep", encoding="utf-8")
            self.assertFalse(om.ensure_vault_plugin_dirs(vault))
            self.assertEqual(plugins.read_text(encoding="utf-8"), "keep")

    def test_rejects_symlinked_config_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            vault = root / "vault"
            outside = root / "outside"
            vault.mkdir()
            outside.mkdir()
            try:
                (vault / ".obsidian").symlink_to(outside, target_is_directory=True)
            except (OSError, NotImplementedError) as exc:
                self.skipTest(f"当前系统不支持创建目录符号链接：{exc}")
            self.assertFalse(om.ensure_vault_plugin_dirs(vault))
            self.assertFalse((outside / "plugins").exists())

    def test_rejects_broken_symlinked_plugins_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            config = vault / ".obsidian"
            config.mkdir()
            missing_target = vault / "missing-target"
            try:
                (config / "plugins").symlink_to(missing_target, target_is_directory=True)
            except (OSError, NotImplementedError) as exc:
                self.skipTest(f"当前系统不支持创建目录符号链接：{exc}")
            self.assertFalse(om.ensure_vault_plugin_dirs(vault))

    def test_rejects_config_path_that_is_a_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            (vault / ".obsidian").write_text("keep", encoding="utf-8")
            self.assertFalse(om.ensure_vault_plugin_dirs(vault))
            self.assertEqual((vault / ".obsidian").read_text(encoding="utf-8"), "keep")


if __name__ == "__main__":
    unittest.main()

def test_rolls_back_new_config_directory_when_plugins_creation_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            original_mkdir = Path.mkdir

            def fail_plugins(path, *args, **kwargs):
                if path.name == "plugins":
                    raise PermissionError("simulated permission failure")
                return original_mkdir(path, *args, **kwargs)

            with patch.object(Path, "mkdir", autospec=True, side_effect=fail_plugins):
                self.assertFalse(om.ensure_vault_plugin_dirs(vault))
            self.assertFalse((vault / ".obsidian").exists())
