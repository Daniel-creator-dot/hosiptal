# ✅ Patient Registration Strip() Error Fixed

## Problem
Patient registration was failing with error:
```
Error creating patient: 'NoneType' object has no attribute 'strip'. Please try again.
```

## Root Cause
In `hospital/views.py`, the code was calling `.strip()` on values that could be `None`:
```python
first_name = cleaned_data.get('first_name', '').strip()
```

The issue is that `cleaned_data.get('first_name', '')` can still return `None` if the field value in `cleaned_data` is explicitly `None`. The default value `''` only applies if the key doesn't exist in the dictionary, not if the value is `None`.

## Solution
Changed all `.strip()` calls to safely handle `None` values:
```python
# Before (unsafe):
first_name = cleaned_data.get('first_name', '').strip()

# After (safe):
first_name = (cleaned_data.get('first_name') or '').strip()
```

The `or ''` ensures that if `cleaned_data.get('first_name')` returns `None`, we use an empty string instead before calling `.strip()`.

## Changes Made

### File: `hospital/views.py` (lines 1086-1092)

Fixed all field extractions to safely handle `None`:
- `first_name = (cleaned_data.get('first_name') or '').strip()`
- `last_name = (cleaned_data.get('last_name') or '').strip()`
- `phone_number = (cleaned_data.get('phone_number') or '').strip()`
- `email = (cleaned_data.get('email') or '').strip()`
- `national_id = (cleaned_data.get('national_id') or '').strip()`

## Verification
✅ No linter errors
✅ Web service restarted
✅ Code now safely handles `None` values

## Test
1. Go to: `http://localhost:8000/hms/patients/new/`
2. Fill out the patient registration form (you can leave optional fields empty)
3. Click "Register Patient"
4. Registration should now work even with empty/None values








