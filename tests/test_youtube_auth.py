import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from youtube_auth import (
    YOUTUBE_SCOPES,
    YouTubeAuthorizationError,
    YouTubeConfigurationError,
    load_youtube_credentials,
    read_youtube_secret,
    validate_youtube_secret,
)


VALID_SECRET = {
    "installed": {
        "client_id": "test.apps.googleusercontent.com",
        "client_secret": "client-secret-value",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": ["http://localhost"],
    }
}


class FakeCredentials:
    _UNSET = object()

    def __init__(
        self,
        *,
        valid=True,
        expired=False,
        refresh_token="refresh-value",
        scopes=YOUTUBE_SCOPES,
        granted_scopes=_UNSET,
    ):
        self.valid = valid
        self.expired = expired
        self.refresh_token = refresh_token
        self.scopes = scopes
        if granted_scopes is not self._UNSET:
            self.granted_scopes = granted_scopes
        self.refresh_error = None

    def refresh(self, _request):
        if self.refresh_error:
            raise self.refresh_error
        self.valid = True
        self.expired = False

    def to_json(self):
        return json.dumps(
            {
                "token": "access-token-value",
                "refresh_token": self.refresh_token,
                "scopes": YOUTUBE_SCOPES,
            }
        )


class FakeFlow:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.kwargs = None

    def run_local_server(self, **kwargs):
        self.kwargs = kwargs
        if self.error:
            raise self.error
        return self.result


