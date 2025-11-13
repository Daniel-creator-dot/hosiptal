# Database Update Instructions

## Status: System Down - Database Migration Required

The system needs database migrations to be created and applied for the new models.

## Steps to Update Database

### 1. Fix Python Environment (if needed)
If you see `ModuleNotFoundError: No module named 'celery'`, install dependencies:
```bash
pip install -r requirements.txt
```

### 2. Create Migrations
```bash
python manage.py makemigrations hospital --name add_missing_features
```

### 3. Apply Migrations
```bash
python manage.py migrate
```

### 4. Verify Migration
Check that all new tables are created:
```bash
python manage.py showmigrations hospital
```

## New Models Being Added

The following models will be added to the database:

1. **Supplier** - Pharmacy suppliers/vendors
2. **PurchaseOrder** - Purchase orders
3. **PurchaseOrderLine** - PO line items
4. **GoodsReceiptNote** - GRN records
5. **GRNLine** - GRN line items
6. **DrugInteraction** - Drug-drug interactions
7. **Dispensing** - Pharmacy dispensing records
8. **Refund** - Refund processing
9. **Remittance** - Insurance remittance posting
10. **RemittanceLine** - Remittance line items
11. **CriticalResultAlert** - Critical lab result alerts
12. **LabAnalyzerInterface** - Lab analyzer interface configuration
13. **ObservationChart** - Nursing observation charts
14. **PatientPortalAccess** - Patient portal access management
15. **StaffMessage** - Staff messaging system
16. **ReferrerPortal** - Referrer/GP portal access

## If Migrations Fail

### Check for Circular Import Issues
If you see import errors, ensure:
1. `models_missing_features.py` is imported in `models.py` (already added)
2. String references are used for forward references (already done)

### Check Database Connection
Verify database settings in `hms/settings.py`:
```python
DATABASES = {
    'default': {
        # Your database config
    }
}
```

### Backup Before Migration
```bash
python manage.py dumpdata > backup_before_migration.json
```

## After Migration

1. **Register Models in Admin** (optional):
   Add to `hospital/admin.py`:
   ```python
   from .models_missing_features import (
       Supplier, PurchaseOrder, DrugInteraction, Dispensing,
       Refund, Remittance, CriticalResultAlert, ObservationChart,
       PatientPortalAccess, StaffMessage, ReferrerPortal
   )
   ```

2. **Create Superuser** (if needed):
   ```bash
   python manage.py createsuperuser
   ```

3. **Run Server**:
   ```bash
   python manage.py runserver
   ```

## Troubleshooting

### Issue: Foreign Key Constraint Errors
- Ensure ClaimsBatch model exists (it's in models_advanced.py)
- Check that all referenced models are migrated first

### Issue: Default Value Errors
- Date fields now use `date.today` instead of `timezone.now().date`
- This is fixed in the updated models_missing_features.py

### Issue: Module Not Found
- Install all requirements: `pip install -r requirements.txt`
- Activate virtual environment if using one

