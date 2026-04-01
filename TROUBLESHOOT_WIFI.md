# 🔧 WiFi Connection Troubleshooting Guide

If your devices still can't connect, follow these steps:

## Step 1: Run Diagnostics

Run the diagnostic tool to identify the issue:
```bash
DIAGNOSE_WIFI_ACCESS.bat
```

This will check:
- ✅ Python and Django installation
- ✅ Network IP addresses
- ✅ Windows Firewall configuration
- ✅ Port 8000 availability
- ✅ Administrator privileges

## Step 2: Fix Windows Firewall

**Most common issue:** Windows Firewall is blocking port 8000.

### Quick Fix:
1. Right-click `FIX_FIREWALL_NOW.bat`
2. Select "Run as administrator"
3. Click "Yes" when prompted

This will add a firewall rule to allow port 8000.

### Manual Fix:
1. Open Windows Defender Firewall
2. Click "Advanced settings"
3. Click "Inbound Rules" → "New Rule"
4. Select "Port" → Next
5. Select "TCP" and enter port "8000"
6. Select "Allow the connection"
7. Check all profiles (Domain, Private, Public)
8. Name it "HMS Port 8000"
9. Click Finish

### PowerShell (as Administrator):
```powershell
netsh advfirewall firewall add rule name="HMS Port 8000" dir=in action=allow protocol=TCP localport=8000
```

## Step 3: Verify Server is Running Correctly

1. Start the server using `START_WIFI_SERVER.bat`
2. Look for this message: `Starting development server at http://0.0.0.0:8000/`
   - ✅ If you see `0.0.0.0:8000` - server is configured correctly
   - ❌ If you see `127.0.0.1:8000` - server is NOT accessible from network

3. The server should show your IP address, for example:
   ```
   http://192.168.1.100:8000 (WiFi access)
   ```

## Step 4: Test from This Computer First

Before testing from other devices, test from the same computer:

1. Open a web browser
2. Try: `http://localhost:8000` (should work)
3. Try: `http://YOUR_IP:8000` (replace with your actual IP)
   - If this doesn't work, the server isn't bound correctly
   - Make sure you see `0.0.0.0:8000` when starting the server

## Step 5: Test from Other Device

1. **Same Network**: Make sure your device is on the SAME WiFi network
   - Check WiFi network name matches exactly
   - Some routers have "Guest Network" that isolates devices

2. **Use Correct IP**: Use the IP address shown when starting the server
   - IP addresses can change when you reconnect to WiFi
   - Run `ipconfig` to find current IP if needed

3. **Use HTTP (not HTTPS)**: Make sure you're using `http://` not `https://`
   - Example: `http://192.168.1.100:8000` ✅
   - Example: `https://192.168.1.100:8000` ❌ (won't work)

## Step 6: Check Router Settings

Some routers have settings that prevent devices from talking to each other:

### AP Isolation / Client Isolation
- This setting prevents devices on the same WiFi from communicating
- **Fix**: Log into your router and disable "AP Isolation" or "Client Isolation"
- Router login is usually at `192.168.1.1` or `192.168.0.1`

### Guest Network
- Guest networks often isolate devices
- **Fix**: Connect both devices to the main network (not guest network)

## Step 7: Check Antivirus Software

Some antivirus software blocks network connections:

1. **Temporarily disable** antivirus firewall to test
2. If it works after disabling, add an exception for port 8000
3. Common antivirus with firewalls:
   - Norton
   - McAfee
   - Kaspersky
   - Avast
   - Windows Defender (already checked above)

## Step 8: Advanced Troubleshooting

### Test with Windows Firewall Disabled (Temporarily)

1. Open Windows Defender Firewall
2. Turn off firewall for Private network (temporarily)
3. Test connection from other device
4. If it works, firewall is the issue - re-enable and add proper rule
5. **Important**: Re-enable firewall after testing!

### Check if Port is Actually Listening

Run this command:
```bash
netstat -ano | findstr ":8000"
```

You should see something like:
```
TCP    0.0.0.0:8000           0.0.0.0:0              LISTENING       12345
```

- ✅ If you see `0.0.0.0:8000` - server is bound correctly
- ❌ If you see `127.0.0.1:8000` - server is NOT accessible from network

### Verify IP Address

Run this to find your IP:
```bash
ipconfig | findstr IPv4
```

Look for the IP under your WiFi adapter (usually starts with `192.168.x.x` or `10.x.x.x`)

## Common Error Messages

### "This site can't be reached" or "Connection refused"
- **Cause**: Firewall blocking or server not running
- **Fix**: Check firewall and verify server is running

### "DisallowedHost" error in Django
- **Cause**: IP address not in ALLOWED_HOSTS
- **Fix**: Should be automatic with PermissiveHostMiddleware, but check Django settings

### "Connection timeout"
- **Cause**: Router blocking or wrong network
- **Fix**: Check router settings, verify same network

### Page loads but shows errors
- **Cause**: Server is accessible but Django has issues
- **Fix**: Check server logs for errors

## Still Not Working?

1. Run `DIAGNOSE_WIFI_ACCESS.bat` and share the output
2. Run `TEST_WIFI_CONNECTION.bat` and share the output
3. Check server logs for any error messages
4. Try accessing from a different device
5. Try a different port (e.g., 8001) to rule out port-specific issues

## Quick Checklist

- [ ] Server is running (`netstat -ano | findstr ":8000"`)
- [ ] Server is bound to `0.0.0.0:8000` (not `127.0.0.1:8000`)
- [ ] Windows Firewall rule exists and is enabled
- [ ] Devices are on the same WiFi network
- [ ] Using correct IP address (from `ipconfig`)
- [ ] Using `http://` not `https://`
- [ ] Router AP Isolation is disabled
- [ ] Antivirus is not blocking connections
- [ ] Can access from same computer using IP address




