#!/usr/bin/env python
"""
Fix employee IDs with non-standard department codes (must be exactly 3 characters)
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
    """Get department code - must be exactly 3 uppercase letters"""
    if department and department.code:
        code = department.code[:3].upper()
        # Remove non-letters and pad if needed
        code = re.sub(r'[^A-Z]', '', code)
        if len(code) < 3:
            code = (code + 'XXX')[:3]
        return code[:3]
    elif department:
        # Use first 3 letters of department name
        dept_name = department.name.upper().replace(' ', '')
        dept_name = re.sub(r'[^A-Z]', '', dept_name)
        if len(dept_name) < 3:
            dept_name = (dept_name + 'XXX')[:3]
        return dept_name[:3]
    else:
        return 'GEN'

def is_standard_format(employee_id):
    """Check if employee ID is in standard format: exactly 3-3-4"""
    if not employee_id:
        return False
    # Must be exactly: 3 uppercase letters - 3 uppercase letters - 4 digits
    pattern = r'^[A-Z]{3}-[A-Z]{3}-\d{4}$'
    return bool(re.match(pattern, employee_id))

def generate_employee_id_for_staff(staff, existing_ids_set):
    """Generate employee ID with proper 3-char department code"""
    dept_code = get_department_code(staff.department)
    prof_code = get_profession_code(staff.profession)
    prefix = f"{dept_code}-{prof_code}"
    
    # Find highest existing number with this prefix
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

def fix_all_non_standard():
    """Fix all non-standard employee IDs"""
    print("=" * 70)
    print("FIXING ALL NON-STANDARD EMPLOYEE IDs")
    print("(Ensuring department codes are exactly 3 characters)")
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
        if not staff.employee_id or not is_standard_format(staff.employee_id):
            staff_to_fix.append(staff)
    
    print(f"Found {len(staff_to_fix)} staff needing updates:")
    for staff in staff_to_fix:
        name = staff.user.get_full_name() if staff.user else "Unknown"
        dept = staff.department.name if staff.department else "None"
        print(f"  - {name}: {staff.employee_id or 'MISSING'} ({staff.profession}, {dept})")
    print()
    
    # Fix each one
    fixed_count = 0
    for staff in staff_to_fix:
        old_id = staff.employee_id or "MISSING"
        new_id = generate_employee_id_for_staff(staff, existing_ids_set)
        staff.employee_id = new_id
        staff.save(update_fields=['employee_id'])
        existing_ids_set.add(new_id)
        
        name = staff.user.get_full_name() if staff.user else "Unknown"
        print(f"  ✅ {name}: {old_id} → {new_id}")
        fixed_count += 1
    
    print()
    print("=" * 70)
    print(f"✅ UPDATED {fixed_count} STAFF MEMBERS")
    print("=" * 70)
    print()
    
    # Final verification
    remaining = sum(1 for s in Staff.objects.filter(is_deleted=False) if not s.employee_id or not is_standard_format(s.employee_id))
    total = Staff.objects.filter(is_deleted=False).count()
    standard = total - remaining
    
    print(f"Total staff: {total}")
    print(f"Standard format: {standard}")
    print(f"Non-standard: {remaining}")
    print()
    
    if remaining == 0:
        print("=" * 70)
        print("✅ ALL STAFF NOW HAVE STANDARD FORMAT EMPLOYEE IDs!")
        print("Format: DEPT-PROF-NUMBER (e.g., ACC-ACC-0001)")
        print("=" * 70)
    else:
        print("=" * 70)
        print(f"⚠️  {remaining} STAFF STILL NEED UPDATES")
        print("=" * 70)

if __name__ == '__main__':
    fix_all_non_standard()





