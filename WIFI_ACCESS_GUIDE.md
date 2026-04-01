# 🌐 WiFi Access Guide

Your HMS application is now configured to be accessible on your local WiFi network!

## ✅ Quick Start

### Option 1: Use the WiFi Server Script (Recommended)
```bash
START_WIFI_SERVER.bat
```

This script will:
- ✅ Find your WiFi IP address automatically
- ✅ Configure Windows Firewall (if needed)
- ✅ Start the server on all network interfaces
- ✅ Show you the exact URLs to use

### Option 2: Use Any Server Script
All server start scripts now support WiFi access:
- `START_WIFI_SERVER.bat` - Best for WiFi (includes firewall setup)
- `START_LOCAL_SERVER.bat` - Full setup with database checks
- `START_SERVER_NOW.bat` - Quick start
- `START_LOCAL_ONLY.bat` - Local mode

## 📱 Access from Other Devices

### Step 1: Find Your IP Address
When you start the server, it will automatically show your IP address. Look for a line like:
```
http://192.168.1.100:8000 (WiFi access)
```

### Step 2: Access from Phone/Tablet
1. Make sure your device is on the **SAME WiFi network**
2. Open a web browser on your device
3. Enter the IP address shown when starting the server (e.g., `http://192.168.1.100:8000`)
4. You should see the HMS login page!

## 🔧 Manual IP Lookup

If you need to find your IP address manually:

### Windows Command Prompt:
```bash
ipconfig
```
Look for "IPv4 Address" under your WiFi adapter (usually starts with `192.168.x.x` or `10.x.x.x`)

### PowerShell:
```powershell
Get-NetIPAddress -AddressFamily IPv4 | Where-Object {$_.InterfaceAlias -like "*Wi-Fi*"}
```

## 🛡️ Windows Firewall

The `START_WIFI_SERVER.bat` script will automatically configure Windows Firewall. If it doesn't work:

### Manual Firewall Configuration:
1. Open Windows Defender Firewall
2. Click "Advanced settings"
3. Click "Inbound Rules" → "New Rule"
4. Select "Port" → Next
5. Select "TCP" and enter port "8000"
6. Select "Allow the connection"
7. Apply to all profiles
8. Name it "HMS Port 8000"

### Or use PowerShell (as Administrator):
```powershell
netsh advfirewall firewall add rule name="HMS Port 8000" dir=in action=allow protocol=TCP localport=8000
```

## ✅ What Was Changed

1. **Server Binding**: All server scripts now use `0.0.0.0:8000` instead of `127.0.0.1:8000`
   - `0.0.0.0` means "listen on all network interfaces"
   - This allows access from other devices on your network

2. **IP Display**: Server scripts now automatically detect and display your WiFi IP address

3. **Django Settings**: Already configured with `PermissiveHostMiddleware` that allows private IP addresses in DEBUG mode

## 🐛 Troubleshooting

### Can't Access from Other Devices?

1. **Check Firewall**: Make sure Windows Firewall allows port 8000
   - Run `START_WIFI_SERVER.bat` (it configures firewall automatically)
   - Or manually allow port 8000 (see above)

2. **Same Network**: Make sure all devices are on the same WiFi network
   - Check WiFi network name matches

3. **Router Settings**: Some routers have "AP Isolation" or "Client Isolation" enabled
   - This prevents devices on the same WiFi from talking to each other
   - Disable this in your router settings if enabled

4. **IP Address**: Make sure you're using the correct IP address
   - The IP shown when starting the server is the one to use
   - IP addresses can change if you reconnect to WiFi

5. **Server Running**: Make sure the server is actually running
   - You should see "Starting development server at http://0.0.0.0:8000/"

### Still Not Working?

1. Try disabling Windows Firewall temporarily to test
2. Check if your antivirus is blocking the connection
3. Make sure you're using HTTP (not HTTPS) - e.g., `http://192.168.1.100:8000`
4. Try accessing from the same computer using the IP address instead of localhost

## 📝 Notes

- The server must be running for other devices to access it
- If you restart your computer or change WiFi networks, your IP address may change
- This configuration is for local development only
- For production, use proper security measures (HTTPS, authentication, etc.)




