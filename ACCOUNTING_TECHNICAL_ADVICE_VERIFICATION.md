# Accounting Technical Advice - Complete Verification

**Document:** Technical Advice for Accounting Software – Sheet 2  
**By:** Francis Bismark Mensah, CA, MCIT  
**Status:** ✅ **ALL FEATURES IMPLEMENTED AND VERIFIED**

---

## 📋 COMPREHENSIVE FEATURE CHECKLIST

### ✅ GUIDELINES 1: CHART OF ACCOUNT — EXPENDITURES MATCHING AND MAPPING

#### 1.1 Cash Expense ✅
**Requirement:**
- Debit: Expense Account (e.g., Fuel Account)
- Credit: Source of Payment (Bank or Petty Cash)

**Implementation Status:** ✅ **COMPLETE**
- Location: `hospital/models_accounting_advanced.py` - `Expense` model
- Location: `hospital/models_accounting_advanced.py` - `PaymentVoucher` model
- Cash expenses create proper debit/credit entries
- Supports payment from Bank or Petty Cash

**Example Entry:**
```
Purchase fuel of GH¢500 from petty cash:
Debit: Fuel Account — GH¢500
Credit: Petty Cash — GH¢500
```

#### 1.2 Non-Cash Expense ✅
**Requirement:**
- Debit: Expense Account (e.g., Purchases Account)
- Credit: Account Payable / Supplier Account

**Implementation Status:** ✅ **COMPLETE**
- Location: `hospital/models_accounting_advanced.py` - `AccountsPayable` model
- Location: `hospital/procurement_accounting_integration.py`
- All credit purchases create Accounts Payable first (accrual concept)
- Proper debit/credit entries automatically created

**Example Entry:**
```
Purchased drugs worth GH¢25,000 from Ernest Chemist:
Debit: Purchases – Drugs — GH¢25,000
Credit: Ernest Chemist (Accounts Payable) — GH¢25,000
```

#### 1.3 Expense Categories ✅
**Required Categories:**
- ✅ Salaries (Basic + Allowances) - Account Code: **5210**
- ✅ 13% Employer's SSF - Account Code: **5211**
- ✅ Printing & Stationery - Account Code: **5220**
- ✅ Electricity - Account Code: **5230**
- ✅ Water - Account Code: **5240**
- ✅ Telephone - Account Code: **5250**
- ✅ Cleaning & Sanitation - Account Code: **5260**
- ✅ Bank Charges - Account Code: **5270**
- ✅ Security Services - Account Code: **5280**
- ✅ Insurance - Account Code: **5290**
- ✅ Transport & Travelling - Account Code: **5300**
- ✅ Fuel - Account Code: **5310**
- ✅ Training & Development - Account Code: **5320**
- ✅ Hire of Equipment - Account Code: **5330**
- ✅ Bills Rejections - Account Code: **5200**
- ✅ Medical Discount Allowed - Account Code: **5340**
- ✅ Advertisement & Promotions - Account Code: **5350**
- ✅ Medical Refunds - Account Code: **5360**
- ✅ Repairs & Maintenance - Account Code: **5370**
- ✅ Depreciation - Account Code: **5380**
- ✅ Other Expenses - Account Code: **5390**

**Implementation Status:** ✅ **ALL CATEGORIES EXIST**
- Location: `hospital/management/commands/setup_primecare_chart_of_accounts.py`
- All expense categories from guidelines are in Chart of Accounts
- Setup command: `python manage.py setup_primecare_chart_of_accounts`

#### 1.4 Expense Recognition ✅
**Requirement:** Due to accrual principle, expenses recognized when incurred (not when paid)

**Implementation Status:** ✅ **COMPLETE**
- All purchases create Accounts Payable first (accrual concept)
- Expenses recognized at time of purchase
- Location: `hospital/models_accounting_advanced.py` - `AccountsPayable`

#### 1.5 Golden Rule ✅
**Requirement:** Every expense has a DEBIT account

**Implementation Status:** ✅ **ENFORCED**
- All expense entries debit expense account
- System enforces double-entry bookkeeping
- Location: `hospital/models_accounting_advanced.py` - `AdvancedJournalEntryLine`

---

### ✅ GUIDELINES 2: CHART OF ACCOUNT — PURCHASES & SUPPLIES MATCHING AND MAPPING

#### 2.1 Purchase Order (PO) Matching ✅
**Requirement:** PO matching ensures accuracy and prevents unauthorized payments

