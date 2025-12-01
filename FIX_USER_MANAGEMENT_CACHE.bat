@echo off
echo.
echo ========================================
echo   Fix User Management URL Cache Issue
echo ========================================
echo.

echo [1/3] Clearing Python cache...
docker-compose exec web find /app -type d -name __pycache__ -exec rm -rf {} + 2>nul
docker-compose exec web find /app -name "*.pyc" -delete 2>nul
echo    ✅ Cache cleared
echo.

echo [2/3] Clearing Django cache...
docker-compose exec web python manage.py shell -c "from django.core.cache import cache; cache.clear(); print('Cache cleared')"
echo    ✅ Django cache cleared
echo.

echo [3/3] Restarting web service...
docker-compose restart web
echo    ✅ Server restarted
echo.

echo ========================================
echo   ✅ FIX APPLIED!
echo ========================================
echo.
echo Please:
echo   1. Clear your browser cache (Ctrl+Shift+Delete)
echo   2. Hard refresh the page (Ctrl+F5)
echo   3. Try accessing: http://192.168.2.216:8000/hms/admin-dashboard/
echo.
pause





