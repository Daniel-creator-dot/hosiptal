#!/bin/bash
# Quick update script for VPS
# Run this on your VPS: cd ~/primemed && bash vps_update.sh

echo "🔄 Updating from GitHub..."

# Check if we're in the right directory
if [ ! -f "manage.py" ]; then
    echo "❌ Error: manage.py not found!"
    echo "Run: cd ~/primemed"
    exit 1
fi

# Pull latest changes
echo "📥 Pulling from GitHub..."
git pull origin main

if [ $? -ne 0 ]; then
    echo "❌ Error pulling from GitHub!"
    exit 1
fi

# Activate virtual environment
if [ -d "venv" ]; then
    echo "🔌 Activating virtual environment..."
    source venv/bin/activate
else
    echo "⚠️  Virtual environment not found. Creating..."
    python3 -m venv venv
    source venv/bin/activate
fi

# Install/update dependencies
echo "📦 Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Run migrations
echo "🗄️  Running migrations..."
python manage.py migrate --noinput

# Collect static files
echo "📁 Collecting static files..."
python manage.py collectstatic --noinput

echo ""
echo "✅ Update complete!"
echo ""
echo "To start server:"
echo "  python manage.py runserver 0.0.0.0:8000"
echo ""
echo "Or with Gunicorn:"
echo "  gunicorn --bind 0.0.0.0:8000 hms.wsgi:application"







