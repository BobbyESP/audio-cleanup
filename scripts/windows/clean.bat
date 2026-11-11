@echo off
rem Clean the audio of a video.  Drag a video onto this file, or from a terminal:
rem   clean.bat "D:\path\recording.mp4" [--atten 24] [--lufs -14] [--engine nr] ...
rem Run "clean.bat --help" for every option.
setlocal
call "%~dp0_common.bat" "%~nx0"

where uv >nul 2>nul || (echo uv not found. Run scripts\windows\setup.bat first. & set "RC=1" & goto :end)

if "%~1"=="" (
  echo Drag a video onto this file, or run:
  echo   clean.bat "D:\path\recording.mp4" [--atten 24] [--lufs -14] ...
  set "RC=1"
  goto :end
)

uv run --project "%ROOT%" --extra deepfilternet audio-cleanup clean %*
set "RC=%ERRORLEVEL%"

:end
if "%PAUSE_AT_END%"=="1" pause
exit /b %RC%
