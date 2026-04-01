#!/usr/bin/env python
"""
Update ALL staff employee IDs to PCMC format
Format: PCMC-DEPT-PROF-NUMBER
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
        code = re.sub(r'[^A-Z]', '', code)
        if len(code) < 3:
            code = (code + 'XXX')[:3]
        return code[:3]
    elif department:
        dept_name = department.name.upper().replace(' ', '')
        dept_name = re.sub(r'[^A-Z]', '', dept_name)
        if len(dept_name) < 3:
            dept_name = (dept_name + 'XXX')[:3]
        return dept_name[:3]
    else:
        return 'GEN'

def is_pcmc_format(employee_id):
    """Check if employee ID is in PCMC format: PCMC-DEPT-PROF-NUMBER"""
    if not employee_id:
        return False
    pattern = r'^PCMC-[A-Z]{3}-[A-Z]{3}-\d{4}$'
    return bool(re.match(pattern, employee_id))

def generate_pcmc_employee_id(staff, existing_ids_set):
    """Generate PCMC format employee ID"""
    institution_prefix = 'PCMC'
    dept_code = get_department_code(staff.department)
    prof_code = get_profession_code(staff.profession)
    prefix = f"{institution_prefix}-{dept_code}-{prof_code}"
    
    # Find highest existing number with this prefix
    existing = Staff.objects.filter(
        employee_id__startswith=prefix,
        is_deleted=False
    ).exclude(pk=staff.pk).order_by('-employee_id').first()
    
    if existing and existing.employee_id and is_pcmc_format(existing.employee_id):
        try:
            parts = existing.employee_id.split('-')
            if len(parts) >= 4:
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

def update_all_to_pcmc():
    """Update all staff to PCMC format"""
    print("=" * 70)
    print("UPDATING ALL STAFF TO PCMC EMPLOYEE ID FORMAT")
    print("Format: PCMC-DEPT-PROF-NUMBER (PrimeCare Medical Center)")
    print("=" * 70)
    print()
    
    all_staff = Staff.objects.filter(is_deleted=False).select_related('user', 'department')
    existing_ids_set = set()
    
    # Collect all PCMC format IDs
    for staff in all_staff:
        if staff.employee_id and is_pcmc_format(staff.employee_id):
            existing_ids_set.add(staff.employee_id)
    
    # Find staff needing updates
    staff_to_update = []
    for staff in all_staff:
        if not staff.employee_id or not is_pcmc_format(staff.employee_id):
            staff_to_update.append(staff)
    
    print(f"Total staff: {all_staff.count()}")
    print(f"Already in PCMC format: {len(existing_ids_set)}")
    print(f"Needing update: {len(staff_to_update)}")
    print()
    
    # Update each staff member
    updated_count = 0
    for staff in staff_to_update:
        old_id = staff.employee_id or "MISSING"
        new_id = generate_pcmc_employee_id(staff, existing_ids_set)
        staff.employee_id = new_id
        staff.save(update_fields=['employee_id'])
        existing_ids_set.add(new_id)
        
        name = staff.user.get_full_name() if staff.user else "Unknown"
        print(f"  ✅ {name}: {old_id} → {new_id}")
        updated_count += 1
    
    print()
    print("=" * 70)
    print(f"✅ UPDATED {updated_count} STAFF MEMBERS")
    print("=" * 70)
    print()
    
    # Final verification
    remaining = sum(1 for s in Staff.objects.filter(is_deleted=False) if not s.employee_id or not is_pcmc_format(s.employee_id))
    total = Staff.objects.filter(is_deleted=False).count()
    pcmc_format = total - remaining
    
    print(f"Total staff: {total}")
    print(f"PCMC format: {pcmc_format}")
    print(f"Non-PCMC format: {remaining}")
    print()
    
    if remaining == 0:
        print("=" * 70)
        print("✅ ALL STAFF NOW HAVE PCMC FORMAT EMPLOYEE IDs!")
        print("Format: PCMC-DEPT-PROF-NUMBER")
        print("Example: PCMC-ACC-ACC-0001")
        print("=" * 70)
    else:
        print("=" * 70)
        print(f"⚠️  {remaining} STAFF STILL NEED UPDATES")
        print("=" * 70)
    
    # Show sample
    print()
    print("Sample of Updated Employee IDs:")
    sample = Staff.objects.filter(is_deleted=False, employee_id__isnull=False).exclude(employee_id='')[:10]
    for staff in sample:
        name = staff.user.get_full_name() if staff.user else "Unknown"
        print(f"  {name}: {staff.employee_id} ({staff.profession})")

if __name__ == '__main__':
    update_all_to_pcmc()





