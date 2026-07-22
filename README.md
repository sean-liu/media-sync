# media-sync

把指定的一条 Zoom 云录制下载到电脑，再上传到 YouTube。它不会实时同步，也不会自动处理账号里的其他录制。

Download one selected Zoom cloud recording and upload it to YouTube. It does not run continuously or sync other recordings automatically.

> MVP 状态 / MVP status: 可运行的命令行版本。默认将视频设为 **私享（private）**，并在下载、上传前让你确认。
>
> Working command-line MVP. Videos default to **private**, and the script asks for confirmation before downloading and uploading.

## 中文说明

### 1. 需要准备

- Python 3.10 或更高版本
- 有云录制的 Zoom 账号（创建 Server-to-Server OAuth 应用通常需要账号管理员权限）
- 有 YouTube 频道的 Google 账号
- 足够保存录制文件的本地磁盘空间

### 2. 安装依赖

安装脚本会检查 Python 3.10 或更高版本、创建项目专用的 `.venv`，并从 `requirements.txt` 安装依赖。可以重复运行；已有的可用虚拟环境会被复用，不可用的普通 `.venv` 目录会被尝试修复或重新创建。

macOS：

```bash
./install-macos.sh
```

如果提示权限不足，先运行 `chmod +x install-macos.sh`。未安装合适 Python 时，脚本会通过已有的 Homebrew 安装 Python 3.12；若没有 Homebrew，则会显示 Python 官网安装指引。

Windows Terminal、PowerShell 或命令提示符（Command Prompt）：

```bat
install-windows.bat
```

如果使用 PowerShell，请运行 `.\install-windows.bat`。

未安装合适 Python 时，脚本会使用 `winget` 安装 Python 3.12。安装失败后修复提示的问题，再次运行同一脚本即可。

安装脚本会尽量使用 UTF-8 显示中英双语日志。若中文仍显示乱码，通常只是终端显示编码问题，不代表安装一定失败；请优先根据英文日志和最后的错误码判断。

macOS 建议在 Terminal、iTerm 或 VS Code 终端中运行，并使用 UTF-8 locale。若当前 locale 看起来不是 UTF-8，安装脚本会给出提示，但不会修改你的终端设置。

### 3. 配置 Zoom

Zoom 登录密码不能交给此脚本，也不要写入任何 JSON 文件。本项目只使用 Zoom Server-to-Server OAuth 应用凭据。

