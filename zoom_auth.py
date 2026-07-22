#!/usr/bin/env python3
"""Shared Zoom credential loading and Server-to-Server OAuth helpers."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping

ZOOM_TOKEN_URL = "https://zoom.us/oauth/token"
ZOOM_ENVIRONMENT_NAMES = (
    "ZOOM_ACCOUNT_ID",
    "ZOOM_CLIENT_ID",
    "ZOOM_CLIENT_SECRET",
)
ZOOM_SECRET_FIELDS = ("account_id", "client_id", "client_secret")


class ZoomConfigurationError(ValueError):
    """Raised when Zoom credentials are missing or invalid."""


@dataclass(frozen=True, repr=False)
class ZoomCredentials:
    account_id: str
    client_id: str
    client_secret: str


def validate_zoom_secret(data: object) -> ZoomCredentials:
    if not isinstance(data, dict):
        raise ZoomConfigurationError(
            "Zoom secret JSON must be an object / Zoom 密钥 JSON 必须是对象"
        )

    values: dict[str, str] = {}
    for field in ZOOM_SECRET_FIELDS:
        value = data.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ZoomConfigurationError(
                f'Zoom secret field "{field}" must be a non-empty string '
                f'/ Zoom 密钥字段“{field}”必须是非空字符串'
            )
        values[field] = value.strip()

    return ZoomCredentials(**values)


def read_zoom_secret(path: Path) -> tuple[ZoomCredentials, str]:
    try:
        contents = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        raise ZoomConfigurationError(
            "Zoom secret file must use UTF-8 / Zoom 密钥文件必须使用 UTF-8 编码"
        ) from error
    except OSError as error:
        raise ZoomConfigurationError(
            f"Could not read Zoom secret file / 无法读取 Zoom 密钥文件: {path}"
        ) from error

    try:
        data = json.loads(contents)
    except json.JSONDecodeError as error:
        raise ZoomConfigurationError(
            "Zoom secret file is not valid JSON / Zoom 密钥文件不是有效的 JSON"
        ) from error
    return validate_zoom_secret(data), contents


def load_zoom_credentials(
    project_root: Path,
    environ: Mapping[str, str] | None = None,
) -> ZoomCredentials:
    environment = os.environ if environ is None else environ
    values = {
        name: environment.get(name, "").strip()
        for name in ZOOM_ENVIRONMENT_NAMES
    }
    configured = [name for name in ZOOM_ENVIRONMENT_NAMES if name in environment]
    if configured and (
        len(configured) != len(ZOOM_ENVIRONMENT_NAMES)
        or any(not value for value in values.values())
    ):
        raise ZoomConfigurationError(
            "Zoom environment variables are incomplete; set all three or unset all three. "
            "File and environment credentials cannot be mixed / Zoom 环境变量不完整；"
            "请全部设置或全部取消设置，不能混用文件与环境变量"
        )
    if len(configured) == len(ZOOM_ENVIRONMENT_NAMES):
        return ZoomCredentials(
            account_id=values["ZOOM_ACCOUNT_ID"],
            client_id=values["ZOOM_CLIENT_ID"],
            client_secret=values["ZOOM_CLIENT_SECRET"],
        )

    secret_path = project_root / "config" / "zoom" / "secret.json"
    if not secret_path.is_file():
        raise ZoomConfigurationError(
            "Zoom configuration was not found. Run configure.py first "
            "/ 找不到 Zoom 配置，请先运行 configure.py"
        )
    try:
        credentials, _ = read_zoom_secret(secret_path)
    except ZoomConfigurationError as error:
        raise ZoomConfigurationError(
            f"{error}. Run configure.py after checking the file "
            "/ 请检查文件后运行 configure.py"
        ) from error
    return credentials


def request_zoom_access_token(
    credentials: ZoomCredentials,
    request_post: Callable[..., object] | None = None,
) -> str:
    if request_post is None:
        try:
            import requests
        except ImportError as error:
            raise RuntimeError(
                "Missing requests package; run the installer first "
                "/ 缺少 requests 依赖，请先运行安装脚本"
            ) from error
        request_post = requests.post

    try:
        response = request_post(
            ZOOM_TOKEN_URL,
            params={
                "grant_type": "account_credentials",
                "account_id": credentials.account_id,
            },
            auth=(credentials.client_id, credentials.client_secret),
            timeout=30,
        )
    except Exception as error:
        raise RuntimeError(
            "Could not contact Zoom authentication service / 无法连接 Zoom 认证服务"
        ) from error

    if not getattr(response, "ok", False):
        status_code = getattr(response, "status_code", "unknown")
        raise RuntimeError(
            f"Zoom authentication failed (HTTP {status_code}) / Zoom 认证失败（HTTP {status_code}）"
        )
    try:
        token = response.json().get("access_token")
    except (AttributeError, ValueError) as error:
        raise RuntimeError(
            "Zoom returned an invalid authentication response / Zoom 返回了无效的认证响应"
        ) from error
    if not isinstance(token, str) or not token:
        raise RuntimeError(
            "Zoom returned no access token / Zoom 未返回访问令牌"
        )
    return token
