# 🔧 Troubleshoot Tablet Access

**Step-by-step guide to fix tablet access issues**

---

## 🔍 Current Status Check

Run this first:
```bash
test-network-access.bat
```

This will show you:
- ✅ If Docker is running
- ✅ If port is listening
- ✅ If firewall rule exists
- ✅ Your IP addresses

---

## 🚨 Most Common Issue: Firewall

**The firewall rule is missing!** This is why your tablet can't connect.

### Fix: Run as Administrator

1. **Right-click** `fix-network-access-admin.bat`
2. Select **"Run as administrator"**
3. Follow the prompts

This will add the Windows Firewall rule to allow port 8000.

---

## 📱 Step-by-Step Troubleshooting

### Step 1: Verify Same WiFi Network

**On your tablet:**
1. Go to WiFi settings
2. Check the network name (SSID)
3. Make sure it's the **SAME** network as your computer

**On your computer:**
1. Check WiFi network name
2. Should match your tablet

### Step 2: Find Correct IP Address

Your computer has multiple IP addresses. You need the **WiFi IP**.

**Most likely WiFi IPs:**
- `192.168.233.1` ← Try this first
- `192.168.64.1` ← Try this second
- `10.132.245.143` ← Try this third

**To find your WiFi IP:**
```bash
ipconfig
```
Look for the adapter named "Wi-Fi" or "Wireless" and find its IPv4 Address.

### Step 3: Test from Tablet

**On your tablet browser, try:**
- `http://192.168.233.1:8000`
- `http://192.168.64.1:8000`
- `http://10.132.245.143:8000`

**One of these should work!**

### Step 4: Check Firewall

**The firewall rule is missing!** This is the main issue.

**Fix:**
1. Run `fix-network-access-admin.bat` as Administrator
2. Or manually add firewall rule (see below)

### Step 5: Verify Docker

```bash
docker ps
```

Should show `chm-web-1` container running with port `0.0.0.0:8000->8000/tcp`

---

## 🛠️ Manual Firewall Fix

If the script doesn't work, add firewall rule manually:

### Method 1: Windows Defender Firewall GUI

1. Open **Windows Defender Firewall**
2. Click **"Advanced settings"**
3. Click **"Inbound Rules"** → **"New Rule"**
4. Select **"Port"** → Next
5. Select **"TCP"** and enter port **8000**
6. Select **"Allow the connection"**
7. Apply to **all profiles** (Domain, Private, Public)
8. Name it: **"HMS Docker Port 8000"**
9. Click Finish

### Method 2: PowerShell (Run as Admin)

```powershell
netsh advfirewall firewall add rule name="HMS Docker Port 8000" dir=in action=allow protocol=TCP localport=8000
```

### Method 3: Command Prompt (Run as Admin)

```cmd
netsh advfirewall firewall add rule name="HMS Docker Port 8000" dir=in action=allow protocol=TCP localport=8000
```

---

## 🔍 Advanced Troubleshooting

### Check if Port is Accessible

**From another computer on the same network:**
```bash
telnet YOUR_IP 8000
```

If it connects, the port is accessible. If it times out, firewall is blocking.

### Check Router Settings

Some routers have **AP Isolation** or **Client Isolation** enabled:
- This prevents devices on WiFi from talking to each other
- Check your router settings
- Disable AP Isolation if enabled

### Check Windows Network Profile

1. Open **Network and Sharing Center**
2. Check your network profile
3. Should be **"Private"** not **"Public"**
4. If Public, change to Private:
   - Settings → Network & Internet → Wi-Fi
   - Click your network
   - Set network profile to "Private"

### Temporarily Disable Firewall (Test Only)

**To test if firewall is the issue:**
1. Temporarily disable Windows Firewall
2. Try accessing from tablet
3. If it works, firewall was the issue
4. Re-enable firewall and add the rule properly

---

## ✅ Quick Fix Checklist

- [ ] Run `test-network-access.bat` to check status
- [ ] Run `fix-network-access-admin.bat` as Administrator
- [ ] Verify tablet is on same WiFi network
- [ ] Try all IP addresses shown
- [ ] Check router doesn't have AP Isolation
- [ ] Verify network profile is "Private"
- [ ] Restart Docker: `docker-compose restart web`

---

## 🎯 Most Likely Solution

**90% of the time, it's the firewall!**

1. **Right-click** `fix-network-access-admin.bat`
2. **Run as administrator**
3. **Try accessing from tablet again**

---

## 📞 Still Not Working?

### Check These:

1. **Docker logs:**
   ```bash
   docker-compose logs web
   ```
   Look for errors

2. **Test from computer:**
   ```bash
   curl http://192.168.233.1:8000/health/
   ```
   Should return HTML

3. **Check port binding:**
   ```bash
   netstat -an | findstr "8000"
   ```
   Should show `0.0.0.0:8000` LISTENING

4. **Ping test from tablet:**
   - Try pinging your computer's IP from tablet
   - If ping fails, network issue
   - If ping works but browser doesn't, firewall issue

---

## 🎉 Success Indicators

You'll know it's working when:
- ✅ Tablet browser shows HMS login page
- ✅ No "connection refused" or "timeout" errors
- ✅ Can access all pages from tablet
- ✅ Works on multiple devices

---

**Run `fix-network-access-admin.bat` as Administrator - that's usually the fix!**

