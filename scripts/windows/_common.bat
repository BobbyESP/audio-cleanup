@echo off
rem Shared setup for the Windows launchers. Not meant to be run directly.
rem Usage (from another .bat):  call "%~dp0_common.bat" "%~nx0"
rem
rem Sets:
rem   ROOT            absolute path of the repository root
rem   PAUSE_AT_END    1 when the launcher was started by double-click / drag-and-drop
rem                   (so the window stays open), 0 when run from an open terminal
rem Also puts uv's default install folder on PATH for this session.

for %%I in ("%~dp0..\..") do set "ROOT=%%~fI"

rem Explorer starts launchers as:  cmd.exe /c ""script.bat" "dropped file""
rem so the launcher's own name appears in %cmdcmdline%. Delayed expansion is used on purpose:
rem it never re-parses the value, so file names with & ( ) ^ in them are harmless.
setlocal EnableDelayedExpansion
set "PAUSE_TMP=0"
if not "!cmdcmdline:%~1=!"=="!cmdcmdline!" set "PAUSE_TMP=1"
endlocal & set "PAUSE_AT_END=%PAUSE_TMP%"

set "PATH=%USERPROFILE%\.local\bin;%PATH%"
