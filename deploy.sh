#!/bin/bash
# Deployment script for VPS
# Run this on your VPS: cd /var/www/chm && bash deploy.sh

set -e  # Exit on error

echo "🚀 Starting deployment..."

# Navigate to project directory
cd /var/www/chm || {
    echo "❌ Error: /var/www/chm directory not found!"
    exit 1
}

echo "📂 Current directory: $(pwd)"

# Pull latest changes from GitHub
echo "📥 Pulling from GitHub..."
git pull origin main || {
    echo "❌ Error: Failed to pull from GitHub!"
    exit 1
}

# Activate virtual environment
echo "🔌 Activating virtual environment..."
if [ ! -d "venv" ]; then
    echo "⚠️  Virtual environment not found. Creating..."
    python3 -m venv venv
fi

source venv/bin/activate || {
    echo "❌ Error: Failed to activate virtual environment!"
    exit 1
}

# Install/update dependencies
echo "📦 Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt || {
    echo "❌ Error: Failed to install dependencies!"
    exit 1
}

# Run migrations
echo "🗄️  Running migrations..."
python manage.py migrate --noinput || {
    echo "❌ Error: Migrations failed!"
    exit 1
}

# Collect static files
echo "📁 Collecting static files..."
python manage.py collectstatic --noinput || {
    echo "❌ Error: Failed to collect static files!"
    exit 1
}

# Restart Gunicorn service
echo "🔄 Restarting Gunicorn service..."
sudo systemctl restart gunicorn-chm.service || {
    echo "❌ Error: Failed to restart Gunicorn service!"
    exit 1
}

# Check service status
echo "✅ Checking service status..."
sudo systemctl status gunicorn-chm.service --no-pager | head -10

echo ""
echo "✅ Deployment complete!"
echo "🌐 Your application should be live now."







