import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class DesktopEntrypointRegressionTests(unittest.TestCase):
    """Protect the existing desktop entry points while mobile code is added."""

    def test_existing_python_core_remains_present(self):
        self.assertTrue((ROOT / "obsidian_manager.py").is_file())

    def test_windows_powershell_launcher_remains_present_and_uses_python_core(self):
        launcher = ROOT / "obsidian_manager.ps1"
        self.assertTrue(launcher.is_file())
        source = launcher.read_text(encoding="utf-8")
        self.assertIn("obsidian_manager.py", source)
        self.assertIn("py -3", source)
        self.assertIn("python ", source)

    def test_macos_linux_shell_launcher_remains_present_and_uses_python3(self):
        launcher = ROOT / "obsidian_manager.sh"
        self.assertTrue(launcher.is_file())
        source = launcher.read_text(encoding="utf-8")
        self.assertIn('exec python3 "$SCRIPT_DIR/obsidian_manager.py"', source)
        self.assertIn('dirname -- "$0"', source)

    def test_desktop_update_subscription_utility_remains_present(self):
        self.assertTrue((ROOT / "plugin_update_subscription.py").is_file())


if __name__ == "__main__":
    unittest.main()
