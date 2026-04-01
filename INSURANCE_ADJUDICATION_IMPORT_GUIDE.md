# Insurance Adjudication Report Import Guide

## Overview

This guide explains how to import insurance adjudication reports from Excel files into the hospital management system. The import script creates `InsuranceReceivable` records and proper accounting journal entries.

## Prerequisites

1. **Install Required Libraries:**
   ```bash
   pip install pandas xlrd openpyxl
   ```
   
   The script supports multiple Excel reading libraries:
   - `pandas` (recommended - supports both .xls and .xlsx)
   - `xlrd` (for .xls files)
   - `openpyxl` (for .xlsx files)

2. **Ensure Insurance Company Exists:**
   - The insurance company must exist in the `Payer` model
   - Payer type should be: `insurance`, `private`, or `nhis`
   - Check existing payers: Django Admin → Payers

3. **Excel File Format:**
   - Supports both `.xls` (old format) and `.xlsx` (new format)
   - First row should contain column headers
   - Data should start from the second row (or specify with `--start-row`)

## Required Excel Columns

The script automatically detects common column names. At minimum, you need:

### Required Columns:
- **Patient Identifier**: Column containing patient MRN, name, or phone number
  - Common names: `Patient`, `Patient Name`, `MRN`, `Member Name`, `Member ID`
  
- **Amount**: Column containing the billed/claim amount
  - Common names: `Amount`, `Total`, `Total Amount`, `Billed Amount`, `Charge`

### Optional Columns:
- **Invoice Number**: `Invoice`, `Invoice Number`, `Bill Number`
- **Claim Number**: `Claim`, `Claim Number`, `Claim No`
- **Claim Date**: `Claim Date`, `Date`, `Service Date`, `Visit Date`
- **Amount Paid**: `Paid`, `Amount Paid`, `Approved`, `Approved Amount`
- **Amount Rejected**: `Rejected`, `Rejection`, `Amount Rejected`, `Denied`
- **Withholding Tax**: `WHT`, `Withholding Tax`, `Tax`, `Tax Withheld`
- **Service Type**: `Service`, `Service Type`, `Category`, `Department`

## Basic Usage

### 1. Dry Run (Recommended First)
Test the import without making changes:

```bash
python manage.py import_insurance_adjudication \
    "insurance excel/COSMO-ADJUDICATION REPORT.xls" \
    --insurance-company "COSMOPOLITAN HEALTH INSURANCE" \
    --dry-run
```

### 2. Actual Import
Once dry run looks good, run the actual import:

```bash
python manage.py import_insurance_adjudication \
    "insurance excel/COSMO-ADJUDICATION REPORT.xls" \
    --insurance-company "COSMOPOLITAN HEALTH INSURANCE"
```

## Advanced Options

### Specify Sheet Name
If Excel has multiple sheets:

```bash
python manage.py import_insurance_adjudication \
    "file.xlsx" \
    --insurance-company "Company Name" \
    --sheet-name "Adjudication Data"
```

### Custom Header Row
If headers are not in the first row:

```bash
python manage.py import_insurance_adjudication \
    "file.xlsx" \
    --insurance-company "Company Name" \
    --header-row 2 \
    --start-row 3
```

### Custom Column Mapping
If column names don't match automatically:

```bash
python manage.py import_insurance_adjudication \
    "file.xlsx" \
    --insurance-company "Company Name" \
    --column-mapping '{"patient_identifier": "Member ID", "amount": "Billed Amount", "claim_number": "Claim #"}'
```

### Skip Journal Entries
If you don't want accounting entries created:

```bash
python manage.py import_insurance_adjudication \
    "file.xlsx" \
    --insurance-company "Company Name" \
    --no-create-journal-entries
```

## Column Mapping Format

The `--column-mapping` option accepts a JSON string mapping internal field names to Excel column names:

```json
{
  "patient_identifier": "Member ID",
  "invoice_number": "Invoice #",
  "claim_number": "Claim Number",
  "claim_date": "Service Date",
  "amount": "Total Billed",
  "amount_paid": "Amount Approved",
  "amount_rejected": "Rejected Amount",
  "withholding_tax": "WHT",
  "service_type": "Department"
}
```

## What Gets Created

### 1. InsuranceReceivable Records
- One record per row in the Excel file
- Links to patient, invoice (if found), and insurance company
- Tracks: total amount, amount paid, balance due, status

### 2. Journal Entries (if enabled)
- **Debit**: Accounts Receivable (Insurance Company)
- **Credit**: Service Revenue
- Automatically posted to General Ledger
- Balanced (debits = credits)

