# 🔧 Server Start Guide

## ❌ Current Issue
**Connection Refused** - Server is not running

## ✅ Quick Fix - Choose One Method:

### Method 1: Use the Batch Script (Easiest)
**Double-click:** `START_SERVER_NOW.bat`

This will:
- Activate virtual environment (if exists)
- Start Django server on port 8000
- Show server URL in the window

### Method 2: Manual Start (If batch doesn't work)

**Step 1: Open PowerShell/Command Prompt in project folder**

**Step 2: Activate virtual environment (if exists)**
```bash
.venv\Scripts\activate
# OR
venv\Scripts\activate
```

**Step 3: Start server**
```bash
python manage.py runserver 127.0.0.1:8000
```

### Method 3: Use Docker (If you prefer Docker)

**Step 1: Start Docker Desktop**
- Make sure Docker Desktop is running

**Step 2: Run startup script**
```bash
🚀_START_DOCKER_HERE.bat
```

---

## 🎯 After Server Starts

1. **Wait for message:** "Starting development server at http://127.0.0.1:8000/"

2. **Open browser:** http://127.0.0.1:8000/hms/patients/create/

3. **Test the new feature:**
   - Look for "💳 Payment Type & Billing Information"
   - Select Insurance/Corporate/Cash
   - Verify fields appear/disappear

---

## 🐛 Troubleshooting

### Error: "No module named 'django'"
**Solution:** Activate virtual environment first
```bash
.venv\Scripts\activate
```

### Error: "Database connection failed"
**Solution:** 
- If using Docker: Start Docker Desktop and run `🚀_START_DOCKER_HERE.bat`
- If using local DB: Make sure PostgreSQL is running

### Error: "Port 8000 already in use"
**Solution:** 
```bash
# Find what's using port 8000
netstat -ano | findstr :8000

# Kill the process or use different port
python manage.py runserver 127.0.0.1:8001
```

---

## ✅ Success Indicators

When server starts successfully, you'll see:
```
Starting development server at http://127.0.0.1:8000/
Quit the server with CTRL-BREAK.
```

Then you can access:
- http://127.0.0.1:8000/ (Home/Login)
- http://127.0.0.1:8000/hms/patients/create/ (Patient Registration)

---

**The batch script `START_SERVER_NOW.bat` should start the server automatically!**

