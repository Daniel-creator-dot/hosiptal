@echo off
cd /d d:\chm
echo Starting Django Server...
python manage.py runserver 0.0.0.0:8000
pause
