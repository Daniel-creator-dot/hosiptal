@echo off
REM ============================================================
REM Run this ON the server (192.168.2.216) to start HMS.
REM Copy this file to the server and double-click or run from cmd.
REM ============================================================
echo.
echo Starting HMS on 0.0.0.0:8000 (accessible from network)...
echo.
cd /d "%~dp0"

if exist venv\Scripts\activate.bat call venv\Scripts\activate.bat
if exist .venv\Scripts\activate.bat call .venv\Scripts\activate.bat

python manage.py runserver 0.0.0.0:8000
pause
