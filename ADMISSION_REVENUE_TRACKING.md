# Admission Revenue Tracking - Complete Implementation

## ✅ Admission Revenue Account Added

Your accounting system now tracks **Admission/Bed Revenue** in account **4060**!

---

## 📊 What's Changed

### Accounting Dashboard - Key Account Balances

**Before** (5 accounts):
```
1010 - Cash
4010 - Laboratory Revenue
4020 - Pharmacy Revenue  
4030 - Imaging Revenue
4040 - Consultation Revenue
```

**After** (6 accounts):
```
1010 - Cash
4010 - Laboratory Revenue
4020 - Pharmacy Revenue
4030 - Imaging Revenue
4040 - Consultation Revenue
4060 - Admission Revenue      ← NEW!
```

---

## 💰 How Admission Revenue Works

### Automatic Posting
When bed charge payment is processed:
1. **Debit**: Cash/Card/Mobile Money account (1010/1020/1030)
2. **Credit**: Admission Revenue account (**4060**)

### Example Journal Entry
```
Date: Nov 7, 2025
Description: Bed charges payment - Receipt RCP20251107...

Debit  1010 Cash                    GHS 360.00
       Credit 4060 Admission Revenue         GHS 360.00

To record: Bed charges for 3 days @ GHS 120/day
```

---

## 🔄 Revenue Flow

```
Patient Admitted
    ↓
Bed charges created (GHS 120)
    ↓
Shows in cashier pending bills
    ↓
Payment Processed
    ↓
Receipt generated
    ↓
ACCOUNTING SYNC:
- Debit: Cash (1010)
- Credit: Admission Revenue (4060)
    ↓
Posted to General Ledger
    ↓
Shows in Accounting Dashboard
```

---

## 📈 Where to See Admission Revenue

### 1. **Accounting Dashboard**
**URL**: http://127.0.0.1:8000/hms/accounting/

**Key Account Balances Section**:
- Shows **4060 - Admission Revenue** with current balance
- Updates automatically when bed charge payments processed

### 2. **General Ledger**
**URL**: http://127.0.0.1:8000/hms/accounting/ledger/

Filter by account 4060 to see:
- All bed charge payment entries
- Running balance
- Transaction dates and descriptions

### 3. **Trial Balance**
**URL**: http://127.0.0.1:8000/hms/accounting/trial-balance/

Shows:
- Account 4060 with total credits (revenue)
- Balances with other accounts

### 4. **Financial Statement**
**URL**: http://127.0.0.1:8000/hms/accounting/financial-statement/

Income Statement section shows:
- Revenue breakdown including Admission Revenue

---

## 🧪 Testing the Feature

### Test 1: Process Bed Payment
```
1. Go to cashier dashboard
2. Find a patient with bed charges
3. Process payment (GHS 120 or more)
4. Payment processed successfully
5. Go to accounting dashboard
6. See Account 4060 balance increased by payment amount
```

### Test 2: Check General Ledger
```
1. Go to: /hms/accounting/ledger/
2. Filter by Account 4060
3. See entry:
   - Credit: GHS XXX
   - Description: Bed charges payment
   - Reference: Receipt number
   - Balance: Running total
```

### Test 3: Financial Reports
```
1. Go to: /hms/accounting/financial-statement/
2. Income Statement section
3. Revenue breakdown shows:
   - Laboratory Revenue: GHS XXX
   - Pharmacy Revenue: GHS XXX
   - Imaging Revenue: GHS XXX
   - Consultation Revenue: GHS XXX
   - Admission Revenue: GHS XXX  ← Should appear here
```

---

## 🔧 Files Modified

### Backend:
1. **`hospital/services/accounting_sync_service.py`**
   - Added `revenue_admission` to ACCOUNT_CODES (4060)
   - Added 'admission' and 'bed' mappings to revenue account
   - Auto-creates Admission Revenue account if missing

2. **`hospital/views_accounting.py`**
   - Added account 4060 to key_accounts display
   - Dashboard now shows 6 key accounts instead of 5

### Already Configured:
1. **`hospital/management/commands/setup_accounting_accounts.py`**
   - Already had Account 4060 'Admission Revenue' defined
   - Verified account exists in database

---

## 📊 Revenue Breakdown

After processing payments, your accounting dashboard will show:

```
Key Account Balances:

Cash (1010)
Balance: GHS 10,865.00         ← Includes bed payments

Laboratory Revenue (4010)
Balance: GHS 170.00

Pharmacy Revenue (4020)
Balance: GHS 40.00

Imaging Revenue (4030)
Balance: GHS 250.00

Consultation Revenue (4040)
Balance: GHS 8,640.00

Admission Revenue (4060)       ← NEW!
Balance: GHS 360.00            ← Bed charge payments
```

---

## 💡 Example Scenarios

### Scenario 1: Single Day Admission
```
Admission: 1 day
Charge: GHS 120
Payment processed

Accounting Entry:
Debit  1010 Cash              120.00
       Credit 4060 Admission Revenue  120.00

Dashboard Shows:
Cash: +120
Admission Revenue: +120
```

### Scenario 2: Multi-Day Stay
```
Admission: 5 days
Charge: GHS 600 (5 × 120)
Payment processed

Accounting Entry:
Debit  1010 Cash              600.00
       Credit 4060 Admission Revenue  600.00

Dashboard Shows:
Cash: +600
Admission Revenue: +600
```

