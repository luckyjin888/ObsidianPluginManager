import io
import unittest
from unittest.mock import patch

import obsidian_manager as om


class OutputAndSelectionTests(unittest.TestCase):
    def test_say_writes_utf8_and_real_newline_after_encoding_error(self):
        class BrokenTextStream:
            encoding = "cp1252"

            def __init__(self):
                self.buffer = io.BytesIO()

            def write(self, value):
                raise UnicodeEncodeError("cp1252", value, 0, 1, "cannot encode")

            def flush(self):
                pass

        stream = BrokenTextStream()
        with patch("obsidian_manager.sys.stdout", stream):
            om.say("中文")
        self.assertEqual(stream.buffer.getvalue(), "中文\n".encode("utf-8"))

    def test_select_numbered_accepts_deduplicated_indexes(self):
        items = [
            {"id": "first", "name": "First"},
            {"id": "second", "name": "Second"},
            {"id": "third", "name": "Third"},
        ]
        with patch("builtins.input", return_value="3,1,3"):
            selected = om.select_numbered(items)
        self.assertEqual([item["id"] for item in selected], ["third", "first"])

    def test_select_numbered_all_returns_all_items(self):
        items = [{"id": "one", "name": "One"}, {"id": "two", "name": "Two"}]
        with patch("builtins.input", return_value="all"):
            self.assertEqual(om.select_numbered(items), items)

    def test_select_numbered_invalid_index_skips_without_partial_selection(self):
        items = [{"id": "one", "name": "One"}, {"id": "two", "name": "Two"}]
        with patch("builtins.input", return_value="1,3"):
            self.assertEqual(om.select_numbered(items), [])

    def test_select_numbered_all_excludes_templater(self):
        items = [
            {"id": "quickadd", "name": "QuickAdd"},
            {"id": "templater-obsidian", "name": "Templater"},
        ]
        with patch("builtins.input", return_value="all"):
            selected = om.select_numbered(items, exclude_all_ids={"templater-obsidian"})
        self.assertEqual([item["id"] for item in selected], ["quickadd"])

    def test_plugin_action_uses_current_install_and_enable_state(self):
        self.assertEqual(om.plugin_action("new", set(), set()), "install_and_enable")
        self.assertEqual(om.plugin_action("installed", {"installed"}, set()), "enable")
        self.assertEqual(om.plugin_action("enabled", {"enabled"}, {"enabled"}), "skip")

    def test_plugin_batch_uses_one_consent_for_all_selected_items(self):
        plan = [
            ({"id": "one", "name": "One", "risk": "normal"}, "install_and_enable"),
            ({"id": "two", "name": "Two", "risk": "normal"}, "enable"),
        ]
        with patch("obsidian_manager.ask_yes_no", return_value=True) as consent:
            self.assertTrue(om.explain_plugin_batch("/vault", plan))
        consent.assert_called_once()

    def test_yes_no_requires_explicit_one_and_defaults_blank_to_no(self):
        with patch("builtins.input", side_effect=["x", "1"]):
            self.assertTrue(om.ask_yes_no("确认"))
        with patch("builtins.input", return_value=""):
            self.assertFalse(om.ask_yes_no("确认"))


if __name__ == "__main__":
    unittest.main()
