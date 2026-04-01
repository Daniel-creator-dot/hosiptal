#!/usr/bin/env python
"""
Create Cashier Account for Fafa Fortune
"""
import os
import sys
import django
from datetime import date

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from hospital.models import Staff, Department
from hospital.utils_roles import assign_user_to_role, create_default_groups, ROLE_FEATURES

User = get_user_model()

def create_fafa_cashier():
    """
    Create cashier account for Fafa Fortune
    """
    print("=" * 70)
    print("CREATING CASHIER ACCOUNT FOR FAFA FORTUNE")
    print("=" * 70)
    print()
    
    # User details
    first_name = "Fafa"
    last_name = "Fortune"
    username = "fafa.fortune"
    email = "fafa.fortune@hospital.com"  # Adjust if needed
    password = "cash@2026"
    profession = "cashier"
    
    # 1. Create or get user
    print("[1/6] Creating user account...")
    user, created = User.objects.get_or_create(
        username=username,
        defaults={
            'email': email,
            'first_name': first_name,
            'last_name': last_name,
            'is_staff': True,
            'is_superuser': False,
            'is_active': True,
        }
    )
    
    if not created:
        # Update existing user
        user.email = email
        user.first_name = first_name
        user.last_name = last_name
        user.is_staff = True
        user.is_superuser = False
        user.is_active = True
        user.save()
        print(f"   [OK] Updated existing user: {username}")
    else:
        print(f"   [OK] Created new user: {username}")
    
    # Set password
    user.set_password(password)
    user.save()
    print(f"   [OK] Password set: {password}")
    print()
    
    # 2. Get or create Finance/Accounting department (cashiers typically in Finance)
    print("[2/6] Setting up department...")
    finance_dept = Department.objects.filter(
        Q(name__icontains='finance') | Q(name__icontains='account') | Q(name__icontains='cashier')
    ).first()
    
    if not finance_dept:
        # Try Accounts or Billing
        finance_dept = Department.objects.filter(
            Q(name__icontains='billing') | Q(code__icontains='ACC') | Q(code__icontains='FIN')
        ).first()
    
    if not finance_dept:
        # Create Finance department if it doesn't exist
        finance_dept = Department.objects.create(
            name='Finance',
            code='FIN',
            description='Finance and Accounting Department',
            is_active=True
        )
        print(f"   [OK] Created Finance department")
    else:
        print(f"   [OK] Found department: {finance_dept.name}")
    print()
    
    # 3. Create or update staff record
    print("[3/6] Creating staff record...")
    from datetime import datetime
    today = date.today()
    
    staff, staff_created = Staff.objects.get_or_create(
        user=user,
        defaults={
            'employee_id': f'CSH-{username.upper().replace(".", "")}',
            'profession': profession,
            'department': finance_dept,
            'date_of_birth': date(1990, 1, 1),  # Default DOB - update if needed
            'date_of_joining': today,
            'phone_number': '',
            'is_active': True,
            'is_deleted': False,
        }
    )
    
    if not staff_created:
        # Update existing staff
        staff.profession = profession
        staff.department = finance_dept
        staff.is_active = True
        staff.is_deleted = False
        if not staff.employee_id:
            staff.employee_id = f'CSH-{username.upper().replace(".", "")}'
        staff.save()
        print(f"   [OK] Updated existing staff record")
        print(f"   [OK] Profession set to: {staff.get_profession_display()}")
    else:
        print(f"   [OK] Created staff record")
        print(f"   [OK] Employee ID: {staff.employee_id}")
        print(f"   [OK] Profession: {staff.get_profession_display()}")
    print()
    
    # 4. Create role groups if needed
    print("[4/6] Setting up role groups...")
    create_default_groups()
    print("   [OK] Role groups ready")
    print()
    
    # 5. Assign cashier role
    print("[5/6] Assigning cashier role...")
    try:
        assign_user_to_role(user, 'cashier')
        print(f"   [OK] Assigned role: {ROLE_FEATURES.get('cashier', {}).get('name', 'Cashier')}")
    except Exception as e:
        print(f"   [WARNING] Warning assigning role: {str(e)}")
    print()
    
    # 6. Verify setup
    print("[6/6] Verifying setup...")
    user.refresh_from_db()
    staff.refresh_from_db()
    
    print(f"   User: {user.get_full_name()} ({user.username})")
    print(f"   Email: {user.email}")
    print(f"   Active: {user.is_active}")
    print(f"   Staff ID: {staff.employee_id}")
    print(f"   Profession: {staff.get_profession_display()}")
    print(f"   Department: {staff.department.name if staff.department else 'None'}")
    
    # Check role
    from hospital.utils_roles import get_user_role
    role = get_user_role(user)
    print(f"   Role: {role}")
    print()
    
    print("=" * 70)
    print("[SUCCESS] CASHIER ACCOUNT CREATED SUCCESSFULLY!")
    print("=" * 70)
    print()
    print("Login Details:")
    print(f"   Username: {username}")
    print(f"   Password: {password}")
    print()
    print("Access:")
    print("   Dashboard: /hms/cashier/dashboard/")
    print("   Central Dashboard: /hms/cashier/central/")
    print()

if __name__ == '__main__':
    from django.db.models import Q
    create_fafa_cashier()

