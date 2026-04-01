# 🚨 URGENT: Start Server to Fix Connection Refused

## ✅ What I've Done
- ✅ Verified Django configuration is correct
- ✅ Verified your IP `192.168.0.105` is configured
- ✅ Created startup scripts

## 🔥 DO THIS NOW (2 Steps):

### Step 1: Configure Firewall (30 seconds) ⚠️ CRITICAL
**Right-click** → `allow_port_8000_firewall.bat` → **Run as administrator**

**This is REQUIRED!** Without this, the server won't accept network connections.

### Step 2: Start the Server
**Double-click** → `START_SERVER_FIXED.bat`

A new window will open showing the server starting. Look for:
```
Starting development server at http://0.0.0.0:8000/
```

## ✅ After Both Steps

**Test local access first:**
- Open browser: http://127.0.0.1:8000/hms/
- Should see login page

**Then test network access:**
- From another device: http://192.168.0.105:8000/hms/
- Should see login page

## 🔍 If Server Doesn't Start

**Check for errors in the server window:**
- Database connection errors?
- Port already in use?
- Missing dependencies?

**Common fixes:**
1. **Port in use:** Close other Python processes or use different port
2. **Database error:** Make sure PostgreSQL/Docker is running
3. **Import error:** Run `pip install -r requirements.txt`

## 📋 Quick Test Commands

**After starting server, verify it's running:**
```powershell
netstat -an | Select-String "8000" | Select-String "LISTENING"
```

Should show:
```
TCP    0.0.0.0:8000           0.0.0.0:0              LISTENING
```

---

**The server MUST be running AND firewall MUST be configured for network access to work!**






