"""
Script to add Mercy Nyarko and Vida Blankson as staff members
with proper departments and roles.
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
                       is_single=True):
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
    
    print(f"\n📋 Summary:")
    print(f"   Username: {username}")
    print(f"   Full Name: {user.get_full_name()}")
    print(f"   Profession: {profession}")
    print(f"   Department: {dept.name}")
    print(f"   Phone: {phone}")
    print(f"   Date of Birth: {date_of_birth}")
    print(f"   Date of Joining: {date_of_joining}")
    print(f"   Marital Status: {'Single' if is_single else 'Married'}")
    print(f"   Role Group: {role_group_name or 'None'}")
    
    return user, staff


def main():
    """Main function to add both staff members."""
    
    print("\n" + "="*60)
    print("ADDING STAFF MEMBERS: MERCY NYARKO & VIDA BLANKSON")
    print("="*60)
    
    # 1. Mercy Nyarko - Midwife
    mercy_user, mercy_staff = create_staff_member(
        username='mercy.nyarko',
        first_name='Mercy',
        last_name='Nyarko',
        email='mercy.nyarko@hospital.com',
        phone='0246072608',
        date_of_birth=datetime(1999, 10, 23).date(),
        date_of_joining=datetime(2025, 7, 1).date(),
        profession='midwife',
        department_name='Maternity',
        is_single=True
    )
    
    # 2. Vida Blankson - Nurse
    vida_user, vida_staff = create_staff_member(
        username='vida.blankson',
        first_name='Vida',
        last_name='Blankson',
        email='vida.blankson@hospital.com',
        phone='0558105165',
        date_of_birth=datetime(1991, 10, 14).date(),
        date_of_joining=datetime(2022, 4, 1).date(),  # First week of April 2022
        profession='nurse',
        department_name='Nurses',
        is_single=True
    )
    
    print("\n" + "="*60)
    print("✅ STAFF MEMBERS ADDED SUCCESSFULLY!")
    print("="*60)
    print("\n📋 Login Credentials:")
    print(f"\n1. Mercy Nyarko (Midwife):")
    print(f"   Username: mercy.nyarko")
    print(f"   Password: staff123")
    print(f"   Dashboard: http://localhost:8000/hms/midwife/dashboard/")
    print(f"\n2. Vida Blankson (Nurse):")
    print(f"   Username: vida.blankson")
    print(f"   Password: staff123")
    print(f"   Dashboard: http://localhost:8000/hms/dashboard/nurse/")
    print("\n⚠️  IMPORTANT: Please change passwords after first login!")
    print("="*60)


if __name__ == '__main__':
    main()