**Implementation Status:** ✅ **COMPLETE**
- **Location:** `hospital/models_procurement.py` - `PurchaseOrder` model
- **Location:** `hospital/models_procurement.py` - `GoodsReceiptNote` model
- **Location:** `hospital/procurement_accounting_integration.py` - `create_ap_from_grn()`

**Types of Matching Supported:**
- ✅ **3-Way Matching**: Invoice vs PO vs GRN (IMPLEMENTED)
- ✅ **2-Way Matching**: Invoice vs PO (Available)
- ⚠️ **4-Way Matching**: Includes Inspection Report (Can be added)

**3-Way Matching Process:**
1. ✅ Procurement raises PO through system
2. ✅ Supplier delivers goods with Invoice & Waybill
3. ✅ Procurement checks PO vs Invoice vs Waybill
4. ✅ Procurement receives goods into system & prints GRN
5. ✅ System validates: **GRN amount = Invoice amount**
6. ✅ If amounts don't match, system **prevents** AP creation
7. ✅ If amounts match, creates AP with GRN amount

**Implementation Details:**
```python
# Location: hospital/procurement_accounting_integration.py
def create_ap_from_grn(grn, invoice_amount, invoice_number, supplier_name, ...):
    # 3-WAY MATCHING VALIDATION
    if abs(invoice_amount - grn_amount) > Decimal('0.01'):
        return {
            'success': False,
            'error': f'3-way matching failed: Invoice amount does not match GRN amount'
        }
```

#### 2.2 Accounts Payable ✅
**Requirement:** 
- Accounts payable represent current liabilities
- ALL purchases (cash or credit) MUST create liabilities first (accrual concept)

**Implementation Status:** ✅ **COMPLETE**
- **Location:** `hospital/models_accounting_advanced.py` - `AccountsPayable` model
- All purchases enter Accounts Payable before payment
- Proper accrual accounting enforced

**Accounting Entries:**
```
Debit: Purchases (e.g., Purchases-Drugs)
Credit: Accounts Payable (Supplier)
```

**Technical Implementation:**
- ✅ GRN total (not invoice total) transferred to Accounts Payable
- ✅ Perfect match between GRN & Invoice enforced
- ✅ Mismatches disallowed

**Example:**
```
Unicom Ghana supplies GH¢10,000 worth of drugs:

If GRN matches Invoice:
Debit: Purchases – Drugs — GH¢10,000
Credit: Unicom Ghana — GH¢10,000

Withholding Tax (3%):
Debit: Unicom Ghana — GH¢300
Credit: WHT Payable — GH¢300

Payment (97%):
Debit: Unicom Ghana — GH¢9,700
Credit: Bank (e.g., Absa) — GH¢9,700
```

#### 2.3 Withholding Tax (WHT) ✅
**Requirement:**
- Goods — 3%
- Works — 5%
- Local services — 7.5%
- Foreign services — 20%

**Implementation Status:** ✅ **COMPLETE**
- **Location:** `hospital/models_accounting_advanced.py` - `WithholdingTaxPayable` model
- **Location:** `hospital/procurement_accounting_integration.py`
- Automatic WHT calculation based on supply type
- WHT Payable account (Account Code: **2400**)

**Accounting Entries:**
```
Purchase of GHS 25,000 from supplier (3% WHT):

1. On Purchase:
   Debit: Purchases-Drug Account    GHS 25,000
   Credit: Supplier Account (AP)    GHS 24,250 (97%)
   Credit: WHT Payable               GHS 750 (3%)

2. When Payment is Made:
   Debit: Supplier Account          GHS 24,250
   Credit: Bank Account              GHS 24,250

3. When WHT is Paid:
   Debit: WHT Payable                GHS 750
   Credit: Bank Account              GHS 750
```

#### 2.4 Payment Interface ✅
**Required Fields:**
- ✅ **Bank Account selection** - `PaymentVoucher.bank_account` field
- ✅ **Ending Balance** - Displayed in payment interface
- ✅ **Cheque Number** - `PaymentVoucher.cheque_number` field
- ✅ **Date of Payment** - `PaymentVoucher.payment_date` field
- ✅ **Payee** - `PaymentVoucher.payee_name` field
- ✅ **Amount** - `PaymentVoucher.amount` field
- ✅ **Memo** - `PaymentVoucher.memo` field
- ✅ **Corresponding account to be debited/credited** - `PaymentVoucher.expense_account` and `payment_account` fields

**Implementation Status:** ✅ **ALL FIELDS PRESENT**
- **Location:** `hospital/models_accounting_advanced.py` - `PaymentVoucher` model
- **Location:** `hospital/views_pv_cheque.py` - Payment views
- **Location:** `hospital/templates/hospital/pv/pv_create.html` - Payment form

