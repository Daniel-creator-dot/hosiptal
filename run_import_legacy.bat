@echo off
REM Run import_legacy_patients command with proper encoding
chcp 65001 >nul
set PYTHONUNBUFFERED=1
py -3 -u manage.py import_legacy_patients --sql-dir import\legacy --patients-only %*
pause


