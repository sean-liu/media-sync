import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import patch

from configure import (
    ZOOM_TEMP_PREFIX,
    configure_zoom,
    move_secret_file,
)


VALID_SECRET = {
    "account_id": "test-account",
    "client_id": "test-client",
    "client_secret": "test-secret",
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

        self.assertEqual(result, 1)
        self.assertTrue(self.source.exists())
        self.assertEqual(self.target.read_text(encoding="utf-8"), '{"existing": true}')
        self.assertFalse(token_fetcher_called)

    def test_keyboard_interrupt_while_writing_cleans_temporary_file(self):
        with patch("configure._write_secret_contents", side_effect=KeyboardInterrupt):
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
        with patch("configure.os.fsync", side_effect=KeyboardInterrupt):
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

        with patch("configure.os.link", side_effect=competing_publish):
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
        with patch("configure.os.link", side_effect=publish_then_interrupt):
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


if __name__ == "__main__":
    unittest.main()
