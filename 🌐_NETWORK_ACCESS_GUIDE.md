# 🌐 Network Access Guide - Access HMS from Other Devices

**Make your HMS accessible from phones, tablets, and other computers on your WiFi network!**

---

## ✅ Quick Setup

### Windows:
```bash
enable-network-access.bat
```

This script will:
- ✅ Get your local IP address
- ✅ Check Docker is running
- ✅ Configure Windows Firewall
- ✅ Show you the access URLs

---

## 🔍 Find Your IP Address

### Method 1: Using the Script
```bash
enable-network-access.bat
```

### Method 2: Manual
```bash
ipconfig
```
Look for "IPv4 Address" under your WiFi adapter (usually starts with 192.168.x.x)

### Method 3: PowerShell
```powershell
Get-NetIPAddress -AddressFamily IPv4 | Where-Object {$_.InterfaceAlias -like "*Wi-Fi*" -or $_.InterfaceAlias -like "*Ethernet*"} | Select-Object IPAddress
```

---

## 🌐 Access URLs

### From This Computer:
- http://localhost:8000
- http://127.0.0.1:8000

### From Other Devices (Replace with YOUR IP):
- http://192.168.233.1:8000 (Example - use your actual IP)
- http://YOUR_IP_ADDRESS:8000

---

## 🔧 Configuration

### Docker is Already Configured ✅

Your `docker-compose.yml` already has:
```yaml
ports:
  - "0.0.0.0:8000:8000"  # ✅ This allows network access
```

### Django Settings ✅

Your `compose.env` has:
```env
ALLOWED_HOSTS=*  # ✅ This allows all hosts
```

---

## 🛡️ Windows Firewall

### Automatic (Recommended):
```bash
enable-network-access.bat
```

### Manual:
1. Open Windows Defender Firewall
2. Click "Advanced settings"
3. Click "Inbound Rules" → "New Rule"
4. Select "Port" → Next
5. Select "TCP" and enter port "8000"
6. Select "Allow the connection"
7. Apply to all profiles
8. Name it "HMS Docker Port 8000"

### Or use PowerShell:
```powershell
netsh advfirewall firewall add rule name="HMS Docker Port 8000" dir=in action=allow protocol=TCP localport=8000
```

---

## 📱 Access from Mobile Devices

### Steps:
1. **Make sure your phone/tablet is on the same WiFi network**
2. **Find your computer's IP address** (use the script above)
3. **Open browser on your device**
4. **Go to**: `http://YOUR_IP:8000`
   - Example: `http://192.168.233.1:8000`
5. **You should see the HMS login page!**

### Troubleshooting Mobile Access:

**Can't connect?**
- ✅ Check both devices are on the same WiFi
- ✅ Check Windows Firewall allows port 8000
- ✅ Try disabling Windows Firewall temporarily to test
- ✅ Make sure Docker container is running: `docker ps`
- ✅ Try accessing from another computer first

**Connection refused?**
- Check Docker is running: `docker ps`
- Restart containers: `docker-compose restart web`
- Check logs: `docker-compose logs web`

**Page loads but shows error?**
- Check ALLOWED_HOSTS includes your IP or is set to `*`
- Check Django settings allow the host

---

## 🖥️ Access from Other Computers

### Same Network:
1. Find your computer's IP address
2. On the other computer, open browser
3. Go to: `http://YOUR_IP:8000`
4. Should work immediately!

### Different Network (Advanced):
- Use port forwarding on your router
- Or use a VPN/tunneling service
- Or deploy to a cloud service (Render, Heroku, etc.)

---

## 🔍 Verify Network Access

### Test from Command Line:
```bash
# From another device on the network
curl http://YOUR_IP:8000/health/
```

### Test from Browser:
- Open browser on another device
- Go to: `http://YOUR_IP:8000`
- Should see the HMS homepage or login page

---

## 🚨 Security Notes

### For Development (Current Setup):
- ✅ `ALLOWED_HOSTS=*` allows all hosts (OK for local network)
- ✅ `DEBUG=True` shows detailed errors (OK for development)
- ⚠️ Only accessible on your local network (WiFi)

### For Production:
- ❌ Change `ALLOWED_HOSTS` to specific domains
- ❌ Set `DEBUG=False`
- ❌ Use HTTPS/SSL
- ❌ Set up proper authentication
- ❌ Use a reverse proxy (nginx)
- ❌ Deploy to a proper server

---

## 📋 Quick Commands

### Check if accessible:
```bash
# From another device
ping YOUR_IP_ADDRESS
curl http://YOUR_IP:8000/health/
```

### Restart services:
```bash
docker-compose restart web
```

### View logs:
```bash
docker-compose logs web
```

### Check Docker status:
```bash
docker ps
```

### Check port binding:
```bash
netstat -an | findstr 8000
```

---

## 🎯 Common IP Addresses

Your IP will typically be:
- `192.168.1.x` (most home routers)
- `192.168.0.x` (some routers)
- `192.168.233.x` (some networks)
- `10.0.0.x` (some networks)

**Use the script to find your exact IP!**

---

## ✅ Checklist

- [ ] Docker is running
- [ ] Web container is running (`docker ps`)
- [ ] Port 8000 is bound to `0.0.0.0` (check docker-compose.yml)
- [ ] Windows Firewall allows port 8000
- [ ] ALLOWED_HOSTS includes `*` or your IP
- [ ] You know your local IP address
- [ ] Other devices are on the same WiFi network
- [ ] You can access from another device

---

## 🆘 Troubleshooting

### "Connection refused" or "Can't connect"
1. Check Docker is running: `docker ps`
2. Check container is running: `docker-compose ps`
3. Check firewall: `netsh advfirewall firewall show rule name="HMS Docker Port 8000"`
4. Restart containers: `docker-compose restart web`

### "Invalid Host Header" or Django error
1. Check ALLOWED_HOSTS in `.env` or `compose.env`
2. Should be `ALLOWED_HOSTS=*` for local network
3. Restart web container: `docker-compose restart web`

### Can access from computer but not phone
1. Make sure phone is on same WiFi
2. Check Windows Firewall allows port 8000
3. Try disabling firewall temporarily to test
4. Check router doesn't have AP isolation enabled

### Port already in use
1. Check what's using port 8000: `netstat -ano | findstr 8000`
2. Stop the service using port 8000
3. Or change port in docker-compose.yml: `"8001:8000"`

---

## 🎉 Success!

Once configured, you can access HMS from:
- ✅ Your computer: `http://localhost:8000`
- ✅ Your phone: `http://YOUR_IP:8000`
- ✅ Your tablet: `http://YOUR_IP:8000`
- ✅ Other computers: `http://YOUR_IP:8000`

**All on the same WiFi network!**

---

**Need help?** Run `enable-network-access.bat` and follow the instructions!

