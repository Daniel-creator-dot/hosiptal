#!/bin/bash
# HMS PostgreSQL Setup Script for Production
# Run this on your Linux server

echo "╔════════════════════════════════════════════════════════════╗"
echo "║        HMS PostgreSQL Production Setup                     ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "⚠️  Please run as root (use sudo)"
    exit 1
fi

# Update system
echo "📦 Updating system packages..."
apt-get update -y
apt-get upgrade -y

# Install PostgreSQL
echo ""
echo "🐘 Installing PostgreSQL..."
apt-get install -y postgresql postgresql-contrib

# Install Python dependencies
echo ""
echo "🐍 Installing Python dependencies..."
apt-get install -y python3-pip python3-dev libpq-dev

# Install Redis (for caching)
echo ""
echo "📦 Installing Redis..."
apt-get install -y redis-server

# Start services
echo ""
echo "🚀 Starting services..."
systemctl start postgresql
systemctl enable postgresql
systemctl start redis-server
systemctl enable redis-server

# Create PostgreSQL database and user
echo ""
echo "🔧 Setting up PostgreSQL database..."
sudo -u postgres psql << EOF
-- Create database
CREATE DATABASE hms_production;

-- Create user
CREATE USER hms_user WITH PASSWORD 'change_this_password_123';

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE hms_production TO hms_user;

-- Grant schema privileges
\c hms_production
GRANT ALL ON SCHEMA public TO hms_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO hms_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO hms_user;

-- Exit
\q
EOF

# Configure PostgreSQL for production
echo ""
echo "⚙️  Optimizing PostgreSQL settings..."
cat >> /etc/postgresql/*/main/postgresql.conf << EOF

# HMS Production Optimizations
max_connections = 200
shared_buffers = 256MB
effective_cache_size = 1GB
maintenance_work_mem = 128MB
checkpoint_completion_target = 0.9
wal_buffers = 16MB
default_statistics_target = 100
random_page_cost = 1.1
effective_io_concurrency = 200
work_mem = 2MB
min_wal_size = 1GB
max_wal_size = 4GB
EOF

# Restart PostgreSQL
systemctl restart postgresql

echo ""
echo "✅ PostgreSQL setup complete!"
echo ""
echo "📝 Database Details:"
echo "   Database: hms_production"
echo "   User: hms_user"
echo "   Password: change_this_password_123"
echo "   Connection: postgresql://hms_user:change_this_password_123@localhost:5432/hms_production"
echo ""
echo "⚠️  IMPORTANT: Change the password after setup!"
echo ""
echo "Next steps:"
echo "1. Update your .env file with DATABASE_URL"
echo "2. Run: python migrate_to_postgresql.py"
echo "3. Run: python manage.py migrate"
echo "4. Run: python manage.py createsuperuser"
echo "5. Run: gunicorn hms.wsgi:application --bind 0.0.0.0:8000 --workers 4"
echo ""

















