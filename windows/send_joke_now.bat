@echo off
rem Double-click to send one joke right now. Optional argument: morning / afternoon / evening (default morning).
set PHASE=%1
if "%PHASE%"=="" set PHASE=morning
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run_joke.ps1" -Phase %PHASE%
pause
