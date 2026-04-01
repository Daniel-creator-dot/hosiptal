# JERRY.XLSX Import - Complete Guide

## 🎯 What This Does

Imports debtors (insurance companies) and creditors (suppliers) from JERRY.xlsx and ensures they appear in ALL accounting reports and statements.

## ✅ What Gets Created

### 1. **Payer Records** (Insurance Companies)
- Creates/updates Payer records for debtors
- Sets `payer_type='private'` (NOT corporate)
- Ensures they're active

### 2. **Supplier Records** (Creditors)
- Creates/updates Supplier records
- **NOT added as insurance** (as requested)
- Ensures they're active

### 3. **Insurance Receivable Entries**
- Creates `InsuranceReceivableEntry` for each debtor with balance
- Links to journal entries
- Appears in:
  - Insurance Receivable page
  - Balance Sheet (Account 1100/1201)
  - General Ledger
  - Trial Balance
  - AR Aging Report

### 4. **Accounts Payable Entries**
- Creates `AccountsPayable` for each creditor with balance
- Links to journal entries
- Appears in:
  - Accounts Payable Report
  - Balance Sheet (Account 2000)
  - General Ledger
  - Trial Balance

### 5. **Journal Entries**
- **For Debtors (Insurance):**
  - Debit: Accounts Receivable (1100)
  - Credit: Consultation Revenue (4110)
  
- **For Creditors (Suppliers):**
  - Debit: Operating Expenses (5100)
  - Credit: Accounts Payable (2000)

## 📋 After Docker Desktop Restart

### Step 1: Start Docker Desktop
```powershell
# Wait for Docker to fully start
```

### Step 2: Run the Fix and Import Script
```powershell
cd D:\chm
python fix_and_import_jerry.py
```

This script will:
1. ✅ Check if `InsuranceReceivableEntry` table exists
2. ✅ Create it if missing
3. ✅ Run the import command
4. ✅ Verify all records were created

### Step 3: Verify Records Appear

#### Check Insurance Receivable Page:
```
http://192.168.2.216:8000/hms/accountant/insurance-receivable/
```
Should show all imported insurance receivable entries.

#### Check Balance Sheet:
```
http://192.168.2.216:8000/hms/accounting/balance-sheet/
```
Should show:
- **Assets:** Insurance Receivables (Account 1100/1201)
- **Liabilities:** Accounts Payable (Account 2000)

#### Check Accounts Payable Report:
```
http://192.168.2.216:8000/hms/accounting/ap-report/
```
Should show all imported supplier balances.

#### Check General Ledger:
```
http://192.168.2.216:8000/hms/accounting/general-ledger/
```
Should show journal entries for:
- Account 1100 (Accounts Receivable) - Debit entries
- Account 4110 (Consultation Revenue) - Credit entries
- Account 5100 (Operating Expenses) - Debit entries
- Account 2000 (Accounts Payable) - Credit entries

#### Check Trial Balance:
```
http://192.168.2.216:8000/hms/accounting/trial-balance/
```
Should show all accounts with balances, including imported ones.

## 🔍 Manual Import (If Script Fails)

If the script fails, run manually:

```powershell
# 1. Check migrations
python manage.py migrate

# 2. Run import
python manage.py import_jerry_excel

# 3. Verify
python check_jerry_import_status.py
```

## 📊 Where Records Appear

### **Insurance Receivables (Debtors):**

1. **Insurance Receivable List Page**
   - URL: `/hms/accountant/insurance-receivable/`
   - Shows: Entry number, insurance company, amount, status

2. **Balance Sheet**
   - Account: 1100 (Accounts Receivable) or 1201 (Insurance Receivables)
   - Shows: Total outstanding insurance receivables

3. **General Ledger**
   - Account: 1100 (Accounts Receivable)
   - Shows: Debit entries for each receivable

4. **Trial Balance**
   - Shows: Account 1100 balance (debit)

5. **AR Aging Report** (if exists)
   - Shows: Aging buckets for insurance receivables

### **Accounts Payable (Creditors):**

1. **Accounts Payable Report**
   - URL: `/hms/accounting/ap-report/`
   - Shows: Bill number, vendor, amount, due date

2. **Balance Sheet**
   - Account: 2000 (Accounts Payable)
   - Shows: Total outstanding payables

3. **General Ledger**
   - Account: 2000 (Accounts Payable)
   - Shows: Credit entries for each payable

4. **Trial Balance**
   - Shows: Account 2000 balance (credit)

5. **Expense Report**
   - Account: 5100 (Operating Expenses)
   - Shows: Expenses from imported payables

## ✅ Verification Checklist

After import, verify:

- [ ] Insurance Receivable entries created
- [ ] Accounts Payable entries created
- [ ] Journal entries created and posted
- [ ] Records visible in Insurance Receivable page
- [ ] Records visible in Balance Sheet
- [ ] Records visible in General Ledger
- [ ] Records visible in Trial Balance
- [ ] Records visible in AP Report
- [ ] All amounts match JERRY.xlsx

## 🚨 Troubleshooting

### Table Doesn't Exist Error
```powershell
# Run the fix script
python fix_and_import_jerry.py
```

### Import Fails
1. Check Excel file exists: `insurance excel/JERRY.xlsx`
2. Check file has correct sheets: "DEBTOR BALANCES" and "CREDITOR BALANCES"
3. Check database connection

### Records Don't Show in Reports
1. Check journal entries were posted
2. Check account codes match (1100, 2000, 4110, 5100)
3. Refresh the report page
4. Check date filters on reports

## 📝 Notes

- **Payers are set to `payer_type='private'`** (NOT corporate)
- **Suppliers are NOT added as insurance**
- All journal entries are automatically posted
- All amounts are in GHS (Ghana Cedis)
- Duplicate entries are skipped if they already exist

## 🎯 Complete Tracking

Every imported record is fully tracked:

1. **Source:** JERRY.xlsx Excel file
2. **Database:** InsuranceReceivableEntry / AccountsPayable tables
3. **Journal Entries:** AdvancedJournalEntry with lines
4. **General Ledger:** AdvancedGeneralLedger entries
5. **Reports:** Balance Sheet, Trial Balance, AP Report, etc.

**Complete audit trail from Excel to Financial Statements!** ✅


