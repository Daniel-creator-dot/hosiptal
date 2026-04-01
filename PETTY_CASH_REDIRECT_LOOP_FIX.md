# ✅ Petty Cash Redirect Loop Fix - Complete

## Problem
The petty cash page (`/hms/accounting/petty-cash/`) was causing a "too many redirects" error (ERR_TOO_MANY_REDIRECTS).

## Root Cause
The views were using `@user_passes_test` decorator which redirects to the login page when the test fails. When a logged-in user fails the test, this creates a redirect loop:
1. User tries to access petty cash
2. `user_passes_test` fails → redirects to login
3. User is already logged in → login redirects back
4. Loop continues

## Fix Applied

**File:** `hospital/views_petty_cash.py`

### 1. Added `role_required` Import
```python
from .decorators import role_required
```

### 2. Updated Access Check Functions
- Added `senior_account_officer` to `is_account_personnel()` 
- Added `senior_account_officer` to `is_account_officer()`

### 3. Replaced All `@user_passes_test` with `@role_required`

**Changed:**
```python
@login_required
@user_passes_test(is_account_personnel)
def petty_cash_list(request):
```

**To:**
```python
@login_required
@role_required('account_personnel', 'account_officer', 'accountant', 'senior_account_officer', 'admin')
def petty_cash_list(request):
```

## Views Updated

✅ `petty_cash_list` - Changed to `role_required`
✅ `petty_cash_create` - Changed to `role_required`
✅ `petty_cash_detail` - Changed to `role_required`
✅ `petty_cash_submit` - Changed to `role_required`
✅ `petty_cash_approve` - Changed to `role_required` (officer roles only)
✅ `petty_cash_reject` - Changed to `role_required` (officer roles only)
✅ `petty_cash_approval_list` - Changed to `role_required` (officer roles only)
✅ `petty_cash_mark_paid` - Changed to `role_required` (officer roles only)

## Why This Fixes the Issue

`role_required` decorator:
- Shows an "Access Denied" page instead of redirecting to login
- Prevents redirect loops
- Provides better user experience
- Includes proper error messages

## Status

✅ **FIXED** - Petty cash page should now load without redirect loops.

The page will either:
- Show the petty cash list (if user has access)
- Show an "Access Denied" page (if user doesn't have access)
- **No more redirect loops!**





