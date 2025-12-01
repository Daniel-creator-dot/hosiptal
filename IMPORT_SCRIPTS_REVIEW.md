# Import Scripts Review - Duplicate Prevention Checklist

## Scripts That Create Patients/Staff

These scripts need to be reviewed to ensure they check for duplicates before creating records.

### Patient Import Scripts

1. **`hospital/management/commands/import_legacy_patients.py`**
   - Status: ⚠️ **REVIEW NEEDED**
   - Should check: MRN, National ID, Email, Name+DOB+Phone
   - Action: Add duplicate checking before `Patient.objects.create()`

2. **`hospital/management/commands/migrate_legacy_to_django.py`**
   - Status: ⚠️ **REVIEW NEEDED**
   - Should check: MRN, National ID, Email
   - Action: Use `get_or_create()` instead of `create()`

3. **`hospital/management/commands/bulk_migrate_legacy.py`**
   - Status: ⚠️ **REVIEW NEEDED**
   - Should check: MRN, National ID, Email
   - Action: Add duplicate checking

4. **`import_patient_final.py`**
   - Status: ⚠️ **REVIEW NEEDED**
   - Should check: MRN, National ID, Email
   - Action: Add duplicate checking

5. **`restore_staff_and_patients.py`**
   - Status: ⚠️ **REVIEW NEEDED**
   - Should check: Employee ID, Username, Email (for staff)
   - Should check: MRN, National ID, Email (for patients)
   - Action: Add duplicate checking

6. **`hospital/views_legacy_patients.py`** (migrate_legacy_patient function)
   - Status: ⚠️ **REVIEW NEEDED**
   - Should check: MRN, National ID, Email
   - Action: Add duplicate checking

### Staff Import Scripts

1. **`hospital/management/commands/import_staff.py`**
   - Status: ⚠️ **REVIEW NEEDED**
   - Should check: Username, Email, Employee ID
   - Action: Use `get_or_create()` instead of `create()`

2. **`restore_staff_and_patients.py`**
   - Status: ⚠️ **REVIEW NEEDED**
   - Should check: Employee ID, Username, Email
   - Action: Add duplicate checking

3. **`create_specialists.py`**
   - Status: ⚠️ **REVIEW NEEDED**
   - Should check: Username, Email
   - Action: Already uses `get_or_create()` - ✅ Good

4. **`hospital/views_it_operations.py`** (create_user function)
   - Status: ⚠️ **REVIEW NEEDED**
   - Should check: Username, Email
   - Action: Already checks for existing username - ✅ Good

## Recommended Pattern

### For Patient Creation:
```python
# GOOD - Check before creating
existing = Patient.objects.filter(
    first_name__iexact=first_name,
    last_name__iexact=last_name,
    date_of_birth=dob,
    is_deleted=False
).first()

if existing:
    # Check phone number match
    if normalize_phone(existing.phone_number) == normalize_phone(phone):
        logger.warning(f"Duplicate patient found: {existing.mrn}")
        return existing  # Return existing instead of creating

# Create new patient
patient = Patient.objects.create(...)
```

### For Staff Creation:
```python
# GOOD - Use get_or_create
staff, created = Staff.objects.get_or_create(
    employee_id=employee_id,
    defaults={
        'user': user,
        'profession': profession,
        # ... other fields
    }
)

if not created:
    logger.warning(f"Staff already exists: {staff.employee_id}")
```

## Action Items

1. **Review each script** listed above
2. **Add duplicate checking** before creating records
3. **Use `get_or_create()`** where appropriate
4. **Test import scripts** to ensure they don't create duplicates
5. **Add logging** when duplicates are detected

## Testing

After updating scripts:
1. Run import script with test data
2. Verify no duplicates created
3. Run again with same data - should skip duplicates
4. Check logs for duplicate detection messages

## Priority

**High Priority** (Used frequently):
- `import_legacy_patients.py`
- `migrate_legacy_to_django.py`
- `restore_staff_and_patients.py`

**Medium Priority** (Used occasionally):
- `bulk_migrate_legacy.py`
- `import_staff.py`

**Low Priority** (One-time use):
- `import_patient_final.py`
- `create_specialists.py`

