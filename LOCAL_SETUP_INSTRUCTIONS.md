# 🔧 Local Setup Instructions (No Docker)

## Current Issue
- Virtual environment is corrupted (pip broken)
- Django not installed
- Need to fix and start locally

## ✅ Quick Fix - Running Now!

I've started a script that will:
1. Fix pip in your venv
2. Install Django and required packages
3. Start the server automatically

**Check the new command window that opened!**

---

## 🎯 What's Happening

The script `FIX_AND_START_LOCAL.bat` is:
- Fixing pip installation
- Installing Django and dependencies
- Starting the server on port 8000

**Wait for it to complete** - it may take 1-2 minutes to install packages.

---

## ✅ Success Indicators

When ready, you'll see:
```
Starting development server at http://127.0.0.1:8000/
Quit the server with CTRL-BREAK.
```

Then open: **http://127.0.0.1:8000/hms/patients/create/**

---

## 🎯 Test the New Feature

Once server is running:

1. **Open browser:** http://127.0.0.1:8000/hms/patients/create/

2. **Look for:** "💳 Payment Type & Billing Information" section

3. **Find:** "Payment Type" dropdown with:
   - Insurance
   - Corporate
   - Cash

4. **Test:** Select each option and watch fields appear/disappear

---

## 🐛 If Installation Fails

If you see errors in the command window:

**Option 1: Use system Python (if installed)**
```bash
# Find system Python
py --version

# Use it directly
py -m pip install django
py manage.py runserver
```

**Option 2: Recreate venv**
```bash
# Delete old venv
rmdir /s venv

# Create new venv
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python manage.py runserver
```

---

## 📋 What to Check

In the command window, look for:
- ✅ "Successfully installed django..."
- ✅ "Starting development server..."
- ❌ Any error messages (share them if you see any)

---

**The script is running now - check the command window!** 🚀

