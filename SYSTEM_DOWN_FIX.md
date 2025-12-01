# 🔧 System Down - Quick Fix

## ✅ Solution Running Now!

I've started a **quick fix script** that will:
1. Install Django (if needed)
2. Use SQLite database (no PostgreSQL needed)
3. Start the server automatically

**Check the new command window!**

---

## 🎯 What's Happening

The script `START_WITH_SQLITE.bat` is:
- Installing Django and crispy-forms
- Creating SQLite database (no setup needed)
- Starting server on port 8000

**Wait 30-60 seconds** for installation to complete.

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

1. **Open:** http://127.0.0.1:8000/hms/patients/create/

2. **Look for:** "💳 Payment Type & Billing Information"

3. **Test:**
   - Select "Insurance" → Insurance fields appear
   - Select "Corporate" → Corporate fields appear
   - Select "Cash" → Receiving point appears

---

## 🐛 If You See Errors

**Error: "No module named 'django'"**
- Wait for installation to complete (takes 1-2 minutes)
- Check the command window for progress

**Error: "Database connection failed"**
- SQLite should work automatically
- If not, the script will create it

**Error: "Port 8000 in use"**
- Close other command windows
- Or use: `python manage.py runserver 127.0.0.1:8001`

---

## 📋 What to Check

In the command window:
- ✅ "Installing Django..." (should complete)
- ✅ "Running migrations..." (should complete)
- ✅ "Starting development server..." (server running)

---

## 🚀 Quick Alternative

If the script doesn't work, try manually:

```bash
# Install Django
python -m pip install django django-crispy-forms

# Create .env with SQLite
echo DATABASE_URL=sqlite:///db.sqlite3 > .env

# Run migrations
python manage.py migrate

# Start server
python manage.py runserver 127.0.0.1:8000
```

---

**The script is running - check the command window!** 🚀

