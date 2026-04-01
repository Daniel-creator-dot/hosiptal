# ✅ Server Starting - Network Access Setup

## 🚀 Server Status

The Django server is **starting** in the background on `0.0.0.0:8000`.

## ⚠️ CRITICAL: Configure Firewall (Required for Network Access)

**You MUST configure Windows Firewall before accessing from other devices:**

### Quick Method (Recommended):
1. **Right-click** `allow_port_8000_firewall.bat`
2. Select **"Run as administrator"**
3. Click **"Yes"** when prompted
4. Wait for "SUCCESS!" message

### Manual Method:
1. Press `Win + R`
2. Type: `wf.msc` → Enter
3. Click **"Inbound Rules"** → **"New Rule"**
4. Select **"Port"** → Next
5. Select **"TCP"** → Enter **"8000"** → Next
6. Select **"Allow the connection"** → Next
7. Check **all profiles** → Next
8. Name: **"HMS Port 8000"** → Finish

## 🌐 Access URLs

Once the server is fully started and firewall is configured:

### From This Computer:
- http://127.0.0.1:8000/hms/login/
- http://localhost:8000/hms/login/

### From Network Devices (Same WiFi):
- http://192.168.0.105:8000/hms/login/

## 🔍 Verify Server is Running

Open a new PowerShell window and run:
```powershell
netstat -an | Select-String "8000" | Select-String "LISTENING"
```

You should see:
```
TCP    0.0.0.0:8000           0.0.0.0:0              LISTENING
```

## ⏱️ Server Startup Time

The server may take 10-30 seconds to fully start, especially on first run.
Wait a moment, then try accessing:
- http://127.0.0.1:8000/hms/

## 📋 Next Steps

1. ✅ **Wait 10-30 seconds** for server to fully start
2. ✅ **Configure firewall** (run `allow_port_8000_firewall.bat` as admin)
3. ✅ **Test local access**: http://127.0.0.1:8000/hms/
4. ✅ **Test network access**: http://192.168.0.105:8000/hms/

## 🛑 To Stop the Server

If you need to stop the server:
1. Find the Python process running `runserver`
2. Or restart your computer
3. Or use Task Manager to end the Python process

---

**The server is starting! Configure the firewall now to enable network access.**






