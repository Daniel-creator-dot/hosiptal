# Fix 403 Forbidden Admin Access

## Issue
Accountant user getting 403 Forbidden when accessing admin panel for ProfitLossReport.

## Root Cause
User permissions are correct, but Django admin requires:
1. `is_staff=True` ✓ (Granted)
2. Model-specific permissions ✓ (Granted - 164 permissions)
3. Active session with updated permissions

## Solution Applied
1. ✅ Granted `is_staff=True` to accountant user
2. ✅ Granted all accounting model permissions (164 permissions)
3. ✅ Verified all ProfitLossReport permissions are present

## Verification
Run: `python manage.py verify_accountant_permissions --username robbert.kwamegbologah`

Results:
- is_staff: True
- add_profitlossreport: True
- change_profitlossreport: True
- view_profitlossreport: True
- delete_profitlossreport: True
- Can access admin: True

## Next Steps
**The user needs to log out and log back in** for the session to refresh with new permissions.

## Alternative Solution
If logout/login doesn't work, clear the browser cache and cookies for the site.

## Commands Available
- `python manage.py grant_accountant_admin_access --all-accountants` - Grant admin access
- `python manage.py verify_accountant_permissions --username USERNAME` - Verify permissions

