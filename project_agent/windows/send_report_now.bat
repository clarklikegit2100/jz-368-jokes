@echo off
rem Double-click to build and send the project report right now.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run_report.ps1" %*
pause
