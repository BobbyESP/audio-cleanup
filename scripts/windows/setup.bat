@echo off
rem One-time setup on Windows: uv + Python 3.11 + PyTorch/DeepFilterNet + ffmpeg.
rem Safe to run again at any time.
setlocal
call "%~dp0_common.bat" "%~nx0"
cd /d "%ROOT%"

echo === audio-cleanup - setup ===
echo.

rem ---- 1/4 uv --------------------------------------------------------------
where uv >nul 2>nul
if errorlevel 1 (
  echo [1/4] Installing uv...
  powershell -NoProfile -ExecutionPolicy ByPass -Command "irm https://astral.sh/uv/install.ps1 | iex"
) else (
  echo [1/4] uv found.
)
where uv >nul 2>nul || (echo ERROR: uv could not be installed. See https://docs.astral.sh/uv/getting-started/installation/ & goto :fail)
uv --version
echo.

rem ---- 2/4 ffmpeg ----------------------------------------------------------
where ffmpeg >nul 2>nul
if errorlevel 1 (
  echo [2/4] ffmpeg not found, installing it with winget...
  winget install -e --id Gyan.FFmpeg --accept-source-agreements --accept-package-agreements
  echo.
  echo ffmpeg installed. Close this window and run setup.bat again in a NEW window
  echo so Windows picks up the new PATH.
  goto :end
) else (
  echo [2/4] ffmpeg found.
)
echo.

rem ---- 3/4 Python environment ----------------------------------------------
echo [3/4] Creating the environment: Python 3.11 + PyTorch + DeepFilterNet
echo       (about 3 GB the first time, it can take a while)...
uv sync --extra deepfilternet || (echo ERROR: uv sync failed. & goto :fail)
echo.

rem ---- 4/4 check -----------------------------------------------------------
echo [4/4] Checking the installation...
uv run --extra deepfilternet audio-cleanup doctor || (echo ERROR: the check failed, see above. & goto :fail)
echo.
echo Setup complete. Drag a video onto scripts\windows\clean.bat to process it.
goto :end

:fail
set "RC=1"
:end
if not defined RC set "RC=0"
if "%PAUSE_AT_END%"=="1" pause
exit /b %RC%
