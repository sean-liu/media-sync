import json
import tempfile
import unittest
from pathlib import Path

from zoom_auth import (
    ZoomConfigurationError,
    load_zoom_credentials,
    read_zoom_secret,
    validate_zoom_secret,
)


VALID_SECRET = {
    "account_id": "test-account",
    "client_id": "test-client",
    "client_secret": "test-secret",
}


class ZoomSecretValidationTests(unittest.TestCase):
    def test_valid_secret_is_loaded(self):
        credentials = validate_zoom_secret(VALID_SECRET)

        self.assertEqual(credentials.account_id, "test-account")
        self.assertEqual(credentials.client_id, "test-client")
        self.assertEqual(credentials.client_secret, "test-secret")

    def test_secret_must_be_an_object(self):
        with self.assertRaises(ZoomConfigurationError):
            validate_zoom_secret([])

    def test_required_fields_must_be_non_empty_strings(self):
        for field in VALID_SECRET:
            with self.subTest(field=field):
                invalid = dict(VALID_SECRET)
                invalid[field] = " "
                with self.assertRaises(ZoomConfigurationError):
                    validate_zoom_secret(invalid)

    def test_malformed_json_is_rejected_without_echoing_contents(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            secret_path = Path(temporary_directory) / "zoom_secret.json"
            secret_path.write_text('{"client_secret": "do-not-echo"', encoding="utf-8")

            with self.assertRaises(ZoomConfigurationError) as context:
                read_zoom_secret(secret_path)

        self.assertNotIn("do-not-echo", str(context.exception))


class ZoomCredentialPriorityTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.project_root = Path(self.temporary_directory.name)
        secret_path = self.project_root / "config" / "zoom" / "secret.json"
        secret_path.parent.mkdir(parents=True)
        secret_path.write_text(json.dumps(VALID_SECRET), encoding="utf-8")

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_complete_environment_overrides_file(self):
        environment = {
            "ZOOM_ACCOUNT_ID": "environment-account",
            "ZOOM_CLIENT_ID": "environment-client",
            "ZOOM_CLIENT_SECRET": "environment-secret",
        }

        credentials = load_zoom_credentials(self.project_root, environment)

        self.assertEqual(credentials.account_id, "environment-account")
        self.assertEqual(credentials.client_secret, "environment-secret")

    def test_partial_environment_is_rejected_instead_of_mixed_with_file(self):
        with self.assertRaisesRegex(ZoomConfigurationError, "incomplete"):
            load_zoom_credentials(
                self.project_root,
                {"ZOOM_ACCOUNT_ID": "environment-account"},
            )

    def test_empty_environment_values_are_rejected_instead_of_using_file(self):
        with self.assertRaisesRegex(ZoomConfigurationError, "incomplete"):
            load_zoom_credentials(
                self.project_root,
                {
                    "ZOOM_ACCOUNT_ID": "",
                    "ZOOM_CLIENT_ID": "",
                    "ZOOM_CLIENT_SECRET": "",
                },
            )

    def test_file_is_used_when_environment_is_empty(self):
        credentials = load_zoom_credentials(self.project_root, {})

        self.assertEqual(credentials.account_id, "test-account")
        self.assertEqual(credentials.client_secret, "test-secret")


if __name__ == "__main__":
    unittest.main()
