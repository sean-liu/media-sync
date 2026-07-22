#!/usr/bin/env python3
"""Download one Zoom cloud recording and upload it to YouTube."""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import quote

from zoom_auth import load_zoom_credentials, request_zoom_access_token

ZOOM_API_URL = "https://api.zoom.us/v2"
YOUTUBE_SCOPE = ["https://www.googleapis.com/auth/youtube.upload"]
DEFAULT_CLIENT_SECRETS = "config/youtube_client_secret.json"
DEFAULT_YOUTUBE_TOKEN = "config/youtube_token.json"
DOWNLOAD_DIR = "downloads"


def load_dependencies() -> None:
    global requests, Request, Credentials, InstalledAppFlow
    global build, HttpError, MediaFileUpload, tqdm
    try:
        import requests
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
        from googleapiclient.errors import HttpError
        from googleapiclient.http import MediaFileUpload
        from tqdm import tqdm
    except ImportError as error:
        raise RuntimeError(
            "Missing packages / 缺少依赖。Run install-macos.sh or install-windows.bat "
            "/ 请运行 install-macos.sh 或 install-windows.bat"
        ) from error


def prompt(label: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{label}{suffix}: ").strip()
    return value or (default or "")


def zoom_access_token() -> str:
    credentials = load_zoom_credentials(Path(__file__).resolve().parent)
    return request_zoom_access_token(credentials, requests.post)


def api_error(message: str, response: requests.Response) -> str:
    try:
        detail = response.json().get("message") or response.json().get("reason")
    except (ValueError, AttributeError):
        detail = response.text[:300].strip()
    return f"{message} (HTTP {response.status_code})" + (f": {detail}" if detail else "")


def meeting_path_id(meeting_id: str) -> str:
    meeting_id = meeting_id.strip().replace(" ", "")
    # Zoom requires UUIDs beginning with '/' or containing '//' to be encoded twice.
    once = quote(meeting_id, safe="")
    return quote(once, safe="") if meeting_id.startswith("/") or "//" in meeting_id else once


def get_recordings(meeting_id: str, access_token: str) -> dict:
    response = requests.get(
        f"{ZOOM_API_URL}/meetings/{meeting_path_id(meeting_id)}/recordings",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=30,
    )
    if not response.ok:
        raise RuntimeError(api_error("Could not read Zoom recordings / 无法读取 Zoom 录制", response))
    return response.json()


def human_size(byte_count: int | None) -> str:
    size = float(byte_count or 0)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.1f} {unit}"
        size /= 1024
    return "unknown"


def choose_recording(meeting: dict) -> dict:
    recordings = [
        item
        for item in meeting.get("recording_files", [])
        if item.get("file_type", "").upper() == "MP4"
        and item.get("status", "completed") == "completed"
        and item.get("download_url")
    ]
    if not recordings:
        raise RuntimeError("No completed MP4 recording found / 没有找到已完成的 MP4 录制")

    print("\nAvailable recordings / 可用录制:")
    for number, item in enumerate(recordings, 1):
        kind = item.get("recording_type", "video")
        started = item.get("recording_start", "")
        print(f"  {number}. {kind} | {started} | {human_size(item.get('file_size'))}")

    if len(recordings) == 1:
        print("Using the only MP4 recording / 自动选择唯一的 MP4 录制。")
        return recordings[0]
    while True:
        answer = prompt("Choose a number / 请选择序号", "1")
        if answer.isdigit() and 1 <= int(answer) <= len(recordings):
            return recordings[int(answer) - 1]
        print("Invalid choice / 选择无效。")


def safe_filename(value: str) -> str:
    value = re.sub(r"[\\/:*?\"<>|\x00-\x1f]", "_", value).strip(" .")
    return value[:160] or "zoom-recording"


