#!/bin/bash
# Script to restart Django server and clear caches on Linux/Mac

echo "============================================================"
echo "RESTARTING SERVER AND CLEARING CACHES"
echo "============================================================"
echo ""

echo "[1/3] Clearing all caches..."
python manage.py clear_all_caches
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to clear caches"
    exit 1
fi
echo ""

echo "[2/3] Collecting static files..."
python manage.py collectstatic --noinput
if [ $? -ne 0 ]; then
    echo "WARNING: Static files collection had issues, continuing..."
fi
echo ""

echo "[3/3] Starting server..."
echo ""
echo "Server will start on http://127.0.0.1:8000"
echo "Press Ctrl+C to stop the server"
echo ""
python manage.py runserver




