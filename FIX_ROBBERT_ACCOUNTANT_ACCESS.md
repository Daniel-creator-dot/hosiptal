# ✅ Fix Robbert's Accountant Dashboard Access

## Problem
Robbert has no access to the account dashboard and needs to be fixed WITHOUT making him a superuser.

## Solution
Ensure Robbert is properly configured as an Accountant with:
- ✅ In "Accountant" Django group
- ✅ Staff profession = 'accountant'
- ✅ is_staff = True (required for login)
- ✅ is_active = True
- ❌ is_superuser = False (NOT superuser - accounting only)

## Quick Fix Script

Run this script to fix Robbert's access:

```bash
python fix_robbert_accountant_access.py
```

## Manual Fix (via Django Admin)

If you can't run the script, fix manually:

### Step 1: Find Robbert's User
1. Go to Django Admin: `/admin/auth/user/`
2. Search for username: `robbert.kwamegbologah` (or `robbert`)
3. Click on the user

### Step 2: Set User Permissions
- ✅ **Staff status**: Checked (is_staff = True)
- ❌ **Superuser status**: UNCHECKED (is_superuser = False)
- ✅ **Active**: Checked (is_active = True)

### Step 3: Add to Accountant Group
1. Scroll to "Groups" section
2. Select "Accountant" group
3. Click "Save"

### Step 4: Set Staff Profession
1. Go to: `/admin/hospital/staff/`
2. Find Robbert's staff record (linked to his user)
3. Edit the staff record
4. Set **Profession** to: `accountant`
5. Ensure **Is active** is checked
6. Ensure **Is deleted** is UNCHECKED
7. Click "Save"

## Verification

After fixing, verify:

1. **Login as Robbert:**
   - Go to `/hms/login/`
   - Login with Robbert's credentials
   - Should automatically redirect to `/hms/accountant/comprehensive-dashboard/`

2. **Check Role Detection:**
   - Run: `python check_user_roles.py`
   - Should show:
     - Role: `accountant`
     - Dashboard: `/hms/accountant/comprehensive-dashboard/`
     - Groups: `['Accountant']`

3. **Test Dashboard Access:**
   - Visit: `/hms/accountant/comprehensive-dashboard/`
   - Should load without errors
   - Should show accounting KPIs and features

## What the Script Does

The `fix_robbert_accountant_access.py` script:

1. **Finds Robbert** by username
2. **Removes superuser status** (if set)
3. **Ensures is_staff = True** (required for login)
4. **Ensures is_active = True** (account must be active)
5. **Adds to Accountant group** (for role detection)
6. **Sets staff profession = 'accountant'** (fallback role detection)
7. **Verifies setup** and shows dashboard URL

## Expected Result

After running the script:

```
✅ SUCCESS! Robbert is properly configured as Accountant!

Access Details:
  ✅ Can log in (is_staff=True, is_active=True)
  ✅ NOT superuser (accounting access only)
  ✅ In Accountant group
  ✅ Staff profession = 'accountant'
  ✅ Will redirect to: /hms/accountant/comprehensive-dashboard/

Dashboard Access:
  • Main Dashboard: /hms/accountant/comprehensive-dashboard/
  • All accounting features under /hms/accountant/
  • Payment vouchers: /hms/accounting/pv/
  • Cheques: /hms/accounting/cheques/
  • Chart of Accounts: /hms/accountant/chart-of-accounts/
```

## Role Detection Logic

The system detects Robbert as an accountant through:

1. **Primary Method:** Django Groups
   - Checks if user is in "Accountant" group
   - If found, returns role = 'accountant'

2. **Fallback Method:** Staff Profession
   - If no group found, checks `staff.profession`
   - If `profession == 'accountant'`, returns role = 'accountant'

3. **Dashboard URL:**
   - For role = 'accountant', returns: `/hms/accountant/comprehensive-dashboard/`

## Troubleshooting

### If Robbert still can't access dashboard:

1. **Check Group Membership:**
   ```python
   from django.contrib.auth import get_user_model
   User = get_user_model()
   user = User.objects.get(username='robbert.kwamegbologah')
   print(user.groups.all())  # Should show Accountant group
   ```

2. **Check Staff Profession:**
   ```python
   from hospital.models import Staff
   staff = Staff.objects.get(user=user)
   print(staff.profession)  # Should be 'accountant'
   ```

3. **Check Role Detection:**
   ```python
   from hospital.utils_roles import get_user_role, get_user_dashboard_url
   role = get_user_role(user)
   url = get_user_dashboard_url(user)
   print(f"Role: {role}, Dashboard: {url}")
   ```

4. **Check Login Redirect:**
   - Login as Robbert
   - Check if redirects to `/hms/accountant/comprehensive-dashboard/`
   - If not, check `hospital/views_auth.py` `get_success_url()` method

## Important Notes

- ❌ **DO NOT** make Robbert a superuser
- ✅ **DO** ensure he's in Accountant group
- ✅ **DO** ensure staff.profession = 'accountant'
- ✅ **DO** ensure is_staff = True (required for login)
- ✅ **DO** ensure is_active = True

## Access Permissions

Robbert (as Accountant) will have access to:
- ✅ `/hms/accountant/comprehensive-dashboard/` - Main dashboard
- ✅ `/hms/accountant/*` - All accountant features
- ✅ `/hms/accounting/*` - Accounting features
- ✅ `/hms/invoices/` - Invoice management
- ✅ `/hms/payments/` - Payment tracking
- ✅ `/hms/cashier/*` - Cashier features
- ✅ `/hms/procurement/accounts/*` - Procurement accounts approval

Robbert (as Accountant) will NOT have access to:
- ❌ `/admin/` - Django admin (unless is_staff=True, but restricted by middleware)
- ❌ `/hms/admin-dashboard/` - Admin dashboard
- ❌ `/hms/procurement/requests/*` - Procurement management (only approval)

## Conclusion

After running the fix script or manual steps, Robbert will:
- ✅ Have access to accountant dashboard
- ✅ Be able to log in and see accounting features
- ✅ NOT be a superuser (accounting access only)
- ✅ Be properly restricted to accounting features only






