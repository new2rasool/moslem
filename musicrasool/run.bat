@echo off
REM ============================================================
REM  MusicRasool launcher for Windows
REM  (uses the venv created by install.bat)
REM ============================================================
setlocal
cd /d "%~dp0"

if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

python run.py %*
pause
