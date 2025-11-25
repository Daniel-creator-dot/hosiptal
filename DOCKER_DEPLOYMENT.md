# Docker Deployment Guide - HMS with Network Access

This guide explains how to deploy the HMS application using Docker with CSRF fixes and local network access.

## 🚀 Quick Start

### Windows
```bash
docker-start.bat
```

### Linux/Mac
```bash
chmod +x docker-start.sh
./docker-start.sh
```

## 📋 Prerequisites

1. **Docker Desktop** installed and running
2. **Docker Compose** (included with Docker Desktop)
3. **Port 8000** available (or change in docker-compose.yml)

## 🔧 Configuration

### Network IP Addresses

The Docker configuration includes your detected network IPs:
- `192.168.2.97` (Primary WiFi)
- `192.168.233.1`
- `192.168.64.1`
- `172.20.112.1`

### Updating IP Addresses

If your network IP changes, update `docker-compose.yml`:

```yaml
environment:
  - ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0,YOUR_IP_HERE
  - CSRF_TRUSTED_ORIGINS=http://localhost:8000,http://127.0.0.1:8000,http://YOUR_IP_HERE:8000
```

## 🌐 Accessing the Application

### Local Access
- **URL**: http://localhost:8000
- Works on the same machine running Docker

### Network Access (WiFi)
- **URL**: http://192.168.2.97:8000 (or your detected IP)
- Accessible from any device on the same WiFi network
- Mobile phones, tablets, other computers can connect

## 🔐 CSRF Configuration

The CSRF fixes are automatically applied:

1. **CSRF_COOKIE_HTTPONLY = False** - Allows JavaScript to read token
2. **CSRF_TRUSTED_ORIGINS** - Includes all network IPs
3. **ALLOWED_HOSTS** - Includes all network IPs
4. **JavaScript helpers** - Automatically inject CSRF tokens in forms

## 📦 Docker Services

The setup includes:

- **web** - Django application (port 8000)
- **db** - PostgreSQL database (port 5432)
- **redis** - Redis cache (port 6379)
- **celery** - Background task worker
- **celery-beat** - Scheduled task scheduler
- **minio** - Object storage (ports 9000, 9001)

## 🛠️ Common Commands

### Start Services
```bash
docker-compose up -d
```

### View Logs
```bash
docker-compose logs -f web
```

### Stop Services
```bash
docker-compose down
```

### Rebuild After Code Changes
```bash
docker-compose up -d --build
```

### Access Django Shell
```bash
docker-compose exec web python manage.py shell
```

### Run Migrations
```bash
docker-compose exec web python manage.py migrate
```

### Create Superuser
```bash
docker-compose exec web python manage.py createsuperuser
```

## 🔍 Troubleshooting

### CSRF Errors Still Occurring

1. **Check IP addresses**: Ensure your current IP is in `CSRF_TRUSTED_ORIGINS`
2. **Clear browser cache**: Old cookies may cause issues
3. **Check Docker logs**: `docker-compose logs web`
4. **Verify network**: Ensure devices are on the same WiFi network

### Can't Access from Network

1. **Check firewall**: Windows Firewall may block port 8000
2. **Verify IP**: Use `ipconfig` (Windows) or `ifconfig` (Linux/Mac) to get your IP
3. **Check Docker network**: Ensure `network_mode: bridge` is set
4. **Test locally first**: Verify http://localhost:8000 works

### Port Already in Use

If port 8000 is taken, change it in `docker-compose.yml`:

```yaml
ports:
  - "8080:8000"  # Use 8080 externally, 8000 internally
```

Then access at http://YOUR_IP:8080

## 🔒 Security Notes

- **Development Mode**: Currently set to `DEBUG=1` for easier troubleshooting
- **Production**: Set `DEBUG=0` and configure proper SSL certificates
- **CSRF_COOKIE_SECURE**: Automatically set based on DEBUG mode
- **Network Access**: Only accessible on local network (not exposed to internet)

## 📱 Mobile Access

To access from mobile devices:

1. Connect phone/tablet to the same WiFi network
2. Find your computer's IP address (shown in startup script)
3. Open browser and go to: `http://YOUR_IP:8000`
4. Example: `http://192.168.2.97:8000`

## 🔄 Updating the Application

After making code changes:

```bash
# Rebuild and restart
docker-compose up -d --build

# Or just restart if no dependency changes
docker-compose restart web
```

## 📊 Health Checks

All services include health checks. View status:

```bash
docker-compose ps
```

## 🎯 Next Steps

1. Run migrations: `docker-compose exec web python manage.py migrate`
2. Create admin user: `docker-compose exec web python manage.py createsuperuser`
3. Access admin: http://YOUR_IP:8000/admin/
4. Access HMS: http://YOUR_IP:8000/hms/

---

**Need Help?** Check the logs: `docker-compose logs -f`