class YouTubeSecretValidationTests(unittest.TestCase):
    def test_valid_desktop_client_json_is_loaded(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "youtube_secret.json"
            contents = json.dumps(VALID_SECRET)
            path.write_text(contents, encoding="utf-8")

            self.assertEqual(read_youtube_secret(path), contents)

    def test_installed_client_and_required_fields_are_enforced(self):
        with self.assertRaises(YouTubeConfigurationError):
            validate_youtube_secret({"web": VALID_SECRET["installed"]})

        for field in ("client_id", "client_secret", "auth_uri", "token_uri"):
            with self.subTest(field=field):
                invalid = json.loads(json.dumps(VALID_SECRET))
                invalid["installed"][field] = " "
                with self.assertRaises(YouTubeConfigurationError):
                    validate_youtube_secret(invalid)

    def test_non_utf8_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "youtube_secret.json"
            path.write_bytes(b"\xff\xfe\x00")

            with self.assertRaisesRegex(YouTubeConfigurationError, "UTF-8"):
                read_youtube_secret(path)

    def test_invalid_json_does_not_echo_secret_contents(self):
        sensitive = "do-not-echo-client-secret"
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "youtube_secret.json"
            path.write_text(f'{{"client_secret": "{sensitive}"', encoding="utf-8")

            with self.assertRaises(YouTubeConfigurationError) as context:
                read_youtube_secret(path)

        self.assertNotIn(sensitive, str(context.exception))


class YouTubeAuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.secret = self.root / "secret.json"
        self.token = self.root / "token.json"
        self.secret.write_text(json.dumps(VALID_SECRET), encoding="utf-8")

    def tearDown(self):
        self.temporary_directory.cleanup()

    @staticmethod
    def unused_loader(*_args):
        raise AssertionError("token loader should not be called")

    @staticmethod
    def request_factory():
        return object()

    def test_oauth_success_saves_private_utf8_token_without_api_service(self):
        credentials = FakeCredentials()
        flow = FakeFlow(result=credentials)

        real_import = __import__

        def reject_api_service_import(name, *args, **kwargs):
            if name.startswith("googleapiclient"):
                raise AssertionError("YouTube Data API service must not be imported")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=reject_api_service_import):
            result = load_youtube_credentials(
                self.secret,
                self.token,
                interactive=True,
                credentials_loader=self.unused_loader,
                request_factory=self.request_factory,
                flow_factory=lambda path, scopes: flow,
            )

        self.assertEqual(result.status, "authorized")
        self.assertTrue(self.token.is_file())
        self.assertEqual(json.loads(self.token.read_text(encoding="utf-8"))["token"], "access-token-value")
        self.assertEqual(flow.kwargs["port"], 0)
        self.assertTrue(flow.kwargs["open_browser"])
        self.assertEqual(flow.kwargs["timeout_seconds"], 300)
        if os.name == "posix":
            self.assertEqual(self.token.stat().st_mode & 0o777, 0o600)

    def test_oauth_without_confirmable_upload_scope_is_rejected(self):
        credentials = FakeCredentials(scopes=None)
        del credentials.scopes
        flow = FakeFlow(result=credentials)

        with self.assertRaisesRegex(YouTubeAuthorizationError, "youtube.upload"):
            load_youtube_credentials(
                self.secret,
                self.token,
                interactive=True,
                credentials_loader=self.unused_loader,
                request_factory=self.request_factory,
                flow_factory=lambda path, scopes: flow,
            )

        self.assertFalse(self.token.exists())

    def test_existing_valid_token_is_reused_without_browser(self):
        self.token.write_text("{}", encoding="utf-8")
        credentials = FakeCredentials()
        flow_called = False

        def flow_factory(*_args):
            nonlocal flow_called
            flow_called = True
            raise AssertionError("browser flow must not start")

        result = load_youtube_credentials(
            self.secret,
            self.token,
            interactive=True,
            credentials_loader=lambda *_args: credentials,
            request_factory=self.request_factory,
            flow_factory=flow_factory,
        )

        self.assertEqual(result.status, "existing")
        self.assertFalse(flow_called)

    def test_actual_granted_scopes_override_requested_scopes(self):
        credentials = FakeCredentials(
            scopes=YOUTUBE_SCOPES,
            granted_scopes=["unrelated.scope"],
        )
        flow = FakeFlow(result=credentials)

        with self.assertRaisesRegex(YouTubeAuthorizationError, "youtube.upload"):
            load_youtube_credentials(
                self.secret,
                self.token,
                interactive=True,
                credentials_loader=self.unused_loader,
                request_factory=self.request_factory,
                flow_factory=lambda path, scopes: flow,
            )

        self.assertFalse(self.token.exists())

    def test_oauth_failure_hides_underlying_token_and_secret(self):
        sensitive_token = "do-not-print-access-token"
        sensitive_secret = "do-not-print-client-secret"
        flow = FakeFlow(error=RuntimeError(f"{sensitive_token} {sensitive_secret}"))

        with self.assertRaises(YouTubeAuthorizationError) as context:
            load_youtube_credentials(
                self.secret,
                self.token,
                interactive=True,
                credentials_loader=self.unused_loader,
                request_factory=self.request_factory,
                flow_factory=lambda path, scopes: flow,
            )

        self.assertNotIn(sensitive_token, str(context.exception))
        self.assertNotIn(sensitive_secret, str(context.exception))
        self.assertFalse(self.token.exists())

    def test_oauth_keyboard_interrupt_is_reported_as_cancellation(self):
        flow = FakeFlow(error=KeyboardInterrupt())

        with self.assertRaises(KeyboardInterrupt):
            load_youtube_credentials(
                self.secret,
                self.token,
                interactive=True,
                credentials_loader=self.unused_loader,
                request_factory=self.request_factory,
                flow_factory=lambda path, scopes: flow,
            )

    def test_runtime_without_token_never_starts_browser(self):
        flow_called = False

        def flow_factory(*_args):
            nonlocal flow_called
            flow_called = True
            raise AssertionError("browser flow must not start")

        with self.assertRaisesRegex(YouTubeAuthorizationError, "configure.py"):
            load_youtube_credentials(
                self.secret,
                self.token,
                interactive=False,
                credentials_loader=self.unused_loader,
                request_factory=self.request_factory,
                flow_factory=flow_factory,
            )

        self.assertFalse(flow_called)

    def test_runtime_refresh_failure_requests_reconfiguration_without_browser(self):
        self.token.write_text("{}", encoding="utf-8")
        credentials = FakeCredentials(valid=False, expired=True)
        credentials.refresh_error = RuntimeError("sensitive-refresh-response")
        flow_called = False

        def flow_factory(*_args):
            nonlocal flow_called
            flow_called = True
            raise AssertionError("browser flow must not start")

        with self.assertRaises(YouTubeAuthorizationError) as context:
            load_youtube_credentials(
                self.secret,
                self.token,
                interactive=False,
                credentials_loader=lambda *_args: credentials,
                request_factory=self.request_factory,
                flow_factory=flow_factory,
            )

        self.assertIn("configure.py", str(context.exception))
        self.assertNotIn("sensitive-refresh-response", str(context.exception))
        self.assertFalse(flow_called)

    def test_refresh_succeeds_without_browser_and_safely_rewrites_token(self):
        self.token.write_text("{}", encoding="utf-8")
        credentials = FakeCredentials(valid=False, expired=True)
        flow_called = False

        def flow_factory(*_args):
            nonlocal flow_called
            flow_called = True
            raise AssertionError("browser flow must not start")

        result = load_youtube_credentials(
            self.secret,
            self.token,
            interactive=False,
            credentials_loader=lambda *_args: credentials,
            request_factory=self.request_factory,
            flow_factory=flow_factory,
        )

        self.assertEqual(result.status, "refreshed")
        self.assertEqual(json.loads(self.token.read_text(encoding="utf-8"))["token"], "access-token-value")
        self.assertFalse(flow_called)
        if os.name == "posix":
            self.assertEqual(self.token.stat().st_mode & 0o777, 0o600)
if __name__ == "__main__":
    unittest.main()
