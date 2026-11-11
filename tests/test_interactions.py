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

    def test_yes_no_requires_explicit_one_and_defaults_blank_to_no(self):
        with patch("builtins.input", side_effect=["x", "1"]):
            self.assertTrue(om.ask_yes_no("确认"))
        with patch("builtins.input", return_value=""):
            self.assertFalse(om.ask_yes_no("确认"))


if __name__ == "__main__":
    unittest.main()
