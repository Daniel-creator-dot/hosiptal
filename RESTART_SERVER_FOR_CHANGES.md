# 🔄 Restart Server to Load Patient Card Changes

## Why Restart is Needed

Django loads Python code when the server starts. After making changes to:
- **Models** (`hospital/models.py`)
- **Views** (`hospital/views.py`) 
- **Templates** (usually auto-reloaded, but sometimes needs restart)

You need to **restart the Django development server** for changes to take effect.

## ✅ Changes Made

1. ✅ Enhanced `hospital/models.py` with secure QR authentication
2. ✅ Updated `hospital/views.py` with improved QR card view
3. ✅ Created `hospital/templates/hospital/patient_qr_card.html` (new template)
4. ✅ Added Bootstrap Icons CDN link

## 🔄 How to Restart Server

### If Server is Running in Terminal:

1. **Stop the server:**
   - Go to the terminal window running Django
   - Press `Ctrl + C` to stop

2. **Start the server again:**
   ```bash
   python manage.py runserver
   ```
   or
   ```bash
   python manage.py runserver 0.0.0.0:8000
   ```

### If Using Docker:

```bash
docker-compose restart
```
or
```bash
docker-compose down
docker-compose up
```

### Clear Python Cache (Optional but Recommended):

Clear Python bytecode cache to ensure fresh code:

**Windows PowerShell:**
```powershell
cd d:\chm
Get-ChildItem -Path "hospital" -Filter "__pycache__" -Recurse -Directory | Remove-Item -Recurse -Force
Get-ChildItem -Path "hospital" -Filter "*.pyc" -Recurse | Remove-Item -Force
```

**Windows CMD:**
```cmd
cd d:\chm
for /d /r hospital %d in (__pycache__) do @if exist "%d" rd /s /q "%d"
for /r hospital %f in (*.pyc) do @if exist "%f" del /q "%f"
```

**Linux/Mac:**
```bash
cd /path/to/chm
find hospital -type d -name __pycache__ -exec rm -r {} +
find hospital -name "*.pyc" -delete
```

## ✅ Verification Steps

After restarting, verify changes are loaded:

### 1. Check Django Can Import the Model:

```bash
python manage.py shell
```

Then in the shell:
```python
from hospital.models import PatientQRCode
print(PatientQRCode.__doc__)  # Should show "Secure QR code profile..."
print(hasattr(PatientQRCode, 'build_payload'))  # Should be True
exit()
```

### 2. Check Template Exists:

```bash
python manage.py shell
```

```python
from django.template.loader import get_template
template = get_template('hospital/patient_qr_card.html')
print("Template found:", template)
exit()
```

### 3. Test a Patient Card URL:

1. Go to: `http://localhost:8000/hms/patients/`
2. Click any patient
3. Look for "Print QR Card" button
4. Click it or manually go to: `/hms/patients/<uuid>/qr-card/`

### 4. Check Server Logs:

When you access the patient card page, you should see in server logs:
```
[INFO] Refreshing QR profile for patient PMC...
```
or
```
GET /hms/patients/.../qr-card/ HTTP/1.1 200
```

## 🐛 If Still Not Working After Restart

### 1. Clear Browser Cache:
- Hard refresh: `Ctrl + Shift + R` (Windows) or `Cmd + Shift + R` (Mac)
- Or clear browser cache completely

### 2. Check File Permissions:
Make sure Django can read the template file:
```bash
# Check file exists and is readable
dir hospital\templates\hospital\patient_qr_card.html
```

### 3. Verify Changes Are Saved:

Check file modification times:
```bash
# Windows PowerShell
Get-Item hospital\models.py | Select-Object LastWriteTime
Get-Item hospital\templates\hospital\patient_qr_card.html | Select-Object LastWriteTime
```

### 4. Check for Syntax Errors:

```bash
python manage.py check
python manage.py validate
```

### 5. Check Django Auto-Reload:

Django development server auto-reloads on file changes, but:
- **Models** require server restart
- **Views** usually auto-reload, but restart if needed
- **Templates** usually auto-reload

### 6. Force Template Reload:

If template isn't updating, restart is required.

## 📝 Quick Restart Checklist

- [ ] Stop Django server (Ctrl+C)
- [ ] (Optional) Clear Python cache
- [ ] Start Django server (`python manage.py runserver`)
- [ ] Test patient card URL
- [ ] Check browser console for errors
- [ ] Verify QR code generates

## 🚀 Expected Behavior After Restart

When you access `/hms/patients/<uuid>/qr-card/`:

1. **If QR profile exists:**
   - Shows beautiful patient card
   - QR code image displays
   - Patient information shows

2. **If QR profile doesn't exist:**
   - Automatically creates QR profile
   - Generates QR code
   - Shows patient card

3. **If patient doesn't exist:**
   - 404 error (expected)

## 💡 Tip: Auto-Reload vs Manual Restart

**Auto-reloads (no restart needed):**
- Template files (*.html)
- Static files (CSS, JS)
- View code (usually)

**Requires restart:**
- Model changes
- Settings changes
- New Python packages
- URL configuration (sometimes)

**When in doubt, restart!**

---

**Next Steps:**
1. Stop your Django server
2. Clear cache (optional)
3. Start server again
4. Test patient card page
5. Verify all features work




