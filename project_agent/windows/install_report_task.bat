@echo off
rem Double-click to register the daily project report task (07:30 local time). Optional: -At 07:00
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_report_task.ps1" %*
pause
