"""
Setup script for Robbert and Jeremiah roles
- Robbert: Head of Account/Finance
- Jeremiah Anthony Amissah: General Manager (Admin/Superuser with full oversight)
"""

import os
import sys
import django

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

# Fix encoding for Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

from django.contrib.auth.models import User, Group
from hospital.models import Staff, Department
from hospital.models_hod_simple import HeadOfDepartment
from hospital.models_hr import ShiftTemplate

def find_or_create_department(name):
    """Find or create a department"""
    dept, created = Department.objects.get_or_create(
        name=name,
        defaults={'code': name.upper()[:10], 'is_active': True}
    )
    if created:
        print(f"  ✅ Created department: {name}")
    return dept

def setup_robbert_hod():
    """Setup Robbert as Head of Account/Finance"""
    print(f"\n{'='*70}")
    print(f"Setting up Robbert as Head of Account/Finance")
    print(f"{'='*70}")
    
    # Find Robbert
    robbert = None
    for username in ['robbert.kwamegbologah', 'robbert', 'robbert.kwame']:
        try:
            user = User.objects.get(username__icontains=username)
            robbert = Staff.objects.filter(user=user, is_deleted=False).first()
            if robbert:
                break
        except:
            continue
    
    if not robbert:
        # Try searching by name
        robbert = Staff.objects.filter(
            user__first_name__icontains='Robbert',
            is_deleted=False
        ).first()
    
    if not robbert:
        print("  ❌ Robbert not found!")
        print("     Please ensure Robbert Kwame Gbologah exists in the system.")
        return False
    
    print(f"  ✅ Found staff: {robbert.user.get_full_name()} ({robbert.user.username})")
    
    # Find or create Finance/Accounts department
    finance_dept = None
    for dept_name in ['Finance', 'Accounts', 'Account', 'Accounting']:
        finance_dept = Department.objects.filter(name__icontains=dept_name, is_deleted=False).first()
        if finance_dept:
            break
    
    if not finance_dept:
        finance_dept = find_or_create_department('Finance')
    
    print(f"  ✅ Using department: {finance_dept.name}")
    
    # Update Robbert's department if needed
    if robbert.department != finance_dept:
        robbert.department = finance_dept
        robbert.save()
        print(f"  ✅ Updated Robbert's department to {finance_dept.name}")
    
    # Check if already HOD
    if hasattr(robbert, 'hod_designation'):
        hod = robbert.hod_designation
        if hod.department == finance_dept and hod.is_active:
            print(f"  ℹ️  Already HOD of {finance_dept.name}")
        else:
            hod.department = finance_dept
            hod.is_active = True
            hod.save()
            print(f"  ✅ Updated HOD designation")
    else:
        # Create HOD designation
        hod = HeadOfDepartment.objects.create(
            staff=robbert,
            department=finance_dept,
            can_manage_schedules=True,
            can_approve_procurement=True,
            can_approve_leave=True,
            is_active=True
        )
        print(f"  ✅ Created HOD designation")
    
    # Ensure Robbert is in Accountant group
    accountant_group, _ = Group.objects.get_or_create(name='Accountant')
    robbert.user.groups.add(accountant_group)
    print(f"  ✅ Added to Accountant group")
    
    # Create shift templates for Finance department
    create_shift_templates(finance_dept)
    
    return True

