import argparse
import io
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import patch

import zoom_to_youtube
from youtube_auth import YouTubeAuthorizationError


class UploadAuthorizationTests(unittest.TestCase):
    def test_default_paths_use_layered_youtube_directory(self):
        self.assertEqual(
            zoom_to_youtube.DEFAULT_CLIENT_SECRETS,
            "config/youtube/secret.json",
        )
        self.assertEqual(
            zoom_to_youtube.DEFAULT_YOUTUBE_TOKEN,
            "config/youtube/token.json",
        )

    def test_upload_auth_is_noninteractive_and_points_to_configure(self):
        error = YouTubeAuthorizationError(
            "No valid YouTube token was found. Run configure.py first "
            "/ 找不到有效的 YouTube 令牌，请先运行 configure.py"
        )
        with patch("zoom_to_youtube.load_youtube_credentials", side_effect=error) as loader:
            with self.assertRaisesRegex(YouTubeAuthorizationError, "configure.py"):
                zoom_to_youtube.youtube_credentials(
                    Path("config/youtube/secret.json"),
                    Path("config/youtube/token.json"),
                )

        loader.assert_called_once_with(
            Path("config/youtube/secret.json"),
            Path("config/youtube/token.json"),
            interactive=False,
        )

    def test_main_checks_youtube_token_before_prompting_or_downloading(self):
        args = argparse.Namespace()
        error = YouTubeAuthorizationError(
            "No valid YouTube token was found. Run configure.py first "
            "/ 找不到有效的 YouTube 令牌，请先运行 configure.py"
        )
        with patch("zoom_to_youtube.parse_args", return_value=args):
            with patch("zoom_to_youtube.load_dependencies"):
                with patch("zoom_to_youtube.youtube_credentials", side_effect=error):
                    with patch("zoom_to_youtube.prompt") as prompt:
                        with redirect_stderr(io.StringIO()):
                            result = zoom_to_youtube.main()

        self.assertEqual(result, 1)
        prompt.assert_not_called()


if __name__ == "__main__":
    unittest.main()
