@echo off
rem Report durations, start times and timestamp gaps of recordings (can take a minute or two).
rem   - Drag one or more videos onto this file; the report is saved next to the first one.
rem   - Or run it from a terminal with no arguments to analyse every .mp4 in the current folder.
rem The report is saved as diagnose_report.txt.
setlocal
call "%~dp0_common.bat" "%~nx0"

where uv >nul 2>nul || (echo uv not found. Run scripts\windows\setup.bat first. & set "RC=1" & goto :end)

echo Analysing timestamps (can take a minute or two)...
if "%~1"=="" (
  uv run --project "%ROOT%" audio-cleanup diagnose -o diagnose_report.txt
) else (
  uv run --project "%ROOT%" audio-cleanup diagnose -o "%~dp1diagnose_report.txt" %*
)
set "RC=%ERRORLEVEL%"

:end
if "%PAUSE_AT_END%"=="1" pause
exit /b %RC%