### 3. Account Creation
- Creates Accounts Receivable account for insurance company if needed
- Uses account code: `1200-{insurance_company_id}`
- Creates default revenue account if needed: `4100` (Service Revenue)

## Patient Matching

The script tries multiple methods to find patients:

1. **MRN** (Medical Record Number) - Exact match
2. **Name** - First name and last name match (case-insensitive)
3. **Phone Number** - Exact match

If patient is not found, the row is skipped with an error message.

## Invoice Matching

If `invoice_number` column is provided:
- Script tries to find matching invoice by invoice number
- If found, links receivable to invoice
- If not found, receivable is created without invoice link (still valid)

## Status Determination

Receivable status is set automatically:
- **Paid**: If `amount_paid >= total_amount`
- **Partial**: If `amount_paid > 0` but less than total
- **Pending**: If `amount_paid = 0` (default)

## Error Handling

The script:
- ✅ Continues processing even if individual rows fail
- ✅ Reports all errors at the end
- ✅ Shows row numbers for failed rows
- ✅ Validates data before importing
- ✅ Uses database transactions (all or nothing per row)

## Output Summary

After import, you'll see:

```
============================================================
IMPORT SUMMARY
============================================================
Total rows in file: 150
Rows processed: 148
Records created: 145
Records updated: 3
Records skipped: 0
Errors: 2
============================================================
```

## Verification

After import, verify the data:

### 1. Check Insurance Receivables
```python
# In Django shell
from hospital.models_accounting_advanced import InsuranceReceivable
from hospital.models import Payer

payer = Payer.objects.get(name__icontains="COSMO")
receivables = InsuranceReceivable.objects.filter(insurance_company=payer)
print(f"Total receivables: {receivables.count()}")
print(f"Total amount: {sum(r.total_amount for r in receivables)}")
```

### 2. Check Journal Entries
```python
from hospital.models_accounting_advanced import AdvancedJournalEntry

entries = AdvancedJournalEntry.objects.filter(
    reference__startswith="IR"
).order_by('-entry_date')[:10]

for entry in entries:
    print(f"{entry.entry_number}: {entry.total_debit} (Debit = Credit: {entry.is_balanced})")
```

### 3. Check Accounting Balances
```python
from hospital.models_accounting import Account

ar_account = Account.objects.get(account_code__startswith="1200")
revenue_account = Account.objects.get(account_code="4100")

# Check balances (requires General Ledger entries)
print(f"AR Balance: {ar_account.balance}")
print(f"Revenue: {revenue_account.balance}")
```

## Troubleshooting

### Error: "Insurance company not found"
- Check the exact name in Django Admin → Payers
- Use partial name matching (script uses `icontains`)
- Ensure payer type is `insurance`, `private`, or `nhis`

### Error: "Patient not found"
- Verify patient exists in database
- Check MRN format matches exactly
- Try using patient name instead of MRN
- Check for typos in Excel file

### Error: "No Excel reading library found"
```bash
pip install pandas xlrd openpyxl
```

### Error: "Invalid amount"
- Check for non-numeric values in amount column
- Remove currency symbols (₵, GHS, $)
- Check for commas in numbers (script handles this)

### Error: "Missing required columns"
- Use `--column-mapping` to specify custom column names
- Check Excel file has headers in first row
- Use `--header-row` if headers are elsewhere

## Example Files

Sample Excel files are located in:
```
insurance excel/
├── COSMO-ADJUDICATION REPORT - PRIMECARE MEDICAL CENTRE-1ST OCT 2025 - 31ST OCT 2025.XLS
├── EQUITY-ADJUDICATION REPORT - PRIMECARE MEDICAL CENTRE-1ST AUG 2025 - 31ST AUG 2025.XLS
└── GAB-ADJUDICATION REPORT - PRIMECARE MEDICAL CENTRE-1ST SEP 2025 - 30TH SEP 2025.XLS
```

## Best Practices

1. **Always run dry-run first** to check for errors
2. **Backup database** before large imports
3. **Import in batches** for very large files (split Excel if needed)
4. **Verify data** after import using Django Admin or shell
5. **Keep Excel files** as backup/reference
6. **Document** any custom column mappings used

## Support

For issues or questions:
1. Check error messages in import output
2. Review this guide
3. Check Django Admin for created records
4. Use Django shell to inspect data

## Related Commands

- `python manage.py check_enrollment` - Check insurance enrollment status
- `python manage.py import_insurance_data` - Import insurance companies
- `python manage.py import_legacy_patients` - Import patients from legacy system



