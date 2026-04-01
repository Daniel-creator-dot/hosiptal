#!/bin/bash
# Docker Startup Script for HMS
# This script ensures all structures are updated and services are ready

echo "🚀 Starting HMS Docker Services..."

# Start all services
docker-compose up -d --remove-orphans

# Wait for services to be healthy
echo "⏳ Waiting for services to be healthy..."
sleep 15

# Run migrations
echo "📊 Running database migrations..."
docker-compose exec -T web python manage.py migrate --noinput

# Setup RBAC roles
echo "👥 Setting up RBAC roles..."
docker-compose exec -T web python manage.py setup_rbac || true

# Collect static files
echo "📦 Collecting static files..."
docker-compose exec -T web python manage.py collectstatic --noinput || true

echo "✅ HMS is ready!"
echo "🌐 Access the application at: http://localhost:8000"











