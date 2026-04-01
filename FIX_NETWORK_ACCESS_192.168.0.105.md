# 🔧 Fix Network Access - 192.168.0.105

## 🐛 Problem
Getting `ERR_CONNECTION_REFUSED` when trying to access:
```
http://192.168.0.105:8000
```

## ✅ Solution

### Step 1: Configure Windows Firewall (REQUIRED)

**Option A: Run the firewall script as Administrator**
1. Right-click `allow_port_8000_firewall.bat`
2. Select **"Run as administrator"**
3. Click "Yes" when prompted
4. Wait for "SUCCESS!" message

**Option B: Manual Firewall Configuration**
1. Press `Win + R`, type `wf.msc`, press Enter
2. Click **"Inbound Rules"** → **"New Rule"**
3. Select **"Port"** → Next
4. Select **"TCP"** → Enter **"8000"** → Next
5. Select **"Allow the connection"** → Next
6. Check **all profiles** (Domain, Private, Public) → Next
7. Name: **"HMS Port 8000"** → Finish

### Step 2: Start the Server

**Double-click:** `START_NETWORK_SERVER.bat`

This will:
- ✅ Check if port 8000 is available
- ✅ Start the server on `0.0.0.0:8000` (accessible from network)
- ✅ Show you all available IP addresses

### Step 3: Access from Other Devices

Once the server is running, you can access it from:

**From this computer:**
- http://127.0.0.1:8000
- http://localhost:8000
- http://192.168.0.105:8000

**From other devices on the same network:**
- http://192.168.0.105:8000

## 🔍 Verification

### Check if Server is Running
```powershell
netstat -an | findstr ":8000"
```

You should see:
```
TCP    0.0.0.0:8000           0.0.0.0:0              LISTENING
```

### Check Firewall Rule
```powershell
netsh advfirewall firewall show rule name="HMS Port 8000"
```

## ⚠️ Common Issues

### Issue 1: "Port 8000 is already in use"
**Solution:** Stop the existing server (Ctrl+C in that window) or use a different port.

### Issue 2: Still getting connection refused after firewall setup
**Solution:** 
1. Make sure you ran the firewall script **as Administrator**
2. Restart the server after configuring firewall
3. Check Windows Firewall is not blocking Python/Django

### Issue 3: Can access locally but not from network
**Solution:**
1. Verify server is running on `0.0.0.0:8000` (not `127.0.0.1:8000`)
2. Check both devices are on the same network
3. Try disabling Windows Firewall temporarily to test (then re-enable)

## 📋 Quick Start Commands

**Start server:**
```bash
python manage.py runserver 0.0.0.0:8000
```

**Check server status:**
```bash
netstat -an | findstr ":8000"
```

**Test connection:**
```bash
curl http://192.168.0.105:8000
```

## ✅ Configuration Status

Your IP `192.168.0.105` is already configured in:
- ✅ `ALLOWED_HOSTS` in `hms/settings.py`
- ✅ `CSRF_TRUSTED_ORIGINS` in `hms/settings.py`

You just need to:
1. ✅ Configure firewall (one-time setup)
2. ✅ Start the server

---

**After completing these steps, you should be able to access:**
```
http://192.168.0.105:8000/hms/login/
```






