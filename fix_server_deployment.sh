#!/bin/bash
# Fix common server deployment errors
# Run this script on your server after deployment

set -e  # Exit on error

echo "================================================================"
echo "  SERVER DEPLOYMENT ERROR FIXER"
echo "================================================================"
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Check if virtual environment exists
if [ -d "venv" ]; then
    echo -e "${GREEN}[OK]${NC} Virtual environment found"
    source venv/bin/activate
elif [ -d ".venv" ]; then
    echo -e "${GREEN}[OK]${NC} Virtual environment found"
    source .venv/bin/activate
else
    echo -e "${YELLOW}[WARNING]${NC} No virtual environment found, using system Python"
fi

echo ""
echo "================================================================"
echo "  Step 1: Creating Required Directories"
echo "================================================================"
echo ""

# Create directories
mkdir -p staticfiles
mkdir -p media
mkdir -p media/patient_profiles
mkdir -p media/documents
mkdir -p media/uploads
mkdir -p logs

echo -e "${GREEN}[OK]${NC} Directories created"

echo ""
echo "================================================================"
echo "  Step 2: Fixing File Permissions"
echo "================================================================"
echo ""

# Fix permissions (if not root, use sudo)
if [ "$EUID" -eq 0 ]; then
    chown -R www-data:www-data staticfiles media logs 2>/dev/null || true
    chmod -R 755 staticfiles media logs
    chmod -R 644 staticfiles/* 2>/dev/null || true
    chmod -R 644 media/* 2>/dev/null || true
    echo -e "${GREEN}[OK]${NC} Permissions fixed (as root)"
else
    chmod -R 755 staticfiles media logs 2>/dev/null || true
    echo -e "${GREEN}[OK]${NC} Permissions fixed (as user)"
    echo -e "${YELLOW}[INFO]${NC} If you need to change ownership, run: sudo chown -R www-data:www-data staticfiles media logs"
fi

echo ""
echo "================================================================"
echo "  Step 3: Checking Settings"
echo "================================================================"
echo ""

# Check .env file
if [ ! -f ".env" ]; then
    echo -e "${RED}[ERROR]${NC} .env file not found!"
    echo "Creating .env from template..."
    if [ -f "env.example" ]; then
        cp env.example .env
        echo -e "${YELLOW}[WARNING]${NC} Please edit .env file with your settings!"
    else
        echo -e "${RED}[ERROR]${NC} env.example not found. Please create .env manually."
        exit 1
    fi
else
    echo -e "${GREEN}[OK]${NC} .env file exists"
fi

echo ""
echo "================================================================"
echo "  Step 4: Checking Database Connection"
echo "================================================================"
echo ""

python manage.py check --database default 2>&1 | grep -q "System check identified" && {
    echo -e "${GREEN}[OK]${NC} Database connection successful"
} || {
    echo -e "${RED}[ERROR]${NC} Database connection failed!"
    echo "Please check:"
    echo "  1. DATABASE_URL in .env file"
    echo "  2. PostgreSQL is running"
    echo "  3. Database credentials are correct"
    exit 1
}

echo ""
echo "================================================================"
echo "  Step 5: Running Database Migrations"
echo "================================================================"
echo ""

python manage.py migrate --noinput
echo -e "${GREEN}[OK]${NC} Migrations completed"

echo ""
echo "================================================================"
echo "  Step 6: Collecting Static Files"
echo "================================================================"
echo ""

python manage.py collectstatic --noinput --clear
echo -e "${GREEN}[OK]${NC} Static files collected"

echo ""
echo "================================================================"
echo "  Step 7: Verifying Installation"
echo "================================================================"
echo ""

# Run Django check
python manage.py check --deploy 2>&1 | grep -v "WARNINGS:" | grep -v "security.W" || true

echo ""
echo "================================================================"
echo -e "${GREEN}  DEPLOYMENT FIX COMPLETE!${NC}"
echo "================================================================"
echo ""
echo "Next steps:"
echo "  1. Configure your web server (Nginx/Apache)"
echo "  2. Set up process manager (Supervisor/systemd)"
echo "  3. Configure SSL/HTTPS"
echo "  4. Set DEBUG=False in .env for production"
echo "  5. Generate secure SECRET_KEY"
echo ""
echo "For detailed instructions, see:"
echo "  - PRODUCTION_DEPLOYMENT_GUIDE.md"
echo "  - DOCKER_PRODUCTION_SETUP.md"
echo ""



