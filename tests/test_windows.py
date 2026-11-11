import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import obsidian_manager as om


class WindowsPlatformTests(unittest.TestCase):
    def test_detects_standard_per_user_install_location(self):
        with tempfile.TemporaryDirectory() as tmp:
            local = Path(tmp) / "LocalAppData"
            install = local / "Programs" / "Obsidian"
            install.mkdir(parents=True)
            with patch("obsidian_manager.platform.system", return_value="Windows"):
                with patch.dict(os.environ, {"LOCALAPPDATA": str(local)}, clear=True):
                    self.assertEqual(om.find_obsidian(), install)

    def test_detects_program_files_install_location(self):
        with tempfile.TemporaryDirectory() as tmp:
            program_files = Path(tmp) / "Program Files"
            install = program_files / "Obsidian"
            install.mkdir(parents=True)
            with patch("obsidian_manager.platform.system", return_value="Windows"):
                with patch.dict(os.environ, {"ProgramFiles": str(program_files)}, clear=True):
                    self.assertEqual(om.find_obsidian(), install)

    def test_only_uses_obsidian_com_as_windows_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = Path(tmp)
            (app / "Obsidian.exe").write_bytes(b"GUI executable placeholder")
            with patch("obsidian_manager.platform.system", return_value="Windows"):
                result = om.cli_candidates(app)
            self.assertEqual(result, [app / "Obsidian.com"])
            self.assertNotIn(app / "Obsidian.exe", result)

    def test_windows_cli_candidate_is_not_the_gui_executable(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = Path(tmp)
            (app / "Obsidian.exe").write_bytes(b"GUI executable placeholder")
            with patch("obsidian_manager.platform.system", return_value="Windows"):
                source = next((p for p in om.cli_candidates(app) if p.is_file()), None)
            self.assertIsNone(source)


if __name__ == "__main__":
    unittest.main()
