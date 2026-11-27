from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
PACKAGER = ROOT / "tools" / "package_mobile_plugin.py"


class MobilePluginPackageTests(unittest.TestCase):
    def test_builds_flat_zip_with_runtime_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "plugin"
            source.mkdir()
            (source / "manifest.json").write_text(
                json.dumps({"id": "cross-platform-manager", "version": "0.1.0"}),
                encoding="utf-8",
            )
            (source / "main.js").write_text("/* bundled plugin */", encoding="utf-8")
            output = Path(temporary) / "package.zip"

            subprocess.run(
                [sys.executable, str(PACKAGER), "--source", str(source), "--output", str(output)],
                check=True,
                capture_output=True,
                text=True,
            )

            with ZipFile(output) as archive:
                self.assertEqual(set(archive.namelist()), {"manifest.json", "main.js"})

    def test_rejects_missing_main_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "plugin"
            source.mkdir()
            (source / "manifest.json").write_text(
                json.dumps({"id": "cross-platform-manager", "version": "0.1.0"}),
                encoding="utf-8",
            )
            result = subprocess.run(
                [sys.executable, str(PACKAGER), "--source", str(source)],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("main.js", result.stderr)


if __name__ == "__main__":
    unittest.main()
