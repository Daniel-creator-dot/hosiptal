# ✅ Discharge Accounting Fix

**Date:** January 13, 2026  
**Status:** ✅ **COMPLETE**

---

## 🐛 Problem

When a patient was discharged:
- Bed charges were calculated and invoice was updated
- **BUT** accounting entries (AR/Receivables) were not being created or updated
- Discharge didn't show in accounting system

---

## ✅ Solution

### **1. Enhanced Invoice Update Handling**

Updated `signals_accounting.py` to properly handle invoice updates (not just creation):

**For Insurance/Corporate Payers:**
- Now checks for existing `InsuranceReceivableEntry` by invoice number (not just amount)
- Updates existing entry when invoice amount changes on discharge
- Recalculates revenue breakdown from invoice lines
- Updates outstanding amount based on invoice balance

**For Cash Payers:**
- Now updates existing `AdvancedAccountsReceivable` when invoice amount changes
- Recalculates `balance_due` properly: `invoice_amount - amount_paid`
- Logs update for audit trail

### **2. Discharge Process Enhancement**

Updated `bed_billing_service.py`:
- Ensures `issued_at` timestamp is set when invoice is updated
- Explicitly triggers accounting signal after invoice save
- This ensures AR entries are created/updated immediately on discharge

---

## 🔧 Technical Changes

### **File: `hospital/signals_accounting.py`**

**Before:**
- Only checked for existing entries by exact amount match
- Didn't update existing entries when invoice changed
- Could create duplicates if amount changed

**After:**
- Finds existing entries by invoice number in notes
- Updates existing entries with new amounts
- Recalculates revenue breakdown from invoice lines
- Updates outstanding amounts properly

### **File: `hospital/services/bed_billing_service.py`**

**Added:**
- Sets `issued_at` timestamp if missing
- Explicitly triggers `post_save` signal after invoice save
- Ensures accounting sync happens immediately

---

## 📊 How It Works Now

### **Discharge Flow:**

```
1. Patient Discharged
   ↓
2. Bed Billing Service calculates final charges
   ↓
3. Invoice updated with final bed charges
   ↓
4. Invoice status set to 'issued'
   ↓
5. Invoice.save() triggers post_save signal
   ↓
6. Signal checks for existing AR entry
   ↓
7. If exists: Updates with new amount
   If not: Creates new AR entry
   ↓
8. Accounting entries created/updated
   ↓
9. Shows in accounting system ✅
```

---

## ✅ What's Fixed

1. **AR Entries Created on Discharge:**
   - Insurance/Corporate: Creates/updates `InsuranceReceivableEntry`
   - Cash: Creates/updates `AdvancedAccountsReceivable`

2. **Amount Updates:**
   - Existing entries are updated when invoice amount changes
   - Revenue breakdown recalculated from invoice lines
   - Outstanding amounts properly updated

3. **No Duplicates:**
   - Checks for existing entries by invoice number
   - Updates instead of creating duplicates

4. **Immediate Sync:**
   - Accounting entries created/updated immediately on discharge
   - No manual intervention needed

---

## 🚀 Testing

To verify the fix:

1. **Discharge a patient:**
   - Go to Bed Management
   - Discharge a patient
   - Check invoice is updated with final charges

2. **Check Accounting:**
   - Go to Accounting Dashboard
   - Check Accounts Receivable
   - Should see entry for discharged patient
   - Amount should match final bed charges

3. **Check Insurance Receivables:**
   - If patient has insurance/corporate payer
   - Check Insurance Receivables
   - Should see entry with correct breakdown

---

## 📝 Notes

- The fix handles both new invoices and updated invoices
- Works for all payer types (cash, insurance, corporate)
- Revenue breakdown is automatically calculated from invoice lines
- All changes are logged for audit trail

---

**Status:** ✅ **DISCHARGE ACCOUNTING FIXED**

Discharged patients now properly show in accounting system with correct AR entries and amounts.
