# Quick HTTPS Setup for Network Camera Access

## Problem
Camera access requires HTTPS. Other machines on the network accessing via HTTP (`http://192.168.x.x:8000`) cannot use the camera.

## Solution: Use HTTPS

### Step 1: Generate Certificate (One-time setup)
```bash
python setup_https_simple.py
```

### Step 2: Start Server with HTTPS
**Option A: Use the batch file (Windows)**
```bash
START_HTTPS_SERVER.bat
```

**Option B: Manual command**
```bash
python manage.py runserver_plus --cert-file certs/server.crt --key-file certs/server.key 0.0.0.0:8000
```

### Step 3: Access from Network Machines

1. **Find your server's IP address:**
   - Windows: Run `ipconfig` → Look for IPv4 Address
   - Example: `192.168.2.216`

2. **Access from other machines:**
   - URL: `https://192.168.2.216:8000`
   - **Important**: Use `https://` (not `http://`)

3. **Accept Security Warning:**
   - Browser will show "Not Secure" warning (this is normal for self-signed certificates)
   - Click **"Advanced"** → **"Proceed to site"**
   - Camera will work after accepting

## Quick Reference

| Location | URL Format |
|----------|-----------|
| Same machine | `https://localhost:8000` |
| Network machines | `https://YOUR_IP:8000` |
| Example | `https://192.168.2.216:8000` |

## Troubleshooting

### "Connection Refused"
- Make sure server is running on `0.0.0.0:8000` (not just `127.0.0.1`)
- Check Windows Firewall allows port 8000

### "Certificate Error"
- This is **normal** for self-signed certificates
- Click "Advanced" → "Proceed to site"
- Or add exception in browser

### "Camera Still Not Working"
- Make sure you're using `https://` (not `http://`)
- Check browser console (F12) for errors
- Verify camera permissions are allowed

---

**Status**: ✅ Ready to use
**Certificate Location**: `certs/server.crt` and `certs/server.key`
