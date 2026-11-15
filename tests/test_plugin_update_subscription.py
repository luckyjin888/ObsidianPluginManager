import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
import urllib.error

import plugin_update_subscription as watcher


ATOM = b"""<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>tag:github.com,2008:Repository/1/v1.2.3</id>
    <title>v1.2.3</title>
    <updated>2026-11-16T00:00:00Z</updated>
    <link rel="alternate" href="https://github.com/example/plugin/releases/tag/v1.2.3" />
  </entry>
</feed>"""


class ReleaseSubscriptionTests(unittest.TestCase):
    def test_parse_feed_extracts_latest_release(self):
        result = watcher.parse_feed(ATOM)
        self.assertEqual(result["title"], "v1.2.3")
        self.assertEqual(result["updated"], "2026-11-16T00:00:00Z")
        self.assertTrue(result["link"].endswith("v1.2.3"))

    def test_parse_feed_empty_feed(self):
        self.assertIsNone(watcher.parse_feed(
            b'<feed xmlns="http://www.w3.org/2005/Atom"></feed>'
        ))

    def test_parse_feed_rejects_oversized_payload(self):
        with self.assertRaises(ValueError):
            watcher.parse_feed(b"x" * (watcher.MAX_FEED_BYTES + 1))

    def test_first_check_establishes_baseline_without_false_update(self):
        response = Mock()
        response.read.return_value = ATOM
        response.headers = {"ETag": '"feed-tag"'}
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        with patch.object(watcher.urllib.request, "urlopen", return_value=response):
            record, status = watcher.check_one("Example", "example/plugin", {})
        self.assertEqual(status, "baseline")
        self.assertEqual(record["latest"]["title"], "v1.2.3")
        self.assertEqual(record["etag"], '"feed-tag"')

    def test_existing_release_change_is_reported(self):
        response = Mock()
        response.read.return_value = ATOM
        response.headers = {}
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        previous = {"latest": {"id": "old-release"}}
        with patch.object(watcher.urllib.request, "urlopen", return_value=response):
            record, status = watcher.check_one("Example", "example/plugin", previous)
        self.assertEqual(status, "new")

    def test_conditional_headers_are_sent(self):
        response = Mock()
        response.read.return_value = ATOM
        response.headers = {}
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        previous = {"etag": '"cached"', "last_modified": "yesterday"}
        with patch.object(watcher.urllib.request, "urlopen", return_value=response) as opened:
            watcher.check_one("Example", "example/plugin", previous)
        request = opened.call_args.args[0]
        self.assertEqual(request.get_header("If-none-match"), '"cached"')
        self.assertEqual(request.get_header("If-modified-since"), "yesterday")

    def test_http_304_keeps_previous_release(self):
        error = urllib.error.HTTPError("https://github.com/example/plugin/releases.atom", 304,
                                       "Not Modified", {}, None)
        with patch.object(watcher.urllib.request, "urlopen", side_effect=error):
            record, status = watcher.check_one(
                "Example", "example/plugin", {"latest": {"id": "same"}}
            )
        self.assertEqual(status, "not_modified")
        self.assertEqual(record["latest"]["id"], "same")

    def test_cache_round_trip_uses_atomic_json_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cache.json"
            watcher.save_cache(path, {"example/plugin": {"latest": {"id": "one"}}})
            self.assertEqual(watcher.load_cache(path)["example/plugin"]["latest"]["id"], "one")

    def test_cache_refuses_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "target.json"
            target.write_text("{}", encoding="utf-8")
            link = root / "cache.json"
            try:
                link.symlink_to(target)
            except (OSError, NotImplementedError) as exc:
                self.skipTest(f"当前系统不支持符号链接：{exc}")
            with self.assertRaises(RuntimeError):
                watcher.load_cache(link)


if __name__ == "__main__":
    unittest.main()
