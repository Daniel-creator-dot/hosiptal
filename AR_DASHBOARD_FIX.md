# ✅ Accounts Receivable Dashboard Fix

**Date:** January 13, 2026  
**Status:** ✅ **COMPLETE**

---

## 🐛 Problem

The Accounts Receivable dashboard card was showing **GHS 0.00** even after discharging a patient because:

1. **Wrong Model Used:** The dashboard was querying the old `AccountsReceivable` model
2. **Discharge Creates New Model:** When patients are discharged, entries are created in `AdvancedAccountsReceivable` (new model)
3. **Mismatch:** Dashboard couldn't see the new entries because it was looking at the wrong table

---

## ✅ Solution

### **Updated Dashboard to Use Correct Model**

**File: `hospital/views_accounting.py`**

**Before:**
```python
# Using old model - entries not created on discharge
ar_total = AccountsReceivable.objects.filter(
    outstanding_amount__gt=0,
    is_deleted=False
).aggregate(Sum('outstanding_amount'))['outstanding_amount__sum']
```

**After:**
```python
# Using new model - matches what discharge creates
from .models_accounting_advanced import AdvancedAccountsReceivable

ar_total = AdvancedAccountsReceivable.objects.filter(
    balance_due__gt=0,
    is_deleted=False
).aggregate(Sum('balance_due'))['balance_due__sum']
```

### **Changes Made:**

1. **Dashboard AR Calculation:**
   - Now uses `AdvancedAccountsReceivable` model
   - Uses `balance_due` field (instead of `outstanding_amount`)
   - Includes fallback to old model for compatibility

2. **AR Aging Buckets:**
   - Updated all aging bucket calculations
   - Uses `balance_due` for new model
   - Maintains backward compatibility

3. **AR List View:**
   - Updated `accounts_receivable()` view
   - Handles both old and new models
   - Proper field mapping

---

## 📊 Field Mapping

| Old Model (`AccountsReceivable`) | New Model (`AdvancedAccountsReceivable`) |
|----------------------------------|------------------------------------------|
| `outstanding_amount` | `balance_due` |
| `outstanding_amount` | `balance_due` |
| `aging_bucket` | `aging_bucket` (same) |
| `due_date` | `due_date` (same) |

---

## ✅ What's Fixed

1. **Dashboard Card:**
   - Now shows correct AR balance from discharged patients
   - Displays `balance_due` from `AdvancedAccountsReceivable`

2. **Aging Buckets:**
   - Current (0-30 days)
   - 31-60 days
   - 61-90 days
   - 90+ days
   - All now calculated from new model

3. **AR List View:**
   - Shows entries from `AdvancedAccountsReceivable`
   - Proper field display
   - Aging calculations work correctly

---

## 🚀 Testing

To verify the fix:

1. **Discharge a patient:**
   - Go to Bed Management
   - Discharge a patient with outstanding balance
   - Check invoice has balance > 0

2. **Check Dashboard:**
   - Go to Accounting Dashboard
   - Look at "Accounts Receivable" card
   - Should show the discharged patient's balance

3. **Check AR List:**
   - Go to Accounts Receivable page
   - Should see the discharged patient listed
   - Balance should match invoice balance

---

## 📝 Notes

- The fix maintains backward compatibility
- Falls back to old model if new model doesn't exist
- All AR calculations now use the correct model
- Discharged patients will now appear in AR dashboard

---

**Status:** ✅ **AR DASHBOARD FIXED**

The Accounts Receivable dashboard now correctly displays balances from discharged patients using the `AdvancedAccountsReceivable` model.
