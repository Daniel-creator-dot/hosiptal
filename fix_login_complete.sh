#!/bin/bash
# Complete login fix script for VPS
# Run this on your VPS: cd /var/www/chm && bash fix_login_complete.sh

set -e

echo "🔐 Complete Login Fix Script"
echo "=============================="
echo ""

# Check if we're in the right directory
if [ ! -f "manage.py" ]; then
    echo "❌ Error: manage.py not found!"
    echo "Run: cd /var/www/chm"
    exit 1
fi

# Activate virtual environment
if [ -d "venv" ]; then
    echo "🔌 Activating virtual environment..."
    source venv/bin/activate
else
    echo "❌ Virtual environment not found!"
    exit 1
fi

# Step 1: Run login diagnostic
echo ""
echo "1️⃣  Running login diagnostic..."
python fix_login_issues.py

echo ""
read -p "Press Enter to continue with fixes..."

# Step 2: Check database
echo ""
echo "2️⃣  Checking database..."
python check_database.py

# Step 3: Check if users exist
echo ""
echo "3️⃣  Checking users..."
USER_COUNT=$(python manage.py shell -c "from django.contrib.auth.models import User; print(User.objects.count())" 2>/dev/null || echo "0")

if [ "$USER_COUNT" -eq "0" ]; then
    echo "   ⚠️  No users found!"
    echo ""
    echo "   Creating superuser..."
    python manage.py createsuperuser
else
    echo "   ✅ Found $USER_COUNT user(s)"
    echo ""
    echo "   If you can't login, reset password:"
    echo "   python reset_user_password.py <username> <new_password>"
fi

# Step 4: Run migrations (ensure auth tables are up to date)
echo ""
echo "4️⃣  Running migrations..."
python manage.py migrate --noinput

# Step 5: Check session configuration
echo ""
echo "5️⃣  Checking session configuration..."
python manage.py shell <<EOF
from django.conf import settings
print(f"SESSION_ENGINE: {getattr(settings, 'SESSION_ENGINE', 'Not set')}")
print(f"SESSION_COOKIE_SECURE: {getattr(settings, 'SESSION_COOKIE_SECURE', 'Not set')}")
print(f"CSRF_COOKIE_SECURE: {getattr(settings, 'CSRF_COOKIE_SECURE', 'Not set')}")
EOF

# Step 6: Collect static files
echo ""
echo "6️⃣  Collecting static files..."
python manage.py collectstatic --noinput

# Step 7: Restart Gunicorn
echo ""
echo "7️⃣  Restarting Gunicorn..."
sudo systemctl restart gunicorn-chm.service
sleep 2

# Step 8: Check service status
echo ""
echo "8️⃣  Checking service status..."
sudo systemctl status gunicorn-chm.service --no-pager | head -15

echo ""
echo "✅ Login fix complete!"
echo ""
echo "Next steps:"
echo "1. Try logging in at: http://$(hostname -I | awk '{print $1}')/hms/login/"
echo "2. If still can't login, check logs: sudo journalctl -u gunicorn-chm.service -f"
echo "3. Reset password: python reset_user_password.py <username> <new_password>"
echo "4. Check diagnostic: python fix_login_issues.py"







