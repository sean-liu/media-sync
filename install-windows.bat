@echo off
setlocal EnableExtensions

rem Use UTF-8 for bilingual output on modern Windows terminals.
chcp 65001 >nul 2>&1

cd /d "%~dp0"
if errorlevel 1 exit /b 1

set "VENV_DIR=%CD%\.venv"
set "VENV_PYTHON=%CD%\.venv\Scripts\python.exe"
set "REQUIREMENTS=%CD%\requirements.txt"

echo [INFO] Installing media-sync / 正在安装 media-sync
if not exist "%REQUIREMENTS%" (
    echo [ERROR] requirements.txt not found / 找不到 requirements.txt 1>&2
    exit /b 2
)

if exist "%VENV_PYTHON%" (
    "%VENV_PYTHON%" -c "import sys; raise SystemExit(0 if sys.version_info ^>= (3, 10) else 1)" >nul 2>&1
    if not errorlevel 1 (
        "%VENV_PYTHON%" -m pip --version >nul 2>&1
        if not errorlevel 1 (
            echo [INFO] Reusing existing .venv / 复用现有 .venv
            goto install_requirements
        )
    )
    echo [WARN] Existing .venv is incomplete or outdated; repairing it. / 现有 .venv 不完整或版本过旧，正在修复。
)

call :find_python
if defined PYTHON_EXE goto create_venv

call :install_python
if not "%ERRORLEVEL%"=="0" exit /b %ERRORLEVEL%

call :find_python
if not defined PYTHON_EXE (
    echo [ERROR] Python was installed but cannot be located. Open a new terminal and run this installer again. 1>&2
    echo [ERROR] Python 已安装但仍无法找到。请打开新的终端，再运行本安装脚本。 1>&2
    exit /b 3
)

:create_venv
echo [INFO] Using compatible Python / 使用符合版本要求的 Python
"%PYTHON_EXE%" %PYTHON_ARGS% --version
echo [INFO] Creating or repairing .venv / 正在创建或修复 .venv
echo [RUN ] "%PYTHON_EXE%" %PYTHON_ARGS% -m venv "%VENV_DIR%"
"%PYTHON_EXE%" %PYTHON_ARGS% -m venv "%VENV_DIR%"
if not errorlevel 1 goto venv_created
set "COMMAND_STATUS=%ERRORLEVEL%"
echo [ERROR] Could not create .venv. Exit code: %COMMAND_STATUS%. Fix the error above and run this installer again. 1>&2
echo [ERROR] 无法创建 .venv。错误码：%COMMAND_STATUS%。请修复上方错误后重新运行本安装脚本。 1>&2
exit /b %COMMAND_STATUS%

:venv_created
if not exist "%VENV_PYTHON%" goto invalid_venv
"%VENV_PYTHON%" -c "import sys; raise SystemExit(0 if sys.version_info ^>= (3, 10) else 1)" >nul 2>&1
if errorlevel 1 goto invalid_venv
"%VENV_PYTHON%" -m pip --version >nul 2>&1
if errorlevel 1 goto invalid_venv
goto install_requirements

:invalid_venv
echo [ERROR] .venv is incomplete. Remove .venv and run this installer again. 1>&2
echo [ERROR] .venv 不完整。请删除 .venv 后重新运行本安装脚本。 1>&2
exit /b 3

:install_requirements
echo [INFO] Installing packages from requirements.txt / 正在从 requirements.txt 安装依赖
echo [RUN ] "%VENV_PYTHON%" -m pip install --requirement "%REQUIREMENTS%"
"%VENV_PYTHON%" -m pip install --requirement "%REQUIREMENTS%"
if not errorlevel 1 goto install_complete
set "COMMAND_STATUS=%ERRORLEVEL%"
echo [ERROR] Package installation failed. Exit code: %COMMAND_STATUS%. Fix the error above and run this installer again. 1>&2
echo [ERROR] 依赖安装失败。错误码：%COMMAND_STATUS%。请修复上方错误后重新运行本安装脚本。 1>&2
exit /b %COMMAND_STATUS%

:install_complete
echo [INFO] Installation complete / 安装完成
echo Next / 下一步: "%VENV_PYTHON%" zoom_to_youtube.py
exit /b 0

:find_python
set "PYTHON_EXE="
set "PYTHON_ARGS="

py -3 -c "import sys; raise SystemExit(0 if sys.version_info ^>= (3, 10) else 1)" >nul 2>&1
if not errorlevel 1 (
    set "PYTHON_EXE=py"
    set "PYTHON_ARGS=-3"
    exit /b 0
)

python -c "import sys; raise SystemExit(0 if sys.version_info ^>= (3, 10) else 1)" >nul 2>&1
if not errorlevel 1 (
    set "PYTHON_EXE=python"
    exit /b 0
)

python3 -c "import sys; raise SystemExit(0 if sys.version_info ^>= (3, 10) else 1)" >nul 2>&1
if not errorlevel 1 (
    set "PYTHON_EXE=python3"
    exit /b 0
)

if exist "%LocalAppData%\Programs\Python\Python312\python.exe" (
    "%LocalAppData%\Programs\Python\Python312\python.exe" -c "import sys; raise SystemExit(0 if sys.version_info ^>= (3, 10) else 1)" >nul 2>&1
    if not errorlevel 1 set "PYTHON_EXE=%LocalAppData%\Programs\Python\Python312\python.exe"
)
exit /b 0

:install_python
where winget >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python 3.10+ and winget were not found. Install Python from https://www.python.org/downloads/windows/ and try again. 1>&2
    echo [ERROR] 未找到 Python 3.10+ 和 winget。请从上述网址安装 Python 后重试。 1>&2
    exit /b 2
)

echo [INFO] Python 3.10+ not found; installing Python 3.12 with winget.
echo [INFO] 未找到 Python 3.10+；正在通过 winget 安装 Python 3.12。
echo [RUN ] winget install --id Python.Python.3.12 --exact --source winget --scope user --accept-package-agreements --accept-source-agreements
winget install --id Python.Python.3.12 --exact --source winget --scope user --accept-package-agreements --accept-source-agreements
set "INSTALL_STATUS=%ERRORLEVEL%"
if not "%INSTALL_STATUS%"=="0" echo [ERROR] winget could not install Python (exit %INSTALL_STATUS%) / winget 安装 Python 失败（错误码 %INSTALL_STATUS%） 1>&2
exit /b %INSTALL_STATUS%
