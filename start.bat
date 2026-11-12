@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  where py >nul 2>&1 && py -3 -m venv .venv
  if not exist ".venv\Scripts\python.exe" python -m venv .venv
  if not exist ".venv\Scripts\python.exe" (
    echo Python 3.12 or newer is required.
    echo Install it from https://www.python.org/downloads/ and enable "Add python.exe to PATH".
    pause
    exit /b 1
  )
  ".venv\Scripts\python.exe" -m pip install -U pip
  ".venv\Scripts\python.exe" -m pip install -r "%~dp0requirements.txt"
  if errorlevel 1 (
    echo.
    echo Installation failed.
    pause
    exit /b 1
  )
)

set AWS_EC2_METADATA_DISABLED=true
if exist ".venv\Scripts\pythonw.exe" (
  start "" ".venv\Scripts\pythonw.exe" -m s3viewer
) else (
  ".venv\Scripts\python.exe" -m s3viewer
)
