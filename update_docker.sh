#!/bin/bash
# Docker Update Script - Apply All Latest Changes
# This script rebuilds and restarts Docker containers with all latest changes

echo "🐳 Docker Update Script - Starting..."
echo ""

# Step 1: Stop containers
echo "📦 Step 1: Stopping containers..."
docker-compose down

# Step 2: Rebuild images
echo "🔨 Step 2: Rebuilding images (this may take a few minutes)..."
docker-compose build --no-cache

# Step 3: Start services
echo "🚀 Step 3: Starting services..."
docker-compose up -d

# Step 4: Wait for services to be ready
echo "⏳ Step 4: Waiting for services to be ready..."
sleep 10

# Step 5: Run migrations
echo "🔄 Step 5: Running database migrations..."
docker-compose exec -T web python manage.py migrate --noinput

# Step 6: Collect static files
echo "📁 Step 6: Collecting static files..."
docker-compose exec -T web python manage.py collectstatic --noinput --clear

# Step 7: Check system health
echo "✅ Step 7: Checking system health..."
docker-compose exec -T web python manage.py check

# Step 8: Show service status
echo "📊 Step 8: Service status:"
docker-compose ps

echo ""
echo "✅ Docker update complete!"
echo "🌐 Access the application at: http://localhost:8000"
echo ""
echo "📋 To view logs, run: docker-compose logs -f web"
echo "🛑 To stop services, run: docker-compose down"
