@echo off
echo Adding firewall rule to allow port 8000...
netsh advfirewall firewall add rule name="Django HMS Server" dir=in action=allow protocol=TCP localport=8000
echo.
echo Done! Port 8000 is now open for WiFi access.
echo.
echo Share this URL with your WiFi users: http://192.168.0.108:8000/
echo.
pause













