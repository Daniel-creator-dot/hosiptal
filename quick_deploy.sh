#!/bin/bash
# Quick deployment script - run this on your VPS

echo "🚀 Quick HMS Deployment..."

# Change to your project directory
PROJECT_DIR="/opt/hms/primemed"
if [ ! -d "$PROJECT_DIR" ]; then
    PROJECT_DIR="~/primemed"
fi

cd $PROJECT_DIR || exit 1

# Activate virtual environment
if [ -d "venv" ]; then
    source venv/bin/activate
else
    echo "Creating virtual environment..."
    python3 -m venv venv
    source venv/bin/activate
fi

# Pull latest code
echo "📥 Pulling from GitHub..."
git pull origin main || git clone https://github.com/jerry6193/primemed.git .

# Install/update dependencies
echo "📦 Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Run migrations
echo "🗄️  Running migrations..."
python manage.py migrate --noinput

# Collect static
echo "📁 Collecting static files..."
python manage.py collectstatic --noinput

echo "✅ Deployment complete!"
echo "Run: python manage.py runserver 0.0.0.0:8000"
echo "Or: gunicorn --bind 0.0.0.0:8000 hms.wsgi:application"







