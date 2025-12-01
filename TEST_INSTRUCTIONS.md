# Test Patient Registration

## Test Data:
- **First Name:** Test
- **Last Name:** Patient
- **Phone:** 0247904675
- **Email:** test@example.com
- **Date of Birth:** 1990-01-01
- **Gender:** Male
- **Address:** Test Address
- **Next of Kin Name:** Test Kin
- **Next of Kin Relationship:** Parent

## Test Steps:

### Step 1: First Registration
1. Go to: http://localhost:8000/hms/patients/new/
2. Fill in the form with the data above
3. Click "Register Patient"
4. **Expected:** ✅ Success! Patient created with MRN

### Step 2: Duplicate Test
1. Go back to: http://localhost:8000/hms/patients/new/
2. Fill in the **EXACT SAME** data again
3. Click "Register Patient"
4. **Expected:** ❌ Error message "⚠️ Duplicate patient detected!"

### Step 3: Verify
1. Go to: http://localhost:8000/hms/patients/
2. Search for "Test Patient"
3. **Expected:** Should find only ONE patient

## What to Look For:

✅ **Success Indicators:**
- First registration succeeds
- Second registration shows duplicate error
- Only one patient in database

❌ **Failure Indicators:**
- Second patient is created
- No error message shown
- Two patients with same name/phone

## If Duplicate is Created:

Run this to check:
```bash
docker exec chm-web-1 python manage.py shell -c "from hospital.models import Patient; print(Patient.objects.filter(first_name__iexact='Test', last_name__iexact='Patient', is_deleted=False).count())"
```

Should return: `1` (not 2)

