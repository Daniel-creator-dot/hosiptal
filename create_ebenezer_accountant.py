#!/usr/bin/env python
"""
Create account for Ebenezer Moses Donkor - Accountant
"""
import os
import sys
import django
from datetime import datetime

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.utils import timezone
from hospital.models import Staff, Department
from hospital.utils_roles import assign_user_to_role, create_default_groups

User = get_user_model()


def create_ebenezer_accountant():
    """Create account for Ebenezer Moses Donkor as Accountant"""
    print("=" * 70)
    print("CREATING ACCOUNT FOR EBENEZER MOSES DONKOR - ACCOUNTANT")
    print("=" * 70)
    print()
    
    # User details
    first_name = "Ebenezer Moses"
    last_name = "Donkor"
    username = "ebenezer.donkor"
    email = "ebenezer.donkor@hospital.local"
    password = "admin123"  # Default password - should be changed after first login
    dob = datetime(2024, 5, 1).date()  # May 1, 2024
    date_of_joining = datetime(2025, 12, 21).date()  # December 21, 2025
    profession = "accountant"
    
    # 1. Create or get user
    print("[1/6] Creating user account...")
    user, created = User.objects.get_or_create(
        username=username,
        defaults={
            'email': email,
            'first_name': first_name,
            'last_name': last_name,
            'is_staff': True,
            'is_superuser': False,  # Not superuser - accountant only
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
        print(f"   ✅ Updated existing user: {username}")
    else:
        print(f"   ✅ Created new user: {username}")
    
    # Set password
    user.set_password(password)
    user.save()
    print(f"   ✅ Password set: {password}")
    print()
    
    # 2. Get or create Accounting department
    print("[2/6] Setting up department...")
    accounting_dept = Department.objects.filter(
        name__icontains='account'
    ).first()
    
    if not accounting_dept:
        accounting_dept = Department.objects.filter(
            name__icontains='finance'
        ).first()
    
    if not accounting_dept:
        # Create accounting department if it doesn't exist
        accounting_dept = Department.objects.create(
            name='Accounting',
            code='ACC',
            description='Accounting and Finance Department',
            is_active=True
        )
        print(f"   ✅ Created Accounting department")
    else:
        print(f"   ✅ Found department: {accounting_dept.name}")
    print()
    
    # 3. Create or update staff record
    print("[3/6] Creating staff record...")
    staff, staff_created = Staff.objects.get_or_create(
        user=user,
        defaults={
            'employee_id': f'ACC-{username.upper()}',
            'profession': profession,
            'department': accounting_dept,
            'date_of_birth': dob,
            'date_of_joining': date_of_joining,
            'phone_number': '',
            'is_active': True,
            'is_deleted': False,
        }
    )
    
    if not staff_created:
        # Update existing staff
        staff.profession = profession
        staff.department = accounting_dept
        staff.date_of_birth = dob
        staff.date_of_joining = date_of_joining
        staff.is_active = True
        staff.is_deleted = False
        staff.save()
        print(f"   ✅ Updated existing staff record")
    else:
        print(f"   ✅ Created new staff record")
    
    print(f"   Employee ID: {staff.employee_id}")
    print(f"   DOB: {dob}")
    print(f"   Date of Joining: {date_of_joining}")
    print()
    
    # 4. Create default groups
    print("[4/6] Creating role groups...")
    create_default_groups()
    print("   ✅ Role groups ready")
    print()
    
    # 5. Assign accountant role
    print("[5/6] Assigning accountant role...")
    assign_user_to_role(user, 'accountant')
    print("   ✅ Assigned accountant role")
    print()
    
    # 6. Add to Accountant group
    print("[6/6] Adding to Accountant group...")
    accountant_group, _ = Group.objects.get_or_create(name='Accountant')
    user.groups.add(accountant_group)
    print("   ✅ Added to Accountant group")
    print()
    
    # Summary
    print("=" * 70)
    print("✅ ACCOUNT CREATED SUCCESSFULLY!")
    print("=" * 70)
    print()
    print("User Details:")
    print(f"  Username: {username}")
    print(f"  Password: {password} (⚠️ Change after first login!)")
    print(f"  Email: {email}")
    print(f"  Full Name: {first_name} {last_name}")
    print(f"  Role: Accountant")
    print(f"  Employee ID: {staff.employee_id}")
    print(f"  Date of Birth: {dob}")
    print(f"  Date of Joining: {date_of_joining}")
    print()
    print("Access:")
    print(f"  - Login URL: http://192.168.0.105:8000/hms/login/")
    print(f"  - Accountant Dashboard: http://192.168.0.105:8000/hms/accountant/comprehensive-dashboard/")
    print(f"  - Accounting Dashboard: http://192.168.0.105:8000/hms/accounting/")
    print()
    print("Accountant has access to:")
    print("  ✅ All accounting features")
    print("  ✅ Invoices management")
    print("  ✅ Payments tracking")
    print("  ✅ Cashier sessions")
    print("  ✅ Financial reports")
    print("  ✅ Procurement accounts approval")
    print("  ✅ Comprehensive accountant dashboard")
    print("  ✅ All accounting dashboards")
    print()
    print("=" * 70)
    
    return user, staff


if __name__ == '__main__':
    create_ebenezer_accountant()