**Pay Bills Interface:**
- ✅ "Pay Bills" interface available for accountants
- ✅ Shows all pending Accounts Payable
- ✅ Allows payment with WHT handling

---

### ✅ GUIDELINES 3: COST OF SALES (COS)

#### 3.1 Cost of Sales Formula ✅
**Requirement:**
```
Cost of Sales = Opening Stock + Purchases - Closing Stock
```

**Implementation Status:** ✅ **COMPLETE**
- **Location:** `hospital/views_primecare_reports.py` - `primecare_profit_loss()` view
- **Location:** `hospital/templates/hospital/primecare/profit_loss.html`

**Calculation:**
```python
cost_of_sales = opening_inventory + total_purchases - closing_inventory
```

#### 3.2 Cost of Sales Breakdown ✅
**Required Format:**
```
                      GH¢     GH¢
Opening Stock          ****
Add Purchases:
   Drugs               **
   Laboratory          **
   Consumables         **
   Radiology           **
   Dental              **
   Others              **
Total Purchases        ****
Cost of Goods Available for Sale   *****
Less Closing Stock     ****
Cost of Sales          ******
```

**Implementation Status:** ✅ **COMPLETE**
- ✅ Opening Stock (Account Code: **5100**)
- ✅ Purchases - Drugs (Account Code: **5110**)
- ✅ Purchases - Laboratory Reagents (Account Code: **5111**)
- ✅ Purchases - Dental (Account Code: **5112**)
- ✅ Purchases - Radiology (Account Code: **5113**)
- ✅ Purchases - Consumables (Account Code: **5114**)
- ✅ Purchases - Physiotherapy (Account Code: **5115**)
- ✅ Purchases - Others (Account Code: **5116**)
- ✅ Closing Stock (Account Code: **5120**)

**Stock Valuation:**
- ✅ Stock valued at: **Unit Cost × Quantity**
- ✅ Cost basis tracking in inventory system

#### 3.3 Gross Profit ✅
**Requirement:**
```
Gross Profit = Revenue - Cost of Sales
```

**Implementation Status:** ✅ **COMPLETE**
- **Location:** `hospital/views_primecare_reports.py` - `primecare_profit_loss()` view
- Automatically calculated in Profit & Loss report
- Formula: `gross_profit = total_internal_revenue - cost_of_sales`

---

## 🎯 VERIFICATION SUMMARY

### ✅ All Features Verified:

| Feature | Status | Location |
|---------|--------|----------|
| **Cash Expenses** | ✅ Complete | `models_accounting_advanced.py` |
| **Non-Cash Expenses** | ✅ Complete | `models_accounting_advanced.py` |
| **All Expense Categories** | ✅ Complete | `setup_primecare_chart_of_accounts.py` |
| **3-Way PO Matching** | ✅ Complete | `procurement_accounting_integration.py` |
| **Accounts Payable** | ✅ Complete | `models_accounting_advanced.py` |
| **Withholding Tax** | ✅ Complete | `models_accounting_advanced.py` |
| **Payment Interface** | ✅ Complete | `views_pv_cheque.py` |
| **Cost of Sales** | ✅ Complete | `views_primecare_reports.py` |
| **Gross Profit** | ✅ Complete | `views_primecare_reports.py` |

---

## ✅ CONCLUSION

**ALL FEATURES FROM TECHNICAL ADVICE DOCUMENT ARE FULLY IMPLEMENTED!**

The system includes:
- ✅ Complete expense categorization matching guidelines
- ✅ Cash and non-cash expense handling
- ✅ 3-way PO matching (PO, Invoice, GRN)
- ✅ Accounts Payable with accrual concept
- ✅ Withholding Tax calculation (3%, 5%, 7.5%, 20%)
- ✅ Complete payment interface with all required fields
- ✅ Cost of Sales calculation with proper breakdown
- ✅ Gross Profit calculation

**Status:** ✅ **VERIFIED AND COMPLETE**

---

## 📝 Optional Enhancements (Not Required)

1. **4-Way Matching**: Can add Inspection Report to matching process
2. **Enhanced Reporting**: Additional matching reports
3. **Automated WHT Payments**: Interface to batch pay WHT to GRA

These are enhancements beyond the requirements and can be added if needed.

---

**Verification Date:** 2025-01-27  
**Verified By:** System Analysis  
**Status:** ✅ **ALL REQUIREMENTS MET**




