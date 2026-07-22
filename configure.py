#!/usr/bin/env python3
"""Validate and install the project-root Zoom secret file."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Callable

from zoom_auth import (
    ZoomConfigurationError,
    ZoomCredentials,
    read_zoom_secret,
    request_zoom_access_token,
)

PROJECT_ROOT = Path(__file__).resolve().parent
ZOOM_INPUT = "zoom_secret.json"
ZOOM_TARGET = Path("config") / "zoom" / "secret.json"


def confirmed(input_func: Callable[[str], str]) -> bool:
    answer = input_func(
        "Validate and move this file? / 是否验证并移动此文件？(y/N): "
    ).strip().lower()
    return answer in ("y", "yes", "是")


def move_secret_file(source: Path, target: Path, contents: str) -> bool:
    target.parent.mkdir(parents=True, exist_ok=True)
    file_descriptor: int | None = None
    created = False
    try:
        file_descriptor = os.open(
            target,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )
        created = True
        with os.fdopen(file_descriptor, "w", encoding="utf-8", newline="") as output:
            file_descriptor = None
            output.write(contents)
            output.flush()
            os.fsync(output.fileno())
        source.unlink()
    except Exception:
        if file_descriptor is not None:
            os.close(file_descriptor)
        if created and source.exists():
            target.unlink(missing_ok=True)
        raise

    if os.name == "posix":
        try:
            target.chmod(0o600)
        except OSError:
            return False
    return True


def configure_zoom(
    project_root: Path,
    input_func: Callable[[str], str] = input,
    token_fetcher: Callable[[ZoomCredentials], str] = request_zoom_access_token,
) -> int:
    source = project_root / ZOOM_INPUT
    target = project_root / ZOOM_TARGET

    if target.exists():
        print(
            "Zoom configuration already exists. Check the existing configuration; "
            "neither file was changed / Zoom 配置已存在，请检查现有配置；两个文件均未更改"
        )
        return 1
    if not source.is_file():
        print(
            f"Place {ZOOM_INPUT} in the project root and run this script again "
            f"/ 请将 {ZOOM_INPUT} 放到项目根目录后重新运行此脚本"
        )
        return 1

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
    except FileExistsError:
        print(
            "Zoom configuration appeared during setup; neither file was overwritten "
            "/ 配置过程中出现了已有 Zoom 配置；未覆盖任何文件",
            file=sys.stderr,
        )
        return 1
    except OSError:
        print(
            "Could not move the Zoom secret file; check both locations "
            "/ 无法移动 Zoom 密钥文件，请检查两个位置",
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


def main() -> int:
    try:
        return configure_zoom(PROJECT_ROOT)
    except KeyboardInterrupt:
        print("\nCancelled; no files were changed / 已取消，未更改任何文件")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
