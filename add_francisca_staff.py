#!/usr/bin/env python
"""
Script to add Francisca Mawunyo Quarshie as a staff member
"""
import os
import sys
import django
from datetime import date

# Setup Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from django.contrib.auth import get_user_model
from hospital.models import Staff, Department

User = get_user_model()

def add_francisca_staff():
    """
    Add Francisca Mawunyo Quarshie as a staff member
    """
    print("=" * 60)
    print("Adding Francisca Mawunyo Quarshie to Staff")
    print("=" * 60)
    print()
    
    # Staff details
    username = "bob"
    email = "franscisca510@gmail.com"
    first_name = "Francisca"
    last_name = "Mawunyo Quarshie"
    password = "francisca2025"  # Default password - should be changed on first login
    date_of_birth = date(2002, 1, 8)  # 08/01/2002
    date_of_joining = date(2025, 12, 21)  # 21/12/2025
    gender = "female"
    
    # 1. Create or get user account
    print("[1/4] Creating user account...")
    user, user_created = User.objects.get_or_create(
        username=username,
        defaults={
            'email': email,
            'first_name': first_name,
            'last_name': last_name,
            'is_staff': True,
            'is_active': True,
        }
    )
    
    if not user_created:
        # Update existing user
        user.email = email
        user.first_name = first_name
        user.last_name = last_name
        user.is_staff = True
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
    
    # 2. Get or create a default department (we'll use a general department)
    print("[2/4] Setting up department...")
    # Try to find a suitable department - use first available or create General
    department = Department.objects.filter(
        is_active=True,
        is_deleted=False
    ).first()
    
    if not department:
        # Create a General department if none exists
        department = Department.objects.create(
            name='General',
            code='GEN',
            description='General Department',
            is_active=True
        )
        print(f"   ✅ Created General department")
    else:
        print(f"   ✅ Using department: {department.name}")
    print()
    
    # 3. Determine profession - since not specified, we'll use a default
    # You can change this later via admin
    profession = 'admin'  # Default to admin, can be changed
    
    # 4. Create or update staff record
    print("[3/4] Creating staff record...")
    staff, staff_created = Staff.objects.get_or_create(
        user=user,
        defaults={
            'profession': profession,
            'department': department,
            'date_of_birth': date_of_birth,
            'date_of_joining': date_of_joining,
            'gender': gender,
            'personal_email': email,
            'phone_number': '',
            'is_active': True,
            'is_deleted': False,
        }
    )
    
    if not staff_created:
        # Update existing staff
        staff.profession = profession
        staff.department = department
        staff.date_of_birth = date_of_birth
        staff.date_of_joining = date_of_joining
        staff.gender = gender
        staff.personal_email = email
        staff.is_active = True
        staff.is_deleted = False
        staff.save()
        print(f"   ✅ Updated existing staff record")
    else:
        print(f"   ✅ Created new staff record")
    
    print(f"   ✅ Employee ID: {staff.employee_id}")
    print()
    
    # 5. Summary
    print("[4/4] Summary")
    print("=" * 60)
    print(f"✅ User Account:")
    print(f"   Username: {user.username}")
    print(f"   Email: {user.email}")
    print(f"   Full Name: {user.get_full_name()}")
    print(f"   Password: {password} (CHANGE ON FIRST LOGIN)")
    print()
    print(f"✅ Staff Profile:")
    print(f"   Employee ID: {staff.employee_id}")
    print(f"   Profession: {staff.get_profession_display()}")
    print(f"   Department: {staff.department.name}")
    print(f"   Date of Birth: {staff.date_of_birth}")
    print(f"   Date of Joining: {staff.date_of_joining}")
    print(f"   Gender: {staff.get_gender_display()}")
    print()
    print("=" * 60)
    print("✅ STAFF MEMBER ADDED SUCCESSFULLY!")
    print("=" * 60)
    print()
    print("📝 Next Steps:")
    print("   1. User should login with:")
    print(f"      Username: {username}")
    print(f"      Password: {password}")
    print("   2. Change password on first login")
    print("   3. Update profession/department if needed via admin")
    print()
    
    return staff

if __name__ == '__main__':
    try:
        staff = add_francisca_staff()
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)





