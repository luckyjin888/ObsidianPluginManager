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
            (install / "Obsidian.exe").write_bytes(b"test")
            with patch("obsidian_manager.platform.system", return_value="Windows"):
                with patch("obsidian_manager.windows_running_obsidian_paths", return_value=[]), patch("obsidian_manager.windows_registered_obsidian_paths", return_value=[]):
                    with patch.dict(os.environ, {"LOCALAPPDATA": str(local)}, clear=True):
                        self.assertEqual(om.find_obsidian(), install)

    def test_detects_program_files_install_location(self):
        with tempfile.TemporaryDirectory() as tmp:
            program_files = Path(tmp) / "Program Files"
            install = program_files / "Obsidian"
            install.mkdir(parents=True)
            (install / "Obsidian.exe").write_bytes(b"test")
            with patch("obsidian_manager.platform.system", return_value="Windows"):
                with patch("obsidian_manager.windows_running_obsidian_paths", return_value=[]), patch("obsidian_manager.windows_registered_obsidian_paths", return_value=[]):
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

    def test_detects_install_on_non_c_drive(self):
        with tempfile.TemporaryDirectory() as tmp:
            drive_d = Path(tmp) / "D"
            install = drive_d / "Program Files" / "Obsidian"
            install.mkdir(parents=True)
            (install / "Obsidian.exe").write_bytes(b"test")
            with patch("obsidian_manager.platform.system", return_value="Windows"):
                with patch("obsidian_manager.windows_running_obsidian_paths", return_value=[]), patch("obsidian_manager.windows_registered_obsidian_paths", return_value=[]):
                    with patch("obsidian_manager.windows_drive_roots", return_value=[drive_d]):
                        with patch.dict(os.environ, {}, clear=True):
                            self.assertEqual(om.find_obsidian(), install)

    def test_checks_common_custom_folder_on_other_drive(self):
        with tempfile.TemporaryDirectory() as tmp:
            drive_e = Path(tmp) / "E"
            install = drive_e / "Apps" / "Obsidian"
            install.mkdir(parents=True)
            (install / "Obsidian.exe").write_bytes(b"test")
            with patch("obsidian_manager.platform.system", return_value="Windows"):
                with patch("obsidian_manager.windows_running_obsidian_paths", return_value=[]), patch("obsidian_manager.windows_registered_obsidian_paths", return_value=[]):
                    with patch("obsidian_manager.windows_drive_roots", return_value=[drive_e]):
                        with patch.dict(os.environ, {}, clear=True):
                            self.assertEqual(om.find_obsidian(), install)

    def test_detects_custom_location_from_running_process(self):
        with tempfile.TemporaryDirectory() as tmp:
            install = Path(tmp) / "PortableApps" / "Obsidian"
            install.mkdir(parents=True)
            (install / "Obsidian.exe").write_bytes(b"test")
            with patch("obsidian_manager.platform.system", return_value="Windows"):
                with patch("obsidian_manager.windows_running_obsidian_paths", return_value=[install]):
                    with patch("obsidian_manager.windows_registered_obsidian_paths", return_value=[]):
                        with patch("obsidian_manager.windows_drive_roots", return_value=[]):
                            with patch.dict(os.environ, {}, clear=True):
                                self.assertEqual(om.find_obsidian(), install)

    def test_manual_path_accepts_exe_or_install_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            install = Path(tmp) / "MyApps" / "Obsidian"
            install.mkdir(parents=True)
            exe = install / "Obsidian.exe"
            exe.write_bytes(b"test")
            with patch("obsidian_manager.platform.system", return_value="Windows"):
                with patch("builtins.input", return_value=str(exe)):
                    self.assertEqual(om.prompt_manual_obsidian_path(None), install)

    def test_macos_install_requires_valid_app_bundle_layout(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = Path(tmp) / "Obsidian.app"
            contents = app / "Contents"
            (contents / "MacOS").mkdir(parents=True)
            (contents / "Info.plist").write_text("plist", encoding="utf-8")
            executable = contents / "MacOS" / "Obsidian"
            executable.write_text("#!/bin/sh\n", encoding="utf-8")
            executable.chmod(0o755)
            with patch("obsidian_manager.platform.system", return_value="Darwin"):
                self.assertEqual(om.is_obsidian_install(app), app)
                self.assertIsNone(om.is_obsidian_install(Path(tmp)))

    def test_linux_install_requires_resources_and_executable(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = Path(tmp) / "Obsidian"
            resources = app / "resources"
            resources.mkdir(parents=True)
            (resources / "app.asar").write_bytes(b"placeholder")
            executable = app / "obsidian"
            executable.write_text("#!/bin/sh\n", encoding="utf-8")
            executable.chmod(0o755)
            with patch("obsidian_manager.platform.system", return_value="Linux"):
                self.assertEqual(om.is_obsidian_install(app), app)
                self.assertIsNone(om.is_obsidian_install(Path(tmp)))

    def test_cli_registration_rejects_unrelated_executable(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = Path(tmp) / "Obsidian.app"
            (app / "Contents" / "MacOS").mkdir(parents=True)
            source = app / "Contents" / "MacOS" / "obsidian-cli"
            source.write_text("#!/bin/sh\n", encoding="utf-8")
            source.chmod(0o755)
            unrelated = Path(tmp) / "obsidian-cli"
            unrelated.write_text("#!/bin/sh\n", encoding="utf-8")
            unrelated.chmod(0o755)
            with patch("obsidian_manager.platform.system", return_value="Darwin"):
                self.assertTrue(om.is_valid_cli_source(app, source))
                self.assertFalse(om.is_valid_cli_source(app, unrelated))

if __name__ == "__main__":
    unittest.main()
