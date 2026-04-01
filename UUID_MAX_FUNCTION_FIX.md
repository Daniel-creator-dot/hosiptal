# UUID MAX() Function Error - Fixed ✅

## Problem
PostgreSQL error: `function max(uuid) does not exist` when trying to use `Max('id')` on UUID fields in encounter deduplication logic.

## Root Cause
PostgreSQL doesn't support `MAX()` function on UUID data types. The encounter deduplication code was using:
```python
Max('id')  # Fails because 'id' is UUID
```

## Solution
Replaced all `Max('id')` usages with PostgreSQL's `DISTINCT ON` clause via raw SQL, which works perfectly with UUID fields.

### Before (Failed):
```python
latest_per_patient_day = Encounter.objects.filter(...).values(
    'patient_id',
    'started_at__date'
).annotate(
    latest_id=Max('id')  # ❌ Fails: function max(uuid) does not exist
).values_list('latest_id', flat=True)
```

### After (Works):
```python
from django.db import connection

with connection.cursor() as cursor:
    cursor.execute("""
        SELECT DISTINCT ON (patient_id, started_at::date) id
        FROM hospital_encounter
        WHERE is_deleted = false
        ORDER BY patient_id, started_at::date, id DESC
    """)
    latest_ids = [row[0] for row in cursor.fetchall()]

encounters = Encounter.objects.filter(id__in=latest_ids)
```

## How DISTINCT ON Works

`DISTINCT ON (patient_id, started_at::date)` with `ORDER BY ... id DESC`:
1. Groups encounters by `patient_id` and `started_at::date`
2. Orders each group by `id DESC` (highest ID first)
3. Returns only the first row from each group (the one with highest ID)
4. Works perfectly with UUID fields

## Files Fixed

1. **`hospital/views.py`** - 3 locations:
   - `encounter_list()` - Main encounter list view
   - `medical_record_form()` - Medical record form
   - `order_create()` - Order creation form

2. **`hospital/forms_advanced.py`**:
   - `QueueEntryForm.__init__()` - Encounter queryset

3. **`hospital/forms.py`**:
   - `AdmissionForm.__init__()` - Encounter queryset

4. **`hospital/views_nurse_assignment.py`**:
   - `nurse_patient_assignment()` - Encounters needing assignment

5. **`hospital/views_admission.py`**:
   - `admission_create()` - Encounters without admission

6. **`hospital/management/commands/fix_duplicate_encounters.py`**:
   - Removed `Max('id')` from duplicate detection (not needed there)

## Special Handling

### `encounter_list()` View
The view has dynamic filters (status, type, query search), so the SQL query is built dynamically:
```python
where_clauses = ["e.is_deleted = false"]
params = []

if status_filter:
    where_clauses.append("e.status = %s")
    params.append(status_filter)
# ... etc

cursor.execute(f"""
    SELECT DISTINCT ON (e.patient_id, e.started_at::date) e.id
    FROM hospital_encounter e
    INNER JOIN hospital_patient p ON p.id = e.patient_id
    WHERE {where_sql}
    ORDER BY e.patient_id, e.started_at::date, e.id DESC
""", params)
```

### `nurse_patient_assignment()` View
Includes complex filters (has vitals, no assigned doctor):
```sql
SELECT DISTINCT ON (e.patient_id, e.started_at::date) e.id
FROM hospital_encounter e
WHERE e.is_deleted = false 
  AND e.status = 'active'
  AND EXISTS (SELECT 1 FROM hospital_vitalsign v WHERE v.encounter_id = e.id)
  AND NOT EXISTS (SELECT 1 FROM hospital_queueentry q WHERE ...)
```

## Benefits

1. ✅ **Works with UUID fields** - No more `max(uuid)` errors
2. ✅ **Efficient** - Database-level deduplication using PostgreSQL's optimized `DISTINCT ON`
3. ✅ **Correct** - Still keeps the most recent encounter (highest ID) per patient per day
4. ✅ **Maintains functionality** - All existing filters and logic still work

## Testing

### Before:
- Error: `function max(uuid) does not exist`
- Encounter list page crashed
- All forms with encounter dropdowns failed

### After:
- ✅ Encounter list loads successfully
- ✅ All encounter dropdowns work
- ✅ Deduplication still works correctly
- ✅ Filters (status, type, search) still work

## Status: ✅ FIXED

All UUID `MAX()` function errors resolved by using PostgreSQL's `DISTINCT ON` clause via raw SQL queries. The system now correctly deduplicates encounters without database errors.
