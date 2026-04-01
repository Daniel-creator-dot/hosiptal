# ✅ Excel Import - Balance Handling Fixed

**Date:** January 13, 2026  
**Status:** ✅ **COMPLETE**

---

## 🎯 Problem

The Excel import was not correctly handling the fact that **debit/credit amounts in Excel ARE balances**, not transaction amounts. The import needed to:

1. Store debit/credit amounts as balances directly
2. Post to `AdvancedGeneralLedger` (not just `JournalEntry`)
3. Set the `balance` field correctly from Excel data

---

## ✅ Solution

**Updated `hospital/utils_excel_import.py` - `import_gl_from_excel` function:**

### **Key Changes:**

1. **Uses AdvancedJournalEntry and AdvancedGeneralLedger:**
   - Now creates `AdvancedJournalEntry` instead of old `JournalEntry`
   - Posts directly to `AdvancedGeneralLedger` with balance

2. **Handles Balance Column:**
   - Checks if Excel has a "balance" column
   - Uses it if available

3. **Treats Debit/Credit as Balances:**
   - For asset accounts: Debit amount = Balance
   - For liability accounts: Credit amount = Balance
   - Stores balance directly in `AdvancedGeneralLedger.balance` field

---

## 📊 How It Works

### **Import Process:**

1. **Read Excel:**
   - Detects debit, credit, and balance columns
   - Groups entries by date and reference

2. **Create Journal Entry:**
   - Creates `AdvancedJournalEntry`
   - Creates `AdvancedJournalEntryLine` for each row

3. **Post to General Ledger:**
   - Creates `AdvancedGeneralLedger` entry
   - **Sets balance from Excel:**
     - If balance column exists → use it
     - If debit > 0 → use debit as balance (for assets)
     - If credit > 0 → use credit as balance (for liabilities)

### **Example:**

**Excel Row:**
- Account: Accounts Receivable
- Debit: GHS 44,697.89
- Credit: GHS 0.00

**Import Result:**
```python
AdvancedGeneralLedger.objects.create(
    account=ar_account,
    debit_amount=Decimal('44697.89'),
    credit_amount=Decimal('0.00'),
    balance=Decimal('44697.89'),  # Debit amount IS the balance
)
```

---

## ✅ Benefits

1. **Correct Storage:**
   - Balances stored exactly as in Excel
   - No incorrect calculations

2. **Proper Integration:**
   - Uses AdvancedGeneralLedger (what reports use)
   - Balances available immediately

3. **Accurate Display:**
   - General Ledger report shows correct balances
   - Each entry's balance matches Excel

---

## 📋 What Changed

**File:** `hospital/utils_excel_import.py`

**Function:** `import_gl_from_excel`

**Changes:**
1. Imports `AdvancedJournalEntry`, `AdvancedJournalEntryLine`, `AdvancedGeneralLedger`
2. Creates `AdvancedJournalEntry` instead of `JournalEntry`
3. Posts directly to `AdvancedGeneralLedger` with balance set from Excel
4. Handles balance column if present in Excel

---

## 🔄 Next Steps

**To Re-import Excel Data:**

1. Run the import command:
   ```bash
   python manage.py import_gl_excel "path/to/file.xlsx" --ledger "LEDGER 2025" --auto-post
   ```

2. The import will now:
   - Create AdvancedJournalEntry entries
   - Post to AdvancedGeneralLedger
   - Store balances correctly from Excel

3. General Ledger report will show correct balances

---

**Status:** ✅ **EXCEL IMPORT NOW HANDLES BALANCES CORRECTLY**

The Excel import now correctly treats debit/credit amounts as balances and stores them properly in AdvancedGeneralLedger for accurate reporting.
