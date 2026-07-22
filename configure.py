#!/usr/bin/env python3
"""Configure local Zoom and YouTube credentials from exact root filenames."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Callable

from secure_files import move_private_text
from youtube_auth import (
    YouTubeAuthorizationError,
    YouTubeConfigurationError,
    YouTubeCredentialsResult,
    load_youtube_credentials,
    read_youtube_secret,
    verify_youtube_credentials,
)
from zoom_auth import (
    ZoomConfigurationError,
    ZoomCredentials,
    read_zoom_secret,
    request_zoom_access_token,
)

PROJECT_ROOT = Path(__file__).resolve().parent
ZOOM_INPUT = "zoom_secret.json"
ZOOM_TARGET = Path("config") / "zoom" / "secret.json"
ZOOM_TEMP_PREFIX = ".zoom-secret-"
YOUTUBE_INPUT = "youtube_secret.json"
YOUTUBE_TARGET = Path("config") / "youtube" / "secret.json"
YOUTUBE_TOKEN = Path("config") / "youtube" / "token.json"
YOUTUBE_TEMP_PREFIX = ".youtube-secret-"


def confirmed(input_func: Callable[[str], str]) -> bool:
    answer = input_func(
        "Validate and move this file? / 是否验证并移动此文件？(y/N): "
    ).strip().lower()
    return answer in ("y", "yes", "是")


def move_secret_file(
    source: Path,
    target: Path,
    contents: str,
    temporary_prefix: str = ZOOM_TEMP_PREFIX,
) -> bool:
    return move_private_text(
        source,
        target,
        contents,
        temporary_prefix=temporary_prefix,
    )


def _report_move_interrupt(platform: str, source: Path, target: Path) -> None:
    if target.exists() and source.exists():
        print(
            f"Setup was interrupted after a final {platform} configuration appeared. "
            "Both files were kept; inspect them before removing the root input "
            f"/ 最终 {platform} 配置出现后设置被中断；两个文件均已保留，"
            "删除根目录输入文件前请先检查",
            file=sys.stderr,
        )
    elif target.exists():
        print(
            f"Setup was interrupted after the final {platform} configuration was saved. "
            "The root input is already gone; check the final file before retrying "
            f"/ 最终 {platform} 配置保存后设置被中断；根目录输入文件已不存在，"
            "重试前请检查最终文件",
            file=sys.stderr,
        )
    else:
        print(
            f"Setup was interrupted before the final {platform} configuration was published. "
            "The input file was kept and temporary files were cleaned up "
            f"/ 最终 {platform} 配置发布前设置被中断；输入文件已保留，临时文件已清理",
            file=sys.stderr,
        )


def configure_zoom(
    project_root: Path,
    input_func: Callable[[str], str] = input,
    token_fetcher: Callable[[ZoomCredentials], str] = request_zoom_access_token,
) -> int:
    source = project_root / ZOOM_INPUT
    target = project_root / ZOOM_TARGET

    if target.exists():
        print(
            "Zoom is already configured; the existing file was not overwritten "
            "/ Zoom 已配置，未覆盖现有文件"
        )
        if source.exists():
            print(
                f"The root {ZOOM_INPUT} was kept / 根目录 {ZOOM_INPUT} 已保留"
            )
        return 0
    if not source.is_file():
        print(
            f"No {ZOOM_INPUT} found; skipping Zoom setup "
            f"/ 未找到 {ZOOM_INPUT}，跳过 Zoom 配置"
        )
        return 0

    try:
        credentials, contents = read_zoom_secret(source)
    except ZoomConfigurationError as error:
        print(f"Error / 错误: {error}", file=sys.stderr)
        return 1

    print(
        "Valid Zoom fields found (values hidden): account_id, client_id, client_secret "
        "/ 已找到有效 Zoom 字段（值已隐藏）：account_id、client_id、client_secret"
    )
    print(f"The file will be moved to {ZOOM_TARGET} / 文件将移动到 {ZOOM_TARGET}")
    if not confirmed(input_func):
        print("Cancelled; no files were changed / 已取消，未更改任何文件")
        return 0

    print("Validating with Zoom / 正在通过 Zoom 验证凭据...")
    try:
        access_token = token_fetcher(credentials)
    except Exception:
        print(
            "Zoom credential validation failed; the input file was kept "
            "/ Zoom 凭据验证失败，输入文件已保留",
            file=sys.stderr,
        )
        return 1
    del access_token
    print("Zoom credential validation succeeded / Zoom 凭据验证成功")

    try:
        permissions_set = move_secret_file(source, target, contents)
    except KeyboardInterrupt:
        _report_move_interrupt("Zoom", source, target)
        return 130
    except FileExistsError:
        print(
            "Zoom configuration appeared during setup; neither file was overwritten "
            "/ 配置过程中出现了已有 Zoom 配置；未覆盖任何文件",
            file=sys.stderr,
        )
        return 1
    except OSError:
        print(
            "Could not complete the Zoom secret move; check the root input and config/zoom/ "
            "for final or temporary files / 无法完成 Zoom 密钥移动；请检查根目录输入文件"
            "以及 config/zoom/ 中的最终文件或临时文件",
            file=sys.stderr,
        )
        return 1

    print(f"Zoom configuration saved at {ZOOM_TARGET} / Zoom 配置已保存到 {ZOOM_TARGET}")
    if not permissions_set:
        print(
            "Warning: could not restrict file permissions; protect this file manually "
            "/ 警告：无法限制文件权限，请手动保护此文件",
            file=sys.stderr,
        )
    return 0


def configure_youtube(
    project_root: Path,
    input_func: Callable[[str], str] = input,
    credentials_loader: Callable[..., YouTubeCredentialsResult] = load_youtube_credentials,
    verifier: Callable[[Any], None] = verify_youtube_credentials,
) -> int:
    source = project_root / YOUTUBE_INPUT
    target = project_root / YOUTUBE_TARGET
    token_path = project_root / YOUTUBE_TOKEN
    permissions_set = True

    if target.exists():
        print(
            "YouTube OAuth client is already saved; the existing file was not overwritten "
            "/ YouTube OAuth 客户端已保存，未覆盖现有文件"
        )
        if source.exists():
            print(
                f"The root {YOUTUBE_INPUT} was kept / 根目录 {YOUTUBE_INPUT} 已保留"
            )
        try:
            read_youtube_secret(target)
        except YouTubeConfigurationError as error:
            print(f"Error / 错误: {error}", file=sys.stderr)
            return 1
    else:
        if not source.is_file():
            print(
                f"No {YOUTUBE_INPUT} found; skipping YouTube setup "
                f"/ 未找到 {YOUTUBE_INPUT}，跳过 YouTube 配置"
            )
            return 0
        try:
            contents = read_youtube_secret(source)
        except YouTubeConfigurationError as error:
            print(f"Error / 错误: {error}", file=sys.stderr)
            return 1

        print(
            "Valid Google Desktop OAuth fields found (values hidden): installed client "
            "/ 已找到有效 Google 桌面 OAuth 字段（值已隐藏）：installed 客户端"
        )
        print(f"The file will be moved to {YOUTUBE_TARGET} / 文件将移动到 {YOUTUBE_TARGET}")
        if not confirmed(input_func):
            print("Cancelled; no YouTube files were changed / 已取消，未更改 YouTube 文件")
            return 0

        try:
            permissions_set = move_secret_file(
                source,
                target,
                contents,
                YOUTUBE_TEMP_PREFIX,
            )
        except KeyboardInterrupt:
            _report_move_interrupt("YouTube", source, target)
            return 130
        except FileExistsError:
            print(
                "YouTube configuration appeared during setup; neither file was overwritten "
                "/ 配置过程中出现了已有 YouTube 配置；未覆盖任何文件",
                file=sys.stderr,
            )
            return 1
        except OSError:
            print(
                "Could not complete the YouTube secret move; check the root input and "
                "config/youtube/ for final or temporary files / 无法完成 YouTube 密钥移动；"
                "请检查根目录输入文件以及 config/youtube/ 中的最终文件或临时文件",
                file=sys.stderr,
            )
            return 1

        print(
            f"YouTube OAuth client saved at {YOUTUBE_TARGET} "
            f"/ YouTube OAuth 客户端已保存到 {YOUTUBE_TARGET}"
        )

    print(
        "Checking YouTube authorization; the system browser opens only if authorization is needed "
        "/ 正在检查 YouTube 授权；仅在需要授权时打开系统浏览器"
    )
    try:
        result = credentials_loader(target, token_path, interactive=True)
        verifier(result.credentials)
    except KeyboardInterrupt:
        print(
            "YouTube authorization was cancelled; the saved OAuth client was kept "
            "/ YouTube 授权已取消；已保存的 OAuth 客户端仍保留",
            file=sys.stderr,
        )
        return 130
    except (YouTubeAuthorizationError, YouTubeConfigurationError) as error:
        print(f"Error / 错误: {error}", file=sys.stderr)
        return 1

    if result.status == "existing":
        print("YouTube is already authorized / YouTube 已完成授权")
    elif result.status == "refreshed":
        print("YouTube token refreshed safely / YouTube 令牌已安全刷新")
    else:
        print(f"YouTube token saved at {YOUTUBE_TOKEN} / YouTube 令牌已保存到 {YOUTUBE_TOKEN}")
    print("YouTube API access verified without uploading / 已验证 YouTube API 访问，未上传视频")

    if not permissions_set or not result.permissions_set:
        print(
            "Warning: could not restrict private-file permissions; protect the files manually "
            "/ 警告：无法限制私密文件权限，请手动保护这些文件",
            file=sys.stderr,
        )
    return 0


def main(project_root: Path = PROJECT_ROOT) -> int:
    try:
        zoom_result = configure_zoom(project_root)
        if zoom_result == 130:
            return 130
        youtube_result = configure_youtube(project_root)
        if youtube_result == 130:
            return 130
        return 1 if 1 in (zoom_result, youtube_result) else 0
    except KeyboardInterrupt:
        print("\nCancelled / 已取消")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
