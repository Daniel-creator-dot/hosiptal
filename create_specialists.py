#!/usr/bin/env python
"""
Create Specialists for All Major Specialties
Ensures referral system has specialists available
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from django.contrib.auth.models import User
from hospital.models import Staff, Department
from hospital.models_specialists import Specialty, SpecialistProfile

def create_specialists():
    print("=" * 70)
    print("Creating Specialists for Referral System")
    print("=" * 70)
    print()
    
    # Define specialists to create
    specialists_data = [
        {
            'username': 'dr.surgeon',
            'first_name': 'Michael',
            'last_name': 'Thompson',
            'email': 'surgeon@hospital.com',
            'specialty_name': 'Surgery',
            'qualification': 'MBBS, FRCS',
            'license_number': 'MDC-SRG-2015',
        },
        {
            'username': 'dr.obgyn',
            'first_name': 'Sarah',
            'last_name': 'Williams',
            'email': 'obgyn@hospital.com',
            'specialty_name': 'Obstetrics & Gynecology',
            'qualification': 'MBBS, FRCOG',
            'license_number': 'MDC-OBG-2016',
        },
        {
            'username': 'dr.pediatrician',
            'first_name': 'James',
            'last_name': 'Rodriguez',
            'email': 'pediatrics@hospital.com',
            'specialty_name': 'Pediatrics',
            'qualification': 'MBBS, MRCPCH',
            'license_number': 'MDC-PED-2017',
        },
        {
            'username': 'dr.orthopedic',
            'first_name': 'Robert',
            'last_name': 'Anderson',
            'email': 'orthopedics@hospital.com',
            'specialty_name': 'Orthopedics',
            'qualification': 'MBBS, FRCS (Orth)',
            'license_number': 'MDC-ORT-2018',
        },
        {
            'username': 'dr.ent',
            'first_name': 'Emily',
            'last_name': 'Davis',
            'email': 'ent@hospital.com',
            'specialty_name': 'Ear, Nose & Throat (ENT)',
            'qualification': 'MBBS, FRCS (ENT)',
            'license_number': 'MDC-ENT-2019',
        },
    ]
    
    created_count = 0
    skipped_count = 0
    
    for spec_data in specialists_data:
        try:
            # Check if user already exists
            user = User.objects.filter(username=spec_data['username']).first()
            
            if not user:
                # Create user
                user = User.objects.create_user(
                    username=spec_data['username'],
                    email=spec_data['email'],
                    first_name=spec_data['first_name'],
                    last_name=spec_data['last_name'],
                    password='hospital123'  # Default password
                )
                print(f"[+] Created user: {user.get_full_name()}")
            else:
                print(f"[i] User exists: {user.get_full_name()}")
            
            # Create or get staff profile
            dept = Department.objects.filter(name__icontains=spec_data['specialty_name'].split()[0]).first()
            if not dept:
                dept = Department.objects.first()
            
            staff, staff_created = Staff.objects.get_or_create(
                user=user,
                defaults={
                    'employee_id': f'EMP{user.id:05d}',
                    'profession': 'doctor',
                    'department': dept,
                    'specialization': spec_data['qualification'],
                    'license_number': spec_data['license_number'],
                }
            )
            
            if staff_created:
                print(f"[+] Created staff profile for: {staff.user.get_full_name()}")
            
            # Get specialty
            specialty = Specialty.objects.filter(name=spec_data['specialty_name']).first()
            if not specialty:
                print(f"[!] Specialty not found: {spec_data['specialty_name']}")
                continue
            
            # Create specialist profile
            specialist, spec_created = SpecialistProfile.objects.get_or_create(
                staff=staff,
                defaults={
                    'specialty': specialty,
                    'qualification': spec_data['qualification'],
                    'experience_years': 5,
                    'consultation_fee': 50.00,
                    'is_active': True,
                }
            )
            
            if spec_created:
                print(f"[+] Created specialist profile: {specialist.staff.user.get_full_name()} ({specialty.name})")
                created_count += 1
            else:
                print(f"[i] Specialist already exists: {specialist.staff.user.get_full_name()}")
                skipped_count += 1
            
        except Exception as e:
            print(f"[ERROR] Failed to create specialist {spec_data['first_name']} {spec_data['last_name']}: {e}")
    
    print()
    print("=" * 70)
    print(f"[SUCCESS] Specialist Creation Complete!")
    print(f"  Created: {created_count} new specialists")
    print(f"  Skipped: {skipped_count} (already exist)")
    print("=" * 70)
    print()
    print("Summary of all specialists:")
    print("-" * 70)
    
    all_specialists = SpecialistProfile.objects.filter(is_active=True)
    for spec in all_specialists:
        print(f"  {spec.staff.user.get_full_name():30s} - {spec.specialty.name:30s} - {spec.qualification}")
    
    print()
    print("Total Active Specialists:", all_specialists.count())
    print()
    print("You can now refer patients to these specialists!")
    print("Default password for new users: hospital123")
    print()

if __name__ == '__main__':
    create_specialists()

