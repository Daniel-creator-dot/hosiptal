# COMPLETE DUPLICATE PREVENTION FIX

## Problem
Duplicates are being created through multiple entry points:
1. Web form (patient_create view)
2. REST API (PatientViewSet)
3. Django Admin
4. Direct model.save() calls

## Solution: 6 Layers of Protection

### Layer 1: Form Validation (`hospital/forms.py`)
- `PatientForm.clean()` checks for duplicates
- Validates before form submission
- Shows error to user

### Layer 2: View Validation (`hospital/views.py`)
- `patient_create` view checks for duplicates inside transaction
- Uses `select_for_update()` for row locking
- Prevents race conditions

### Layer 3: Serializer Validation (`hospital/serializers.py`)
- `PatientSerializer.validate()` checks for duplicates
- Prevents API from creating duplicates
- Returns validation error to API client

### Layer 4: Admin Validation (`hospital/admin.py`)
- `PatientAdmin.save_model()` checks for duplicates
- Prevents admin interface from creating duplicates
- Shows error message in admin

### Layer 5: Model Save Method (`hospital/models.py`)
- `Patient.save()` checks for duplicates BEFORE saving
- **FINAL SAFETY NET** - catches ANY bypass
- Uses `select_for_update()` with transaction
- Raises `IntegrityError` if duplicate found

### Layer 6: Database Constraints
- Unique constraint on `mrn`
- Unique constraint on `national_id`
- Database-level protection

## How It Works

### Duplicate Detection Logic:
1. **Name + Phone** (primary check)
   - Normalizes phone numbers (024 = +233 = 233)
   - Checks case-insensitive name match
   - Works even if DOB is missing or default

2. **Email** (secondary check)
   - Case-insensitive email match
   - Only if email provided

3. **National ID** (tertiary check)
   - Exact match on national_id
   - Only if national_id provided

### Phone Number Normalization:
- `0241234567` → `233241234567`
- `+233241234567` → `233241234567`
- `233241234567` → `233241234567`
- All formats are treated as the same number

## Files Modified

1. **hospital/models.py**
   - Added duplicate check in `save()` method
   - Uses `select_for_update()` for row locking
   - Raises `IntegrityError` on duplicate

2. **hospital/serializers.py**
   - Added `validate()` method to `PatientSerializer`
   - Checks duplicates before API creation
   - Returns validation error

3. **hospital/admin.py**
   - Added `save_model()` override to `PatientAdmin`
   - Checks duplicates before admin save
   - Shows error message

4. **hospital/views.py** (already fixed)
   - Transaction-based duplicate checks
   - Row locking with `select_for_update()`

5. **hospital/forms.py** (already fixed)
   - Form validation with duplicate checks

## Testing

### Test Web Form:
1. Go to: http://localhost:8000/hms/patients/new/
2. Register "reece loft" with phone 0247904675
3. Try to register again
4. **Should see duplicate error**

### Test API:
```bash
curl -X POST http://localhost:8000/api/patients/ \
  -H "Content-Type: application/json" \
  -d '{"first_name":"reece","last_name":"loft","phone_number":"0247904675"}'
```
**Should return validation error if duplicate**

### Test Admin:
1. Go to: http://localhost:8000/admin/hospital/patient/add/
2. Try to create duplicate
3. **Should see error message**

## Why This Will Work

1. **Model.save() is ALWAYS called** - no way to bypass
2. **Transaction with row locking** - prevents race conditions
3. **Multiple entry points protected** - form, API, admin
4. **Phone normalization** - catches different formats
5. **Aggressive checking** - name + phone even without DOB

## Fix Existing Duplicates

Run this to merge existing duplicates:
```bash
python manage.py fix_duplicates --fix
```

## Next Steps

1. Test all three entry points (form, API, admin)
2. Fix existing duplicates with management command
3. Monitor logs for any duplicate attempts
4. Verify no new duplicates are created

