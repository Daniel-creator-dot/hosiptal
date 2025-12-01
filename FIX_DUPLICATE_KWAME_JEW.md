# Fix for "kwame jew" Duplicate Issue

## Problem
Two patients named "kwame jew" were created with different MRNs (PMC2025000013 and PMC2025000012), both with phone 0247904675.

## Root Cause
The duplicate check was requiring `name + DOB + phone`, but:
1. If DOB is missing or default (2000-01-01), the check might not catch duplicates properly
2. Form validation might not be running properly
3. Need more aggressive duplicate checking

## Fixes Applied

### 1. More Aggressive Duplicate Check
- Now checks by `name + phone` even if DOB is missing
- Checks by `name + DOB + phone` if DOB is provided
- This catches duplicates even when DOB is not entered

### 2. Form Validation Enforcement
- Added explicit check for form validation errors
- Logs validation errors for debugging
- Ensures form.clean() duplicate checks run first

### 3. Additional Database Index
- Added index on `(first_name, last_name, phone_number)`
- Speeds up duplicate detection queries

### 4. Better Logging
- Added warning logs when duplicates are detected
- Helps track when and why duplicates slip through

## How to Fix Existing Duplicates

Run this command to merge the "kwame jew" duplicates:

```bash
python manage.py fix_duplicates --fix
```

This will:
- Keep the oldest record (first created)
- Merge data from duplicates
- Mark duplicates as deleted

## Test the Fix

1. Go to: http://localhost:8000/hms/patients/new/
2. Try to register "kwame jew" again with phone 0247904675
3. Should see duplicate error immediately

## Files Modified

1. `hospital/views.py` - More aggressive duplicate checking
2. `hospital/forms.py` - Check by name+phone even without DOB
3. `hospital/models.py` - Added name+phone index
4. `hospital/migrations/1043_add_patient_duplicate_indexes.py` - Added name+phone index

## Next Steps

1. Run migration: `python manage.py migrate hospital 1043`
2. Fix existing duplicates: `python manage.py fix_duplicates --fix`
3. Test registration - duplicates should now be prevented

