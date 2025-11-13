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

