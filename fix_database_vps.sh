#!/bin/bash
# Database fix script for VPS
# Run this on your VPS: cd /var/www/chm && bash fix_database_vps.sh

set -e

echo "🔧 Database Fix Script for VPS"
echo "================================"
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

# Step 1: Check PostgreSQL service
echo ""
echo "1️⃣  Checking PostgreSQL service..."
if systemctl is-active --quiet postgresql; then
    echo "   ✅ PostgreSQL is running"
else
    echo "   ⚠️  PostgreSQL is not running. Starting..."
    sudo systemctl start postgresql
    sudo systemctl enable postgresql
    sleep 2
    if systemctl is-active --quiet postgresql; then
        echo "   ✅ PostgreSQL started successfully"
    else
        echo "   ❌ Failed to start PostgreSQL"
        echo "   Check logs: sudo journalctl -u postgresql -n 50"
        exit 1
    fi
fi

# Step 2: Check database exists
echo ""
echo "2️⃣  Checking database..."
DB_NAME=$(python -c "import os; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings'); import django; django.setup(); from django.conf import settings; print(settings.DATABASES['default']['NAME'])")
DB_USER=$(python -c "import os; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings'); import django; django.setup(); from django.conf import settings; print(settings.DATABASES['default']['USER'])")

echo "   Database: $DB_NAME"
echo "   User: $DB_USER"

# Check if database exists
if sudo -u postgres psql -lqt | cut -d \| -f 1 | grep -qw "$DB_NAME"; then
    echo "   ✅ Database exists"
else
    echo "   ⚠️  Database does not exist. Creating..."
    sudo -u postgres psql <<EOF
CREATE DATABASE $DB_NAME;
CREATE USER $DB_USER WITH PASSWORD 'change_this_password';
ALTER ROLE $DB_USER SET client_encoding TO 'utf8';
ALTER ROLE $DB_USER SET default_transaction_isolation TO 'read committed';
ALTER ROLE $DB_USER SET timezone TO 'UTC';
GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;
ALTER USER $DB_USER CREATEDB;
\q
EOF
    echo "   ✅ Database created"
    echo "   ⚠️  IMPORTANT: Update DATABASE_URL in .env file with the password you set!"
fi

# Step 3: Check database connection
echo ""
echo "3️⃣  Testing database connection..."
python check_database.py

if [ $? -ne 0 ]; then
    echo ""
    echo "❌ Database connection failed!"
    echo ""
    echo "Troubleshooting steps:"
    echo "1. Check .env file has correct DATABASE_URL"
    echo "2. Verify PostgreSQL is listening: sudo netstat -tlnp | grep 5432"
    echo "3. Check PostgreSQL logs: sudo tail -f /var/log/postgresql/postgresql-*.log"
    echo "4. Test connection manually: sudo -u postgres psql -d $DB_NAME"
    exit 1
fi

# Step 4: Run migrations
echo ""
echo "4️⃣  Running migrations..."
python manage.py migrate --noinput

if [ $? -ne 0 ]; then
    echo "   ❌ Migrations failed!"
    exit 1
fi

echo "   ✅ Migrations completed"

# Step 5: Check for superuser
echo ""
echo "5️⃣  Checking for superuser..."
USER_COUNT=$(python manage.py shell -c "from django.contrib.auth.models import User; print(User.objects.count())")

if [ "$USER_COUNT" -eq 0 ]; then
    echo "   ⚠️  No users found!"
    echo "   Create superuser with: python manage.py createsuperuser"
else
    echo "   ✅ Found $USER_COUNT user(s)"
fi

# Step 6: Collect static files
echo ""
echo "6️⃣  Collecting static files..."
python manage.py collectstatic --noinput

echo ""
echo "✅ Database fix complete!"
echo ""
echo "Next steps:"
echo "1. If no users exist, create one: python manage.py createsuperuser"
echo "2. Restart Gunicorn: sudo systemctl restart gunicorn-chm.service"
echo "3. Check service status: sudo systemctl status gunicorn-chm.service"







