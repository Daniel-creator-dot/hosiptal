@echo off
echo ======================================================================
echo     CREATING MIGRATIONS FOR ACCOUNTING SYSTEM
echo ======================================================================
echo.

echo Answering 'n' to all rename questions and '1' for default options...
echo.

REM Answer 'n' to renames and '1' to non-nullable field questions
(echo n & echo n & echo n & echo n & echo n & echo n & echo 1 & echo ) | python manage.py makemigrations hospital

echo.
echo ======================================================================
echo     APPLYING MIGRATIONS
echo ======================================================================
echo.

python manage.py migrate

echo.
echo ======================================================================
echo     MIGRATIONS COMPLETE!
echo ======================================================================
echo.

pause




















