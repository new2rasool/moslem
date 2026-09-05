@echo off
REM ============================================================
REM  MusicRasool - One-command installer for Windows
REM ------------------------------------------------------------
REM  Requirements: Python 3.9 - 3.12 (64-bit) installed and on PATH
REM                https://www.python.org/downloads/
REM  Optional    : FFmpeg (https://www.gyan.dev/ffmpeg/builds/)
REM                The installer can auto-download it below.
REM ============================================================
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ============================================
echo    MusicRasool Auto Installer  (Windows)
echo ============================================

REM ---------------- 1. Find Python ----------------
echo [1/5] Checking Python ...
set "PY_CMD="
for %%P in (py python) do (
    where %%P >nul 2>nul
    if not errorlevel 1 set "PY_CMD=%%P"
)
if not defined PY_CMD (
    echo [ERROR] Python not found. Install Python 3.10 (64-bit) from python.org
    echo         and tick "Add Python to PATH".
    pause
    exit /b 1
)

REM try to get a 3.9-3.12 interpreter
set "PYTHON_BIN=python"
%PY_CMD% -c "import sys; v=sys.version_info; raise SystemExit(0 if (3,9)<=v[:2]<=(3,12) else 1)" >nul 2>nul
if errorlevel 1 (
    echo [WARN] Default Python is not 3.9-3.12. Trying py -3.10 ...
    py -3.10 -c "print('ok')" >nul 2>nul
    if not errorlevel 1 (
        set "PYTHON_BIN=py -3.10"
    ) else (
        echo [WARN] No Python 3.10 found; using default. ntgcalls may need
        echo         a manual wheel. Python 3.10-3.12 is recommended.
    )
)
%PYTHON_BIN% --version

REM ---------------- 2. FFmpeg ----------------
echo [2/5] Checking FFmpeg ...
where ffmpeg >nul 2>nul
if errorlevel 1 (
    echo   ffmpeg not found - downloading static build via pip fallback ...
    echo   (a static ffmpeg will be bundled with the bot)
) else (
    ffmpeg -version 2>nul | findstr /b "ffmpeg" 
)

REM ---------------- 3. Virtual env ----------------
echo [3/5] Creating virtual environment ...
if not exist "venv" (
    %PYTHON_BIN% -m venv venv
    if errorlevel 1 (
        echo [ERROR] Could not create venv. Is python3-venv / ensurepip available?
        pause
        exit /b 1
    )
)
call venv\Scripts\activate.bat
python -m pip install --upgrade pip wheel setuptools

REM ---------------- 4. Requirements ----------------
echo [4/5] Installing requirements ...
REM ntgcalls is a native binding - install the rest first
findstr /v /b /c:"ntgcalls" requirements.txt > requirements_nontg.txt
python -m pip install -r requirements_nontg.txt
if errorlevel 1 (
    echo [ERROR] pip install failed. See messages above.
    pause
    exit /b 1
)
del /q requirements_nontg.txt

echo   Installing ntgcalls (prebuilt wheel only) ...
python -m pip install --only-binary=:all: ntgcalls==1.1.3
if errorlevel 1 (
    echo   ntgcalls 1.1.3 wheel not found for this Python - trying 1.2.3 ...
    python -m pip install --only-binary=:all: ntgcalls==1.2.3
    if errorlevel 1 (
        echo [ERROR] Could not install ntgcalls from prebuilt wheels.
        echo         Use Python 3.10 - 3.12 (64-bit) and retry.
        pause
        exit /b 1
    )
)

REM ffmpeg fallback
where ffmpeg >nul 2>nul
if errorlevel 1 (
    echo   Installing static ffmpeg fallback ...
    python -m pip install -q imageio-ffmpeg==0.4.9
)

REM ---------------- 5. .env ----------------
echo [5/5] Configuration ...
if exist ".env" (
    echo   .env already exists - keeping it.
) else (
    echo   No .env found - creating it now.
    echo   Get API_ID/API_HASH from https://my.telegram.org
    echo   Get BOT_TOKEN from https://t.me/BotFather
    echo   Get your numeric ID from https://t.me/userinfobot
    echo.
    set /p API_ID_IN=  API_ID     : 
    set /p API_HASH_IN=  API_HASH   : 
    set /p BOT_TOKEN_IN=  BOT_TOKEN  : 
    set /p OWNER_ID_IN=  OWNER_ID   : 
    set /p SUDO_ID_IN=  SUDO_ID (Enter=same): 
    if "!SUDO_ID_IN!"=="" set "SUDO_ID_IN=!OWNER_ID_IN!"
    if "!API_ID_IN!"=="" goto incomplete
    if "!API_HASH_IN!"=="" goto incomplete
    if "!BOT_TOKEN_IN!"=="" goto incomplete
    if "!OWNER_ID_IN!"=="" goto incomplete
    (
        echo # MusicRasool configuration
        echo API_ID=!API_ID_IN!
        echo API_HASH=!API_HASH_IN!
        echo BOT_TOKEN=!BOT_TOKEN_IN!
        echo OWNER_ID=!OWNER_ID_IN!
        echo SUDO_ID=!SUDO_ID_IN!
        echo DEFAULT_LANG=fa
        echo DOWNLOAD_DIR=downloads
        echo MELOBIT_API=https://api.melobit.com/v1
    ) > .env
    echo   .env written.
    goto done

    :incomplete
    echo [WARN] Incomplete input - copying .env.example instead.
    copy /y .env.example .env >nul
)

:done
echo ============================================
echo   Setup complete!
echo   1. Run:  run.bat
echo   2. In private chat with the bot send /login
echo      then: phone number, login code, (2FA).
echo   3. Send /restart, add the helper to your
echo      group and start streaming.
echo ============================================
pause
