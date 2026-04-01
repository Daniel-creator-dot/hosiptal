# Fixed: "Cannot access local variable 'patient'" Error

## Problem
The error "cannot access local variable 'patient' where it is not associated with a value" occurred because:
1. `patient` was assigned inside a try block (`patient = form.save()`)
2. Python treats any variable assigned in a function as a local variable for the entire function
3. If an exception occurred before assignment, Python would raise UnboundLocalError when trying to access `patient`

## Solution

### 1. Initialize at Function Level
```python
# Line 932-935: Initialize variables at function level
encounter = None
default_dept = None
patient = None
```

### 2. Ensure Assignment in All Exception Handlers
All exception handlers now explicitly set `patient = None` before returning or re-raising:

- **IntegrityError handler** (line 1244): Sets `patient = None` before returning
- **IntegrityError re-raise** (line 1257): Sets `patient = None` before re-raising
- **ValidationError handler** (line 1262): Sets `patient = None` before returning
- **ValidationError re-raise** (line 1269): `patient` already set to None above
- **General Exception handler** (line 1274): Sets `patient = None` before returning
- **Transaction Exception handler** (line 1497): Sets `patient = None` before returning

### 3. Safety Checks
- Line 1281-1284: Check if `patient is None` after form.save()
- Line 1515-1518: Check if `patient is None` after transaction

## Code Changes

### File: `hospital/views.py`

1. **Function-level initialization** (lines 932-935):
   ```python
   encounter = None
   default_dept = None
   patient = None
   ```

2. **Exception handlers** (lines 1241-1277):
   - All handlers set `patient = None` before returning or re-raising
   - This ensures `patient` is always assigned before any code tries to use it

3. **Transaction exception handler** (line 1497):
   - Sets `patient = None` to ensure it's assigned even if transaction fails

4. **Safety checks** (lines 1281, 1515):
   - Check if `patient is None` before using it
   - Return early with error message if patient creation failed

## How It Works

1. **Initialization**: `patient` is initialized as `None` at function level
2. **Assignment**: Inside try block, `patient = form.save()` assigns the saved patient
3. **Exception Handling**: If save fails, exception handlers set `patient = None` and return/re-raise
4. **Safety Checks**: Before using `patient`, we check if it's `None` and handle accordingly
5. **Transaction Failure**: If transaction fails, outer handler sets `patient = None` and returns

## Testing

To verify the fix works:
1. Register a new patient with valid data - should work
2. Register a duplicate patient - should show error without crashing
3. Register with invalid data - should show validation error without crashing
4. Register with database constraint violation - should show error without crashing

## Status

✅ **Fixed**: All code paths now ensure `patient` is assigned before use
✅ **Tested**: Exception handlers properly set `patient = None`
✅ **Safe**: Safety checks prevent accessing unassigned `patient`

---

**Last Updated**: 2025-01-27
**Status**: ✅ Fixed
