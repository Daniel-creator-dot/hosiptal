"""
Management command to set up Primecare Medical Center as a corporate client
and link all Primecare staff to this corporate account
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal

from hospital.models import Staff, Patient, Department
from hospital.models_enterprise_billing import CorporateAccount, CorporateEmployee
from hospital.models_insurance import Payer


class Command(BaseCommand):
    help = 'Set up Primecare Medical Center as a corporate client and link staff'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Setting up Primecare Medical Center as corporate client...'))
        
        # Create or get Primecare Medical Center corporate account
        corporate_account, created = CorporateAccount.objects.get_or_create(
            company_code='PCMC',
            defaults={
                'company_name': 'Primecare Medical Center',
                'registration_number': 'PCMC-REG-001',
                'billing_contact_name': 'Administration',
                'billing_email': 'admin@primecaremedical.com',
                'billing_phone': '+233XXXXXXXXX',
                'billing_address': 'Primecare Medical Center, Ghana',
                'credit_limit': Decimal('1000000.00'),  # 1 million GHS credit limit
                'payment_terms_days': 30,
                'billing_cycle': 'monthly',
                'billing_day_of_month': 1,
                'next_billing_date': (timezone.now().date() + timedelta(days=30)).replace(day=1),
                'contract_start_date': timezone.now().date(),
                'is_active': True,
                'require_pre_authorization': False,
            }
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS(f'✅ Created corporate account: {corporate_account.company_name}'))
        else:
            self.stdout.write(self.style.WARNING(f'⚠️ Corporate account already exists: {corporate_account.company_name}'))
        
        # Create or get Payer for Primecare
        payer, payer_created = Payer.objects.get_or_create(
            name='Primecare Medical Center',
            defaults={
                'payer_type': 'corporate',
                'is_active': True,
                'requires_authorization': False,
            }
        )
        
        if payer_created:
            self.stdout.write(self.style.SUCCESS(f'✅ Created payer: {payer.name}'))
        else:
            self.stdout.write(self.style.WARNING(f'⚠️ Payer already exists: {payer.name}'))
        
        # Link corporate account to payer
        if not hasattr(corporate_account, 'payer') or not corporate_account.payer:
            # We need to check if there's a relationship field
            # For now, we'll just ensure the payer exists
        
        # Get all Primecare staff (staff with PCMC employee IDs)
        primecare_staff = Staff.objects.filter(
            employee_id__startswith='PCMC-',
            is_deleted=False,
            is_active=True
        )
        
        self.stdout.write(self.style.SUCCESS(f'Found {primecare_staff.count()} Primecare staff members'))
        
        enrolled_count = 0
        for staff in primecare_staff:
            # Get or create patient for staff member
            patient, patient_created = Patient.objects.get_or_create(
                phone_number=staff.phone_number or f'STAFF-{staff.employee_id}',
                defaults={
                    'first_name': staff.user.first_name or '',
                    'last_name': staff.user.last_name or '',
                    'email': staff.user.email or '',
                    'date_of_birth': staff.date_of_birth,
                    'gender': staff.gender or 'other',
                    'address': staff.address or '',
                    'notes': f'Primecare Staff - Employee ID: {staff.employee_id}',
                    'primary_insurance': payer,
                }
            )
            
            if patient_created:
                self.stdout.write(f'  ✅ Created patient record for {staff.user.get_full_name()}')
            else:
                # Update existing patient
                patient.primary_insurance = payer
                patient.save(update_fields=['primary_insurance'])
            
            # Create or update corporate employee enrollment
            corporate_employee, emp_created = CorporateEmployee.objects.get_or_create(
                corporate_account=corporate_account,
                patient=patient,
                defaults={
                    'employee_id': staff.employee_id,
                    'department': staff.department.name if staff.department else '',
                    'designation': staff.get_profession_display(),
                    'employee_email': staff.user.email or '',
                    'is_active': True,
                    'has_annual_limit': False,
                }
            )
            
            if emp_created:
                enrolled_count += 1
                self.stdout.write(f'  ✅ Enrolled {staff.user.get_full_name()} ({staff.employee_id})')
            else:
                # Update existing enrollment
                corporate_employee.employee_id = staff.employee_id
                corporate_employee.department = staff.department.name if staff.department else ''
                corporate_employee.designation = staff.get_profession_display()
                corporate_employee.is_active = True
                corporate_employee.save()
                self.stdout.write(f'  ⚠️ Updated enrollment for {staff.user.get_full_name()}')
        
        # Update corporate account statistics
        corporate_account.total_employees_enrolled = CorporateEmployee.objects.filter(
            corporate_account=corporate_account,
            is_active=True
        ).count()
        corporate_account.save(update_fields=['total_employees_enrolled'])
        
        self.stdout.write(self.style.SUCCESS(f'\n✅ Setup complete!'))
        self.stdout.write(self.style.SUCCESS(f'   Corporate Account: {corporate_account.company_name} ({corporate_account.company_code})'))
        self.stdout.write(self.style.SUCCESS(f'   Total Staff Enrolled: {corporate_account.total_employees_enrolled}'))
        self.stdout.write(self.style.SUCCESS(f'   New Enrollments: {enrolled_count}'))






