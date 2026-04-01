# ✅ Insurance Companies & Plans Import from db_3 - Complete

## Summary

Successfully imported **79 insurance companies** and created **76 insurance plans** from the `db_3` database dump.

## What Was Imported

### Source File
- **File**: `import/db_3_extracted/insurance_companies.sql`
- **Total Records**: 79 insurance companies

### Import Results
- ✅ **79 Companies Updated** (companies already existed, data refreshed)
- ✅ **76 Plans Created** (3 skipped - cash type companies don't need plans)
- ✅ **All companies linked to their respective plans**

## Insurance Companies Imported

### Major Insurance Companies
1. **APEX MUTUAL HEALTH** (APEX) - Insurance
2. **NHIS** (NHIS) - National Health Insurance
3. **ACACIA HEALTH INSURANCE** (ACA) - Insurance
4. **COSMOPOLITAN HEALTH INSURANCE** (COSMO) - Insurance
5. **GLICO HEALTHCARE** (GLI) - Insurance
6. **KAISER MUTUAL HEALTHCARE** (KAI) - Insurance
7. **METROPOLITAN HEALTH INSURANCE** (METRO) - Insurance
8. **NATIONWIDE MUTUAL HEALTH** (NMH) - Insurance
9. **PHOENIX HEALTH INSURANCE** (PHI) - Insurance
10. **PREMIER MUTUAL HEALTH** (PMH) - Insurance
11. **ACE MEDICAL INSURANCE** (ACE) - Insurance
12. **GAB HEALTH INSURANCE** - Insurance
13. **EQUITY INSURANCE** - Insurance
14. **UNIVERSAL HEALTH INSURANCE** - Insurance
15. **CIGNA INTERNATIONAL** - Insurance
16. **CAL BANK LTD - MEDFOCUS** - Insurance

### Corporate Accounts
- Multiple corporate accounts including:
  - BEIGE CARE
  - ZENITH BANK GHANA LIMITED
  - CAPITAL BANK
  - A1 CAKE BREAD
  - ECG (Electricity Company of Ghana)
  - JAPAN MOTORS
  - And many more...

## Plan Types Created

Each insurance company received a default plan based on their type:

1. **Corporate Plans** (`corporate`) - For corporate accounts
2. **NHIS Plans** (`basic`) - For NHIS
3. **Standard Plans** (`standard`) - For regular insurance companies

### Plan Features
- ✅ 100% coverage for consultations, labs, imaging, pharmacy, surgery, and admissions
- ✅ Active status matching company status
- ✅ Effective date set to today
- ✅ Unique plan codes (e.g., `APEX-PLAN-001`, `NHIS-PLAN-001`)

## Management Command

**Command**: `import_insurance_from_db3`

**Usage**:
```bash
# Dry run (preview)
python manage.py import_insurance_from_db3 --file import/db_3_extracted/insurance_companies.sql --dry-run

# Actual import
python manage.py import_insurance_from_db3 --file import/db_3_extracted/insurance_companies.sql

# Import without creating plans
python manage.py import_insurance_from_db3 --file import/db_3_extracted/insurance_companies.sql --no-create-plans
```

## Data Mapping

### Company Status
- `inactive = 0` → `is_active = True`, `status = 'active'`
- `inactive = 1` → `is_active = False`, `status = 'inactive'`
- `pricelevel = 'cash'` → `status = 'inactive'` (not insurance)

### Plan Type Mapping
- `pricelevel = 'corp'` → Plan Type: `corporate`
- `pricelevel = 'nhis'` → Plan Type: `basic`
- `pricelevel = 'ins'` → Plan Type: `standard`
- `pricelevel = 'cash'` → No plan created

## Code Generation

Company codes are generated from:
1. **CMS ID** (if available) - e.g., "APEX", "NHIS", "COSMO"
2. **Name abbreviation** - First letters of key words
3. **Fallback** - First 4 characters of name

## Verification

To verify the import:

```bash
# Check company count
docker-compose exec web python manage.py shell -c "from hospital.models_insurance_companies import InsuranceCompany; print(InsuranceCompany.objects.count())"

# Check plan count
docker-compose exec web python manage.py shell -c "from hospital.models_insurance_companies import InsurancePlan; print(InsurancePlan.objects.count())"

# List companies with plans
docker-compose exec web python manage.py shell -c "from hospital.models_insurance_companies import InsuranceCompany; [print(f'{c.name}: {c.plans.count()} plans') for c in InsuranceCompany.objects.all()[:10]]"
```

## Next Steps

1. ✅ **Companies Imported** - All 79 companies are in the system
2. ✅ **Plans Created** - 76 default plans created
3. 🔄 **Customize Plans** - Adjust coverage percentages, limits, and exclusions as needed
4. 🔄 **Link Patients** - Link existing patients to their insurance companies and plans
5. 🔄 **Test Billing** - Verify insurance billing works correctly with imported companies

## Files Created

- ✅ `hospital/management/commands/import_insurance_from_db3.py` - Import command

## Status

✅ **COMPLETE** - All insurance companies and plans successfully imported from db_3

---

**Date**: 2026-01-14  
**Command**: `import_insurance_from_db3`  
**Source**: `import/db_3_extracted/insurance_companies.sql`
