"""
Management command to add/update specialist doctors with consultation fees
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.db import transaction
from hospital.models import Staff, Department
from hospital.models_specialists import Specialty, SpecialistProfile
from decimal import Decimal


class Command(BaseCommand):
    help = 'Add or update specialist doctors with their consultation fees'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS('Adding/Updating Specialist Doctors'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write('')

        # Get or create departments
        general_dept, _ = Department.objects.get_or_create(
            name='General Medicine',
            defaults={'code': 'GEN', 'is_active': True}
        )

        # Get or create specialties
        specialties_map = {}
        specialty_data = [
            ('Physician Specialist', 'PHYS'),
            ('Dietitian', 'DIET'),
            ('Dental Surgeon', 'DENT'),
            ('ENT Specialist', 'ENT'),
            ('Gynaecology', 'GYN'),
            ('Antenatal Care', 'ANC'),
            ('Physiotherapy', 'PHYSIO'),
            ('Urology', 'URO'),
            ('Ophthalmology', 'OPHTH'),
            ('General Surgery', 'SURG'),
            ('Psychiatry', 'PSYCH'),
            ('Paediatrics', 'PED'),
        ]

        for spec_name, spec_code in specialty_data:
            specialty, created = Specialty.objects.get_or_create(
                name=spec_name,
                defaults={
                    'code': spec_code,
                    'is_active': True,
                }
            )
            specialties_map[spec_name] = specialty
            if created:
                self.stdout.write(self.style.SUCCESS(f'Created specialty: {spec_name}'))

        # Define specialists to create/update
        specialists_data = [
            {
                'first_name': 'Elikem',
                'last_name': 'Kumah',
                'username': 'dr.elikem.kumah',
                'email': 'dr.elikem.kumah@hospital.com',
                'specialty_name': 'Dental Surgeon',
                'consultation_fee': Decimal('150.00'),
                'qualification': 'BDS, MDS',
                'notes': '',
            },
            {
                'first_name': 'Rebecca',
                'last_name': 'Abalo',
                'username': 'dr.rebecca.abalo',
                'email': 'dr.rebecca.abalo@hospital.com',
                'specialty_name': 'Psychiatry',
                'consultation_fee': Decimal('350.00'),
                'qualification': 'MBBS, MRCPsych',
                'notes': 'First visit: 350, Subsequent: 300',
            },
            {
                'first_name': 'Lartey',
                'last_name': 'Lorna',
                'username': 'dr.lartey.lorna',
                'email': 'dr.lartey.lorna@hospital.com',
                'specialty_name': 'Psychiatry',
                'consultation_fee': Decimal('350.00'),
                'qualification': 'MBBS, MRCPsych',
                'notes': 'First visit: 350, Subsequent: 300',
            },
            {
                'first_name': 'Mustapha',
                'last_name': 'Dadzie',
                'username': 'dr.mustapha.dadzie',
                'email': 'dr.mustapha.dadzie@hospital.com',
                'specialty_name': 'Psychiatry',
                'consultation_fee': Decimal('350.00'),
                'qualification': 'MBBS, MRCPsych',
                'notes': 'First visit: 350, Subsequent: 300',
            },
        ]

        created_count = 0
        updated_count = 0
        skipped_count = 0

        with transaction.atomic():
            for spec_data in specialists_data:
                try:
                    # Get or create user
                    username = spec_data['username']
                    user, user_created = User.objects.get_or_create(
                        username=username,
                        defaults={
                            'first_name': spec_data['first_name'],
                            'last_name': spec_data['last_name'],
                            'email': spec_data['email'],
                            'is_staff': True,
                        }
                    )

                    # Update user info if it exists
                    if not user_created:
                        user.first_name = spec_data['first_name']
                        user.last_name = spec_data['last_name']
                        if not user.email:
                            user.email = spec_data['email']
                        user.is_staff = True
                        user.save()

                    # Set password if new user
                    if user_created:
                        user.set_password('hospital123')
                        user.save()

                    # Get or create staff profile
                    staff, staff_created = Staff.objects.get_or_create(
                        user=user,
                        defaults={
                            'employee_id': f'EMP{user.id:06d}',
                            'profession': 'doctor',
                            'department': general_dept,
                            'is_active': True,
                        }
                    )

                    # Update staff if exists
                    if not staff_created:
                        if not staff.employee_id:
                            staff.employee_id = f'EMP{user.id:06d}'
                        staff.profession = 'doctor'
                        staff.department = general_dept
                        staff.is_active = True
                        staff.save()

                    # Get specialty
                    specialty_name = spec_data['specialty_name']
                    specialty = specialties_map.get(specialty_name)
                    if not specialty:
                        self.stdout.write(self.style.ERROR(
                            f'Specialty not found: {specialty_name} for {spec_data["first_name"]} {spec_data["last_name"]}'
                        ))
                        skipped_count += 1
                        continue

                    # Build qualification with notes if applicable
                    qualification = spec_data['qualification']
                    if spec_data.get('notes'):
                        qualification = f"{qualification} ({spec_data['notes']})"

                    # Get or create specialist profile
                    specialist_profile, spec_created = SpecialistProfile.objects.get_or_create(
                        staff=staff,
                        defaults={
                            'specialty': specialty,
                            'qualification': qualification,
                            'consultation_fee': spec_data['consultation_fee'],
                            'is_active': True,
                        }
                    )

                    # Update specialist profile if exists
                    if not spec_created:
                        specialist_profile.specialty = specialty
                        specialist_profile.qualification = qualification
                        specialist_profile.consultation_fee = spec_data['consultation_fee']
                        specialist_profile.is_active = True
                        specialist_profile.save()
                        updated_count += 1
                        self.stdout.write(self.style.SUCCESS(
                            f'Updated: {user.get_full_name()} - {specialty.name} '
                            f'(Fee: GHS {spec_data["consultation_fee"]})'
                        ))
                    else:
                        created_count += 1
                        self.stdout.write(self.style.SUCCESS(
                            f'Created: {user.get_full_name()} - {specialty.name} '
                            f'(Fee: GHS {spec_data["consultation_fee"]}, Username: {username})'
                        ))

                except Exception as e:
                    self.stdout.write(self.style.ERROR(
                        f'Error creating {spec_data["first_name"]} {spec_data["last_name"]}: {str(e)}'
                    ))
                    skipped_count += 1

        # Summary
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS('Specialist Doctors Setup Complete!'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS(f'Created: {created_count}'))
        self.stdout.write(self.style.SUCCESS(f'Updated: {updated_count}'))
        self.stdout.write(self.style.WARNING(f'Skipped: {skipped_count}'))
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('Note: Default password for new users is "hospital123"'))
        self.stdout.write('')

        # Display all active specialists
        self.stdout.write(self.style.SUCCESS('Active Specialists:'))
        self.stdout.write('-' * 70)
        all_specialists = SpecialistProfile.objects.filter(is_active=True).select_related(
            'staff__user', 'specialty'
        ).order_by('specialty__name', 'staff__user__last_name')

        current_specialty = None
        for spec in all_specialists:
            if spec.specialty.name != current_specialty:
                current_specialty = spec.specialty.name
                self.stdout.write('')
                self.stdout.write(self.style.SUCCESS(f'{current_specialty}:'))
            self.stdout.write(
                f'  • {spec.staff.user.get_full_name():40s} - '
                f'GHS {spec.consultation_fee:>8.2f} - {spec.qualification}'
            )

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(f'Total Active Specialists: {all_specialists.count()}'))
