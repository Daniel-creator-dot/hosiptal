# ✅ FIX ROBBERT'S ACCOUNTANT ACCESS - READY TO RUN

## Quick Fix Command

When your Django server is running, execute this command:

```bash
python manage.py fix_robbert_accountant
```

## What This Does

The command will:
1. ✅ Find Robbert by username
2. ✅ Remove superuser status (if set) - **WON'T make him superuser**
3. ✅ Ensure is_staff = True (required for login)
4. ✅ Ensure is_active = True
5. ✅ Add to "Accountant" group
6. ✅ Set staff profession = 'accountant'
7. ✅ Verify setup and show dashboard URL

## Expected Output

```
======================================================================
FIXING ROBBERT'S ACCOUNTANT DASHBOARD ACCESS
======================================================================

✅ Found user: robbert.kwamegbologah
   Email: robbert.kwamegbologah@hospital.local
   Full Name: Robbert Kwame Gbologah

[1/5] Ensuring NOT superuser (accounting access only)...
   ✅ Already not superuser

[2/5] Ensuring staff access...
   ✅ Set as staff

[3/5] Ensuring account is active...
   ✅ Account already active

[4/5] Adding to Accountant group...
   ✅ Added to Accountant group

[5/5] Setting up staff record...
   ✅ Updated staff record as accountant

======================================================================
VERIFICATION
======================================================================

Username: robbert.kwamegbologah
Full Name: Robbert Kwame Gbologah
Email: robbert.kwamegbologah@hospital.local

is_staff: True
is_superuser: False ❌ (Should be False)
is_active: True

Groups: ['Accountant']
Staff Profession: accountant

Detected Role: accountant
Dashboard URL: /hms/accountant/comprehensive-dashboard/

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

## After Running

1. **Robbert can now log in** at `/hms/login/`
2. **Will be automatically redirected** to `/hms/accountant/comprehensive-dashboard/`
3. **Has access to all accounting features**
4. **NOT a superuser** (accounting access only)

## Alternative: Manual Fix via Django Admin

If you prefer to fix manually:

1. Go to: `/admin/auth/user/`
2. Find: `robbert.kwamegbologah`
3. Set:
   - ✅ Staff status: Checked
   - ❌ Superuser status: UNCHECKED
   - ✅ Active: Checked
4. Add to "Accountant" group
5. Go to: `/admin/hospital/staff/`
6. Find Robbert's staff record
7. Set Profession: `accountant`
8. Save

## Verification

After running the command, test:

1. **Login as Robbert:**
   - Go to `/hms/login/`
   - Login with Robbert's credentials
   - Should redirect to `/hms/accountant/comprehensive-dashboard/`

2. **Check Dashboard:**
   - Should see accounting KPIs
   - Should see all accounting features
   - Should NOT see admin features

## Important

- ❌ **Robbert will NOT be a superuser**
- ✅ **Robbert will have accountant access only**
- ✅ **Robbert will be restricted to accounting features**

---

**Run the command now:**
```bash
python manage.py fix_robbert_accountant
```






