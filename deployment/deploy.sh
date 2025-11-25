#!/bin/bash
# HMS Quick Deployment Script
# Run this on your production server after uploading files

echo "╔════════════════════════════════════════════════════════════╗"
echo "║           HMS Production Deployment Script                 ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}⚠️  Please run with sudo${NC}"
    exit 1
fi

# Check if .env exists
if [ ! -f ".env" ]; then
    echo -e "${RED}❌ Error: .env file not found!${NC}"
    echo ""
    echo "Please create .env file first:"
    echo "   cp PRODUCTION_ENV_TEMPLATE.txt .env"
    echo "   nano .env  # Update with your values"
    exit 1
fi

echo -e "${GREEN}✅ Found .env file${NC}"
echo ""

# Create log directory
echo "📁 Creating log directory..."
mkdir -p /var/log/hms
chown www-data:www-data /var/log/hms
echo -e "${GREEN}   ✅ Log directory created${NC}"
echo ""

# Set up Python virtual environment
echo "🐍 Setting up Python environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
echo -e "${GREEN}   ✅ Python environment ready${NC}"
echo ""

# Run migrations
echo "🔄 Running database migrations..."
python manage.py migrate --noinput
echo -e "${GREEN}   ✅ Migrations complete${NC}"
echo ""

# Import data if export exists
if [ -f "hms_data_export.json" ]; then
    echo "📥 Importing data from SQLite export..."
    python import_to_postgresql.py
    echo -e "${GREEN}   ✅ Data imported${NC}"
    echo ""
fi

# Collect static files
echo "📦 Collecting static files..."
python manage.py collectstatic --noinput --clear
echo -e "${GREEN}   ✅ Static files collected${NC}"
echo ""

# Set permissions
echo "🔐 Setting permissions..."
chown -R www-data:www-data /var/www/hms
chmod -R 755 /var/www/hms
echo -e "${GREEN}   ✅ Permissions set${NC}"
echo ""

# Configure Supervisor
echo "⚙️  Configuring Supervisor..."
cp deployment/hms.conf /etc/supervisor/conf.d/
supervisorctl reread
supervisorctl update
echo -e "${GREEN}   ✅ Supervisor configured${NC}"
echo ""

# Configure Nginx
echo "🌐 Configuring Nginx..."
cp deployment/hms-nginx.conf /etc/nginx/sites-available/hms

echo -e "${YELLOW}⚠️  Update server_name in Nginx config:${NC}"
echo "   sudo nano /etc/nginx/sites-available/hms"
echo "   (Press Enter when done)"
read

ln -sf /etc/nginx/sites-available/hms /etc/nginx/sites-enabled/
nginx -t

if [ $? -eq 0 ]; then
    systemctl restart nginx
    echo -e "${GREEN}   ✅ Nginx configured and restarted${NC}"
else
    echo -e "${RED}   ❌ Nginx configuration error - please fix${NC}"
    exit 1
fi
echo ""

# Start HMS service
echo "🚀 Starting HMS service..."
supervisorctl start hms
echo -e "${GREEN}   ✅ HMS service started${NC}"
echo ""

# Show status
echo "=" * 70
echo -e "${GREEN}✅ DEPLOYMENT COMPLETE!${NC}"
echo "=" * 70
echo ""

echo "📊 Service Status:"
supervisorctl status hms
echo ""

echo "🌐 Your HMS is now running!"
echo ""
echo "Access your system at:"
echo "   http://your-server-ip/hms/"
echo ""
echo "🔐 Next steps:"
echo "1. Create superuser:"
echo "   python manage.py createsuperuser"
echo ""
echo "2. Set up SSL/HTTPS:"
echo "   sudo certbot --nginx -d your-domain.com"
echo ""
echo "3. Test your deployment:"
echo "   curl http://localhost/hms/"
echo ""
echo "📋 Useful commands:"
echo "   View logs:      sudo tail -f /var/log/hms/gunicorn.log"
echo "   Restart app:    sudo supervisorctl restart hms"
echo "   Stop app:       sudo supervisorctl stop hms"
echo "   Check status:   sudo supervisorctl status"
echo ""

















