#!/usr/bin/env bash

set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)" || exit 1
VENV_DIR="$SCRIPT_DIR/.venv"
VENV_PYTHON="$VENV_DIR/bin/python"
REQUIREMENTS="$SCRIPT_DIR/requirements.txt"
PYTHON=""

info() {
    printf '[INFO] %s\n' "$1"
}

error() {
    printf '[ERROR] %s\n' "$1" >&2
}

run() {
    printf '[RUN ]'
    printf ' %q' "$@"
    printf '\n'
    "$@"
}

is_compatible_python() {
    "$1" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' \
        >/dev/null 2>&1
}

is_usable_venv() {
    [ -x "$VENV_PYTHON" ] &&
        is_compatible_python "$VENV_PYTHON" &&
        "$VENV_PYTHON" -m pip --version >/dev/null 2>&1
}

find_python() {
    local candidate
    for candidate in python3 python; do
        if command -v "$candidate" >/dev/null 2>&1 && is_compatible_python "$candidate"; then
            PYTHON="$(command -v "$candidate")"
            return 0
        fi
    done

    if command -v brew >/dev/null 2>&1; then
        candidate="$(brew --prefix python@3.12 2>/dev/null)/bin/python3.12"
        if [ -x "$candidate" ] && is_compatible_python "$candidate"; then
            PYTHON="$candidate"
            return 0
        fi
    fi
    return 1
}

cd "$SCRIPT_DIR" || exit 1
info "Installing media-sync / 正在安装 media-sync"

if [ ! -f "$REQUIREMENTS" ]; then
    error "requirements.txt not found / 找不到 requirements.txt"
    exit 2
fi

if is_usable_venv; then
    info "Reusing existing .venv / 复用现有 .venv"
else
    if ! find_python; then
        if ! command -v brew >/dev/null 2>&1; then
            error "Python 3.10+ is required, and Homebrew was not found."
            error "需要 Python 3.10+，且未找到 Homebrew。请从 https://www.python.org/downloads/macos/ 安装 Python 后重试。"
            exit 2
        fi

        info "Python 3.10+ not found; installing Python 3.12 with Homebrew."
        info "未找到 Python 3.10+；正在通过 Homebrew 安装 Python 3.12。"
        run brew install python@3.12
        status=$?
        if [ "$status" -ne 0 ]; then
            error "Homebrew could not install Python (exit ${status}) / Homebrew 安装 Python 失败（错误码 ${status}）"
            exit "$status"
        fi
        if ! find_python; then
            error "Python was installed but cannot be located / Python 已安装但仍无法找到"
            exit 3
        fi
    fi

    info "Using $($PYTHON --version 2>&1) / 使用 $($PYTHON --version 2>&1)"
    if [ -e "$VENV_DIR" ] || [ -L "$VENV_DIR" ]; then
        if [ ! -d "$VENV_DIR" ] || [ -L "$VENV_DIR" ]; then
            error ".venv is unusable and is not a regular directory / .venv 不可用且不是普通目录"
            error "Move or remove .venv manually, then run this installer again / 请手动移动或删除 .venv 后重试"
            exit 3
        fi
        info "Recreating unusable .venv / 正在重新创建不可用的 .venv"
        run "$PYTHON" -m venv --clear "$VENV_DIR"
    else
        info "Creating .venv / 正在创建 .venv"
        run "$PYTHON" -m venv "$VENV_DIR"
    fi
    status=$?
    if [ "$status" -ne 0 ]; then
        error "Could not create .venv (exit ${status}) / 无法创建 .venv（错误码 ${status}）"
        exit "$status"
    fi
fi

if ! is_usable_venv; then
    error ".venv is incomplete or uses an unsupported Python version / .venv 不完整或 Python 版本不受支持"
    error "Remove .venv and run this installer again / 请删除 .venv 后重新运行本安装脚本"
    exit 3
fi

info "Installing packages from requirements.txt / 正在从 requirements.txt 安装依赖"
run "$VENV_PYTHON" -m pip install --requirement "$REQUIREMENTS"
status=$?
if [ "$status" -ne 0 ]; then
    error "Package installation failed (exit ${status}); fix the issue and run this installer again."
    error "依赖安装失败（错误码 ${status}）；修复问题后重新运行本安装脚本即可。"
    exit "$status"
fi

info "Installation complete / 安装完成"
printf 'Next / 下一步: "%s" zoom_to_youtube.py\n' "$VENV_PYTHON"
