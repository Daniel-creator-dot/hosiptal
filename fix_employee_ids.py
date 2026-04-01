#!/usr/bin/env python
"""
Fix Employee IDs for all staff members
- Generate employee IDs for staff without them
- Update profession codes to include all professions
- Ensure Ebenezer Donkor has an employee ID
"""
import os
import sys
import django

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
        # Use first 3 letters of department name
        return department.name[:3].upper().replace(' ', '')
    else:
        return 'GEN'

def generate_employee_id_for_staff(staff):
    """Generate employee ID for a staff member"""
    dept_code = get_department_code(staff.department)
    prof_code = get_profession_code(staff.profession)
    prefix = f"{dept_code}-{prof_code}"
    
    # Find highest existing number with this prefix
    existing = Staff.objects.filter(
        employee_id__startswith=prefix,
        is_deleted=False
    ).exclude(pk=staff.pk).order_by('-employee_id').first()
    
    if existing and existing.employee_id:
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
    
    return f"{prefix}-{new_num:04d}"

def fix_all_employee_ids():
    """Fix employee IDs for all staff"""
    print("=" * 70)
    print("FIXING EMPLOYEE IDs FOR ALL STAFF")
    print("=" * 70)
    print()
    
    # Get all active staff without employee IDs
    staff_without_ids = Staff.objects.filter(
        Q(employee_id__isnull=True) | Q(employee_id=''),
        is_deleted=False
    )
    
    print(f"Found {staff_without_ids.count()} staff without employee IDs")
    print()
    
    # Fix each staff member
    fixed_count = 0
    for staff in staff_without_ids:
        old_id = staff.employee_id or "MISSING"
        new_id = generate_employee_id_for_staff(staff)
        
        # Check if ID already exists
        while Staff.objects.filter(employee_id=new_id, is_deleted=False).exclude(pk=staff.pk).exists():
            # Increment number if duplicate
            parts = new_id.split('-')
            if len(parts) >= 3:
                try:
                    num = int(parts[-1]) + 1
                    new_id = f"{'-'.join(parts[:-1])}-{num:04d}"
                except ValueError:
                    new_id = f"{new_id}-001"
            else:
                new_id = f"{new_id}-001"
        
        staff.employee_id = new_id
        staff.save(update_fields=['employee_id'])
        
        name = staff.user.get_full_name() if staff.user else "Unknown"
        print(f"✅ {name}: {old_id} → {new_id}")
        fixed_count += 1
    
    print()
    print(f"Fixed {fixed_count} staff members")
    print()
    
    # Check Ebenezer specifically
    print("Checking Ebenezer Donkor...")
    try:
        ebenezer = Staff.objects.get(user__username='ebenezer.donkor', is_deleted=False)
        print(f"✅ Ebenezer Donkor:")
        print(f"   Employee ID: {ebenezer.employee_id}")
        print(f"   Profession: {ebenezer.profession}")
        print(f"   Department: {ebenezer.department.name if ebenezer.department else 'None'}")
        
        if not ebenezer.employee_id:
            print("   ⚠️  Generating employee ID...")
            ebenezer.employee_id = generate_employee_id_for_staff(ebenezer)
            ebenezer.save(update_fields=['employee_id'])
            print(f"   ✅ Generated: {ebenezer.employee_id}")
    except Staff.DoesNotExist:
        print("❌ Ebenezer Donkor not found!")
    except Staff.MultipleObjectsReturned:
        print("⚠️  Multiple Ebenezer Donkor records found!")
    
    print()
    print("=" * 70)
    print("✅ EMPLOYEE ID FIX COMPLETE")
    print("=" * 70)

if __name__ == '__main__':
    fix_all_employee_ids()





