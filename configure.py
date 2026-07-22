#!/usr/bin/env python3
"""Validate and install the project-root Zoom secret file."""

from __future__ import annotations

import os
import sys
import tempfile
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
ZOOM_TEMP_PREFIX = ".zoom-secret-"


def confirmed(input_func: Callable[[str], str]) -> bool:
    answer = input_func(
        "Validate and move this file? / 是否验证并移动此文件？(y/N): "
    ).strip().lower()
    return answer in ("y", "yes", "是")


def _write_secret_contents(file_descriptor: int, contents: str) -> None:
    with open(
        file_descriptor,
        "w",
        encoding="utf-8",
        newline="",
        closefd=False,
    ) as output:
        output.write(contents)
        output.flush()
        os.fsync(output.fileno())


def move_secret_file(source: Path, target: Path, contents: str) -> bool:
    target.parent.mkdir(parents=True, exist_ok=True)
    file_descriptor: int | None = None
    temporary_path: Path | None = None
    permissions_set = True
    try:
        file_descriptor, temporary_name = tempfile.mkstemp(
            prefix=ZOOM_TEMP_PREFIX,
            suffix=".tmp",
            dir=target.parent,
        )
        temporary_path = Path(temporary_name)
        if os.name == "posix":
            try:
                temporary_path.chmod(0o600)
            except OSError:
                permissions_set = False

        _write_secret_contents(file_descriptor, contents)
        os.close(file_descriptor)
        file_descriptor = None

        # Hard-link publication is atomic and fails if the target already exists.
        os.link(temporary_path, target)
        temporary_path.unlink()
        temporary_path = None
        source.unlink()
    except BaseException as error:
        cleanup_error: OSError | None = None
        if file_descriptor is not None:
            try:
                os.close(file_descriptor)
            except OSError as close_error:
                cleanup_error = close_error
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError as unlink_error:
                cleanup_error = cleanup_error or unlink_error
        if cleanup_error is not None:
            raise cleanup_error from error
        raise
    return permissions_set


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
    except KeyboardInterrupt:
        if target.exists() and source.exists():
            print(
                "Setup was interrupted after a final Zoom configuration appeared. "
                "Both files were kept; inspect them before removing the root input "
                "/ 最终 Zoom 配置出现后设置被中断；两个文件均已保留，"
                "删除根目录输入文件前请先检查",
                file=sys.stderr,
            )
        elif target.exists():
            print(
                "Setup was interrupted after the final Zoom configuration was saved. "
                "The root input is already gone; check the final file before retrying "
                "/ 最终 Zoom 配置保存后设置被中断；根目录输入文件已不存在，"
                "重试前请检查最终文件",
                file=sys.stderr,
            )
        else:
            print(
                "Setup was interrupted before the final Zoom configuration was published. "
                "The input file was kept and temporary files were cleaned up "
                "/ 最终 Zoom 配置发布前设置被中断；输入文件已保留，临时文件已清理",
                file=sys.stderr,
            )
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


def main() -> int:
    try:
        return configure_zoom(PROJECT_ROOT)
    except KeyboardInterrupt:
        print("\nCancelled / 已取消")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