1. 请账号管理员打开 [Zoom App Marketplace](https://marketplace.zoom.us/)，选择 **Develop → Build App**。
2. 创建并激活 **Server-to-Server OAuth** 应用。
3. 在应用的 **Scopes** 页面添加读取云录制所需的权限：
   `cloud_recording:read:list_recording_files:admin`。如果你的 Zoom 页面只显示传统权限，请添加 `recording:read:admin`。
4. 从应用页面取得 **Account ID、Client ID、Client Secret**。
5. 在项目根目录新建 `zoom_secret.json`，内容如下（请替换示例值，不要加入 Zoom 登录密码）：

```json
{
  "account_id": "YOUR_ACCOUNT_ID",
  "client_id": "YOUR_CLIENT_ID",
  "client_secret": "YOUR_CLIENT_SECRET"
}
```

6. 无参数运行配置程序：

macOS：

```bash
.venv/bin/python configure.py
```

Windows：

```bat
.venv\Scripts\python.exe configure.py
```

程序只会识别项目根目录的 `zoom_secret.json`。确认后，它会临时向 Zoom 验证凭据；成功后将文件移动到 `config/zoom/secret.json`。临时输入文件和整个 `config/` 都已被 Git 忽略，验证取得的 Zoom access token 只在本次运行内使用，不会保存。

高级用户也可以用完整的三个环境变量覆盖文件配置：

```bash
export ZOOM_ACCOUNT_ID="你的 Account ID"
export ZOOM_CLIENT_ID="你的 Client ID"
export ZOOM_CLIENT_SECRET="你的 Client Secret"
```

必须同时设置三个变量；只设置一部分会报错，不会与文件配置混用。不要把这些值写进代码或提交到 Git。

### 4. 配置 YouTube（只需一次）

YouTube 配置仍使用下面的现有手动流程；`configure.py` 当前只处理 Zoom，后续任务才会加入 `youtube_secret.json` 支持。

1. 打开 [Google Cloud Console](https://console.cloud.google.com/) 并创建或选择项目。
2. 启用 **YouTube Data API v3**。
3. 配置 OAuth consent screen（OAuth 同意屏幕）。应用在测试状态时，把自己的 Google 账号添加为测试用户。
4. 创建 OAuth Client ID，应用类型选择 **Desktop app（桌面应用）**。
5. 在项目目录创建 `config` 文件夹；下载 JSON，改名为 `youtube_client_secret.json`，放进该文件夹。

目录结构如下：

```text
config/
├── youtube_client_secret.json  # 从 Google Cloud 下载
└── youtube_token.json          # 首次授权后由程序生成
```

第一次上传时浏览器会打开 Google 授权页面。授权成功后，脚本会在本地保存 `config/youtube_token.json`，以后通常不需要再次登录。整个 `config/` 目录已被 Git 忽略，不会提交其中的凭据。

### 5. 运行

```bash
.venv/bin/python zoom_to_youtube.py
```

Windows 请运行 `.venv\Scripts\python.exe zoom_to_youtube.py`。以下示例在 macOS 使用 `.venv/bin/python`；Windows 用户替换为 `.venv\Scripts\python.exe` 即可。

按提示输入 Zoom 会议 ID（通常是 10–11 位数字）或某一次会议的 UUID。脚本会：

1. 列出该会议已完成的 MP4 录制；
2. 让你选择录制、填写 YouTube 标题和简介；
3. 显示摘要并等待确认；
4. 下载到 `downloads/`，然后上传到 YouTube。

上传成功后会显示 YouTube 链接。本地 MP4 会保留，方便确认成功后自行删除。

常用选项：

```bash
# 直接提供会议 ID
.venv/bin/python zoom_to_youtube.py 12345678901

# 上传为不公开（知道链接的人可观看）
.venv/bin/python zoom_to_youtube.py 12345678901 --privacy unlisted

# 查看全部选项
.venv/bin/python zoom_to_youtube.py --help
```

建议先使用 `private`（默认值）测试。只有确认内容、版权和隐私都合适时才使用 `public`。

### 常见问题

- **Zoom 返回 401/403：** 检查应用是否已激活、三个凭据是否正确，以及录制读取权限是否已添加。
- **Zoom 找不到会议：** 确认录制属于这个 Zoom 账号。重复会议可改用该次会议的 UUID。
- **找不到 MP4：** 等待 Zoom 完成云录制处理，并确认会议确实录制了视频。
- **Google 显示应用未验证：** 个人测试项目可把自己的账号加入 OAuth 测试用户；不要给不信任的应用授权。
- **上传中断：** 重新运行即可；已完整下载的同名文件会被复用。YouTube 上传会对常见临时服务错误自动重试。

## English guide

### 1. Prerequisites

- Python 3.10 or newer
- A Zoom account containing the cloud recording (creating a Server-to-Server OAuth app usually requires account admin access)
- A Google account with a YouTube channel
- Enough local disk space for the recording

### 2. Install packages

The installers check for Python 3.10 or newer, create a project-local `.venv`, and install every package from `requirements.txt`. They are safe to rerun, reuse a working virtual environment, and attempt to repair or recreate an unusable regular `.venv` directory.

macOS:

```bash
./install-macos.sh
```

If permission is denied, run `chmod +x install-macos.sh` first. When suitable Python is missing, the installer uses an existing Homebrew installation to install Python 3.12. Without Homebrew, it prints instructions for installing Python from the official website.

Windows Terminal, PowerShell, or Command Prompt:

```bat
install-windows.bat
```

In PowerShell, run `.\install-windows.bat`.

When suitable Python is missing, the installer installs Python 3.12 with `winget`. If installation fails, fix the reported issue and run the same installer again.

The installer tries to use UTF-8 for bilingual logs. If Chinese text still looks garbled, it is usually a terminal display-encoding issue rather than proof that installation failed; use the English logs and the final exit code as the source of truth.

On macOS, run the installer in Terminal, iTerm, or the VS Code terminal with a UTF-8 locale. If the current locale does not look like UTF-8, the installer prints a warning but does not change your terminal settings.

### 3. Configure Zoom

Never give this script your Zoom sign-in password or put that password in any JSON file. This project uses only Zoom Server-to-Server OAuth app credentials.

1. Ask an account administrator to open the [Zoom App Marketplace](https://marketplace.zoom.us/) and choose **Develop → Build App**.
2. Create and activate a **Server-to-Server OAuth** app.
3. On its **Scopes** page, add `cloud_recording:read:list_recording_files:admin`. If your Zoom account only shows classic scopes, add `recording:read:admin`.
4. Copy its **Account ID, Client ID, and Client Secret**.
5. Create `zoom_secret.json` in the project root with the following content (replace the examples and do not add your Zoom sign-in password):

```json
{
  "account_id": "YOUR_ACCOUNT_ID",
  "client_id": "YOUR_CLIENT_ID",
  "client_secret": "YOUR_CLIENT_SECRET"
}
```

6. Run the configuration program without arguments:

macOS:

```bash
.venv/bin/python configure.py
```

Windows:

```bat
.venv\Scripts\python.exe configure.py
```

The program recognizes only `zoom_secret.json` in the project root. After confirmation, it temporarily validates the credentials with Zoom and, on success, moves the file to `config/zoom/secret.json`. Git ignores both the temporary input file and the entire `config/` directory. The Zoom access token obtained for validation is used only for that run and is never saved.

Advanced users can instead override the file with all three environment variables:

```bash
export ZOOM_ACCOUNT_ID="your Account ID"
export ZOOM_CLIENT_ID="your Client ID"
export ZOOM_CLIENT_SECRET="your Client Secret"
```

All three variables must be set together. A partial set is rejected and is never mixed with file credentials. Never put these values in the source code or commit them to Git.

### 4. Configure YouTube (once)

YouTube still uses the existing manual process below. `configure.py` currently handles only Zoom; support for `youtube_secret.json` belongs to a later task.

1. Open [Google Cloud Console](https://console.cloud.google.com/) and create or select a project.
2. Enable **YouTube Data API v3**.
3. Configure the OAuth consent screen. If the app is in testing, add your Google account as a test user.
4. Create an OAuth Client ID with application type **Desktop app**.
5. Create a `config` folder in the project directory. Download the JSON, rename it to `youtube_client_secret.json`, and place it in that folder.

The resulting layout is:

```text
config/
├── youtube_client_secret.json  # downloaded from Google Cloud
└── youtube_token.json          # generated after the first authorization
```

On the first upload, a browser opens for Google authorization. The script then stores `config/youtube_token.json` locally so later runs normally do not require another login. Git ignores the entire `config/` directory so its credentials are not committed.

### 5. Run

```bash
.venv/bin/python zoom_to_youtube.py
```

On Windows, run `.venv\Scripts\python.exe zoom_to_youtube.py`. The examples below use `.venv/bin/python` on macOS; Windows users can substitute `.venv\Scripts\python.exe`.

Enter a Zoom meeting ID (usually 10–11 digits) or the UUID of a specific meeting occurrence. The script will:

1. list completed MP4 recordings for that meeting;
2. let you choose one and enter its YouTube title and description;
3. show a summary and ask for confirmation;
4. download it to `downloads/`, then upload it to YouTube.

After a successful upload, it prints the YouTube link. The local MP4 is kept so you can verify the upload before deleting it yourself.

Useful options:

```bash
# Supply the meeting ID directly
.venv/bin/python zoom_to_youtube.py 12345678901

# Make the video unlisted (anyone with the link can watch)
.venv/bin/python zoom_to_youtube.py 12345678901 --privacy unlisted

# Show every option
.venv/bin/python zoom_to_youtube.py --help
```

Test with `private` (the default) first. Only use `public` after checking the content, copyright, and participant privacy.

### Troubleshooting

- **Zoom returns 401/403:** Check that the app is activated, all three credentials are correct, and the recording-read scope was added.
- **Zoom cannot find the meeting:** Confirm that the recording belongs to this Zoom account. For a recurring meeting, try the occurrence UUID.
- **No MP4 is found:** Wait for Zoom to finish processing and confirm that the meeting recorded video.
- **Google says the app is unverified:** For a personal test project, add your account as an OAuth test user. Never authorize an app you do not trust.
- **The upload is interrupted:** Run the script again. A completely downloaded file of the same name is reused, and common temporary YouTube errors are retried automatically.

## Files / 文件

- `requirements.txt` — Python package list / Python 依赖清单
- `install-macos.sh` — macOS installer / macOS 安装脚本
- `install-windows.bat` — Windows installer / Windows 安装脚本
- `configure.py` — Zoom credential setup / Zoom 凭据配置
- `zoom_auth.py` — shared Zoom authentication helpers / Zoom 认证共享逻辑
- `zoom_to_youtube.py` — interactive transfer workflow / 交互式传输流程
- `README.md` — setup and usage instructions / 配置与使用说明

Users are responsible for complying with Zoom and YouTube terms, copyright rules, and participant privacy requirements.

使用者有责任遵守 Zoom 与 YouTube 的条款、版权规则以及参与者隐私要求。
