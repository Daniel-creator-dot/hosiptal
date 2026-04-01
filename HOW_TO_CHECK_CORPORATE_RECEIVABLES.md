# How to Check Corporate Receivables

## Overview
Corporate receivables are amounts owed by corporate clients (companies) for services provided to their employees. This guide shows you how to view and track corporate receivables in the system.

## Methods to Check Corporate Receivables

### 1. **Dedicated Corporate Receivables Report** (Recommended)
**URL**: `/hms/accounting/corporate-receivables/`

This report shows:
- All outstanding receivables from corporate payers only
- Aging breakdown (Current, 0-30, 31-60, 61-90, 90+ days)
- Filter by specific corporate payer
- Filter by aging bucket
- Total outstanding amounts

**Features**:
- Shows only invoices with `payer_type='corporate'`
- Includes aging analysis
- Can filter by specific corporate company
- Can filter by aging period

### 2. **General Accounts Receivable Aging Report**
**URL**: `/hms/accounting/ar-aging/`

This shows ALL receivables (corporate, insurance, cash). To identify corporate receivables:
- Look for invoices where the payer type is "Corporate"
- The payer name will be the corporate company name

### 3. **Django Admin**
**URL**: `/admin/hospital/advancedaccountsreceivable/`

Filter by:
- Invoice → Payer → Payer Type = "corporate"
- Balance Due > 0

### 4. **Using Django Shell/Management Command**

You can also check programmatically:

```python
from hospital.models_accounting_advanced import AdvancedAccountsReceivable
from hospital.models import Payer

# Get all corporate receivables
corporate_ar = AdvancedAccountsReceivable.objects.filter(
    balance_due__gt=0,
    invoice__payer__payer_type='corporate'
).select_related('invoice', 'invoice__payer', 'patient')

# Total corporate receivables
total = sum(ar.balance_due for ar in corporate_ar)
print(f"Total Corporate Receivables: GHS {total:,.2f}")

# By corporate payer
for payer in Payer.objects.filter(payer_type='corporate', is_active=True):
    payer_ar = corporate_ar.filter(invoice__payer=payer)
    payer_total = sum(ar.balance_due for ar in payer_ar)
    print(f"{payer.name}: GHS {payer_total:,.2f}")
```

## Understanding Corporate Receivables

### What are Corporate Receivables?
- Amounts owed by corporate clients for services provided to their employees
- Created when invoices are issued with `payer_type='corporate'`
- Tracked in `AdvancedAccountsReceivable` model
- Linked to `Invoice` → `Payer` (where `payer_type='corporate'`)

### Key Fields:
- **Invoice**: The original invoice
- **Patient**: The employee/patient who received services
- **Payer**: The corporate company (with `payer_type='corporate'`)
- **Balance Due**: Outstanding amount
- **Due Date**: When payment is expected
- **Aging Bucket**: How old the receivable is (0-30, 31-60, 61-90, 90+ days)

## Quick Access Links

1. **Corporate Receivables Report**: 
   - `http://192.168.2.216:8000/hms/accounting/corporate-receivables/`

2. **All Receivables (including corporate)**:
   - `http://192.168.2.216:8000/hms/accounting/ar-aging/`

3. **Admin - Advanced Accounts Receivable**:
   - `http://192.168.2.216:8000/admin/hospital/advancedaccountsreceivable/`

4. **Admin - Corporate Payers**:
   - `http://192.168.2.216:8000/admin/hospital/payer/?payer_type__exact=corporate`

## Notes

- Corporate receivables are separate from **Insurance Receivables** (which use `InsuranceReceivableEntry`)
- Corporate receivables use the standard `AdvancedAccountsReceivable` model
- Make sure the payer is set to `payer_type='corporate'` when creating invoices for corporate clients
- The aging buckets help identify overdue accounts that need collection follow-up


