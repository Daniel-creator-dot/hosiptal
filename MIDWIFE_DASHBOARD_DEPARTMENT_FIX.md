# ✅ Midwife Dashboard Department Filter Fix

## 🔍 Issue

The midwife dashboard was throwing a `FieldError` because the `Encounter` model doesn't have a direct `department` field. The error was:
```
Cannot resolve keyword 'department' into field
```

## 🔧 Root Cause

The `Encounter` model structure:
- ❌ Does NOT have a direct `department` field
- ✅ Has `provider` (ForeignKey to `Staff`) - and `Staff` has `department`
- ✅ Has `location` (ForeignKey to `Ward`) - and `Ward` has `department`

## ✅ Solution

Changed all `Encounter` queries from:
```python
encounters.filter(department=maternity_dept)
```

To:
```python
encounters.filter(
    Q(provider__department=maternity_dept) | Q(location__department=maternity_dept)
)
```

This filters encounters where:
- The provider's department is Maternity, OR
- The location's department is Maternity

## 📝 Files Modified

**File:** `hospital/views_role_dashboards.py`

### Changes Made:

1. **Maternity Encounters Query** (line ~320)
   - Fixed: `filter(department=maternity_dept)`
   - To: `filter(Q(provider__department=maternity_dept) | Q(location__department=maternity_dept))`

2. **Recent Maternity Patients Query** (line ~330)
   - Fixed: `filter(encounters__department=maternity_dept)`
   - To: `filter(Q(encounters__provider__department=maternity_dept) | Q(encounters__location__department=maternity_dept))`

3. **Pending Vitals Query** (line ~357)
   - Fixed: `filter(department=maternity_dept)`
   - To: `filter(Q(provider__department=maternity_dept) | Q(location__department=maternity_dept))`

4. **Active Maternity Encounters Query** (line ~368)
   - Fixed: `filter(department=maternity_dept)`
   - To: `filter(Q(provider__department=maternity_dept) | Q(location__department=maternity_dept))`

5. **Statistics Base Queries** (line ~375-376)
   - Fixed: `filter(department=maternity_dept)`
   - To: `filter(Q(provider__department=maternity_dept) | Q(location__department=maternity_dept))`

6. **Visit Types Distribution Query** (line ~435)
   - Fixed: `filter(department=maternity_dept)`
   - To: `filter(Q(provider__department=maternity_dept) | Q(location__department=maternity_dept))`

## ✅ Note

The `Appointment` model DOES have a direct `department` field, so that filter remains unchanged:
```python
upcoming_appointments.filter(department=maternity_dept)  # ✅ This is correct
```

## 🎯 Result

The midwife dashboard now correctly filters encounters by department using the proper relationship paths:
- Through `provider__department` (staff member's department)
- Through `location__department` (ward's department)

**The dashboard should now load without errors!** ✅














