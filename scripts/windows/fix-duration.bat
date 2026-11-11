@echo off
rem Fix the wrong duration of an already processed video (bogus OBS chapter markers).
rem Nothing is re-encoded; it takes a few seconds. Drag the video onto this file, or:
rem   fix-duration.bat "D:\path\recording_clean.mp4" [--drop]
rem The result is written next to the original as <name>_fixed.mp4.
setlocal
call "%~dp0_common.bat" "%~nx0"

where uv >nul 2>nul || (echo uv not found. Run scripts\windows\setup.bat first. & set "RC=1" & goto :end)

if "%~1"=="" (
  echo Drag an already processed video onto this file, or run:
  echo   fix-duration.bat "D:\path\recording_clean.mp4" [--drop]
  set "RC=1"
  goto :end
)

uv run --project "%ROOT%" audio-cleanup fix-chapters %*
set "RC=%ERRORLEVEL%"

:end
if "%PAUSE_AT_END%"=="1" pause
exit /b %RC%
