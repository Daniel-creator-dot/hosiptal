# 🚀 **PROPER STARTUP & SHUTDOWN - DATA PRESERVATION**

## ✅ **Follow This to Keep Your Data Safe!**

---

## 🟢 **PROPER STARTUP (When Turning On Computer)**

### **Step 1: Navigate to Project**
```bash
cd C:\Users\user\chm
```

### **Step 2: Verify Database**
```bash
python manage.py verify_database
```

**Look for:**
- ✅ Database file exists
- ✅ Size shown (should be ~10 MB)
- ✅ Record counts displayed
- ✅ "All migrations applied"
- ✅ "All staff have users"

**If errors appear:**
```bash
python manage.py migrate
```

### **Step 3: Start Django Server**
```bash
python manage.py runserver
```

**Wait for:**
```
Starting development server at http://127.0.0.1:8000/
Quit the server with CTRL-BREAK.
```

### **Step 4: Start Celery Worker** (New Terminal)
```bash
cd C:\Users\user\chm
python -m celery -A hms worker --loglevel=info --pool=solo
```

**Wait for:**
```
celery@... ready.
```

### **Step 5: Start Celery Beat** (New Terminal)
```bash
cd C:\Users\user\chm
python -m celery -A hms beat --loglevel=info
```

**Wait for:**
```
beat: Starting...
```

### **Step 6: Verify System**
Open browser: `http://127.0.0.1:8000/`

---

## 🔴 **PROPER SHUTDOWN (When Turning Off Computer)**

### **Step 1: Create Backup**
```bash
cd C:\Users\user\chm
python manage.py backup_database
```

**Wait for:**
```
BACKUP COMPLETED SUCCESSFULLY!
```

### **Step 2: Stop Celery Beat**
- Go to Celery Beat terminal
- Press `Ctrl + C`
- Wait for "Shutdown complete"

### **Step 3: Stop Celery Worker**
- Go to Celery Worker terminal
- Press `Ctrl + C`
- Wait for "Shutdown complete"

### **Step 4: Stop Django Server**
- Go to Django server terminal
- Press `Ctrl + C`
- Wait for "Quit the server" message

### **Step 5: Verify Backup Created**
```bash
dir backups\
```

**Look for:** New backup folder with today's date

### **Step 6: Safe to Shutdown**
Now you can safely turn off your computer!

---

## ⚡ **Quick Daily Workflow**

### **Morning (Starting Work):**
```bash
# Terminal 1
cd C:\Users\user\chm
python manage.py verify_database  # Quick check
python manage.py runserver

# Terminal 2
cd C:\Users\user\chm
python -m celery -A hms worker --loglevel=info --pool=solo

# Terminal 3
cd C:\Users\user\chm
python -m celery -A hms beat --loglevel=info
```

### **Evening (Ending Work):**
```bash
# Any terminal
python manage.py backup_database

# Then:
Ctrl + C in all terminals
Wait for shutdown messages
Close computer
```

---

## 🛡️ **Data Safety Checklist**

### **Before Shutdown:**
- ✅ Create backup: `python manage.py backup_database`
- ✅ Stop all services properly (Ctrl + C, wait for messages)
- ✅ Verify backup created: Check `backups/` folder
- ✅ Don't force close terminals

### **After Startup:**
- ✅ Verify database: `python manage.py verify_database`
- ✅ Check migrations: `python manage.py migrate`
- ✅ Start all services in order
- ✅ Test a page to verify data shows

---

## 🆘 **If Data Doesn't Show After Startup**

### **Troubleshooting Steps:**

#### **1. Check Database File**
```bash
dir db.sqlite3
```
Should show file size ~10 MB

#### **2. Verify Data Exists**
```bash
python manage.py verify_database
```
Should show record counts

#### **3. Check Migrations**
```bash
python manage.py showmigrations
```
All should have `[X]` marks

#### **4. Restart Server**
```bash
Ctrl + C
python manage.py runserver
```

#### **5. Hard Refresh Browser**
```
Press: Ctrl + Shift + R
```

#### **6. If Still Missing - Restore Backup**
```bash
python manage.py restore_database --backup=backup_LATEST
```

---

## 📊 **Monitor Automated Backups**

### **Check if Celery is Running:**

**Look for these processes in Task Manager:**
- ✅ `python.exe` (Django server)
- ✅ `python.exe` (Celery worker)
- ✅ `python.exe` (Celery beat)

**Or check terminals:**
- All 3 terminals should be actively running
- No error messages
- Logs scrolling (Celery)

### **Verify Automated Backup Happened:**
```bash
dir backups\automated\
```

**Should see:**
- New backup folder each day
- Timestamped folders
- Growing list of backups

---

## 🎯 **Protection Status**

### **What's Protecting Your Data:**

1. ✅ **SQLite Database** - Reliable file-based DB
2. ✅ **Manual Backups** - On demand via command
3. ✅ **Automated Backups** - Daily via Celery
4. ✅ **Verification Tool** - Check integrity anytime
5. ✅ **Restore Tool** - Quick recovery
6. ✅ **Migration System** - Schema version control
7. ✅ **Manifest Files** - Track backup metadata

### **Current Backup Status:**
```
✅ First Manual Backup: Created (10.09 MB)
✅ Automated Backups: Configured (runs daily)
✅ Verification: Available anytime
✅ Restore: Ready if needed
```

---

## 📝 **Create Backup Reminder Checklist**

### **Print This and Put on Your Desk:**

```
DAILY CHECKLIST:
□ Morning: Verify database
□ Start: Run all 3 terminals (Django, Celery x2)
□ Work: Make changes confidently
□ Evening: Create backup
□ Shutdown: Stop services properly (Ctrl + C)

WEEKLY CHECKLIST:
□ Copy backups to USB drive
□ Check automated backups folder
□ Run database verification
□ Test accessing all data

MONTHLY CHECKLIST:
□ Upload backups to cloud
□ Test a restore process
□ Clean old backups (keep 30-90 days)
□ Review system logs
```

---

## ✅ **YOUR DATA IS NOW SAFE!**

✅ Backup system created  
✅ First backup completed (10.09 MB)  
✅ Automated daily backups scheduled  
✅ Weekly verification scheduled  
✅ Restore process available  
✅ Comprehensive guides created  

**Follow the startup/shutdown process and your data will ALWAYS be preserved!** 💾✨

---

## 🎊 **Quick Commands Reference**

```bash
# Create backup
python manage.py backup_database

# Verify data
python manage.py verify_database

# Restore backup
python manage.py restore_database --backup=backup_YYYYMMDD_HHMMSS

# Check migrations
python manage.py showmigrations

# Apply migrations
python manage.py migrate
```

**Save these commands - they're your data safety net!** 🛡️💾🎉
































