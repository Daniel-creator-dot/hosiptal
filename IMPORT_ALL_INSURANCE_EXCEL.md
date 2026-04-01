# Import All Insurance Excel Files - Quick Guide

## Quick Start

To import ALL Excel files from the "insurance excel" folder:

```bash
# Dry run first (recommended)
python manage.py import_all_insurance_excel --dry-run

# Actual import
python manage.py import_all_insurance_excel
```

## What It Does

1. **Scans** the "insurance excel" folder for all .xls and .xlsx files
2. **Detects** insurance company from filename (COSMO, EQUITY, GAB, etc.)
3. **Creates** insurance companies if they don't exist
4. **Imports** all receivables from each file
5. **Creates** journal entries for accounting
6. **Shows** summary of what was imported

## Files Found

The script will process:
- COSMO-ADJUDICATION REPORT files
- EQUITY-ADJUDICATION REPORT files  
- GAB-ADJUDICATION REPORT files
- JERRY.xlsx (if it's an insurance file)

## Viewing Imported Data

After import, view the data at:
- **Insurance Receivable List**: `/hms/accountant/insurance-receivable/`
- **Django Admin**: `/admin/hospital/insurancereceivable/`

## Requirements

Install Excel reading libraries:
```bash
pip install pandas xlrd openpyxl
```

## Troubleshooting

If you get "No module named 'pandas'":
```bash
pip install pandas xlrd openpyxl
```

If insurance company not found, the script will create it automatically.



