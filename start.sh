#!/bin/bash

# HMS Startup Script

echo "Starting Hospital Management System..."

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "Error: Docker is not running. Please start Docker and try again."
    exit 1
fi

# Build and start services
echo "Building and starting services..."
docker-compose up -d --build

# Wait for services to be ready
echo "Waiting for services to be ready..."
sleep 10

# Run migrations
echo "Running database migrations..."
docker-compose exec web python manage.py migrate

# Initialize system
echo "Initializing system..."
docker-compose exec web python manage.py init_hms

# Collect static files
echo "Collecting static files..."
docker-compose exec web python manage.py collectstatic --noinput

echo ""
echo "✅ HMS is now running!"
echo ""
echo "🌐 Web Interface: http://localhost:8000"
echo "🔧 Admin Panel: http://localhost:8000/admin"
echo "❤️  Health Check: http://localhost:8000/health/"
echo "📊 Metrics: http://localhost:8000/prometheus/"
echo "🗄️  MinIO Console: http://localhost:9001"
echo ""
echo "Default Admin Credentials:"
echo "Username: admin"
echo "Password: admin123"
echo ""
echo "To stop the services, run: docker-compose down"
