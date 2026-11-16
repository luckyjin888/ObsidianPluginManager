import io
import json
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

RELEASE = json.dumps({
    "id": 12345,
    "name": "Release 1.2.3",
    "tag_name": "v1.2.3",
    "published_at": "2026-11-16T00:00:00Z",
    "html_url": "https://github.com/example/plugin/releases/tag/v1.2.3",
}).encode("utf-8")


def mock_response(payload=RELEASE, headers=None):
    response = Mock()
    response.read.return_value = payload
    response.headers = headers or {}
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    return response


def http_error(code, headers=None, body=b"{}"):
    return urllib.error.HTTPError(
        "https://api.github.com/repos/example/plugin/releases/latest",
        code, "HTTP error", headers or {}, io.BytesIO(body)
    )


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

    def test_parse_release_extracts_api_fields(self):
        result = watcher.parse_release(RELEASE)
        self.assertEqual(result["id"], "12345")
        self.assertEqual(result["title"], "Release 1.2.3")
        self.assertTrue(result["link"].endswith("v1.2.3"))

    def test_first_check_establishes_baseline_without_false_update(self):
        with patch.object(watcher.urllib.request, "urlopen", return_value=mock_response(headers={"ETag": '"tag"'})):
            record, status = watcher.check_one("Example", "example/plugin", {})
        self.assertEqual(status, "baseline")
        self.assertEqual(record["latest"]["id"], "12345")
        self.assertEqual(record["etag"], '"tag"')

    def test_legacy_atom_cache_migrates_as_baseline_without_old_validators(self):
        legacy = {
            "checked": True,
            "etag": '"atom-etag"',
            "last_modified": "yesterday",
            "latest": {"id": "tag:github.com,2008:Repository/1/v1.0.0"},
        }
        with patch.object(watcher.urllib.request, "urlopen", return_value=mock_response()) as opened:
            record, status = watcher.check_one("Example", "example/plugin", legacy)
        request = opened.call_args.args[0]
        self.assertEqual(status, "baseline")
        self.assertIsNone(request.get_header("If-none-match"))
        self.assertIsNone(request.get_header("If-modified-since"))
        self.assertEqual(record["source"], watcher.CACHE_SOURCE)
        self.assertEqual(record["latest"]["id"], "12345")

    def test_first_release_after_empty_feed_is_reported(self):
        previous = {"source": watcher.CACHE_SOURCE, "checked": True, "latest": None}
        with patch.object(watcher.urllib.request, "urlopen", return_value=mock_response()):
            record, status = watcher.check_one("Example", "example/plugin", previous)
        self.assertEqual(status, "new")
        self.assertEqual(record["latest"]["title"], "Release 1.2.3")

    def test_existing_release_change_is_reported(self):
        previous = {"source": watcher.CACHE_SOURCE, "latest": {"id": "old-release"}}
        with patch.object(watcher.urllib.request, "urlopen", return_value=mock_response()):
            record, status = watcher.check_one("Example", "example/plugin", previous)
        self.assertEqual(status, "new")

    def test_conditional_headers_and_api_url_are_sent(self):
        previous = {"source": watcher.CACHE_SOURCE, "etag": '"cached"', "last_modified": "yesterday"}
        with patch.dict("os.environ", {"GITHUB_TOKEN": "test-secret"}, clear=True):
            with patch.object(watcher.urllib.request, "urlopen", return_value=mock_response()) as opened:
                watcher.check_one("Example", "example/plugin", previous)
        request = opened.call_args.args[0]
        self.assertEqual(request.full_url, "https://api.github.com/repos/example/plugin/releases/latest")
        self.assertEqual(request.get_header("If-none-match"), '"cached"')
        self.assertEqual(request.get_header("If-modified-since"), "yesterday")
        self.assertEqual(request.get_header("Authorization"), "Bearer test-secret")

    def test_token_is_not_required_and_not_added_when_missing(self):
        with patch.dict("os.environ", {}, clear=True):
            with patch.object(watcher.urllib.request, "urlopen", return_value=mock_response()) as opened:
                watcher.check_one("Example", "example/plugin", {})
        request = opened.call_args.args[0]
        self.assertIsNone(request.get_header("Authorization"))

    def test_http_304_keeps_previous_release(self):
        error = http_error(304)
        with patch.object(watcher.urllib.request, "urlopen", side_effect=error):
            record, status = watcher.check_one(
                "Example", "example/plugin", {"source": watcher.CACHE_SOURCE, "latest": {"id": "same"}}
            )
        self.assertEqual(status, "not_modified")
        self.assertEqual(record["latest"]["id"], "same")

    def test_http_404_means_no_public_release(self):
        with patch.object(watcher.urllib.request, "urlopen", side_effect=http_error(404)):
            record, status = watcher.check_one("Example", "example/plugin", {})
        self.assertEqual(status, "empty")
        self.assertIsNone(record["latest"])

    def test_429_honors_retry_after_and_retries(self):
        with patch.object(watcher.urllib.request, "urlopen",
                          side_effect=[http_error(429, {"Retry-After": "2"}), mock_response()]) as opened:
            with patch.object(watcher.time, "sleep") as sleep:
                record, status = watcher.check_one("Example", "example/plugin", {})
        self.assertEqual(status, "baseline")
        self.assertEqual(opened.call_count, 2)
        sleep.assert_called_once_with(2)

    def test_rate_limit_403_retries_but_permission_403_does_not(self):
        rate_error = http_error(403, {"Retry-After": "1", "X-RateLimit-Remaining": "0"},
                                b'{"message":"API rate limit exceeded"}')
        with patch.object(watcher.urllib.request, "urlopen",
                          side_effect=[rate_error, mock_response()]) as opened:
            with patch.object(watcher.time, "sleep"):
                watcher.check_one("Example", "example/plugin", {})
        self.assertEqual(opened.call_count, 2)

        permission_error = http_error(403, {"X-RateLimit-Remaining": "100"},
                                      b'{"message":"Resource not accessible"}')
        with patch.object(watcher.urllib.request, "urlopen", side_effect=permission_error) as opened:
            with self.assertRaisesRegex(RuntimeError, "不是已确认的限流"):
                watcher.check_one("Example", "example/plugin", {})
        self.assertEqual(opened.call_count, 1)

    def test_headerless_secondary_rate_limit_uses_one_minute_minimum(self):
        error = http_error(403, {}, b'{"message":"You have exceeded a secondary rate limit"}')
        self.assertEqual(watcher.rate_limit_retry_delay(error), 60)

    def test_subscription_caps_cumulative_rate_limit_wait(self):
        first = http_error(429, {"Retry-After": "40"})
        second = http_error(429, {"Retry-After": "40"})
        with patch.object(watcher.urllib.request, "urlopen", side_effect=[first, second]) as opened:
            with patch.object(watcher.time, "sleep") as sleep:
                with self.assertRaisesRegex(RuntimeError, "累计等待将超过 60 秒"):
                    watcher.check_one("Example", "example/plugin", {})
        self.assertEqual(opened.call_count, 2)
        sleep.assert_called_once_with(40)

    def test_run_shares_rate_limit_wait_budget_across_plugins(self):
        first_limit = http_error(429, {"Retry-After": "40"})
        second_limit = http_error(429, {"Retry-After": "40"})
        with tempfile.TemporaryDirectory() as tmp:
            cache_path = Path(tmp) / "cache.json"
            with patch.object(
                watcher, "PLUGINS",
                (("First", "example/first"), ("Second", "example/second"))
            ):
                with patch.object(
                    watcher.urllib.request, "urlopen",
                    side_effect=[first_limit, mock_response(), second_limit]
                ) as opened:
                    with patch.object(watcher.time, "sleep") as sleep:
                        result = watcher.run(cache_path)
        self.assertEqual(result, 1)
        self.assertEqual(opened.call_count, 3)
        sleep.assert_called_once_with(40)

    def test_legacy_cache_404_does_not_retain_atom_validators(self):
        legacy = {
            "checked": True,
            "etag": '"legacy-atom-etag"',
            "last_modified": "yesterday",
            "latest": {"id": "old-atom-entry"},
        }
        with patch.object(watcher.urllib.request, "urlopen", side_effect=http_error(404)):
            record, status = watcher.check_one("Example", "example/plugin", legacy)
        self.assertEqual(status, "empty")
        self.assertNotIn("etag", record)
        self.assertNotIn("last_modified", record)
        self.assertEqual(record["source"], watcher.CACHE_SOURCE)

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
