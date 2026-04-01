# 🔧 System Down - Troubleshooting Guide

## ✅ **Current Status**

**Good News**: The server IS running and responding on port 8000!

- ✅ Django server: **RUNNING**
- ✅ Port 8000: **LISTENING**
- ✅ Server responding: **YES**
- ✅ System check: **PASSED** (0 issues)
- ✅ Database: **CONNECTED**

---

## 🌐 **Access the System**

### **Try These URLs:**

1. **Localhost (on this computer):**
   - http://localhost:8000/hms/
   - http://127.0.0.1:8000/hms/

2. **Network (from other devices):**
   - http://192.168.2.216:8000/hms/
   - Replace `192.168.2.216` with your actual IP address

3. **Login Page:**
   - http://localhost:8000/hms/login/

---

## 🔍 **If You Still Can't Access**

### **1. Clear Browser Cache**
- **Chrome/Edge**: Press `Ctrl + Shift + Delete`
- Select "Cached images and files"
- Click "Clear data"
- Try again

### **2. Try Different Browser**
- Use Chrome, Firefox, or Edge
- Try incognito/private mode (`Ctrl + Shift + N`)

### **3. Check Firewall**
The server is running, but Windows Firewall might be blocking access.

**To allow access:**
```powershell
# Run PowerShell as Administrator
New-NetFirewallRule -DisplayName "HMS Django Server" -Direction Inbound -LocalPort 8000 -Protocol TCP -Action Allow
```

### **4. Restart Server (If Needed)**

**Option A: Use the fix script**
```batch
restart_server_fix.bat
```

**Option B: Manual restart**
```batch
cd d:\chm
python manage.py runserver 0.0.0.0:8000
```

---

## 🚨 **Common Issues & Solutions**

### **Issue 1: "This site can't be reached"**
**Solution:**
1. Check if server is running:
   ```batch
   netstat -ano | findstr :8000
   ```
2. If not running, start it:
   ```batch
   cd d:\chm
   python manage.py runserver 0.0.0.0:8000
   ```

### **Issue 2: "Connection refused"**
**Solution:**
- Server might have crashed
- Restart using `restart_server_fix.bat`

### **Issue 3: "Page loads but shows errors"**
**Solution:**
1. Clear Django cache:
   ```batch
   python manage.py clear_all_caches
   ```
2. Check for errors:
   ```batch
   python manage.py check
   ```

### **Issue 4: "Can't access from other devices"**
**Solution:**
1. Make sure server is running on `0.0.0.0:8000` (not just `127.0.0.1:8000`)
2. Check Windows Firewall (see above)
3. Verify network IP address:
   ```batch
   ipconfig
   ```
   Look for "IPv4 Address" under your network adapter

---

## 🔄 **Quick Restart Commands**

### **Full Restart (Recommended):**
```batch
restart_server_fix.bat
```

### **Simple Restart:**
```batch
cd d:\chm
python manage.py runserver 0.0.0.0:8000
```

### **Restart with Cache Clear:**
```batch
cd d:\chm
python manage.py clear_all_caches
python manage.py runserver 0.0.0.0:8000
```

---

## 📋 **Verify Server Status**

### **Check if Server is Running:**
```batch
netstat -ano | findstr :8000
```
Should show: `TCP    0.0.0.0:8000           0.0.0.0:0              LISTENING`

### **Test Server Response:**
```batch
curl http://localhost:8000/hms/
```
Or open in browser: http://localhost:8000/hms/

### **Check for Errors:**
```batch
python manage.py check
```

---

## ✅ **Next Steps**

1. **Try accessing**: http://localhost:8000/hms/
2. **If it doesn't work**, run: `restart_server_fix.bat`
3. **Clear browser cache** and try again
4. **Check firewall** if accessing from network

---

## 🆘 **Still Having Issues?**

If the system is still down after trying the above:

1. **Check server console** for error messages
2. **Check database connection**:
   ```batch
   python manage.py dbshell
   ```
3. **Check logs** in the console where server is running
4. **Restart computer** if all else fails

---

## 📞 **Quick Reference**

- **Server Status**: ✅ RUNNING on port 8000
- **Access URL**: http://localhost:8000/hms/
- **Restart Script**: `restart_server_fix.bat`
- **System Check**: `python manage.py check`

**The server is running - try accessing it now!** 🚀
