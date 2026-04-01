# 🚀 Quick Fix: Access 192.168.0.105:8000

## ✅ What I've Done

1. ✅ Created firewall configuration script: `allow_port_8000_firewall.bat`
2. ✅ Created server startup script: `START_SERVER_NOW_SIMPLE.bat`
3. ✅ Verified your IP `192.168.0.105` is configured in Django settings

## 🔥 DO THIS NOW (2 Steps):

### Step 1: Configure Firewall (30 seconds)
**Right-click** → `allow_port_8000_firewall.bat` → **Run as administrator**

This allows incoming connections on port 8000.

### Step 2: Start the Server
**Double-click** → `START_SERVER_NOW_SIMPLE.bat`

This starts the server on `0.0.0.0:8000` (accessible from network).

## ✅ After Both Steps Complete

You can access from:
- **This computer:** http://127.0.0.1:8000/hms/login/
- **Other devices:** http://192.168.0.105:8000/hms/login/

## 🔍 Verify It's Working

1. **Check server is running:**
   - Look for "Starting development server at http://0.0.0.0:8000/" in the terminal

2. **Test local access:**
   - Open browser: http://127.0.0.1:8000/hms/
   - Should see the login page

3. **Test network access:**
   - From another device on same WiFi: http://192.168.0.105:8000/hms/
   - Should see the login page

## ⚠️ If Still Not Working

1. **Firewall not configured?**
   - Make sure you ran `allow_port_8000_firewall.bat` **as Administrator**
   - Check: `netsh advfirewall firewall show rule name="HMS Port 8000"`

2. **Server not starting?**
   - Check for errors in the terminal window
   - Make sure port 8000 is not already in use
   - Try: `netstat -an | findstr ":8000"`

3. **Can access locally but not from network?**
   - Firewall is blocking - configure it as admin
   - Both devices must be on same WiFi network
   - Try disabling Windows Firewall temporarily to test

---

**Your IP is configured correctly. Just need firewall + server running!**






