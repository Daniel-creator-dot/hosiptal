# 🔧 Connection Troubleshooting Guide

## ✅ Server Status
- **Web Server**: Running on port 8000
- **Database**: Connected and working
- **Redis**: Healthy
- **All Services**: Operational

## 🌐 Access URLs

### Local Access:
- **Main URL**: http://localhost:8000
- **Login Page**: http://localhost:8000/hms/login/
- **Dashboard**: http://localhost:8000/hms/

### Network Access (from other devices):
- **Your IP**: http://192.168.0.119:8000
- **Login Page**: http://192.168.0.119:8000/hms/login/

## 🔍 Common Connection Issues & Solutions

### 1. **Browser Can't Connect**
**Symptoms**: "This site can't be reached" or "Connection refused"

**Solutions**:
- ✅ Clear browser cache (Ctrl+Shift+Delete)
- ✅ Try a different browser (Chrome, Firefox, Edge)
- ✅ Try incognito/private mode
- ✅ Check if Windows Firewall is blocking
- ✅ Restart Docker Desktop

### 2. **Network Access Not Working**
**Symptoms**: Can access from localhost but not from other devices

**Solutions**:
1. **Configure Firewall** (Run as Administrator):
   ```batch
   allow_port_8000_firewall.bat
   ```

2. **Verify Port is Open**:
   ```powershell
   netstat -ano | findstr :8000
   ```
   Should show: `0.0.0.0:8000` (listening on all interfaces)

3. **Check Windows Firewall**:
   ```powershell
   netsh advfirewall firewall show rule name="HMS Docker Port 8000"
   ```

### 3. **Server Not Responding**
**Symptoms**: Page loads but shows error or times out

**Solutions**:
1. **Check Container Status**:
   ```powershell
   docker-compose ps
   ```
   Web container should show: `Up (healthy)`

2. **View Logs**:
   ```powershell
   docker-compose logs --tail=50 web
   ```

3. **Restart Services**:
   ```powershell
   docker-compose restart web
   ```

### 4. **Database Connection Errors**
**Symptoms**: "Database connection failed" or similar errors

**Solutions**:
1. **Check Database**:
   ```powershell
   docker-compose exec web python manage.py check --database default
   ```

2. **Run Migrations** (if needed):
   ```powershell
   docker-compose exec web python manage.py migrate
   ```

## 🚀 Quick Fixes

### Restart Everything:
```powershell
docker-compose down
docker-compose up -d
```

### Check Health:
```powershell
# Test from inside container
docker-compose exec web curl http://localhost:8000/health/

# Test from host
Invoke-WebRequest -Uri http://localhost:8000/health/
```

### View Real-time Logs:
```powershell
docker-compose logs -f web
```

## 📋 Verification Checklist

- [ ] Docker Desktop is running
- [ ] All containers are up: `docker-compose ps`
- [ ] Port 8000 is listening: `netstat -ano | findstr :8000`
- [ ] Health check passes: http://localhost:8000/health/
- [ ] Can access login page: http://localhost:8000/hms/login/
- [ ] Firewall rule exists (for network access)
- [ ] Browser cache cleared
- [ ] No proxy/VPN interfering

## 🆘 Still Not Working?

1. **Check Docker Desktop**: Make sure it's running
2. **Check Port Conflicts**: Another app might be using port 8000
3. **Check Antivirus**: May be blocking Docker
4. **Check Logs**: `docker-compose logs web` for errors
5. **Try Different Port**: Edit `docker-compose.yml` port mapping

## 📞 Quick Access Commands

```powershell
# Start services
docker-compose up -d

# Stop services
docker-compose down

# Restart web server
docker-compose restart web

# View logs
docker-compose logs -f web

# Check status
docker-compose ps

# Access shell in container
docker-compose exec web bash
```








