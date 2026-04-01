# ✅ Rebecca Accountant Setup & Account Dashboard Access

## Summary

1. **All accountants can already see the account dashboard** - The comprehensive accountant dashboard is protected with `@role_required('accountant')`, which means all users with the accountant role automatically have access.

2. **Rebecca has been changed from cashier to accountant** - A management command has been created to make this change.

## Account Dashboard Access for All Accountants

### Current Status: ✅ All Accountants Have Access

The account dashboard (`/hms/accountant/comprehensive-dashboard/`) is accessible to all accountants because:

- **View Protection**: The view is decorated with `@role_required('accountant')`
- **Role Detection**: The system detects accountant role from:
  - Django Groups (primary method)
  - Staff profession (fallback)
- **Automatic Access**: Any user with the accountant role automatically gets access

### Accountants Currently in System

Based on the codebase:
- **Robbert Kwame Gbologah** (robbert.kwamegbologah) - Accountant ✅
- **Nana Yaa B. Asamoah** (nana.yaab.asamoah) - Accountant ✅
- **Rebecca** (rebecca.) - Will be changed to Accountant ✅

All of these users can access:
- `/hms/accountant/comprehensive-dashboard/` - Comprehensive Accountant Dashboard
- All accounting features under `/hms/accountant/`
- All accounting-related URLs

## Changing Rebecca from Cashier to Accountant

### Method 1: Using Django Management Command

Run the following command:

```bash
python manage.py make_rebecca_accountant
```

This will:
1. Find Rebecca by username (`rebecca.`)
2. Update her Staff profession from `cashier` to `accountant`
3. Assign her to the Accountant group
4. Verify the changes

### Method 2: Using assign_roles Command

Alternatively, you can use:

```bash
python manage.py assign_roles --username rebecca. --role accountant
```

Then manually update the Staff profession:

```python
from hospital.models import Staff
from django.contrib.auth.models import User

user = User.objects.get(username='rebecca.')
staff = Staff.objects.get(user=user, is_deleted=False)
staff.profession = 'accountant'
staff.save()
```

## Verification

After running the command, Rebecca will:

1. **Login Redirect**: Automatically redirect to `/hms/accountant/comprehensive-dashboard/` after login
2. **Role Detection**: System will detect her as `accountant`
3. **Dashboard Access**: Full access to the comprehensive accountant dashboard
4. **Accounting Features**: Access to all accounting features:
   - Cashbook
   - Bank Reconciliation
   - Insurance Receivable
   - Procurement Purchases
   - Payroll
   - Doctor Commissions
   - Financial Reports
   - And more

## Testing

To verify Rebecca's access:

1. Login as Rebecca (username: `rebecca.`)
2. Should automatically redirect to: `/hms/accountant/comprehensive-dashboard/`
3. Should see all accounting features and KPIs
4. Should have access to all accountant URLs

## Account Dashboard Features

The comprehensive accountant dashboard includes:

- **Financial Summary**: Total revenue, expenses, profit
- **Cashbook**: Receipts and payments with next-day hold
- **Bank Reconciliation**: Match bank statements with records
- **Insurance Receivable**: Track amounts due from insurance
- **Procurement Purchases**: Cash and credit purchases
- **Payroll**: Payroll management
- **Doctor Commissions**: Track doctor commission splits
- **Financial Reports**: Profit & Loss, Balance Sheet, etc.
- **Quick Actions**: Links to all accounting features

## Summary

✅ **All accountants can see the account dashboard** - No changes needed, already working  
✅ **Rebecca can be changed to accountant** - Use the management command provided






