@echo off
rem Double-click to register the three daily joke tasks (08:00 / 12:30 / 20:00 local time).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_tasks.ps1" %*
pause
