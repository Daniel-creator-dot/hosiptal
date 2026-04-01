# ✅ Fixed: Independent Balances (No Cumulative Calculation)

**Date:** January 13, 2026  
**Status:** ✅ **COMPLETE**

---

## 🎯 Problem

The General Ledger report was still showing **cumulative running balances** instead of **independent balances** for each entry. Each entry represents a different company's balance and should be displayed independently.

**Issue:**
- Entry 1: Debit GHS 44,697.89 → Balance showed GHS 475,561.22 (wrong - cumulative)
- Entry 2: Debit GHS 10,339.30 → Balance showed GHS 10,339.30 (correct)
- Entry 3: Debit GHS 6,070.60 → Balance showed GHS 16,409.90 (wrong - cumulative: 10,339.30 + 6,070.60)

**Root Cause:**
- View was using stored `balance` field which may have been calculated cumulatively
- Should always use `debit_amount` directly as the balance for Excel entries

---

## ✅ Solution

**Updated `hospital/views_accounting_advanced.py` - `general_ledger_report` view:**

### **Before (Wrong):**
```python
# Was checking stored balance first (which may be cumulative)
if entry.balance and entry.balance != 0:
    entry.running_balance = entry.balance  # Wrong - may be cumulative
elif entry.debit_amount > 0:
    entry.running_balance = entry.debit_amount
```

### **After (Correct):**
```python
# Always use debit/credit amount directly as balance (for Excel entries)
# Each entry is independent - don't use stored balance which may be cumulative
if entry.debit_amount and entry.debit_amount > 0:
    entry.running_balance = entry.debit_amount  # Debit IS the balance
elif entry.credit_amount and entry.credit_amount > 0:
    entry.running_balance = entry.credit_amount  # Credit IS the balance
elif entry.balance and entry.balance != 0:
    entry.running_balance = entry.balance  # Fallback only
```

---

## 📊 How It Works Now

### **Excel Entries (Opening Balances):**
- **Debit Amount = Balance** (for that specific company)
- Each entry is **independent**
- No cumulative calculation
- Each company's balance shown separately

### **Example:**
```
Entry 1: Ghana Comm. Tech. University
- Debit: GHS 44,697.89
- Balance: GHS 44,697.89 (not cumulative)

Entry 2: Anointed Electricals Limited
- Debit: GHS 10,339.30
- Balance: GHS 10,339.30 (not cumulative, independent)

Entry 3: Asuogyaman Company Limited
- Debit: GHS 6,070.60
- Balance: GHS 6,070.60 (not cumulative, independent)
```

---

## ✅ Key Changes

1. **Priority Order:**
   - **First:** Use `debit_amount` as balance (for Excel entries)
   - **Second:** Use `credit_amount` as balance (for liability accounts)
   - **Last:** Use stored `balance` field (fallback only)

2. **No Cumulative Calculation:**
   - Each entry's balance = its own debit/credit amount
   - No addition of previous balances
   - Each company's balance is independent

3. **Preserves Excel Values:**
   - Debit amounts from Excel are used directly
   - No recalculation or cumulative totals

---

## 📋 What Changed

**File:** `hospital/views_accounting_advanced.py`

**Function:** `general_ledger_report`

**Change:** Now **always** uses `debit_amount` or `credit_amount` directly as the balance for Excel entries, ignoring any stored balance that may have been calculated cumulatively.

---

**Status:** ✅ **INDEPENDENT BALANCES NOW DISPLAYED CORRECTLY**

The General Ledger report now shows each entry's balance independently, matching the debit amount from Excel, with no cumulative calculation.
