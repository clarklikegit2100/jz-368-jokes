@echo off
rem Double-click to preview the report in this window without sending it.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run_report.ps1" -DryRun
pause
