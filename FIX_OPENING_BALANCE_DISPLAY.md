# ✅ Fixed: Opening Balance Display in General Ledger

**Date:** January 13, 2026  
**Status:** ✅ **COMPLETE**

---

## 🎯 Problem

The General Ledger report was **incorrectly calculating running balances** by adding up debits and credits, when the Excel entries were actually **opening balances** (carried forward from a previous system).

**Issue:**
- Excel entries represent **cumulative balances** from the old system
- The report was treating them as individual transactions and recalculating
- This caused incorrect running balance displays

---

## ✅ Solution

**Updated `hospital/views_accounting_advanced.py` - `general_ledger_report` view:**

### **Before (Wrong):**
```python
# Always recalculated running balance
running_balances[account_code] += entry.debit_amount - entry.credit_amount
entry.running_balance = running_balances[account_code]
```

### **After (Correct):**
```python
# Use stored balance from Excel if available (opening balances)
if entry.balance and entry.balance != 0:
    # Use the stored balance from Excel (opening balance/carried forward)
    entry.running_balance = entry.balance
else:
    # Calculate running balance for new entries only
    if entry.account.account_type in ['asset', 'expense']:
        running_balances[account_code] += entry.debit_amount - entry.credit_amount
    else:
        running_balances[account_code] += entry.credit_amount - entry.debit_amount
    entry.running_balance = running_balances[account_code]
```

---

## 📊 How It Works Now

### **1. Excel Import Entries (Opening Balances)**
- Uses the **stored `balance` field** from `AdvancedGeneralLedger`
- This balance was imported from Excel and represents the **carried forward balance**
- No recalculation needed - displays the balance as-is

### **2. New System Entries**
- If `balance` is 0 or not set, calculates running balance
- Properly handles account types (assets vs liabilities)
- Adds/subtracts based on debits and credits

---

## ✅ Benefits

1. **Correct Display:**
   - Opening balances from Excel show correctly
   - No double-counting or incorrect calculations

2. **Proper Accounting:**
   - Opening balances are preserved as imported
   - New transactions calculate correctly

3. **Flexible:**
   - Works for both Excel imports and new entries
   - Handles different account types correctly

---

## 📋 What Changed

**File:** `hospital/views_accounting_advanced.py`

**Function:** `general_ledger_report`

**Change:** Now checks if entry has a stored balance (from Excel) and uses it directly instead of recalculating.

---

**Status:** ✅ **OPENING BALANCES NOW DISPLAY CORRECTLY**

The General Ledger report now correctly shows the opening balances from Excel as they were imported, without recalculating them as if they were new transactions.
