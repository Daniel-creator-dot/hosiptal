#!/usr/bin/env python
"""
Script to create Dr. Ali - Gynecologist account
DOB: 23/06/1979
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
from hospital.models_specialists import Specialty, SpecialistProfile

User = get_user_model()

def create_dr_ali():
    """
    Create Dr. Ali - Gynecologist account
    """
    print("=" * 70)
    print("Creating Dr. Ali - Gynecologist Account")
    print("=" * 70)
    print()
    
    # Staff details
    username = "dr.ali"
    email = "dr.ali@hospital.com"
    first_name = "Ali"
    last_name = "Gynecologist"
    password = "dr.ali2025"  # Default password - should be changed on first login
    date_of_birth = date(1979, 6, 23)  # 23/06/1979
    date_of_joining = date.today()  # Today's date
    profession = "doctor"
    specialty_name = "Gynecology"
    qualification = "MBBS, MRCOG"  # Standard gynecology qualification
    consultation_fee = 100.00  # Default consultation fee
    
    # 1. Create or get user account
    print("[1/5] Creating user account...")
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
    
    # 2. Get or create department (Medical/Surgery department)
    print("[2/5] Setting up department...")
    medical_dept = Department.objects.filter(
        name__icontains='medical'
    ).first()
    
    if not medical_dept:
        medical_dept = Department.objects.filter(
            name__icontains='surgery'
        ).first()
    
    if not medical_dept:
        medical_dept = Department.objects.filter(
            name__icontains='obstetrics'
        ).first()
    
    if not medical_dept:
        # Create Medical department if it doesn't exist
        medical_dept = Department.objects.create(
            name='Medical',
            code='MED',
            description='Medical Department',
            is_active=True
        )
        print(f"   ✅ Created Medical department")
    else:
        print(f"   ✅ Found department: {medical_dept.name}")
    print()
    
    # 3. Create or update staff record
    print("[3/5] Creating staff record...")
    staff, staff_created = Staff.objects.get_or_create(
        user=user,
        defaults={
            'employee_id': f'DOC-{username.upper()}',
            'profession': profession,
            'department': medical_dept,
            'date_of_birth': date_of_birth,
            'date_of_joining': date_of_joining,
            'phone_number': '',
            'specialization': specialty_name,
            'is_active': True,
            'is_deleted': False,
        }
    )
    
    if not staff_created:
        # Update existing staff
        staff.profession = profession
        staff.department = medical_dept
        staff.date_of_birth = date_of_birth
        staff.specialization = specialty_name
        staff.is_active = True
        staff.is_deleted = False
        staff.save()
        print(f"   ✅ Updated existing staff record")
    else:
        print(f"   ✅ Created new staff record")
    print()
    
    # 4. Get or create Gynecology specialty
    print("[4/5] Setting up Gynecology specialty...")
    specialty, specialty_created = Specialty.objects.get_or_create(
        name=specialty_name,
        defaults={
            'code': 'GYN',
            'description': 'Gynecology and Obstetrics',
            'icon': 'bi-gender-female',
            'is_active': True,
        }
    )
    
    if specialty_created:
        print(f"   ✅ Created specialty: {specialty_name}")
    else:
        print(f"   ✅ Found existing specialty: {specialty_name}")
    print()
    
    # 5. Create specialist profile
    print("[5/5] Creating specialist profile...")
    specialist_profile, spec_created = SpecialistProfile.objects.get_or_create(
        staff=staff,
        defaults={
            'specialty': specialty,
            'qualification': qualification,
            'experience_years': 10,  # Assuming 10 years experience
            'consultation_fee': consultation_fee,
            'is_active': True,
        }
    )
    
    if not spec_created:
        # Update existing specialist profile
        specialist_profile.specialty = specialty
        specialist_profile.qualification = qualification
        specialist_profile.consultation_fee = consultation_fee
        specialist_profile.is_active = True
        specialist_profile.save()
        print(f"   ✅ Updated existing specialist profile")
    else:
        print(f"   ✅ Created new specialist profile")
    print()
    
    # Summary
    print("=" * 70)
    print("✅ DR. ALI ACCOUNT CREATION COMPLETE!")
    print("=" * 70)
    print()
    print(f"Username: {username}")
    print(f"Password: {password}")
    print(f"Full Name: {user.get_full_name()}")
    print(f"Email: {email}")
    print(f"Date of Birth: {date_of_birth.strftime('%d/%m/%Y')}")
    print(f"Specialty: {specialty_name}")
    print(f"Qualification: {qualification}")
    print(f"Department: {medical_dept.name}")
    print(f"Employee ID: {staff.employee_id}")
    print()
    print("🔐 IMPORTANT: Please change the password on first login!")
    print()
    print("Dashboard URL: /hms/specialists/my-dashboard/")
    print("=" * 70)
    print()

if __name__ == '__main__':
    create_dr_ali()




