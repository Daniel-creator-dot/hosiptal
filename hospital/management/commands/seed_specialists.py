"""
Management command to create sample specialist profiles for testing
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from hospital.models import Staff, Department
from hospital.models_specialists import Specialty, SpecialistProfile
from decimal import Decimal


class Command(BaseCommand):
    help = 'Create sample specialist profiles for dentists and other specialists'

    def handle(self, *args, **options):
        # Get or create departments
        dental_dept, _ = Department.objects.get_or_create(
            name='Dental Department',
            defaults={'code': 'DENT', 'is_active': True}
        )
        
        general_dept, _ = Department.objects.get_or_create(
            name='General Medicine',
            defaults={'code': 'GEN', 'is_active': True}
        )
        
        # Get specialties
        dentistry_specialty = Specialty.objects.filter(name__icontains='dentistry').first()
        cardiology_specialty = Specialty.objects.filter(name__icontains='cardiology').first()
        ophthalmology_specialty = Specialty.objects.filter(name__icontains='ophthalmology').first()
        
        if not dentistry_specialty:
            self.stdout.write(self.style.ERROR('Dentistry specialty not found. Please run seed_specialties first.'))
            return
        
        specialists_to_create = []
        
        # Create dentist specialists
        if dentistry_specialty:
            dentists = [
                {
                    'username': 'dentist1',
                    'first_name': 'John',
                    'last_name': 'Dentist',
                    'email': 'dentist1@hospital.com',
                    'specialty': dentistry_specialty,
                    'department': dental_dept,
                    'qualification': 'BDS, MDS',
                    'consultation_fee': Decimal('80.00'),
                },
                {
                    'username': 'dentist2',
                    'first_name': 'Sarah',
                    'last_name': 'Smile',
                    'email': 'dentist2@hospital.com',
                    'specialty': dentistry_specialty,
                    'department': dental_dept,
                    'qualification': 'BDS',
                    'consultation_fee': Decimal('80.00'),
                },
            ]
            specialists_to_create.extend(dentists)
        
        # Create other specialists
        if cardiology_specialty:
            specialists_to_create.append({
                'username': 'cardiologist1',
                'first_name': 'Michael',
                'last_name': 'Heart',
                'email': 'cardiologist1@hospital.com',
                'specialty': cardiology_specialty,
                'department': general_dept,
                'qualification': 'MD, Cardiology',
                'consultation_fee': Decimal('120.00'),
            })
        
        if ophthalmology_specialty:
            specialists_to_create.append({
                'username': 'eye_doctor1',
                'first_name': 'Emily',
                'last_name': 'Vision',
                'email': 'eye_doctor1@hospital.com',
                'specialty': ophthalmology_specialty,
                'department': general_dept,
                'qualification': 'MD, Ophthalmology',
                'consultation_fee': Decimal('100.00'),
            })
        
        created_count = 0
        skipped_count = 0
        
        for spec_data in specialists_to_create:
            # Check if user exists
            user, user_created = User.objects.get_or_create(
                username=spec_data['username'],
                defaults={
                    'first_name': spec_data['first_name'],
                    'last_name': spec_data['last_name'],
                    'email': spec_data['email'],
                    'is_staff': True,
                }
            )
            
            if not user_created:
                self.stdout.write(self.style.WARNING(f'User {spec_data["username"]} already exists, skipping specialist profile creation.'))
                skipped_count += 1
                continue
            
            # Set password
            user.set_password('password123')
            user.save()
            
            # Create staff profile
            staff, staff_created = Staff.objects.get_or_create(
                user=user,
                defaults={
                    'employee_id': f'EMP{spec_data["username"].upper()}',
                    'profession': 'doctor',
                    'department': spec_data['department'],
                    'is_active': True,
                }
            )
            
            # Create specialist profile
            specialist_profile, spec_created = SpecialistProfile.objects.get_or_create(
                staff=staff,
                defaults={
                    'specialty': spec_data['specialty'],
                    'qualification': spec_data['qualification'],
                    'consultation_fee': spec_data['consultation_fee'],
                    'is_active': True,
                }
            )
            
            if spec_created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(
                    f'Created: {user.get_full_name()} - {spec_data["specialty"].name} '
                    f'(Username: {spec_data["username"]}, Password: password123)'
                ))
            else:
                skipped_count += 1
                self.stdout.write(self.style.WARNING(f'Specialist profile already exists for {user.get_full_name()}'))
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\nSuccessfully created specialist profiles!\n'
                f'Created: {created_count}\n'
                f'Skipped: {skipped_count}\n'
                f'Note: Default password for all users is "password123"'
            )
        )





































