"""
Script to add Adwoa Fosuah as a midwife staff member
with proper department and role.
"""
import os
import sys
import django
from datetime import datetime

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from hospital.models import Staff, Department

User = get_user_model()

def create_staff_member(username, first_name, last_name, email, phone, 
                       date_of_birth, date_of_joining, profession, department_name, 
                       is_single=True, salary=None):
    """Create a staff member with user account and proper setup."""
    
    print(f"\n{'='*60}")
    print(f"Creating: {first_name} {last_name}")
    print(f"{'='*60}")
    
    # Get or create department
    dept, created = Department.objects.get_or_create(
        name=department_name,
        defaults={
            'code': department_name.upper().replace(' ', '_')[:10],
            'description': f'{department_name} Department'
        }
    )
    if created:
        print(f"✅ Created department: {department_name}")
    else:
        print(f"✅ Using existing department: {department_name}")
    
    # Check if user already exists
    user = None
    try:
        user = User.objects.get(username=username)
        print(f"⚠️  User already exists: {username}")
    except User.DoesNotExist:
        # Create user
        user = User.objects.create_user(
            username=username,
            email=email,
            password='staff123',  # Default password - should be changed
            first_name=first_name,
            last_name=last_name,
            is_staff=True,
            is_active=True
        )
        print(f"✅ Created user: {username}")
    
    # Check if staff record exists
    staff = None
    try:
        staff = Staff.objects.get(user=user)
        print(f"⚠️  Staff record already exists for {username}")
        
        # Update existing staff record
        staff.profession = profession
        staff.department = dept
        staff.phone_number = phone
        staff.date_of_birth = date_of_birth
        staff.date_of_joining = date_of_joining
        staff.marital_status = 'single' if is_single else 'married'
        staff.is_active = True
        staff.is_deleted = False
        staff.save()
        print(f"✅ Updated staff record")
    except Staff.DoesNotExist:
        # Create staff record
        staff = Staff.objects.create(
            user=user,
            profession=profession,
            department=dept,
            phone_number=phone,
            date_of_birth=date_of_birth,
            date_of_joining=date_of_joining,
            marital_status='single' if is_single else 'married',
            is_active=True,
            is_deleted=False
        )
        print(f"✅ Created staff record")
    
    # Assign role group
    role_group_name = None
    if profession == 'midwife':
        role_group_name = 'Midwife'
    elif profession == 'nurse':
        role_group_name = 'Nurse'
    
    if role_group_name:
        group, created = Group.objects.get_or_create(name=role_group_name)
        user.groups.add(group)
        if created:
            print(f"✅ Created and assigned to group: {role_group_name}")
        else:
            print(f"✅ Assigned to group: {role_group_name}")
    
    # Note about salary in staff_notes if provided
    if salary:
        if not staff.staff_notes:
            staff.staff_notes = f"Salary: {salary}"
        else:
            staff.staff_notes += f"\nSalary: {salary}"
        staff.save()
        print(f"✅ Added salary information: {salary}")
    
    print(f"\n📋 Summary:")
    print(f"   Username: {username}")
    print(f"   Full Name: {user.get_full_name()}")
    print(f"   Profession: {profession}")
    print(f"   Department: {dept.name}")
    print(f"   Phone: {phone}")
    print(f"   Date of Birth: {date_of_birth}")
    print(f"   Date of Joining: {date_of_joining}")
    print(f"   Marital Status: {'Single' if is_single else 'Married'}")
    if salary:
        print(f"   Salary: {salary}")
    print(f"   Role Group: {role_group_name or 'None'}")
    
    return user, staff


def main():
    """Main function to add Adwoa Fosuah."""
    
    print("\n" + "="*60)
    print("ADDING STAFF MEMBER: ADWOA FOSUAH")
    print("="*60)
    
    # Adwoa Fosuah - Midwife
    adwoa_user, adwoa_staff = create_staff_member(
        username='adwoa.fosuah',
        first_name='Adwoa',
        last_name='Fosuah',
        email='adwoa.fosuah@hospital.com',
        phone='0505663363',
        date_of_birth=datetime(1999, 3, 16).date(),
        date_of_joining=datetime(2025, 8, 1).date(),
        profession='midwife',
        department_name='Maternity',
        is_single=True,
        salary=1500
    )
    
    print("\n" + "="*60)
    print("✅ STAFF MEMBER ADDED SUCCESSFULLY!")
    print("="*60)
    print("\n📋 Login Credentials:")
    print(f"\nAdwoa Fosuah (Midwife):")
    print(f"   Username: adwoa.fosuah")
    print(f"   Password: staff123")
    print(f"   Dashboard: http://localhost:8000/hms/midwife/dashboard/")
    print(f"   Salary: 1500 (recorded in staff notes)")
    print("\n⚠️  IMPORTANT: Please change password after first login!")
    print("="*60)


if __name__ == '__main__':
    main()














