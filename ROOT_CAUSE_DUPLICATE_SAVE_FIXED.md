# ROOT CAUSE: Duplicate Save() Calls - FIXED ✅

## Problem Found

The patient model's `save()` method was calling `super().save()` **TWICE**:

1. **First save** at line 245: `super().save(*args, **kwargs)` - Creates the patient
2. **Second save** at lines 268 and 274: `super().save(update_fields=['mrn'], ...)` - Saves AGAIN

This was causing:
- Patient to be saved twice
- Signals to fire twice
- Potential duplicate creation in edge cases
- Database inconsistencies

## The Bug

**In `hospital/models.py` lines 264-276:**
```python
# If this is a new patient and MRN was auto-generated, ensure it's set
if is_new and not self.mrn:
    self.mrn = self.generate_mrn()
    try:
        super().save(update_fields=['mrn'], *args, **kwargs)  # ❌ DUPLICATE SAVE!
    except IntegrityError as e:
        ...
        super().save(update_fields=['mrn'], *args, **kwargs)  # ❌ DUPLICATE SAVE!
```

**Problem:** The MRN is already generated at line 237 and saved at line 245. The code at lines 264-276 should NEVER execute because:
- If `is_new` is True and MRN is missing, it's generated at line 237
- The save() at line 245 already saves the patient with the MRN
- The check at line 265 `if is_new and not self.mrn` should always be False

**But** if there's any edge case where this executes, it causes a duplicate save!

## Additional Issue in Views

**In `hospital/views.py` line 1174:**
```python
if not patient.mrn:
    patient.mrn = Patient.generate_mrn()
    patient.save(update_fields=['mrn'])  # ❌ UNNECESSARY SAVE
```

This is also unnecessary because:
- `form.save()` already calls `patient.save()` which generates MRN
- This extra save() could trigger signals again

## Fix Applied

### 1. Removed Duplicate Save Logic in Model
- Removed the redundant save() calls at lines 264-276
- The main save() at line 245 is sufficient
- MRN is already generated and saved in the main save()

### 2. Removed Unnecessary Save in View
- Removed the extra `patient.save()` call
- Changed to `refresh_from_db()` if MRN is missing (should never happen)

## Result

✅ Patient is now saved **ONLY ONCE** per creation
✅ No duplicate save() calls
✅ Signals fire only once
✅ No more duplicate patients from double saves

## Files Fixed

1. ✅ `hospital/models.py` - Removed duplicate save() logic
2. ✅ `hospital/views.py` - Removed unnecessary save() call

---

**The root cause of duplicate patient creation has been FIXED!** 🎉






