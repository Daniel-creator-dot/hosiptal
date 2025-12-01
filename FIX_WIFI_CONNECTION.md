# 🔧 Fix WiFi Connection - Quick Guide

## ✅ What I Fixed

1. **Updated IP Address**: Changed from `192.168.0.102` to `192.168.0.100` (your current IP)
2. **Updated docker-compose.yml**: Added your current IP to CSRF_TRUSTED_ORIGINS
3. **Updated firewall script**: Now shows the correct IP address
4. **Restarted web service**: Applied the new configuration

## 🚨 IMPORTANT: Configure Windows Firewall

**You MUST run the firewall script as Administrator to allow network connections!**

### Option 1: Run the Script (Easiest)
1. Right-click `allow_port_8000_firewall.bat`
2. Select **"Run as administrator"**
3. Click **"Yes"** when prompted
4. Wait for it to complete

### Option 2: Manual Firewall Configuration
1. Open **Windows Defender Firewall**
2. Click **"Advanced Settings"**
3. Click **"Inbound Rules"** → **"New Rule"**
4. Select **"Port"** → Next
5. Select **"TCP"** → Enter **"8000"** → Next
6. Select **"Allow the connection"** → Next
7. Check **all profiles** (Domain, Private, Public) → Next
8. Name: **"HMS Docker Port 8000"** → Finish

## 🌐 Access Your App

After configuring the firewall, access your app from:

- **Local (same computer)**: http://localhost:8000
- **Network (WiFi devices)**: http://192.168.0.100:8000

## 📱 Test from Another Device

1. Make sure the device is on the **same WiFi network**
2. Open a browser
3. Go to: **http://192.168.0.100:8000**
4. You should see the HMS login page

## ❓ About the Port Change

You mentioned changing the port, but I see port **8000** is still configured. 

**If you changed to a different port:**
- Let me know which port you want to use
- I'll update docker-compose.yml and the firewall script
- We'll need to restart the services

**If you're still using port 8000:**
- Just run the firewall script as administrator
- Everything else is already configured!

## 🔍 Troubleshooting

**Can't connect from other devices?**
1. ✅ Make sure firewall script was run as administrator
2. ✅ Verify devices are on the same WiFi network
3. ✅ Check router settings (disable "AP Isolation" if enabled)
4. ✅ Try accessing from the same computer first: http://192.168.0.100:8000

**Connection refused?**
- Firewall is blocking it → Run the firewall script

**400 Bad Request?**
- IP not in ALLOWED_HOSTS → Already fixed, restart services if needed

**Still not working?**
- Check if Docker is running: `docker-compose ps`
- View logs: `docker-compose logs web`
- Test local first: http://localhost:8000









