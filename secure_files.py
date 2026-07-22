"""Small helpers for safely publishing private UTF-8 files."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


def _write_utf8(file_descriptor: int, contents: str) -> None:
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


def publish_private_text(
    target: Path,
    contents: str,
    *,
    temporary_prefix: str,
    replace: bool,
) -> bool:
    """Publish private text atomically and return whether mode 0600 was set."""
    target.parent.mkdir(parents=True, exist_ok=True)
    file_descriptor: int | None = None
    temporary_path: Path | None = None
    permissions_set = True
    try:
        file_descriptor, temporary_name = tempfile.mkstemp(
            prefix=temporary_prefix,
            suffix=".tmp",
            dir=target.parent,
        )
        temporary_path = Path(temporary_name)
        if os.name == "posix":
            try:
                temporary_path.chmod(0o600)
            except OSError:
                permissions_set = False

        _write_utf8(file_descriptor, contents)
        os.close(file_descriptor)
        file_descriptor = None

        if replace:
            os.replace(temporary_path, target)
        else:
            # A hard link publishes atomically and fails if target already exists.
            os.link(temporary_path, target)
            temporary_path.unlink()
        temporary_path = None
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


def move_private_text(
    source: Path,
    target: Path,
    contents: str,
    *,
    temporary_prefix: str,
) -> bool:
    """Publish without overwriting, then remove the source path."""
    permissions_set = publish_private_text(
        target,
        contents,
        temporary_prefix=temporary_prefix,
        replace=False,
    )
    source.unlink()
    return permissions_set
