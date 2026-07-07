#!/usr/bin/env bash
# Render Build Script for HMS Application
# This script runs during the build phase on Render

set -o errexit  # Exit on error
set -o pipefail # Exit on pipe failure
set -o nounset  # Exit on undefined variable

echo "🏗️  Starting HMS build process..."

# Upgrade pip
echo "📦 Upgrading pip..."
pip install --upgrade pip

# Install Python dependencies
echo "📦 Installing Python dependencies..."
pip install -r requirements.txt

# Install additional production dependencies if not in requirements.txt
echo "📦 Ensuring production dependencies..."
pip install gunicorn whitenoise psycopg2-binary dj-database-url

# Collect static files
echo "🎨 Collecting static files..."
python manage.py collectstatic --no-input --clear

# Validate database configuration (Render must use external PostgreSQL)
echo "🔍 Validating database configuration..."
python << 'PYEOF'
import os
import sys

url = os.environ.get("DATABASE_URL", "").strip()
if not url:
    print("ERROR: DATABASE_URL is not set.")
    print("Set your Supabase PostgreSQL URL in Render Dashboard -> Environment.")
    sys.exit(1)
if url.startswith("sqlite"):
    print("ERROR: DATABASE_URL cannot be SQLite on Render. Use PostgreSQL (Supabase).")
    sys.exit(1)
if "postgres" not in url:
    print("ERROR: DATABASE_URL must be a PostgreSQL connection string.")
    sys.exit(1)
host = url.split("@")[-1].split("/")[0] if "@" in url else "configured"
print(f"OK: DATABASE_URL host is {host}")
PYEOF

echo "🗄️  Testing database connection..."
python test_db_connection.py

# Run database migrations
echo "🗄️  Running database migrations..."
python manage.py migrate --no-input

# Create cache table for database caching (if not using Redis)
echo "💾 Creating cache table..."
python manage.py createcachetable || true

# Create superuser if it doesn't exist (optional - comment out if not needed)
# echo "👤 Creating default superuser..."
# python manage.py shell << EOF
# from django.contrib.auth import get_user_model
# User = get_user_model()
# if not User.objects.filter(username='admin').exists():
#     User.objects.create_superuser('admin', 'admin@example.com', 'changethispassword')
#     print('Superuser created successfully')
# else:
#     print('Superuser already exists')
# EOF

# Compress static files (if using compression)
echo "🗜️  Compressing static files..."
# python manage.py compress --force || true

echo "✅ Build completed successfully!"

