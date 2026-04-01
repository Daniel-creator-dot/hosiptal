#!/usr/bin/env python
"""
Update ALL existing staff members to use standard employee ID format
Format: DEPT-PROF-NUMBER
"""
import os
import sys
import django
import re

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from hospital.models import Staff, Department
from django.db.models import Q

def get_profession_code(profession):
    """Get profession code for employee ID generation"""
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
    """Get department code (first 3 letters of name if no code)"""
    if department and department.code:
        return department.code[:3].upper()
    elif department:
        # Use first 3 letters of department name, remove spaces
        dept_name = department.name[:3].upper().replace(' ', '')
        # Remove any special characters
        dept_name = re.sub(r'[^A-Z0-9]', '', dept_name)
        # Ensure at least 3 characters
        if len(dept_name) < 3:
            dept_name = (dept_name + 'XXX')[:3]
        return dept_name
    else:
        return 'GEN'

def is_standard_format(employee_id):
    """Check if employee ID is in standard format DEPT-PROF-NUMBER"""
    if not employee_id:
        return False
    # Standard format: DEPT-PROF-NUMBER (e.g., ACC-ACC-0001)
    pattern = r'^[A-Z]{3}-[A-Z]{3}-\d{4}$'
    return bool(re.match(pattern, employee_id))

def generate_employee_id_for_staff(staff, existing_ids_set):
    """Generate employee ID for a staff member"""
    dept_code = get_department_code(staff.department)
    prof_code = get_profession_code(staff.profession)
    prefix = f"{dept_code}-{prof_code}"
    
    # Find highest existing number with this prefix (excluding current staff)
    existing = Staff.objects.filter(
        employee_id__startswith=prefix,
        is_deleted=False
    ).exclude(pk=staff.pk).order_by('-employee_id').first()
    
    if existing and existing.employee_id and is_standard_format(existing.employee_id):
        try:
            # Extract number from employee_id (format: DEPT-PROF-NUMBER)
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
    
    # Check if ID already exists in our set or database
    while new_id in existing_ids_set or Staff.objects.filter(employee_id=new_id, is_deleted=False).exclude(pk=staff.pk).exists():
        new_num += 1
        new_id = f"{prefix}-{new_num:04d}"
    
    return new_id

def update_all_employee_ids():
    """Update all staff to use standard employee ID format"""
    print("=" * 70)
    print("UPDATING ALL STAFF TO STANDARD EMPLOYEE ID FORMAT")
    print("=" * 70)
    print()
    
    # Get all active staff
    all_staff = Staff.objects.filter(is_deleted=False).select_related('user', 'department')
    total_count = all_staff.count()
    
    print(f"Total staff members: {total_count}")
    print()
    
    # Separate staff into those needing update and those already correct
    staff_to_update = []
    staff_already_correct = []
    staff_without_ids = []
    
    for staff in all_staff:
        if not staff.employee_id or staff.employee_id.strip() == '':
            staff_without_ids.append(staff)
        elif is_standard_format(staff.employee_id):
            staff_already_correct.append(staff)
        else:
            staff_to_update.append(staff)
    
    print(f"Staff already in standard format: {len(staff_already_correct)}")
    print(f"Staff needing update: {len(staff_to_update)}")
    print(f"Staff without IDs: {len(staff_without_ids)}")
    print()
    
    # Collect all existing standard format IDs to avoid duplicates
    existing_ids_set = set()
    for staff in staff_already_correct:
        if staff.employee_id:
            existing_ids_set.add(staff.employee_id)
    
    # Update staff without IDs first
    updated_count = 0
    print("Updating staff without employee IDs...")
    for staff in staff_without_ids:
        old_id = staff.employee_id or "MISSING"
        new_id = generate_employee_id_for_staff(staff, existing_ids_set)
        staff.employee_id = new_id
        staff.save(update_fields=['employee_id'])
        existing_ids_set.add(new_id)
        
        name = staff.user.get_full_name() if staff.user else "Unknown"
        print(f"  ✅ {name}: {old_id} → {new_id}")
        updated_count += 1
    
    print()
    
    # Update staff with non-standard format IDs
    print("Updating staff with non-standard employee IDs...")
    for staff in staff_to_update:
        old_id = staff.employee_id
        new_id = generate_employee_id_for_staff(staff, existing_ids_set)
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
    print("Final Verification:")
    all_staff_updated = Staff.objects.filter(is_deleted=False)
    without_ids = all_staff_updated.filter(Q(employee_id__isnull=True) | Q(employee_id='')).count()
    non_standard = sum(1 for s in all_staff_updated if s.employee_id and not is_standard_format(s.employee_id))
    
    print(f"  Staff without IDs: {without_ids}")
    print(f"  Staff with non-standard format: {non_standard}")
    print(f"  Total staff: {all_staff_updated.count()}")
    print()
    
    if without_ids == 0 and non_standard == 0:
        print("=" * 70)
        print("✅ SUCCESS! ALL STAFF NOW HAVE STANDARD FORMAT EMPLOYEE IDs")
        print("=" * 70)
    else:
        print("=" * 70)
        print(f"⚠️  {without_ids + non_standard} STAFF STILL NEED UPDATES")
        print("=" * 70)
    
    # Show sample of updated IDs
    print()
    print("Sample of Updated Employee IDs:")
    sample = Staff.objects.filter(is_deleted=False, employee_id__isnull=False).exclude(employee_id='')[:10]
    for staff in sample:
        name = staff.user.get_full_name() if staff.user else "Unknown"
        print(f"  {name}: {staff.employee_id} ({staff.profession})")

if __name__ == '__main__':
    update_all_employee_ids()





