# HOD Scheduling Setup Guide

## ✅ Issue Fixed!

HOD (Head of Department) Scheduling is now fully operational.

## What Was Fixed:

### 1. **Model Import Issue**
- **Problem**: `models_hod_simple.py` wasn't imported in main `models.py`
- **Fix**: Added import statement to ensure Django recognizes HeadOfDepartment model
- **File**: `hospital/models.py`

### 2. **Staff Model Attribute Error**
- **Problem**: `Staff.full_name` doesn't exist
- **Fix**: Changed to `staff.user.get_full_name()` in HeadOfDepartment model
- **File**: `hospital/models_hod_simple.py`

### 3. **Demo Data Created**
- Created 1 HOD designation (Rebecca - Emergency Department)
- Created 3 shift templates (Morning, Evening, Night)
- Created 7 sample shifts for the current week

## How to Access HOD Scheduling:

### URL:
```
http://localhost:8000/hms/hod/scheduling/
```

### From Dashboard:
Navigate to: **Dashboard** → **HOD Scheduling** tile

## How to Use HOD Scheduling:

### 1. **View as HOD**
- Only users designated as "Head of Department" can access
- Currently: **Rebecca** (username: `rebecca.`)

### 2. **Create Shift Templates**
- Click "Create Shift Template"
- Define shift types: Day, Evening, Night
- Set start/end times
- Reuse templates for scheduling

### 3. **Assign Shifts**
- Click "Create Shift"
- Select staff member
- Choose date and shift type
- Add notes if needed

### 4. **Bulk Assign**
- Assign multiple shifts at once
- Use for weekly/monthly planning
- Apply templates to multiple staff

## Make More HODs:

### Option 1: Django Admin
1. Go to http://localhost:8000/admin/
2. Navigate to **Hospital** → **Heads of Department**
3. Click "Add Head of Department"
4. Select staff member and department
5. Set permissions (manage schedules, approve leave, etc.)
6. Save

### Option 2: Programmatically
```python
from hospital.models import Staff, Department
from hospital.models_hod_simple import HeadOfDepartment

# Get staff and department
staff = Staff.objects.get(user__username='doctor_username')
dept = Department.objects.get(name='Department Name')

# Create HOD
hod = HeadOfDepartment.objects.create(
    staff=staff,
    department=dept,
    can_manage_schedules=True,
    can_approve_procurement=True,
    can_approve_leave=True,
    is_active=True
)
```

## Features Available:

✅ **Shift Management**
- Create individual shifts
- Use shift templates
- View weekly schedules
- Assign staff to shifts

✅ **Staff Overview**
- View all department staff
- See current assignments
- Track shift coverage

✅ **Templates**
- Morning Shift (8 AM - 4 PM)
- Evening Shift (4 PM - 11:59 PM)
- Night Shift (12 AM - 8 AM)
- Create custom templates

✅ **Bulk Operations**
- Bulk assign shifts
- Upload roster from file
- Weekly/monthly planning

## Current Status:

| Component | Status |
|-----------|--------|
| HeadOfDepartment Model | ✅ Working |
| StaffShift Model | ✅ Working |
| ShiftTemplate Model | ✅ Working |
| HOD Dashboard | ✅ Working |
| Shift Creation | ✅ Working |
| Shift Templates | ✅ Working (3 created) |
| Sample Data | ✅ Created |
| Demo HOD | ✅ Rebecca (Emergency Dept) |

## Troubleshooting:

### "Access Denied" Error
- User must be designated as HOD
- Check in Django Admin: Hospital → Heads of Department
- Ensure `is_active=True` on HOD record

### No Data Showing
- Create shift templates first
- Then assign shifts to staff
- Check date range (showing current week)

### Staff Not Appearing
- Ensure staff `is_active=True`
- Check staff assigned to correct department
- Verify `is_deleted=False`

## Next Steps:

1. **Log in as HOD** (or create more HODs)
2. **Create shift templates** for your organization
3. **Assign shifts** to department staff
4. **View and manage** weekly schedules

---

**Last Updated**: November 11, 2025  
**Status**: ✅ Fully Operational  
**Demo User**: rebecca. (Emergency Department HOD)




















