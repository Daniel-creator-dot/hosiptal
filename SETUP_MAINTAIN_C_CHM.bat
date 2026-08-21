@echo off
title Setup - Maintain HMS on C:\chm
cd /d C:\chm
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\chm\scripts\setup_maintain_c_chm.ps1"
echo.
pause
