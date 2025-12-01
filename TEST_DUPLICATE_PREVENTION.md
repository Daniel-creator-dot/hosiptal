# How to Test Duplicate Prevention

## Quick Test Steps

### 1. **Test Patient Registration (Web Interface)**

#### Step 1: Register a Patient
1. Go to: `http://localhost:8000/hms/patients/new/` (or `http://localhost:8000/hms/patient-registration/`)
2. Fill in the form with:
   - First Name: `John`
   - Last Name: `Doe`
   - Date of Birth: `1990-01-01`
   - Phone Number: `0241234567`
   - Email: `john.doe@example.com`
3. Click "Register Patient"
4. Note the MRN that was created (e.g., `PMC2025000123`)

#### Step 2: Try to Register the Same Patient Again
1. Go back to: `http://localhost:8000/hms/patients/create/`
2. Fill in the **EXACT SAME** information:
   - First Name: `John`
   - Last Name: `Doe`
   - Date of Birth: `1990-01-01`
   - Phone Number: `0241234567` (or try `+233241234567` or `233241234567`)
   - Email: `john.doe@example.com`
3. Click "Register Patient"

#### Expected Result:
✅ **You should see an error message like:**
```
⚠️ Duplicate patient detected! A patient with the same name (John Doe), 
date of birth (1990-01-01), and phone number (0241234567) already exists. 
MRN: PMC2025000123. Please verify before proceeding.
```

❌ **If a duplicate is created**, the fix is not working.

---

### 2. **Test with Different Phone Formats**

Test that phone number normalization works:

1. Register patient with: `0241234567`
2. Try to register again with: `+233241234567`
3. Try to register again with: `233241234567`

**Expected Result:** All should be detected as duplicates (same number, different format)

---

### 3. **Test with Email**

1. Register patient with email: `test@example.com`
2. Try to register again with same email but different name

**Expected Result:** Should detect duplicate by email

---

### 4. **Test with National ID**

1. Register patient with National ID: `GHA-123456789-0`
2. Try to register again with same National ID

**Expected Result:** Should detect duplicate by National ID

---

### 5. **Test Double-Click Prevention**

1. Fill out the patient registration form
2. **Rapidly click the "Register Patient" button multiple times**

**Expected Result:** 
- Button should disable after first click
- Should show "Registering..." message
- Only ONE patient should be created

---

### 6. **Test Concurrent Requests (Advanced)**

If you have access to multiple browsers/tabs:

1. Open two browser tabs
2. Fill out the **SAME** patient information in both
3. Submit both forms **simultaneously** (within 1 second)

**Expected Result:** 
- Only ONE patient should be created
- The other should show duplicate error

---

## Command Line Tests

### Check for Existing Duplicates

```bash
python manage.py fix_duplicates --dry-run
```

This shows what duplicates exist in your database (if any).

### Fix Existing Duplicates

```bash
python manage.py fix_duplicates --fix
```

This merges existing duplicates.

### Check Patient Count

```bash
python manage.py shell -c "from hospital.models import Patient; print('Total patients:', Patient.objects.filter(is_deleted=False).count())"
```

### Check Specific Patient

```bash
python manage.py shell -c "from hospital.models import Patient; p = Patient.objects.filter(first_name='John', last_name='Doe').first(); print('Found:', p.mrn if p else 'None')"
```

---

## What to Look For

### ✅ Success Indicators:
- Error message appears when trying to register duplicate
- Button disables on click (prevents double-submission)
- Only one patient created even with rapid clicks
- Phone number normalization works (024 = +233 = 233)

### ❌ Failure Indicators:
- Duplicate patient created without error
- Multiple patients created from single form submission
- No error message when registering duplicate
- Button doesn't disable on click

---

## Troubleshooting

### If duplicates are still being created:

1. **Check migration was applied:**
   ```bash
   python manage.py showmigrations hospital | grep 1043
   ```
   Should show: `[X] 1043_add_patient_duplicate_indexes`

2. **Check database is PostgreSQL:**
   ```bash
   python manage.py shell -c "from django.conf import settings; print(settings.DATABASES['default']['ENGINE'])"
   ```
   Should show: `django.db.backends.postgresql`

3. **Check browser console for JavaScript errors:**
   - Open browser Developer Tools (F12)
   - Check Console tab for errors
   - JavaScript should prevent double-submission

4. **Check server logs:**
   - Look for duplicate detection messages
   - Check for any errors during patient creation

---

## Test Checklist

- [ ] Register patient with name + DOB + phone → Success
- [ ] Try to register same patient again → Error shown
- [ ] Try different phone format (024 vs +233) → Detected as duplicate
- [ ] Try same email → Detected as duplicate
- [ ] Try same National ID → Detected as duplicate
- [ ] Rapidly click submit button → Only one patient created
- [ ] Check button disables on click → Button shows "Registering..."
- [ ] Run `fix_duplicates --dry-run` → See if any existing duplicates

---

## Quick Test Script

Save this as `test_duplicate_prevention.py`:

```python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from hospital.models import Patient

# Test data
test_data = {
    'first_name': 'Test',
    'last_name': 'Patient',
    'date_of_birth': '1990-01-01',
    'phone_number': '0241234567',
    'email': 'test@example.com'
}

# Check if patient exists
existing = Patient.objects.filter(
    first_name__iexact=test_data['first_name'],
    last_name__iexact=test_data['last_name'],
    date_of_birth=test_data['date_of_birth'],
    is_deleted=False
).first()

if existing:
    print(f"✅ Duplicate detection working! Found existing patient: {existing.mrn}")
else:
    print("ℹ️ No existing test patient found. Try registering one first.")
```

Run with: `python test_duplicate_prevention.py`