def download_recording(meeting: dict, recording: dict, access_token: str, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    date = (recording.get("recording_start") or meeting.get("start_time") or "")[:10]
    recording_type = recording.get("recording_type") or "video"
    name = safe_filename(
        f"{date} {meeting.get('topic', 'Zoom recording')} - {recording_type}".strip()
    ) + ".mp4"
    destination = output_dir / name
    expected_size = int(recording.get("file_size") or 0)
    if destination.exists() and expected_size and destination.stat().st_size == expected_size:
        print(f"Already downloaded / 已下载: {destination}")
        return destination

    download_token = meeting.get("download_access_token") or access_token
    print(f"\nDownloading / 正在下载: {destination}")
    with requests.get(
        recording["download_url"],
        headers={"Authorization": f"Bearer {download_token}"},
        stream=True,
        timeout=(30, 300),
    ) as response:
        if not response.ok:
            raise RuntimeError(api_error("Zoom download failed / Zoom 下载失败", response))
        total = int(response.headers.get("content-length") or expected_size)
        temporary = destination.with_suffix(destination.suffix + ".part")
        try:
            with temporary.open("wb") as output, tqdm(
                total=total or None, unit="B", unit_scale=True, desc="Zoom"
            ) as progress:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        output.write(chunk)
                        progress.update(len(chunk))
            if expected_size and temporary.stat().st_size != expected_size:
                raise RuntimeError(
                    "Downloaded file size does not match Zoom / 下载文件大小与 Zoom 记录不符"
                )
            temporary.replace(destination)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise
    return destination


def youtube_credentials(client_secrets: Path, token_file: Path) -> Credentials:
    credentials = None
    if token_file.exists():
        try:
            credentials = Credentials.from_authorized_user_file(token_file, YOUTUBE_SCOPE)
        except (ValueError, json.JSONDecodeError):
            print("Saved YouTube login is invalid; signing in again / 已保存登录无效，将重新登录。")
    if credentials and credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
    if not credentials or not credentials.valid:
        if not client_secrets.exists():
            raise FileNotFoundError(
                f"YouTube OAuth file not found / 找不到 YouTube OAuth 文件: {client_secrets}"
            )
        flow = InstalledAppFlow.from_client_secrets_file(str(client_secrets), YOUTUBE_SCOPE)
        credentials = flow.run_local_server(port=0, prompt="consent")
    token_file.parent.mkdir(parents=True, exist_ok=True)
    token_file.write_text(credentials.to_json(), encoding="utf-8")
    token_file.chmod(0o600)
    return credentials


def upload_to_youtube(
    video_path: Path,
    title: str,
    description: str,
    privacy: str,
    client_secrets: Path,
    token_file: Path,
) -> str:
    credentials = youtube_credentials(client_secrets, token_file)
    youtube = build("youtube", "v3", credentials=credentials, cache_discovery=False)
    request = youtube.videos().insert(
        part="snippet,status",
        body={
            "snippet": {"title": title[:100], "description": description, "categoryId": "22"},
            "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False},
        },
        media_body=MediaFileUpload(str(video_path), chunksize=8 * 1024 * 1024, resumable=True),
    )

    print("\nUploading to YouTube / 正在上传到 YouTube...")
    response = None
    retries = 0
    while response is None:
        try:
            status, response = request.next_chunk()
            if status:
                print(f"YouTube: {status.progress() * 100:.1f}%", end="\r", flush=True)
        except HttpError as error:
            if error.resp.status not in (500, 502, 503, 504) or retries >= 5:
                raise
            retries += 1
            wait = 2**retries
            print(f"\nTemporary YouTube error; retrying in {wait}s / 临时错误，{wait} 秒后重试。")
            time.sleep(wait)
    if not response or "id" not in response:
        raise RuntimeError("YouTube returned no video ID / YouTube 未返回视频 ID")
    return response["id"]


def confirm(summary: str, assume_yes: bool) -> bool:
    print(f"\n{summary}")
    if assume_yes:
        return True
    return prompt("Continue? / 是否继续？(y/N)", "N").lower() in ("y", "yes", "是")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download one Zoom recording and upload it to YouTube / 下载一条 Zoom 录制并上传到 YouTube"
    )
    parser.add_argument("meeting_id", nargs="?", help="Zoom meeting ID or UUID / Zoom 会议 ID 或 UUID")
    parser.add_argument("--title", help="YouTube title / YouTube 标题")
    parser.add_argument("--description", help="YouTube description / YouTube 简介")
    parser.add_argument(
        "--privacy", choices=("private", "unlisted", "public"), default="private",
        help="YouTube visibility (default: private) / 可见性（默认：私享）",
    )
    parser.add_argument("--output-dir", default=DOWNLOAD_DIR, help="Download folder / 下载目录")
    parser.add_argument("--youtube-client-secrets", default=DEFAULT_CLIENT_SECRETS)
    parser.add_argument("--yes", action="store_true", help="Skip final confirmation / 跳过最终确认")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        load_dependencies()
        meeting_id = args.meeting_id or prompt("Zoom meeting ID or UUID / Zoom 会议 ID 或 UUID")
        if not meeting_id:
            raise ValueError("Meeting ID is required / 会议 ID 为必填项")

        print("Connecting to Zoom / 正在连接 Zoom...")
        access_token = zoom_access_token()
        meeting = get_recordings(meeting_id, access_token)
        recording = choose_recording(meeting)
        default_title = meeting.get("topic") or "Zoom recording"
        title = args.title or prompt("YouTube title / YouTube 标题", default_title)
        description = args.description
        if description is None:
            description = prompt("YouTube description / YouTube 简介 (optional / 可选)")
        summary = (
            f"Meeting / 会议: {default_title}\n"
            f"Recording / 录制: {recording.get('recording_type', 'video')} "
            f"({human_size(recording.get('file_size'))})\n"
            f"YouTube: {title} [{args.privacy}]"
        )
        if not confirm(summary, args.yes):
            print("Cancelled / 已取消。")
            return 0

        video_path = download_recording(
            meeting, recording, access_token, Path(args.output_dir).expanduser()
        )
        video_id = upload_to_youtube(
            video_path,
            title,
            description,
            args.privacy,
            Path(args.youtube_client_secrets).expanduser(),
            Path(DEFAULT_YOUTUBE_TOKEN),
        )
        print(f"\nDone / 完成: https://youtu.be/{video_id}")
        print(f"Local file kept at / 本地文件保留在: {video_path}")
        return 0
    except KeyboardInterrupt:
        print("\nCancelled / 已取消。")
        return 130
    except (OSError, ValueError, RuntimeError) as error:
        print(f"\nError / 错误: {error}", file=sys.stderr)
        return 1
    except Exception as error:
        # Third-party HTTP exceptions are loaded at runtime; keep their messages concise.
        if "requests" in globals() and isinstance(error, (requests.RequestException, HttpError)):
            print(f"\nError / 错误: {error}", file=sys.stderr)
            return 1
        raise


if __name__ == "__main__":
    raise SystemExit(main())
