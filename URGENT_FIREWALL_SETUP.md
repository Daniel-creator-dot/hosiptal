# ⚠️ URGENT: Firewall Configuration Required

## ✅ Server Status
The Django server is **starting** in the background on `0.0.0.0:8000`.

## 🔥 CRITICAL: Configure Firewall NOW

The server won't be accessible from other devices until you configure Windows Firewall.

### Quick Fix (30 seconds):

1. **Right-click** `allow_port_8000_firewall.bat`
2. Select **"Run as administrator"**
3. Click **"Yes"** when Windows asks for permission
4. Wait for "SUCCESS!" message

### Alternative: Manual Setup

1. Press `Win + R`
2. Type: `wf.msc` and press Enter
3. Click **"Inbound Rules"** → **"New Rule"**
4. Select **"Port"** → Next
5. Select **"TCP"** → Enter **"8000"** → Next
6. Select **"Allow the connection"** → Next
7. Check **all three boxes** (Domain, Private, Public) → Next
8. Name: **"HMS Port 8000"** → Finish

## ✅ After Firewall Setup

You can access:
- **From this computer:** http://127.0.0.1:8000
- **From network devices:** http://192.168.0.105:8000

## 🔍 Verify Server is Running

Open a new terminal and run:
```powershell
netstat -an | Select-String ":8000"
```

You should see:
```
TCP    0.0.0.0:8000           0.0.0.0:0              LISTENING
```

---

**The server is starting, but you MUST configure the firewall for network access!**






