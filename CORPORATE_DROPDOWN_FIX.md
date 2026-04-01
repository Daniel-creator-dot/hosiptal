# ✅ Corporate Company Dropdown Fixed

## Problem
The "Corporate Company" dropdown in the patient registration form was empty, showing only placeholder dashes ("---------"), even though we had created 66 corporate Payers in the database.

## Root Cause
The form was trying to load corporate companies from the `CorporateAccount` model, but we had created `Payer` records with `payer_type='corporate'` instead.

## Solution

### 1. Updated Form (`hospital/forms.py`)
Changed the `selected_corporate_company` field to load from `Payer` model:

```python
# Load corporate companies from Payer model (corporate payers)
try:
    from .models import Payer
    corporate_payers = Payer.objects.filter(
        payer_type='corporate',
        is_active=True,
        is_deleted=False
    ).order_by('name')
    
    if corporate_payers.exists():
        self.fields['selected_corporate_company'].queryset = corporate_payers
    else:
        # Fallback to CorporateAccount if no corporate payers exist
        from .models_enterprise_billing import CorporateAccount
        self.fields['selected_corporate_company'].queryset = CorporateAccount.objects.filter(
            is_active=True,
            is_deleted=False
        ).order_by('company_name')
```

### 2. Updated View (`hospital/views.py`)
Updated the corporate enrollment logic to handle `Payer` objects instead of `CorporateAccount`:

```python
# selected_corporate_company is now a Payer object (not CorporateAccount)
payer = selected_corporate_company

# Ensure it's corporate type
if payer.payer_type != 'corporate':
    payer.payer_type = 'corporate'
    payer.save(update_fields=['payer_type'])

# Set primary_insurance for billing
patient.primary_insurance = payer
patient.save(update_fields=['primary_insurance'])
```

## Result

✅ **66 Corporate Payers** now available in the dropdown:
- ZENITH BANK GHANA LIMITED
- CAPITAL BANK
- Universal Merchant Bank
- REPUBLIC BANK LTD
- CUMMINS GHANA LIMITED
- JAPAN MOTORS
- NATIONWIDE TECHNOLOGIES LTD
- And 59 more...

## Verification

```bash
# Check corporate payers
docker-compose exec web python manage.py shell -c "
from hospital.models import Payer
corp = Payer.objects.filter(payer_type='corporate', is_active=True, is_deleted=False)
print(f'Corporate Payers: {corp.count()}')
"
```

## Status

✅ **FIXED** - Corporate companies now show in the dropdown when "Corporate" payment type is selected.

---

**Date**: 2026-01-14  
**Issue**: Corporate dropdown empty  
**Fix**: Changed form to load from `Payer` model instead of `CorporateAccount`
