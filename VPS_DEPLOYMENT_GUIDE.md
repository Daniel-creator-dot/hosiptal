# VPS Deployment Guide - GitHub to VPS via PuTTY

## VPS Information
- **Hostname**: 45.8.225.73
- **User**: root
- **Password**: kaqA!S*eM9)q

## Step 1: Connect to VPS via PuTTY

1. **Download PuTTY** (if not installed):
   - Download from: https://www.putty.org/
   - Or use Windows Terminal with SSH

2. **Connect via PuTTY**:
   - Open PuTTY
   - Host Name: `45.8.225.73`
   - Port: `22`
   - Connection type: `SSH`
   - Click "Open"
   - Login as: `root`
   - Password: `kaqA!S*eM9)q`

## Step 2: Initial VPS Setup

Once connected, run these commands:

```bash
# Update system
apt update && apt upgrade -y

# Install essential tools
apt install -y git curl wget nano

# Install Python and pip
apt install -y python3 python3-pip python3-venv

# Install PostgreSQL (if using)
apt install -y postgresql postgresql-contrib

# Install Nginx (for web server)
apt install -y nginx

# Install Node.js (if needed for frontend)
curl -fsSL https://deb.nodesource.com/setup_18.x | bash -
apt install -y nodejs
```

## Step 3: Set Up SSH Key for GitHub (Recommended)

### Option A: Generate SSH Key on VPS

```bash
# Generate SSH key
ssh-keygen -t ed25519 -C "your_email@example.com"
# Press Enter to accept default location
# Press Enter for no passphrase (or set one)

# View public key
cat ~/.ssh/id_ed25519.pub
```

### Option B: Use Personal Access Token (Easier)

1. Go to GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)
2. Generate new token with `repo` permissions
3. Copy the token (you'll use it as password when cloning)

## Step 4: Clone Your Repository

```bash
# Navigate to web directory
cd /var/www
# Or create your project directory
mkdir -p /opt/hms
cd /opt/hms

# Clone repository
# Option 1: Using HTTPS (will prompt for GitHub username and token)
git clone https://github.com/jerry6193/primemed.git

# Option 2: Using SSH (if you set up SSH key)
# First add your SSH key to GitHub: Settings → SSH and GPG keys
git clone git@github.com:jerry6193/primemed.git

cd primemed
```

## Step 5: Set Up Python Environment

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

## Step 6: Configure Environment Variables

```bash
# Create .env file
nano .env
```

Add your environment variables:
```env
DEBUG=False
SECRET_KEY=your-secret-key-here
DATABASE_URL=postgresql://user:password@localhost:5432/hms_db
ALLOWED_HOSTS=45.8.225.73,yourdomain.com
```

## Step 7: Set Up Database

```bash
# Create PostgreSQL database
sudo -u postgres psql
CREATE DATABASE hms_db;
CREATE USER hms_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE hms_db TO hms_user;
\q

# Run migrations
python manage.py migrate
python manage.py collectstatic --noinput
```

## Step 8: Set Up Gunicorn (Production Server)

```bash
# Install gunicorn
pip install gunicorn

# Create gunicorn service file
sudo nano /etc/systemd/system/hms.service
```

Add this content:
```ini
[Unit]
Description=HMS Gunicorn daemon
After=network.target

[Service]
User=root
Group=www-data
WorkingDirectory=/opt/hms/primemed
Environment="PATH=/opt/hms/primemed/venv/bin"
ExecStart=/opt/hms/primemed/venv/bin/gunicorn --workers 3 --bind unix:/opt/hms/primemed/hms.sock hms.wsgi:application

[Install]
WantedBy=multi-user.target
```

```bash
# Start and enable service
sudo systemctl start hms
sudo systemctl enable hms
sudo systemctl status hms
```

## Step 9: Configure Nginx

```bash
# Create Nginx configuration
sudo nano /etc/nginx/sites-available/hms
```

Add this content:
```nginx
server {
    listen 80;
    server_name 45.8.225.73 yourdomain.com;

    location / {
        include proxy_params;
        proxy_pass http://unix:/opt/hms/primemed/hms.sock;
    }

    location /static/ {
        alias /opt/hms/primemed/staticfiles/;
    }

    location /media/ {
        alias /opt/hms/primemed/media/;
    }
}
```

```bash
# Enable site
sudo ln -s /etc/nginx/sites-available/hms /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

## Step 10: Set Up Auto-Deployment (Optional)

### Create Deployment Script

```bash
nano /opt/hms/deploy.sh
```

Add:
```bash
#!/bin/bash
cd /opt/hms/primemed
source venv/bin/activate
git pull origin main
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
sudo systemctl restart hms
echo "Deployment complete!"
```

```bash
# Make executable
chmod +x /opt/hms/deploy.sh
```

## Step 11: Set Up Firewall

```bash
# Allow SSH, HTTP, HTTPS
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw enable
```

## Step 12: Set Up SSL Certificate (Optional but Recommended)

```bash
# Install Certbot
apt install -y certbot python3-certbot-nginx

# Get SSL certificate
certbot --nginx -d yourdomain.com
```

## Quick Commands Reference

```bash
# Connect to VPS
ssh root@45.8.225.73

# Navigate to project
cd /opt/hms/primemed

# Pull latest changes
git pull origin main

# Activate virtual environment
source venv/bin/activate

# Restart services
sudo systemctl restart hms
sudo systemctl restart nginx

# View logs
sudo journalctl -u hms -f
sudo tail -f /var/log/nginx/error.log
```

## Security Recommendations

1. **Change default password** after first login
2. **Set up SSH key authentication** (disable password login)
3. **Use firewall** (ufw)
4. **Keep system updated**: `apt update && apt upgrade`
5. **Use strong SECRET_KEY** in .env
6. **Set DEBUG=False** in production
7. **Regular backups** of database

## Troubleshooting

### Can't connect via PuTTY
- Check if SSH port (22) is open
- Verify IP address is correct
- Check firewall settings

### Git clone fails
- Use Personal Access Token instead of password
- Or set up SSH key authentication

### Application not loading
- Check Gunicorn status: `sudo systemctl status hms`
- Check Nginx status: `sudo systemctl status nginx`
- Check logs: `sudo journalctl -u hms -n 50`

### Database connection errors
- Verify PostgreSQL is running: `sudo systemctl status postgresql`
- Check DATABASE_URL in .env file
- Verify database user permissions







