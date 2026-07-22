import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import patch

from configure import (
    YOUTUBE_TEMP_PREFIX,
    ZOOM_TEMP_PREFIX,
    configure_youtube,
    configure_zoom,
    main,
    move_secret_file,
)
from youtube_auth import YouTubeAuthorizationError, YouTubeCredentialsResult


VALID_SECRET = {
    "account_id": "test-account",
    "client_id": "test-client",
    "client_secret": "test-secret",
}
VALID_YOUTUBE_SECRET = {
    "installed": {
        "client_id": "test.apps.googleusercontent.com",
        "client_secret": "youtube-client-secret",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": ["http://localhost"],
    }
}


class ConfigureZoomTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.project_root = Path(self.temporary_directory.name)
        self.source = self.project_root / "zoom_secret.json"
        self.target = self.project_root / "config" / "zoom" / "secret.json"
        self.source.write_text(json.dumps(VALID_SECRET), encoding="utf-8")

    def tearDown(self):
        self.temporary_directory.cleanup()

    def temporary_secret_files(self):
        if not self.target.parent.exists():
            return []
        return list(self.target.parent.glob(f"{ZOOM_TEMP_PREFIX}*"))

    def test_successful_validation_moves_only_zoom_secret(self):
        youtube_secret = self.project_root / "youtube_secret.json"
        youtube_secret.write_text('{"untouched": true}', encoding="utf-8")

        result = configure_zoom(
            self.project_root,
            input_func=lambda _: "y",
            token_fetcher=lambda credentials: "temporary-access-token",
        )

        self.assertEqual(result, 0)
        self.assertFalse(self.source.exists())
        self.assertEqual(json.loads(self.target.read_text(encoding="utf-8")), VALID_SECRET)
        self.assertNotIn("temporary-access-token", self.target.read_text(encoding="utf-8"))
        self.assertEqual(youtube_secret.read_text(encoding="utf-8"), '{"untouched": true}')
        self.assertEqual(self.temporary_secret_files(), [])

    def test_failed_validation_keeps_input_file(self):
        def reject_credentials(_credentials):
            raise RuntimeError("authentication failed")

        result = configure_zoom(
            self.project_root,
            input_func=lambda _: "y",
            token_fetcher=reject_credentials,
        )

        self.assertEqual(result, 1)
        self.assertTrue(self.source.exists())
        self.assertFalse(self.target.exists())
        self.assertEqual(self.temporary_secret_files(), [])

    def test_existing_target_is_never_overwritten(self):
        self.target.parent.mkdir(parents=True)
        self.target.write_text('{"existing": true}', encoding="utf-8")
        token_fetcher_called = False

        def token_fetcher(_credentials):
            nonlocal token_fetcher_called
            token_fetcher_called = True
            return "temporary-access-token"

        result = configure_zoom(
            self.project_root,
            input_func=lambda _: "y",
            token_fetcher=token_fetcher,
        )

        self.assertEqual(result, 0)
        self.assertTrue(self.source.exists())
        self.assertEqual(self.target.read_text(encoding="utf-8"), '{"existing": true}')
        self.assertFalse(token_fetcher_called)

    def test_keyboard_interrupt_while_writing_cleans_temporary_file(self):
        with patch("secure_files._write_utf8", side_effect=KeyboardInterrupt):
            result = configure_zoom(
                self.project_root,
                input_func=lambda _: "y",
                token_fetcher=lambda _credentials: "temporary-access-token",
            )

        self.assertEqual(result, 130)
        self.assertTrue(self.source.exists())
        self.assertFalse(self.target.exists())
        self.assertEqual(self.temporary_secret_files(), [])

    def test_keyboard_interrupt_during_fsync_cleans_temporary_file(self):
        with patch("secure_files.os.fsync", side_effect=KeyboardInterrupt):
            result = configure_zoom(
                self.project_root,
                input_func=lambda _: "y",
                token_fetcher=lambda _credentials: "temporary-access-token",
            )

        self.assertEqual(result, 130)
        self.assertTrue(self.source.exists())
        self.assertFalse(self.target.exists())
        self.assertEqual(self.temporary_secret_files(), [])

    def test_competing_target_is_not_overwritten(self):
        existing_contents = '{"existing": true}'

        def competing_publish(_temporary_path, target):
            Path(target).write_text(existing_contents, encoding="utf-8")
            raise FileExistsError

        with patch("secure_files.os.link", side_effect=competing_publish):
            result = configure_zoom(
                self.project_root,
                input_func=lambda _: "y",
                token_fetcher=lambda _credentials: "temporary-access-token",
            )

        self.assertEqual(result, 1)
        self.assertTrue(self.source.exists())
        self.assertEqual(self.target.read_text(encoding="utf-8"), existing_contents)
        self.assertEqual(self.temporary_secret_files(), [])

    def test_interrupt_after_publish_keeps_both_files_and_reports_state(self):
        real_link = os.link

        def publish_then_interrupt(temporary_path, target):
            real_link(temporary_path, target)
            raise KeyboardInterrupt

        error_output = io.StringIO()
        with patch("secure_files.os.link", side_effect=publish_then_interrupt):
            with redirect_stderr(error_output):
                result = configure_zoom(
                    self.project_root,
                    input_func=lambda _: "y",
                    token_fetcher=lambda _credentials: "temporary-access-token",
                )

        self.assertEqual(result, 130)
        self.assertTrue(self.source.exists())
        self.assertTrue(self.target.exists())
        self.assertEqual(self.temporary_secret_files(), [])
        self.assertIn("Both files were kept", error_output.getvalue())


class ConfigureYouTubeTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.project_root = Path(self.temporary_directory.name)
        self.source = self.project_root / "youtube_secret.json"
        self.target = self.project_root / "config" / "youtube" / "secret.json"
        self.token = self.project_root / "config" / "youtube" / "token.json"
        self.source.write_text(json.dumps(VALID_YOUTUBE_SECRET), encoding="utf-8")
        self.credentials = object()

    def tearDown(self):
        self.temporary_directory.cleanup()

    def temporary_secret_files(self):
        if not self.target.parent.exists():
            return []
        return list(self.target.parent.glob(f"{YOUTUBE_TEMP_PREFIX}*"))

    def authorize(self, secret_path, token_path, *, interactive):
        self.assertEqual(secret_path, self.target)
        self.assertEqual(token_path, self.token)
        self.assertTrue(interactive)
        return YouTubeCredentialsResult(self.credentials, "authorized")

    def test_successful_setup_moves_exact_file_and_verifies_api(self):
        unrelated = self.project_root / "other.json"
        unrelated.write_text('{"leave": true}', encoding="utf-8")
        verified = []

        result = configure_youtube(
            self.project_root,
            input_func=lambda _: "y",
            credentials_loader=self.authorize,
            verifier=verified.append,
        )

        self.assertEqual(result, 0)
        self.assertFalse(self.source.exists())
        self.assertEqual(
            json.loads(self.target.read_text(encoding="utf-8")),
            VALID_YOUTUBE_SECRET,
        )
        self.assertEqual(unrelated.read_text(encoding="utf-8"), '{"leave": true}')
        self.assertEqual(verified, [self.credentials])
        self.assertEqual(self.temporary_secret_files(), [])
        if os.name == "posix":
            self.assertEqual(self.target.stat().st_mode & 0o777, 0o600)

    def test_existing_target_is_not_overwritten_and_source_is_kept(self):
        existing = dict(VALID_YOUTUBE_SECRET)
        existing["installed"] = dict(existing["installed"], client_id="existing-client")
        self.target.parent.mkdir(parents=True)
        self.target.write_text(json.dumps(existing), encoding="utf-8")

        result = configure_youtube(
            self.project_root,
            input_func=lambda _: "y",
            credentials_loader=self.authorize,
            verifier=lambda _: None,
        )

        self.assertEqual(result, 0)
        self.assertTrue(self.source.exists())
        self.assertEqual(json.loads(self.target.read_text(encoding="utf-8")), existing)

    def test_keyboard_interrupt_during_fsync_cleans_temporary_file(self):
        with patch("secure_files.os.fsync", side_effect=KeyboardInterrupt):
            result = configure_youtube(
                self.project_root,
                input_func=lambda _: "y",
                credentials_loader=self.authorize,
                verifier=lambda _: None,
            )

        self.assertEqual(result, 130)
        self.assertTrue(self.source.exists())
        self.assertFalse(self.target.exists())
        self.assertEqual(self.temporary_secret_files(), [])

    def test_authorization_failure_keeps_client_and_hides_sensitive_details(self):
        sensitive_secret = "never-print-client-secret"
        sensitive_token = "never-print-token"

        def fail_authorization(*_args, **_kwargs):
            cause = RuntimeError(f"{sensitive_secret} {sensitive_token}")
            raise YouTubeAuthorizationError(
                "YouTube authorization was cancelled or failed / YouTube 授权已取消或失败"
            ) from cause

        error_output = io.StringIO()
        with redirect_stderr(error_output):
            result = configure_youtube(
                self.project_root,
                input_func=lambda _: "y",
                credentials_loader=fail_authorization,
                verifier=lambda _: None,
            )

        self.assertEqual(result, 1)
        self.assertFalse(self.source.exists())
        self.assertTrue(self.target.exists())
        self.assertNotIn(sensitive_secret, error_output.getvalue())
        self.assertNotIn(sensitive_token, error_output.getvalue())


class UnifiedConfigureTests(unittest.TestCase):
    def test_one_platform_error_does_not_block_the_other(self):
        project_root = Path("/temporary-project-root")
        with patch("configure.configure_zoom", return_value=1) as configure_zoom_mock:
            with patch("configure.configure_youtube", return_value=0) as configure_youtube_mock:
                result = main(project_root)

        self.assertEqual(result, 1)
        configure_zoom_mock.assert_called_once_with(project_root)
        configure_youtube_mock.assert_called_once_with(project_root)


if __name__ == "__main__":
    unittest.main()