def setup_jeremiah_general_manager():
    """Setup Jeremiah Anthony Amissah as General Manager (Superuser/Admin)"""
    print(f"\n{'='*70}")
    print(f"Setting up Jeremiah Anthony Amissah as General Manager")
    print(f"{'='*70}")
    
    # Find Jeremiah
    jeremiah = None
    for username in ['jeremiah.anthonyamissah', 'jeremiah.anthony', 'jeremiah']:
        try:
            user = User.objects.get(username__icontains=username)
            jeremiah = Staff.objects.filter(user=user, is_deleted=False).first()
            if jeremiah:
                break
        except:
            continue
    
    if not jeremiah:
        # Try searching by name
        jeremiah = Staff.objects.filter(
            user__first_name__icontains='Jeremiah',
            user__last_name__icontains='Amissah',
            is_deleted=False
        ).first()
    
    if not jeremiah:
        print("  ❌ Jeremiah Anthony Amissah not found!")
        print("     Please ensure Jeremiah Anthony Amissah exists in the system.")
        return False
    
    print(f"  ✅ Found staff: {jeremiah.user.get_full_name()} ({jeremiah.user.username})")
    
    # Make Jeremiah a superuser (General Manager has full oversight)
    if not jeremiah.user.is_superuser:
        jeremiah.user.is_superuser = True
        jeremiah.user.is_staff = True
        jeremiah.user.is_active = True
        jeremiah.user.save()
        print(f"  ✅ Made superuser (General Manager - full admin access)")
    else:
        print(f"  ℹ️  Already superuser")
    
    # Add to Admin group
    admin_group, _ = Group.objects.get_or_create(name='Admin')
    jeremiah.user.groups.add(admin_group)
    print(f"  ✅ Added to Admin group")
    
    # Add to HR Manager group (for HR oversight)
    hr_group, _ = Group.objects.get_or_create(name='HR Manager')
    jeremiah.user.groups.add(hr_group)
    print(f"  ✅ Added to HR Manager group")
    
    # Ensure Jeremiah is in BD department (Business Development/Management)
    bd_dept = None
    for dept_name in ['BD', 'Business Development', 'Management', 'General Management']:
        bd_dept = Department.objects.filter(name__icontains=dept_name, is_deleted=False).first()
        if bd_dept:
            break
    
    if not bd_dept:
        bd_dept = find_or_create_department('BD')
    
    if jeremiah.department != bd_dept:
        jeremiah.department = bd_dept
        jeremiah.save()
        print(f"  ✅ Updated department to {bd_dept.name}")
    
    # Check if already HOD of BD (optional, but good to have)
    if not hasattr(jeremiah, 'hod_designation'):
        hod = HeadOfDepartment.objects.create(
            staff=jeremiah,
            department=bd_dept,
            can_manage_schedules=True,
            can_approve_procurement=True,
            can_approve_leave=True,
            is_active=True
        )
        print(f"  ✅ Created HOD designation for {bd_dept.name}")
    else:
        print(f"  ℹ️  Already has HOD designation")
    
    return True

def create_shift_templates(department):
    """Create default shift templates for a department"""
    templates = [
        {'name': 'Morning Shift', 'shift_type': 'day', 'start_time': '06:00', 'end_time': '14:00'},
        {'name': 'Afternoon Shift', 'shift_type': 'evening', 'start_time': '14:00', 'end_time': '22:00'},
        {'name': 'Night Shift', 'shift_type': 'night', 'start_time': '22:00', 'end_time': '06:00'},
        {'name': 'Day Shift', 'shift_type': 'day', 'start_time': '08:00', 'end_time': '17:00'},
    ]
    
    created = 0
    for template_data in templates:
        template, created_flag = ShiftTemplate.objects.get_or_create(
            name=template_data['name'],
            department=department,
            defaults={
                'shift_type': template_data['shift_type'],
                'start_time': template_data['start_time'],
                'end_time': template_data['end_time'],
                'is_active': True,
            }
        )
        if created_flag:
            created += 1
    
    if created > 0:
        print(f"  ✅ Created {created} shift templates")
    return created

def main():
    print("\n" + "="*70)
    print(" " * 15 + "ROBBERT & JEREMIAH ROLE SETUP")
    print("="*70)
    print()
    
    success_count = 0
    
    # Setup Robbert
    if setup_robbert_hod():
        success_count += 1
    
    # Setup Jeremiah
    if setup_jeremiah_general_manager():
        success_count += 1
    
    print(f"\n{'='*70}")
    print(f"SETUP COMPLETE")
    print(f"{'='*70}")
    print(f"✅ Successfully set up {success_count}/2 roles")
    print()
    print("ROBBERT (Head of Account/Finance):")
    print("  ✅ HOD of Finance/Accounts department")
    print("  ✅ Can manage schedules, approve procurement, approve leave")
    print("  ✅ Member of Accountant group")
    print("  ✅ Access: /hms/hod/shift-monitoring/")
    print()
    print("JEREMIAH (General Manager):")
    print("  ✅ Superuser status (full admin access)")
    print("  ✅ Member of Admin and HR Manager groups")
    print("  ✅ HOD of BD department")
    print("  ✅ Can oversee all departments and functions")
    print("  ✅ Access: All admin features and dashboards")
    print()

if __name__ == '__main__':
    main()





