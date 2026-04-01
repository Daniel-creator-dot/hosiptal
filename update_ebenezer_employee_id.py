#!/usr/bin/env python
"""
Update Ebenezer Donkor's employee ID to standard format
"""
import os
import sys
import django

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from hospital.models import Staff

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
        return department.name[:3].upper().replace(' ', '')
    else:
        return 'GEN'

def update_ebenezer_id():
    """Update Ebenezer's employee ID to standard format"""
    print("=" * 70)
    print("UPDATING EBENEZER DONKOR EMPLOYEE ID")
    print("=" * 70)
    print()
    
    try:
        ebenezer = Staff.objects.get(user__username='ebenezer.donkor', is_deleted=False)
        print(f"✅ Found: {ebenezer.user.get_full_name()}")
        print(f"   Current Employee ID: {ebenezer.employee_id}")
        print(f"   Profession: {ebenezer.profession}")
        print(f"   Department: {ebenezer.department.name if ebenezer.department else 'None'}")
        print()
        
        # Generate new ID in standard format
        dept_code = get_department_code(ebenezer.department)
        prof_code = get_profession_code(ebenezer.profession)
        prefix = f"{dept_code}-{prof_code}"
        
        # Find highest existing number with this prefix
        existing = Staff.objects.filter(
            employee_id__startswith=prefix,
            is_deleted=False
        ).exclude(pk=ebenezer.pk).order_by('-employee_id').first()
        
        if existing and existing.employee_id:
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
        
        # Check if new ID already exists
        while Staff.objects.filter(employee_id=new_id, is_deleted=False).exclude(pk=ebenezer.pk).exists():
            new_num += 1
            new_id = f"{prefix}-{new_num:04d}"
        
        old_id = ebenezer.employee_id
        ebenezer.employee_id = new_id
        ebenezer.save(update_fields=['employee_id'])
        
        print(f"✅ Updated Employee ID:")
        print(f"   {old_id} → {new_id}")
        print()
        print("=" * 70)
        print("✅ SUCCESS!")
        print("=" * 70)
        
    except Staff.DoesNotExist:
        print("❌ Ebenezer Donkor not found!")
    except Staff.MultipleObjectsReturned:
        print("⚠️  Multiple Ebenezer Donkor records found!")

if __name__ == '__main__':
    update_ebenezer_id()





