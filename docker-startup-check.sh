#!/bin/bash
# Docker Startup Verification Script
# This script verifies that all required environment variables and configurations are in place

set -e

echo "🔍 Checking Docker configuration..."

# Check if .env file exists
if [ ! -f .env ]; then
    echo "❌ ERROR: .env file not found!"
    echo "📝 Creating .env file from env.example..."
    if [ -f env.example ]; then
        cp env.example .env
        echo "✅ Created .env file. Please update it with your configuration."
    else
        echo "❌ ERROR: env.example not found. Cannot create .env file."
        exit 1
    fi
fi

# Check for required environment variables
echo "🔍 Checking required environment variables..."

REQUIRED_VARS=("DATABASE_URL" "SECRET_KEY")
MISSING_VARS=()

for var in "${REQUIRED_VARS[@]}"; do
    if ! grep -q "^${var}=" .env; then
        MISSING_VARS+=("$var")
    fi
done

if [ ${#MISSING_VARS[@]} -gt 0 ]; then
    echo "⚠️  WARNING: Missing required environment variables:"
    for var in "${MISSING_VARS[@]}"; do
        echo "   - $var"
    done
    echo ""
    echo "📝 Please add these to your .env file."
    echo "   For Docker, DATABASE_URL should be: postgresql://hms_user:hms_password@db:5432/hms_db"
    echo "   (This will be auto-overridden by docker-compose.yml)"
fi

# Check docker-compose.yml
if [ ! -f docker-compose.yml ]; then
    echo "❌ ERROR: docker-compose.yml not found!"
    exit 1
fi

echo "✅ Docker configuration files found"
echo ""
echo "🚀 Ready to start Docker services!"
echo ""
echo "To start all services:"
echo "  docker-compose up -d"
echo ""
echo "To view logs:"
echo "  docker-compose logs -f"
echo ""
echo "To stop services:"
echo "  docker-compose down"
echo ""
echo "To restart services:"
echo "  docker-compose restart"














