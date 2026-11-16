import io
import json
import unittest
import urllib.error
from unittest.mock import Mock, patch

import obsidian_manager as manager


def rate_limit_error(delay="40"):
    return urllib.error.HTTPError(
        "https://api.github.com/repos/example/plugin",
        429,
        "Too Many Requests",
        {"Retry-After": delay},
        io.BytesIO(b'{"message":"rate limit exceeded"}'),
    )


def json_response(payload):
    response = Mock()
    response.read.return_value = json.dumps(payload).encode("utf-8")
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    return response


class InstallerRateLimitBudgetTests(unittest.TestCase):
    def test_registry_and_repo_checks_share_one_60_second_budget(self):
        budget = [0]
        with patch.object(
            manager,
            "open_verified_https",
            side_effect=[
                rate_limit_error("40"),
                json_response([]),
                rate_limit_error("40"),
            ],
        ) as opened:
            with patch.object(manager.time, "sleep") as sleep:
                manager.fetch_registry(rate_limit_wait_budget=budget)
                with self.assertRaisesRegex(RuntimeError, "批量操作累计限流等待将超过 60 秒"):
                    manager.fetch_repo_status(
                        "example/plugin",
                        rate_limit_wait_budget=budget,
                    )

        self.assertEqual(budget, [40])
        self.assertEqual(opened.call_count, 3)
        sleep.assert_called_once_with(40)


if __name__ == "__main__":
    unittest.main()
