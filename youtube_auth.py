"""Shared YouTube OAuth validation, authorization, and token helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from secure_files import publish_private_text

YOUTUBE_SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
YOUTUBE_SECRET_FIELDS = ("client_id", "client_secret", "auth_uri", "token_uri")
YOUTUBE_TOKEN_TEMP_PREFIX = ".youtube-token-"


class YouTubeConfigurationError(ValueError):
    """Raised when the local YouTube OAuth client file is invalid."""


class YouTubeAuthorizationError(RuntimeError):
    """Raised when YouTube authorization cannot be loaded or completed."""


@dataclass(frozen=True, repr=False)
class YouTubeCredentialsResult:
    credentials: Any
    status: str
    permissions_set: bool = True


def validate_youtube_secret(data: object) -> None:
    if not isinstance(data, dict) or not isinstance(data.get("installed"), dict):
        raise YouTubeConfigurationError(
            "YouTube OAuth JSON must contain an installed desktop client "
            "/ YouTube OAuth JSON 必须包含 installed 桌面客户端"
        )

    installed = data["installed"]
    for field in YOUTUBE_SECRET_FIELDS:
        value = installed.get(field)
        if not isinstance(value, str) or not value.strip():
            raise YouTubeConfigurationError(
                f'YouTube OAuth field "installed.{field}" must be a non-empty string '
                f'/ YouTube OAuth 字段“installed.{field}”必须是非空字符串'
            )

    redirect_uris = installed.get("redirect_uris")
    if (
        not isinstance(redirect_uris, list)
        or not redirect_uris
        or any(not isinstance(uri, str) or not uri.strip() for uri in redirect_uris)
    ):
        raise YouTubeConfigurationError(
            'YouTube OAuth field "installed.redirect_uris" must contain a non-empty URI '
            '/ YouTube OAuth 字段“installed.redirect_uris”必须包含非空 URI'
        )


def read_youtube_secret(path: Path) -> str:
    try:
        contents = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        raise YouTubeConfigurationError(
            "YouTube OAuth file must use UTF-8 / YouTube OAuth 文件必须使用 UTF-8 编码"
        ) from error
    except OSError as error:
        raise YouTubeConfigurationError(
            "Could not read the YouTube OAuth file / 无法读取 YouTube OAuth 文件"
        ) from error

    try:
        data = json.loads(contents)
    except json.JSONDecodeError as error:
        raise YouTubeConfigurationError(
            "YouTube OAuth file is not valid JSON / YouTube OAuth 文件不是有效 JSON"
        ) from error
    validate_youtube_secret(data)
    return contents


def _google_oauth_dependencies() -> tuple[Callable[..., Any], Callable[[], Any], Callable[..., Any]]:
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError as error:
        raise YouTubeAuthorizationError(
            "Missing Google OAuth packages; run the installer first "
            "/ 缺少 Google OAuth 依赖，请先运行安装脚本"
        ) from error
    return Credentials.from_authorized_user_file, Request, InstalledAppFlow.from_client_secrets_file


def _save_credentials(
    token_path: Path,
    credentials: Any,
    token_writer: Callable[..., bool],
) -> bool:
    try:
        contents = credentials.to_json()
        if not isinstance(contents, str) or not contents:
            raise ValueError
        return token_writer(
            token_path,
            contents,
            temporary_prefix=YOUTUBE_TOKEN_TEMP_PREFIX,
            replace=True,
        )
    except (OSError, TypeError, ValueError) as error:
        raise YouTubeAuthorizationError(
            "Could not safely save the YouTube token / 无法安全保存 YouTube 令牌"
        ) from error


def _credentials_are_valid(credentials: Any) -> bool:
    if credentials is None:
        return False

    try:
        if not getattr(credentials, "valid", False):
            return False

        required_scopes = set(YOUTUBE_SCOPES)
        granted_scopes = _normalize_scopes(
            getattr(credentials, "granted_scopes", None)
        )
        if granted_scopes:
            return required_scopes.issubset(granted_scopes)

        configured_scopes = _normalize_scopes(getattr(credentials, "scopes", None))
        if configured_scopes:
            return required_scopes.issubset(configured_scopes)

        has_scopes = getattr(credentials, "has_scopes", None)
        if not callable(has_scopes):
            return False
        return bool(has_scopes(YOUTUBE_SCOPES))
    except Exception:
        return False


def _normalize_scopes(scopes: Any) -> set[str]:
    if isinstance(scopes, str):
        return set(scopes.split())
    try:
        return {scope for scope in scopes if isinstance(scope, str)}
    except TypeError:
        return set()


def load_youtube_credentials(
    secret_path: Path,
    token_path: Path,
    *,
    interactive: bool,
    credentials_loader: Callable[..., Any] | None = None,
    request_factory: Callable[[], Any] | None = None,
    flow_factory: Callable[..., Any] | None = None,
    token_writer: Callable[..., bool] = publish_private_text,
) -> YouTubeCredentialsResult:
    if credentials_loader is None or request_factory is None or flow_factory is None:
        default_loader, default_request, default_flow = _google_oauth_dependencies()
        credentials_loader = credentials_loader or default_loader
        request_factory = request_factory or default_request
        flow_factory = flow_factory or default_flow

    credentials = None
    refresh_failed = False
    if token_path.is_file():
        try:
            credentials = credentials_loader(str(token_path))
        except Exception:
            credentials = None

    if _credentials_are_valid(credentials):
        return YouTubeCredentialsResult(credentials, "existing")

    if (
        credentials is not None
        and getattr(credentials, "expired", False)
        and getattr(credentials, "refresh_token", None)
    ):
        try:
            credentials.refresh(request_factory())
        except Exception:
            credentials = None
            refresh_failed = True
        else:
            if _credentials_are_valid(credentials):
                permissions_set = _save_credentials(token_path, credentials, token_writer)
                return YouTubeCredentialsResult(credentials, "refreshed", permissions_set)

    if not interactive:
        if refresh_failed:
            raise YouTubeAuthorizationError(
                "YouTube token refresh failed. Run configure.py again "
                "/ YouTube 令牌刷新失败，请重新运行 configure.py"
            )
        raise YouTubeAuthorizationError(
            "No valid YouTube token was found. Run configure.py first "
            "/ 找不到有效的 YouTube 令牌，请先运行 configure.py"
        )

    read_youtube_secret(secret_path)
    try:
        flow = flow_factory(str(secret_path), YOUTUBE_SCOPES)
        credentials = flow.run_local_server(
            port=0,
            open_browser=True,
            timeout_seconds=300,
            prompt="consent",
            access_type="offline",
        )
    except Exception as error:
        raise YouTubeAuthorizationError(
            "YouTube authorization was cancelled or failed. Check the browser, callback, "
            "and OAuth test-user settings, then retry / YouTube 授权已取消或失败；"
            "请检查浏览器、回调及 OAuth 测试用户设置后重试"
        ) from error

    if credentials is None or not getattr(credentials, "valid", False):
        raise YouTubeAuthorizationError(
            "YouTube authorization did not return valid credentials; retry configure.py "
            "/ YouTube 授权未返回有效凭据，请重新运行 configure.py"
        )
    if not _credentials_are_valid(credentials):
        raise YouTubeAuthorizationError(
            "YouTube authorization did not confirm the required youtube.upload permission; "
            "run configure.py again / YouTube 授权未能确认所需的 youtube.upload 权限，"
            "请重新运行 configure.py"
        )
    permissions_set = _save_credentials(token_path, credentials, token_writer)
    return YouTubeCredentialsResult(credentials, "authorized", permissions_set)
