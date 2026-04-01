# 🚨 URGENT FIX: 404 Error with /None in URL

## Problem

Getting 404 error:
```
http://127.0.0.1:8000/hms/patients/ed4e5cb0-fefc-4875-8b9b-1a033b76eae4/None
```

The `/None` at the end means a variable is None when it shouldn't be.

## Immediate Fix

### Step 1: Check URL Pattern

The QR card URL should be:
```
/hms/patients/{uuid}/qr-card/
```

NOT:
```
/hms/patients/{uuid}/None  ❌
```

### Step 2: Fix Template

The template now uses Django's `{% url %}` tag directly which should prevent this. 

### Step 3: Ensure Patient PK is Valid

Make sure `patient.pk` exists before using it in URLs.

## Quick Test

1. Go directly to QR card URL:
   ```
   http://127.0.0.1:8000/hms/patients/ed4e5cb0-fefc-4875-8b9b-1a033b76eae4/qr-card/
   ```

2. Check if this works (should load QR card page)

3. If it works, the issue is with how the link is being generated

## Likely Cause

Something is generating a link like:
```html
<a href="/hms/patients/{{ patient.pk }}/{{ something_none }}/">
```

Where `something_none` is None.

## Fix Applied

✅ Template now uses direct URL tag: `{% url 'hospital:patient_qr_card' patient.pk %}`
✅ View ensures patient.pk exists before creating URLs
✅ Added safety checks

**Restart server and test again!**