### Scenario 3: Combined Payment
```
Services:
- Lab: GHS 50
- Pharmacy: GHS 30
- Bed (3 days): GHS 360

Total: GHS 440

Individual Accounting Entries:
Debit  1010 Cash              50.00
       Credit 4010 Lab Revenue        50.00

Debit  1010 Cash              30.00
       Credit 4020 Pharmacy Revenue   30.00

Debit  1010 Cash              360.00
       Credit 4060 Admission Revenue  360.00

Dashboard Shows:
Cash: +440
Lab Revenue: +50
Pharmacy Revenue: +30
Admission Revenue: +360
```

---

## 🎯 Service Type Mapping

When processing payments, service types map to revenue accounts:

| Service Type | Account Code | Account Name |
|-------------|--------------|--------------|
| `lab` | 4010 | Laboratory Revenue |
| `pharmacy` | 4020 | Pharmacy Revenue |
| `imaging` | 4030 | Imaging Revenue |
| `consultation` | 4040 | Consultation Revenue |
| `procedure` | 4050 | Procedure Revenue |
| **`admission`** | **4060** | **Admission Revenue** ← NEW! |
| **`bed`** | **4060** | **Admission Revenue** ← NEW! |
| `combined` | 4000 | General Revenue (master) |

---

## 📋 Chart of Accounts Structure

```
ASSETS (1xxx)
├── 1010 Cash on Hand
├── 1020 Card Receipts
├── 1030 Mobile Money
├── 1040 Bank Transfer
└── 1200 Accounts Receivable

LIABILITIES (2xxx)
├── 2010 Unearned Revenue
└── 2020 Accounts Payable

EQUITY (3xxx)
├── 3010 Owner's Equity
└── 3020 Retained Earnings

REVENUE (4xxx)
├── 4000 General Revenue
├── 4010 Laboratory Revenue
├── 4020 Pharmacy Revenue
├── 4030 Imaging Revenue
├── 4040 Consultation Revenue
├── 4050 Procedure Revenue
└── 4060 Admission Revenue    ← NEW!

EXPENSES (5xxx)
├── 5010 Salaries & Wages
├── 5020 Medical Supplies
├── 5030 Utilities
├── 5040 Rent
└── 5050 Depreciation
```

---

## 🚀 What to Do Now

### Refresh Accounting Dashboard
```
http://127.0.0.1:8000/hms/accounting/
```

**You should see**:
- 6 key account balances (including Admission Revenue)
- Current balance for account 4060
- If you've already processed bed payments, the balance will show
- If no bed payments yet, balance will be GHS 0.00

### Process a Bed Payment
```
1. Go to cashier dashboard
2. Admit a patient (if none admitted)
3. Process bed charge payment
4. Go back to accounting dashboard
5. See Account 4060 balance increase by payment amount
```

### View General Ledger
```
1. Go to: /hms/accounting/ledger/
2. Filter by Account: 4060 - Admission Revenue
3. See all bed charge payment entries
4. Verify credits posted correctly
```

---

## ✅ Complete Integration Status

### Bed Billing System:
✅ Auto-charges on admission (GHS 120/day)  
✅ Appears in cashier dashboard immediately  
✅ Shows in patient bills  
✅ Can be paid individually or combined  
✅ Real-time charge updates  
✅ Final calculation at discharge  

### Accounting Integration:
✅ Revenue account created (4060)  
✅ Accounting sync service updated  
✅ **Dashboard displays Admission Revenue** ← JUST FIXED!  
✅ Automatic journal entries  
✅ General ledger posting  
✅ Financial reporting  

---

## 📊 Reporting Capabilities

### Revenue by Service Type
You can now analyze:
- Lab revenue: Account 4010
- Pharmacy revenue: Account 4020
- Imaging revenue: Account 4030
- Consultation revenue: Account 4040
- **Admission revenue: Account 4060** ← Track bed occupancy revenue

### Monthly Admission Revenue
```sql
SELECT SUM(credit_amount) as admission_revenue
FROM hospital_generalledger
WHERE account_code = '4060'
  AND transaction_date >= '2025-11-01'
  AND transaction_date < '2025-12-01'
  AND is_deleted = FALSE
```

### Bed Occupancy Revenue Analysis
```python
from hospital.models_accounting import GeneralLedger, Account
from decimal import Decimal

admission_account = Account.objects.get(account_code='4060')
total_admission_revenue = GeneralLedger.objects.filter(
    account=admission_account,
    is_deleted=False
).aggregate(Sum('credit_amount'))['credit_amount__sum'] or Decimal('0.00')

# Calculate number of bed-days billed
daily_rate = Decimal('120.00')
total_bed_days = total_admission_revenue / daily_rate

print(f"Total Admission Revenue: GHS {total_admission_revenue}")
print(f"Total Bed-Days Billed: {total_bed_days}")
```

---

## 🎉 Summary

**Issue**: No admission charges tracking in accounting dashboard  
**Cause**: Account 4060 existed but wasn't included in dashboard display  
**Fix**: Added account 4060 to key accounts list  
**Result**: Admission Revenue now tracked and displayed  

**Status**: ✅ **COMPLETE**

---

**What You'll See After Refresh**:
1. ✅ 6 key account balances (was 5)
2. ✅ Account 4060 - Admission Revenue
3. ✅ Current balance based on processed bed payments
4. ✅ Updates automatically when bed payments processed
5. ✅ Full audit trail in General Ledger

---

**Refresh your accounting dashboard to see the Admission Revenue account!** 📊

**URL**: http://127.0.0.1:8000/hms/accounting/

---

**Implemented**: November 7, 2025  
**Account Code**: 4060 - Admission Revenue  
**Daily Rate**: GHS 120.00  
**Integration**: Complete across billing and accounting systems
























