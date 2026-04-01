#!/usr/bin/env python
"""
Fix remaining staff with non-standard employee IDs
"""
import os
import sys
import django
import re

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from hospital.models import Staff
from django.db.models import Q

def get_profession_code(profession):
    """Get profession code"""
    profession_codes = {
        'doctor': 'DOC',
        'nurse': 'NUR',
        'pharmacist': 'PHA',
        'lab_technician': 'LAB',
        'radiologist': 'RAD',
        'admin': 'ADM',
        'receptionist': 'REC',
        'cashier': 'CSH',
        'hr_manager': 'HRM',
        'accountant': 'ACC',
        'account_personnel': 'ACP',
        'account_officer': 'ACO',
        'inventory_manager': 'INV',
        'store_manager': 'STM',
        'procurement_officer': 'PRO',
    }
    return profession_codes.get(profession, 'STF')

def get_department_code(department):
    """Get department code"""
    if department and department.code:
        return department.code[:3].upper()
    elif department:
        dept_name = department.name[:3].upper().replace(' ', '')
        dept_name = re.sub(r'[^A-Z0-9]', '', dept_name)
        if len(dept_name) < 3:
            dept_name = (dept_name + 'XXX')[:3]
        return dept_name
    else:
        return 'GEN'

def is_standard_format(employee_id):
    """Check if employee ID is in standard format"""
    if not employee_id:
        return False
    pattern = r'^[A-Z]{3}-[A-Z]{3}-\d{4}$'
    return bool(re.match(pattern, employee_id))

def generate_employee_id_for_staff(staff, existing_ids_set):
    """Generate employee ID"""
    dept_code = get_department_code(staff.department)
    prof_code = get_profession_code(staff.profession)
    prefix = f"{dept_code}-{prof_code}"
    
    existing = Staff.objects.filter(
        employee_id__startswith=prefix,
        is_deleted=False
    ).exclude(pk=staff.pk).order_by('-employee_id').first()
    
    if existing and existing.employee_id and is_standard_format(existing.employee_id):
        try:
            parts = existing.employee_id.split('-')
            if len(parts) >= 3:
                last_num = int(parts[-1])
                new_num = last_num + 1
            else:
                new_num = 1
        except (ValueError, IndexError):
            new_num = 1
    else:
        new_num = 1
    
    new_id = f"{prefix}-{new_num:04d}"
    
    while new_id in existing_ids_set or Staff.objects.filter(employee_id=new_id, is_deleted=False).exclude(pk=staff.pk).exists():
        new_num += 1
        new_id = f"{prefix}-{new_num:04d}"
    
    return new_id

def fix_remaining():
    """Fix remaining non-standard IDs"""
    print("=" * 70)
    print("FIXING REMAINING NON-STANDARD EMPLOYEE IDs")
    print("=" * 70)
    print()
    
    all_staff = Staff.objects.filter(is_deleted=False).select_related('user', 'department')
    existing_ids_set = set()
    
    # Collect all standard format IDs
    for staff in all_staff:
        if staff.employee_id and is_standard_format(staff.employee_id):
            existing_ids_set.add(staff.employee_id)
    
    # Find staff with non-standard IDs
    staff_to_fix = []
    for staff in all_staff:
        if staff.employee_id and not is_standard_format(staff.employee_id):
            staff_to_fix.append(staff)
    
    print(f"Found {len(staff_to_fix)} staff with non-standard IDs:")
    for staff in staff_to_fix:
        name = staff.user.get_full_name() if staff.user else "Unknown"
        print(f"  - {name}: {staff.employee_id} ({staff.profession})")
    print()
    
    # Fix each one
    fixed_count = 0
    for staff in staff_to_fix:
        old_id = staff.employee_id
        new_id = generate_employee_id_for_staff(staff, existing_ids_set)
        staff.employee_id = new_id
        staff.save(update_fields=['employee_id'])
        existing_ids_set.add(new_id)
        
        name = staff.user.get_full_name() if staff.user else "Unknown"
        print(f"  ✅ {name}: {old_id} → {new_id}")
        fixed_count += 1
    
    print()
    print("=" * 70)
    print(f"✅ FIXED {fixed_count} STAFF MEMBERS")
    print("=" * 70)
    print()
    
    # Final check
    remaining = sum(1 for s in Staff.objects.filter(is_deleted=False) if s.employee_id and not is_standard_format(s.employee_id))
    print(f"Remaining non-standard IDs: {remaining}")
    
    if remaining == 0:
        print()
        print("=" * 70)
        print("✅ ALL STAFF NOW HAVE STANDARD FORMAT EMPLOYEE IDs!")
        print("=" * 70)

if __name__ == '__main__':
    fix_remaining()





