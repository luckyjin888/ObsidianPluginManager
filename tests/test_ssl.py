import ssl
import unittest
from unittest.mock import patch
from urllib.error import URLError
from urllib.request import Request

import obsidian_manager as om


class DummyResponse:
    def __init__(self, payload=b'{"ok": true}'):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self.payload


class SSLHandlingTests(unittest.TestCase):
    def setUp(self):
        self.secure_context = ssl.create_default_context()

    def test_all_attempted_contexts_require_chain_and_hostname_validation(self):
        with patch.object(
            om, "ssl_context_candidates",
            return_value=[("测试证书库", self.secure_context)]
        ):
            with patch.object(om.urllib.request, "urlopen", return_value=DummyResponse()):
                response = om.open_verified_https(Request("https://example.com"))
        self.assertIsInstance(response, DummyResponse)
        self.assertEqual(self.secure_context.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(self.secure_context.check_hostname)

    def test_certificate_failure_retries_next_trusted_source(self):
        fallback_context = ssl.create_default_context()
        cert_error = ssl.SSLCertVerificationError("certificate verify failed")
        with patch.object(
            om, "ssl_context_candidates",
            return_value=[("系统证书库", self.secure_context),
                          ("certifi", fallback_context)]
        ):
            with patch.object(
                om.urllib.request, "urlopen",
                side_effect=[URLError(cert_error), DummyResponse()]
            ) as mocked:
                response = om.open_verified_https(Request("https://example.com"))
        self.assertIsInstance(response, DummyResponse)
        self.assertEqual(mocked.call_count, 2)
        self.assertIs(mocked.call_args_list[0].kwargs["context"], self.secure_context)
        self.assertIs(mocked.call_args_list[1].kwargs["context"], fallback_context)

    def test_non_certificate_network_error_does_not_retry(self):
        fallback_context = ssl.create_default_context()
        with patch.object(
            om, "ssl_context_candidates",
            return_value=[("系统证书库", self.secure_context),
                          ("certifi", fallback_context)]
        ):
            with patch.object(
                om.urllib.request, "urlopen",
                side_effect=URLError("network unavailable")
            ) as mocked:
                with self.assertRaises(URLError):
                    om.open_verified_https(Request("https://example.com"))
        self.assertEqual(mocked.call_count, 1)

    def test_insecure_context_is_rejected_before_network_request(self):
        insecure = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        insecure.check_hostname = False
        insecure.verify_mode = ssl.CERT_NONE
        with patch.object(
            om, "ssl_context_candidates",
            return_value=[("错误测试上下文", insecure)]
        ):
            with patch.object(om.urllib.request, "urlopen") as mocked:
                with self.assertRaisesRegex(RuntimeError, "未启用完整证书"):
                    om.open_verified_https(Request("https://example.com"))
        mocked.assert_not_called()

    def test_context_factory_only_returns_verified_contexts(self):
        candidates = om.ssl_context_candidates()
        self.assertTrue(candidates)
        for label, context in candidates:
            with self.subTest(source=label):
                self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
                self.assertTrue(context.check_hostname)

    def test_fetch_repo_status_accepts_git_suffix(self):
        with patch.object(om, "fetch_json_https", return_value={"full_name": "owner/repo"}) as mocked:
            result = om.fetch_repo_status("https://github.com/owner/repo.git")
        self.assertEqual(result, {"full_name": "owner/repo"})
        request = mocked.call_args.args[0]
        self.assertEqual(request.full_url, "https://api.github.com/repos/owner/repo")

    def test_wrapped_certificate_error_is_recognized(self):
        error = URLError(ssl.SSLCertVerificationError("certificate verify failed"))
        self.assertTrue(om.is_certificate_verification_error(error))
        self.assertFalse(om.is_certificate_verification_error(URLError("timeout")))


if __name__ == "__main__":
    unittest.main()
