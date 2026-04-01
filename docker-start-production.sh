#!/bin/bash
# Docker Production Start Script
# Run this on your Docker server after copying files

echo "================================================================"
echo "  Docker Production Setup"
echo "================================================================"
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo -e "${RED}[ERROR] Docker is not installed!${NC}"
    echo "Install Docker: https://docs.docker.com/get-docker/"
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}[ERROR] Docker Compose is not installed!${NC}"
    echo "Install Docker Compose: https://docs.docker.com/compose/install/"
    exit 1
fi

echo -e "${GREEN}[OK] Docker found: $(docker --version)${NC}"
echo -e "${GREEN}[OK] Docker Compose found: $(docker-compose --version)${NC}"
echo ""

# Check required files
echo "Checking required files..."
if [ ! -f "docker-compose.yml" ]; then
    echo -e "${RED}[ERROR] docker-compose.yml not found!${NC}"
    exit 1
fi

if [ ! -f "Dockerfile" ]; then
    echo -e "${RED}[ERROR] Dockerfile not found!${NC}"
    exit 1
fi

if [ ! -f "requirements.txt" ]; then
    echo -e "${RED}[ERROR] requirements.txt not found!${NC}"
    exit 1
fi

echo -e "${GREEN}[OK] All required files found${NC}"
echo ""

# Check if .env exists
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}[WARNING] .env file not found${NC}"
    echo "Creating .env from template if available..."
    if [ -f "env.example" ]; then
        cp env.example .env
        echo -e "${YELLOW}Please edit .env file with your production settings!${NC}"
    fi
    echo ""
fi

# Stop existing containers if running
echo "Stopping any existing containers..."
docker-compose down 2>/dev/null

# Build and start containers
echo ""
echo "Building Docker images..."
docker-compose build

if [ $? -ne 0 ]; then
    echo -e "${RED}[ERROR] Docker build failed!${NC}"
    exit 1
fi

echo ""
echo "Starting Docker containers..."
docker-compose up -d

if [ $? -ne 0 ]; then
    echo -e "${RED}[ERROR] Failed to start containers!${NC}"
    exit 1
fi

# Wait for services to be ready
echo ""
echo "Waiting for services to start..."
sleep 10

# Check service status
echo ""
echo "Service Status:"
docker-compose ps

# Run migrations
echo ""
echo "Running database migrations..."
docker-compose exec -T web python manage.py migrate --noinput

if [ $? -eq 0 ]; then
    echo -e "${GREEN}[OK] Migrations completed${NC}"
else
    echo -e "${YELLOW}[WARNING] Migrations may have failed - check logs${NC}"
fi

# Collect static files
echo ""
echo "Collecting static files..."
docker-compose exec -T web python manage.py collectstatic --noinput

echo ""
echo "================================================================"
echo -e "${GREEN}[SUCCESS] Docker setup complete!${NC}"
echo "================================================================"
echo ""
echo "Services are running:"
echo "  - Web Application: http://localhost:8000"
echo "  - MinIO Console: http://localhost:9001"
echo ""
echo "Useful commands:"
echo "  View logs:        docker-compose logs -f"
echo "  Stop services:    docker-compose down"
echo "  Restart service:  docker-compose restart web"
echo "  Create superuser: docker-compose exec web python manage.py createsuperuser"
echo ""
echo "See DOCKER_PRODUCTION_SETUP.md for complete documentation"
echo ""



