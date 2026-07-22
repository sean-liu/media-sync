import json
import tempfile
import unittest
from pathlib import Path

from configure import configure_zoom


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


if __name__ == "__main__":
    unittest.main()
