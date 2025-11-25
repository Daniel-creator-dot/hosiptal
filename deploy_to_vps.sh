#!/bin/bash
# Quick deployment script for VPS
# Run this on your VPS after initial setup

set -e

echo "🚀 Starting HMS Deployment..."

# Navigate to project directory
cd /opt/hms/primemed || cd ~/primemed

# Activate virtual environment
source venv/bin/activate

# Pull latest changes
echo "📥 Pulling latest changes from GitHub..."
git pull origin main

# Install/update dependencies
echo "📦 Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Run migrations
echo "🗄️  Running database migrations..."
python manage.py migrate --noinput

# Collect static files
echo "📁 Collecting static files..."
python manage.py collectstatic --noinput

# Restart services
echo "🔄 Restarting services..."
sudo systemctl restart hms
sudo systemctl restart nginx

echo "✅ Deployment complete!"
echo "🌐 Application should be available at: http://45.8.225.73"







