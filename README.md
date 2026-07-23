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

### 3. 准备 Zoom 与 YouTube 配置文件

Zoom 的 JSON 是 Server-to-Server OAuth 应用凭据，不是 Zoom 账号密码。不要把登录密码交给本项目，也不要提交、发送或分享 secret 文件。

1. 请账号管理员打开 [Zoom App Marketplace](https://marketplace.zoom.us/)，选择 **Develop → Build App**。
2. 创建并激活 **Server-to-Server OAuth** 应用。
3. 在 **Scopes** 页面添加 `cloud_recording:read:list_recording_files:admin`；如果页面只显示传统权限，请添加 `recording:read:admin`。
4. 从应用页面取得 **Account ID、Client ID、Client Secret**。
5. 在项目根目录新建精确名称 `zoom_secret.json`（替换示例值，不要加入账号密码）：

```json
{
  "account_id": "YOUR_ACCOUNT_ID",
  "client_id": "YOUR_CLIENT_ID",
  "client_secret": "YOUR_CLIENT_SECRET"
}
```

Google 下载的 JSON 是桌面 OAuth 客户端配置，不是 Google 登录密码。账号所有者只应在稍后打开的 Google 系统浏览器页面自行登录；不要在终端或本项目的文件中输入登录密码。

1. 打开 [Google Cloud Console](https://console.cloud.google.com/)，创建或选择项目。
2. 在 API Library 中启用 **YouTube Data API v3**。
3. 配置 **OAuth consent screen（OAuth 同意屏幕）**。如果应用处于测试状态，将实际授权的 Google 账号添加为 **test user（测试用户）**。
4. 创建 OAuth Client ID，应用类型选择 **Desktop app（桌面应用）**。
5. 下载客户端 JSON，将它改名为精确名称 `youtube_secret.json`，放在项目根目录。不要修改或分享其中的 client secret。

此时根目录可以同时有 `zoom_secret.json` 和 `youtube_secret.json`；缺少其中一个不会阻止配置程序处理另一个。

### 4. 运行统一配置

无参数运行：

macOS：

```bash
.venv/bin/python configure.py
```

Windows：

```bat
.venv\Scripts\python.exe configure.py
```

`configure.py` 只从项目根目录读取精确名称 `zoom_secret.json` 和 `youtube_secret.json`，不会扫描、猜测或移动其他 JSON。它会隐藏字段值、显示目标路径并分别请求确认：

- Zoom 凭据先通过 Zoom 临时验证，再安全移动到 `config/zoom/secret.json`；取得的 Zoom access token 不会保存。
- YouTube 客户端验证为 Google Desktop OAuth JSON 后，安全移动到 `config/youtube/secret.json`。随后只申请 `youtube.upload` 权限，在系统浏览器打开 Google 授权页面，并安全生成 `config/youtube/token.json`。
- 已有目标文件不会被覆盖；已有有效 YouTube token 会直接复用，必要时正常刷新。`configure.py` 不上传视频，也不调用 YouTube 频道或其他 Data API；首次实际上传时，YouTube 才会确认该 Google 账号是否有可上传的频道。无需额外授予读取频道资料的权限。

最终目录树：

```text
config/
├── zoom/
│   └── secret.json
└── youtube/
    ├── secret.json
    └── token.json
```

成功移动后根目录输入文件会消失。`config/`、`zoom_secret.json` 和 `youtube_secret.json` 均被 Git 忽略，但这不能替代安全保管：不要提交、发送或分享任何 secret/token。YouTube secret 和 token 都不是 Google 账号密码，但都属于私密授权资料。

高级用户也可以用完整的三个环境变量覆盖文件配置：

```bash
export ZOOM_ACCOUNT_ID="你的 Account ID"
export ZOOM_CLIENT_ID="你的 Client ID"
export ZOOM_CLIENT_SECRET="你的 Client Secret"
```

必须同时设置三个变量；只设置一部分会报错，不会与文件配置混用。不要把这些值写进代码或提交到 Git。

### 5. 下载并上传

```bash
.venv/bin/python zoom_to_youtube.py
```

Windows 请运行 `.venv\Scripts\python.exe zoom_to_youtube.py`。以下示例在 macOS 使用 `.venv/bin/python`；Windows 用户替换为 `.venv\Scripts\python.exe` 即可。

先完成上面的 `configure.py`。上传流程不会临时打开浏览器；如果 YouTube token 缺失、无效或无法刷新，会提示重新运行配置程序。

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
- **YouTube token 无效或刷新失败：** 重新运行 `configure.py`，并只在 Google 系统浏览器页面完成登录与授权。
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

### 3. Prepare the Zoom and YouTube files

The Zoom JSON contains Server-to-Server OAuth app credentials, not your Zoom account password. Never give this project your sign-in password, and do not commit, send, or share the secret file.

1. Ask an account administrator to open the [Zoom App Marketplace](https://marketplace.zoom.us/) and choose **Develop → Build App**.
2. Create and activate a **Server-to-Server OAuth** app.
3. On its **Scopes** page, add `cloud_recording:read:list_recording_files:admin`. If only classic scopes are available, add `recording:read:admin`.
4. Copy its **Account ID, Client ID, and Client Secret**.
5. Create the exact filename `zoom_secret.json` in the project root (replace the examples and do not add an account password):

```json
{
  "account_id": "YOUR_ACCOUNT_ID",
  "client_id": "YOUR_CLIENT_ID",
  "client_secret": "YOUR_CLIENT_SECRET"
}
```

The Google download is a desktop OAuth client configuration, not your Google password. The account owner signs in only on Google's page in the system browser opened later. Never enter a Google password in the terminal or a project file.

1. Open [Google Cloud Console](https://console.cloud.google.com/) and create or select a project.
2. Enable **YouTube Data API v3** in the API Library.
3. Configure the **OAuth consent screen**. While the app is in testing, add the Google account that will authorize it as a **test user**.
4. Create an OAuth Client ID with application type **Desktop app**.
5. Download the client JSON, rename it to the exact filename `youtube_secret.json`, and place it in the project root. Do not edit or share its client secret.

Both `zoom_secret.json` and `youtube_secret.json` may be present together. A missing input does not stop the configuration program from processing the other one.

### 4. Run the unified configuration

Run it without arguments:

macOS:

```bash
.venv/bin/python configure.py
```

Windows:

```bat
.venv\Scripts\python.exe configure.py
```

`configure.py` reads only the exact project-root names `zoom_secret.json` and `youtube_secret.json`; it does not scan, guess, or move other JSON files. It hides field values, shows each destination, and asks for confirmation:

- Zoom credentials are temporarily validated with Zoom, then safely moved to `config/zoom/secret.json`. The temporary Zoom access token is never saved.
- The YouTube client is validated as Google Desktop OAuth JSON, then safely moved to `config/youtube/secret.json`. The program requests only the `youtube.upload` scope, opens Google's authorization page in the system browser, and safely creates `config/youtube/token.json`.
- Existing destinations are never overwritten. A valid YouTube token is reused and refreshed normally when needed. `configure.py` does not upload videos or call YouTube channel or other Data API endpoints; YouTube confirms whether the Google account has an upload-capable channel only on the first real upload. No additional permission to read channel data is requested.

The final layout is:

```text
config/
├── zoom/
│   └── secret.json
└── youtube/
    ├── secret.json
    └── token.json
```

Successful moves remove the corresponding root input. Git ignores `config/`, `zoom_secret.json`, and `youtube_secret.json`, but that is not a substitute for secure handling: never commit, send, or share any secret or token. The YouTube secret and token are not your Google account password, but both contain private authorization data.

Advanced users can instead override the file with all three environment variables:

```bash
export ZOOM_ACCOUNT_ID="your Account ID"
export ZOOM_CLIENT_ID="your Client ID"
export ZOOM_CLIENT_SECRET="your Client Secret"
```

All three variables must be set together. A partial set is rejected and is never mixed with file credentials. Never put these values in the source code or commit them to Git.

### 5. Download and upload

```bash
.venv/bin/python zoom_to_youtube.py
```

On Windows, run `.venv\Scripts\python.exe zoom_to_youtube.py`. The examples below use `.venv/bin/python` on macOS; Windows users can substitute `.venv\Scripts\python.exe`.

Complete `configure.py` first. The upload workflow never opens a browser unexpectedly. If the YouTube token is missing, invalid, or cannot be refreshed, it tells you to run the configuration program again.

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
- **The YouTube token is invalid or cannot refresh:** Run `configure.py` again and complete sign-in and authorization only on Google's page in the system browser.
- **The upload is interrupted:** Run the script again. A completely downloaded file of the same name is reused, and common temporary YouTube errors are retried automatically.

## Files / 文件

- `requirements.txt` — Python package list / Python 依赖清单
- `install-macos.sh` — macOS installer / macOS 安装脚本
- `install-windows.bat` — Windows installer / Windows 安装脚本
- `configure.py` — unified Zoom and YouTube setup / Zoom 与 YouTube 统一配置
- `secure_files.py` — private-file publication helpers / 私密文件安全发布逻辑
- `youtube_auth.py` — shared YouTube authorization helpers / YouTube 授权共享逻辑
- `zoom_auth.py` — shared Zoom authentication helpers / Zoom 认证共享逻辑
- `zoom_to_youtube.py` — interactive transfer workflow / 交互式传输流程
- `README.md` — setup and usage instructions / 配置与使用说明

Users are responsible for complying with Zoom and YouTube terms, copyright rules, and participant privacy requirements.

使用者有责任遵守 Zoom 与 YouTube 的条款、版权规则以及参与者隐私要求。
