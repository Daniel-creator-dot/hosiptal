"""
Management command to seed the database with sample data.
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from hospital.models import (
    Patient, Department, Staff, Ward, Bed, Payer, ServiceCode,
    PriceBook, LabTest, Drug, PharmacyStock
)


class Command(BaseCommand):
    help = 'Seed the database with sample data'

    def handle(self, *args, **options):
        self.stdout.write('Seeding database with sample data...')
        
        # Create departments
        self.stdout.write('Creating departments...')
        dept_medicine = Department.objects.get_or_create(
            name='Medicine',
            defaults={'code': 'MED', 'description': 'General Medicine Department'}
        )[0]
        dept_surgery = Department.objects.get_or_create(
            name='Surgery',
            defaults={'code': 'SUR', 'description': 'Surgical Department'}
        )[0]
        dept_lab = Department.objects.get_or_create(
            name='Laboratory',
            defaults={'code': 'LAB', 'description': 'Laboratory Services'}
        )[0]
        dept_pharmacy = Department.objects.get_or_create(
            name='Pharmacy',
            defaults={'code': 'PHARM', 'description': 'Pharmacy Department'}
        )[0]
        
        # Create staff users
        self.stdout.write('Creating staff...')
        admin_user, _ = User.objects.get_or_create(
            username='admin',
            defaults={
                'email': 'admin@hms.local',
                'first_name': 'Admin',
                'last_name': 'User',
                'is_staff': True,
                'is_superuser': True
            }
        )
        admin_user.set_password('admin123')
        admin_user.save()
        
        doctor_user, _ = User.objects.get_or_create(
            username='doctor1',
            defaults={
                'email': 'doctor1@hms.local',
                'first_name': 'John',
                'last_name': 'Smith',
                'is_staff': True
            }
        )
        doctor_user.set_password('doctor123')
        doctor_user.save()
        
        nurse_user, _ = User.objects.get_or_create(
            username='nurse1',
            defaults={
                'email': 'nurse1@hms.local',
                'first_name': 'Jane',
                'last_name': 'Doe',
                'is_staff': True
            }
        )
        nurse_user.set_password('nurse123')
        nurse_user.save()
        
        # Create staff profiles
        doctor_staff, _ = Staff.objects.get_or_create(
            user=doctor_user,
            defaults={
                'employee_id': 'EMP001',
                'profession': 'doctor',
                'department': dept_medicine,
                'registration_number': 'MD12345',
                'phone_number': '+1234567890',
                'is_active': True
            }
        )
        
        nurse_staff, _ = Staff.objects.get_or_create(
            user=nurse_user,
            defaults={
                'employee_id': 'EMP002',
                'profession': 'nurse',
                'department': dept_medicine,
                'phone_number': '+1234567891',
                'is_active': True
            }
        )
        
        # Set department heads
        dept_medicine.head_of_department = doctor_staff
        dept_medicine.save()
        
        # Create wards
        self.stdout.write('Creating wards...')
        ward_general, _ = Ward.objects.get_or_create(
            name='General Ward A',
            defaults={
                'code': 'GEN-A',
                'ward_type': 'general',
                'department': dept_medicine,
                'capacity': 20,
                'is_active': True
            }
        )
        
        ward_icu, _ = Ward.objects.get_or_create(
            name='ICU',
            defaults={
                'code': 'ICU-1',
                'ward_type': 'icu',
                'department': dept_surgery,
                'capacity': 10,
                'is_active': True
            }
        )
        
        # Create beds
        self.stdout.write('Creating beds...')
        for i in range(1, 21):
            Bed.objects.get_or_create(
                ward=ward_general,
                bed_number=f'A{i:02d}',
                defaults={
                    'bed_type': 'general',
                    'status': 'available',
                    'is_active': True
                }
            )
        
        for i in range(1, 11):
            Bed.objects.get_or_create(
                ward=ward_icu,
                bed_number=f'ICU{i:02d}',
                defaults={
                    'bed_type': 'icu',
                    'status': 'available',
                    'is_active': True
                }
            )
        
        # Create payers
        self.stdout.write('Creating payers...')
        payer_nhis, _ = Payer.objects.get_or_create(
            name='National Health Insurance',
            defaults={
                'payer_type': 'nhis',
                'is_active': True
            }
        )
        
        payer_cash, _ = Payer.objects.get_or_create(
            name='Cash Payment',
            defaults={
                'payer_type': 'cash',
                'is_active': True
            }
        )
        
        # Create service codes
        self.stdout.write('Creating service codes...')
        service_consultation, _ = ServiceCode.objects.get_or_create(
            code='CONSULT',
            defaults={
                'description': 'Consultation Fee',
                'category': 'Consultation',
                'is_active': True
            }
        )
        
        service_lab_cbc, _ = ServiceCode.objects.get_or_create(
            code='LAB-CBC',
            defaults={
                'description': 'Complete Blood Count',
                'category': 'Laboratory',
                'is_active': True
            }
        )
        
        # Create price books
        self.stdout.write('Creating price books...')
        PriceBook.objects.get_or_create(
            payer=payer_nhis,
            service_code=service_consultation,
            defaults={
                'unit_price': Decimal('50.00'),
                'is_active': True
            }
        )
        
        PriceBook.objects.get_or_create(
            payer=payer_cash,
            service_code=service_consultation,
            defaults={
                'unit_price': Decimal('100.00'),
                'is_active': True
            }
        )
        
        # Create lab tests
        self.stdout.write('Creating lab tests...')
        LabTest.objects.get_or_create(
            code='CBC',
            defaults={
                'name': 'Complete Blood Count',
                'specimen_type': 'Blood',
                'tat_minutes': 60,
                'price': Decimal('25.00'),
                'is_active': True
            }
        )
        
        # Create drugs
        self.stdout.write('Creating drugs...')
        Drug.objects.get_or_create(
            name='Paracetamol',
            defaults={
                'generic_name': 'Acetaminophen',
                'strength': '500mg',
                'form': 'Tablet',
                'pack_size': '100 tablets',
                'is_controlled': False,
                'is_active': True
            }
        )
        
        self.stdout.write(self.style.SUCCESS('Successfully seeded database with sample data!'))


