@echo off
echo ========================================
echo Starting HMS Server for Network Access
echo ========================================
echo.
echo IMPORTANT: After this starts, you MUST configure firewall!
echo Right-click allow_port_8000_firewall.bat -^> Run as administrator
echo.
echo Starting server on 0.0.0.0:8000...
echo This will make it accessible from http://192.168.0.105:8000
echo.
echo Press Ctrl+C to stop the server
echo.
echo ========================================
echo.

python manage.py runserver 0.0.0.0:8000

pause






