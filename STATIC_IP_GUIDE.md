# 🔒 Static IP Configuration Guide

## Problem
Your IP address changes every day because it's assigned dynamically by your router (DHCP). This makes it hard to access your HMS from other devices.

## Solution: Set a Static IP Address

### Option 1: Automatic Setup (Recommended)

1. **Right-click** `SET_STATIC_IP.bat`
2. Select **"Run as administrator"**
3. Follow the prompts to select your network adapter
4. The script will use your current IP as the static IP

### Option 2: Manual Setup in Windows

1. **Open Network Settings**:
   - Press `Win + I` → Network & Internet → Properties
   - Or: Control Panel → Network and Sharing Center → Change adapter settings

2. **Find Your Network Adapter**:
   - Right-click your active adapter (WiFi or Ethernet)
   - Select **"Properties"**

3. **Configure IPv4**:
   - Select **"Internet Protocol Version 4 (TCP/IPv4)"**
   - Click **"Properties"**
   - Select **"Use the following IP address"**

4. **Enter Your Current Settings**:
   - **IP Address**: Your current IP (e.g., `192.168.0.119`)
   - **Subnet Mask**: Usually `255.255.255.0` (or `/24`)
   - **Default Gateway**: Your router IP (usually `192.168.0.1` or `192.168.1.1`)

5. **Set DNS Servers**:
   - Select **"Use the following DNS server addresses"**
   - **Preferred DNS**: `8.8.8.8` (Google) or your router IP
   - **Alternate DNS**: `8.8.4.4` (Google) or `1.1.1.1` (Cloudflare)

6. **Click OK** to save

### Option 3: Configure in Router (Best for Permanent Solution)

1. **Access Router Admin Panel**:
   - Usually: http://192.168.0.1 or http://192.168.1.1
   - Check router label for default gateway

2. **Find DHCP/Reservation Settings**:
   - Look for "DHCP Reservations" or "Static IP Assignment"
   - Find your device's MAC address (in Windows: `ipconfig /all`)

3. **Reserve IP for Your Device**:
   - Enter your device's MAC address
   - Assign a static IP (e.g., `192.168.0.100`)
   - Save settings

4. **Restart Your Computer**:
   - Your device will now always get the same IP

## ✅ Verify Static IP

After setting static IP, verify it works:

```powershell
# Check current IP
ipconfig

# Test connectivity
ping 8.8.8.8

# Test HMS access
Invoke-WebRequest -Uri http://localhost:8000/health/
```

## 🔄 Alternative: Use Wildcard CSRF (Already Configured)

**Good News!** Your HMS is already configured to accept connections from any IP in common network ranges:
- `192.168.0.*` to `192.168.255.*`
- `10.*.*.*`
- `172.16.*.*` to `172.31.*.*`

This means even if your IP changes, the system should still work. However, setting a static IP is still recommended for:
- Consistent access URLs
- Easier firewall configuration
- Better network device management

## 🛠️ Quick Commands

### Check Current IP:
```powershell
ipconfig | findstr IPv4
```

### View Network Adapters:
```powershell
Get-NetAdapter | Where-Object {$_.Status -eq "Up"}
```

### View IP Configuration:
```powershell
Get-NetIPConfiguration
```

### Test HMS Access:
```powershell
# Local
Invoke-WebRequest -Uri http://localhost:8000/health/

# Network (replace with your IP)
Invoke-WebRequest -Uri http://192.168.0.119:8000/health/
```

## 📋 Recommended Static IP Ranges

For home/office networks, use these ranges:
- **192.168.0.100 - 192.168.0.200** (Most common)
- **192.168.1.100 - 192.168.1.200**
- **10.0.0.100 - 10.0.0.200**

**Avoid**: Don't use IPs ending in `.1` (usually router) or `.255` (broadcast)

## 🚨 Troubleshooting

### Can't Access Internet After Setting Static IP:
1. Check Default Gateway is correct
2. Verify DNS servers are set
3. Make sure IP is in correct range (not conflicting)

### IP Still Changes:
1. Router may override static IP
2. Use router DHCP reservation instead
3. Check if another device has the same IP

### Can't Access HMS from Network:
1. Run `allow_port_8000_firewall.bat` as Administrator
2. Check Windows Firewall rules
3. Verify IP is correct: `ipconfig`

## 📞 After Setting Static IP

1. **Update Firewall Script**:
   ```batch
   AUTO_UPDATE_IP.bat
   ```

2. **Restart HMS** (if needed):
   ```powershell
   docker-compose restart web
   ```

3. **Access HMS**:
   - Local: http://localhost:8000
   - Network: http://YOUR_STATIC_IP:8000

## 🎯 Summary

**Best Solution**: Set static IP in router (DHCP reservation)
**Quick Solution**: Use `SET_STATIC_IP.bat` script
**Current Status**: System already accepts dynamic IPs via wildcards

Your HMS will work with dynamic IPs, but static IP makes it more reliable and easier to access!








