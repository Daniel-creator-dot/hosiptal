# 🔧 Complete Fix: Network Access to 192.168.0.105:8000

## 🐛 Current Problem
Getting `ERR_CONNECTION_REFUSED` when accessing `http://192.168.0.105:8000`

## ✅ Solution - 3 Steps

### Step 1: Configure Windows Firewall ⚠️ REQUIRED

**This is the most common cause of connection refused errors!**

1. **Right-click** `allow_port_8000_firewall.bat`
2. Select **"Run as administrator"**
3. Click **"Yes"** when Windows asks for permission
4. Wait for "SUCCESS!" message

**OR Manual Method:**
1. Press `Win + R`
2. Type: `wf.msc` → Enter
3. Click **"Inbound Rules"** → **"New Rule"**
4. Select **"Port"** → Next
5. Select **"TCP"** → Enter **"8000"** → Next
6. Select **"Allow the connection"** → Next
7. Check **all profiles** (Domain, Private, Public) → Next
8. Name: **"HMS Port 8000"** → Finish

### Step 2: Start the Server

**Option A: Use the batch file (Recommended)**
- Double-click: `START_SERVER_FIXED.bat`
- Wait for "Starting development server at http://0.0.0.0:8000/"

**Option B: Manual start**
Open PowerShell in this folder and run:
```powershell
python manage.py runserver 0.0.0.0:8000
```

### Step 3: Verify It's Working

1. **Check server is listening:**
   ```powershell
   netstat -an | Select-String "8000" | Select-String "LISTENING"
   ```
   Should show: `TCP    0.0.0.0:8000           0.0.0.0:0              LISTENING`

2. **Test local access:**
   - Open browser: http://127.0.0.1:8000/hms/
   - Should see login page

3. **Test network access:**
   - From another device: http://192.168.0.105:8000/hms/
   - Should see login page

## 🔍 Troubleshooting

### Issue: "Port 8000 already in use"
**Solution:**
```powershell
# Find what's using port 8000
netstat -ano | Select-String "8000"
# Kill the process (replace PID with actual process ID)
taskkill /PID <PID> /F
```

### Issue: "Database connection failed"
**Solution:**
- Make sure PostgreSQL/Docker is running
- Check database settings in `hms/settings.py`
- Run: `python manage.py migrate`

### Issue: "Firewall configured but still can't connect"
**Solutions:**
1. Make sure you ran firewall script **as Administrator**
2. Restart the server after configuring firewall
3. Check Windows Defender isn't blocking Python
4. Try temporarily disabling firewall to test (then re-enable)

### Issue: "Can access locally but not from network"
**Solutions:**
1. Verify server is running on `0.0.0.0:8000` (not `127.0.0.1:8000`)
2. Check both devices are on same WiFi network
3. Verify firewall rule exists: `netsh advfirewall firewall show rule name="HMS Port 8000"`

## 📋 Quick Verification Commands

**Check if server is running:**
```powershell
Test-NetConnection -ComputerName 127.0.0.1 -Port 8000
```

**Check firewall rule:**
```powershell
netsh advfirewall firewall show rule name="HMS Port 8000"
```

**Check what's listening on port 8000:**
```powershell
netstat -ano | Select-String "8000" | Select-String "LISTENING"
```

## ✅ Expected Result

After completing all steps:
- ✅ Server running on `0.0.0.0:8000`
- ✅ Firewall allows port 8000
- ✅ Accessible from http://192.168.0.105:8000
- ✅ Accessible from http://127.0.0.1:8000

---

**Most common issue: Firewall not configured! Make sure Step 1 is done as Administrator.**






