"""
Management command to fix phone numbers in patient/staff records for SMS sending
"""
from django.core.management.base import BaseCommand
from django.db.models import Q
from ...models import Patient, Staff
from ...services.sms_service import SMSService
import re


class Command(BaseCommand):
    help = 'Fix phone numbers in patient/staff records for SMS compatibility'

    def add_arguments(self, parser):
        parser.add_argument(
            '--check-only',
            action='store_true',
            help='Only check, do not fix',
        )
        parser.add_argument(
            '--patient',
            type=str,
            help='Fix phone for specific patient (name or MRN)',
        )

    def format_phone(self, phone):
        """Format phone number to Ghana format (233XXXXXXXXX)"""
        if not phone:
            return None
        
        # Clean phone number
        phone = phone.replace('+', '').replace(' ', '').replace('-', '').replace('(', '').replace(')', '').replace('.', '').strip()
        
        if not phone:
            return None
        
        # Convert to Ghana format
        if phone.startswith('0'):
            phone = '233' + phone[1:]
        elif not phone.startswith('233'):
            if phone.startswith('00233'):
                phone = phone[2:]
            elif len(phone) == 9:
                phone = '233' + phone
            elif len(phone) == 10 and phone.startswith('0'):
                phone = '233' + phone[1:]
            else:
                phone = '233' + phone
        
        # Validate
        if phone.startswith('233') and len(phone) == 12 and phone[3:].isdigit():
            return phone
        
        return None

    def handle(self, *args, **options):
        check_only = options.get('check_only', False)
        patient_filter = options.get('patient')
        
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('FIXING PHONE NUMBERS FOR SMS'))
        self.stdout.write(self.style.SUCCESS('=' * 60))
        
        # Check patients
        self.stdout.write('\n[1] Checking Patients...')
        patient_query = Q(phone_number__isnull=False) & ~Q(phone_number='')
        if patient_filter:
            patient_query &= (Q(first_name__icontains=patient_filter) | 
                            Q(last_name__icontains=patient_filter) | 
                            Q(mrn__icontains=patient_filter))
        
        patients = Patient.objects.filter(patient_query, is_deleted=False)
        invalid_patients = []
        fixed_count = 0
        
        for patient in patients:
            original_phone = patient.phone_number
            formatted_phone = self.format_phone(original_phone)
            
            if not formatted_phone:
                invalid_patients.append({
                    'type': 'Patient',
                    'name': patient.full_name,
                    'mrn': patient.mrn,
                    'phone': original_phone,
                    'issue': 'Invalid format or empty'
                })
            elif formatted_phone != original_phone:
                if not check_only:
                    patient.phone_number = formatted_phone
                    patient.save(update_fields=['phone_number', 'modified'])
                    fixed_count += 1
                    self.stdout.write(self.style.SUCCESS(f'  ✓ Fixed: {patient.full_name} - {original_phone} -> {formatted_phone}'))
                else:
                    self.stdout.write(self.style.WARNING(f'  ⚠ Needs fix: {patient.full_name} - {original_phone} -> {formatted_phone}'))
        
        # Check staff
        self.stdout.write('\n[2] Checking Staff...')
        staff_query = Q(phone_number__isnull=False) & ~Q(phone_number='')
        if patient_filter:
            staff_query &= (Q(user__first_name__icontains=patient_filter) | 
                          Q(user__last_name__icontains=patient_filter))
        
        staff_members = Staff.objects.filter(staff_query, is_deleted=False)
        
        for staff in staff_members:
            original_phone = staff.phone_number
            formatted_phone = self.format_phone(original_phone)
            
            if not formatted_phone:
                invalid_patients.append({
                    'type': 'Staff',
                    'name': staff.user.get_full_name(),
                    'mrn': 'N/A',
                    'phone': original_phone,
                    'issue': 'Invalid format or empty'
                })
            elif formatted_phone != original_phone:
                if not check_only:
                    staff.phone_number = formatted_phone
                    staff.save(update_fields=['phone_number', 'modified'])
                    fixed_count += 1
                    self.stdout.write(self.style.SUCCESS(f'  ✓ Fixed: {staff.user.get_full_name()} - {original_phone} -> {formatted_phone}'))
                else:
                    self.stdout.write(self.style.WARNING(f'  ⚠ Needs fix: {staff.user.get_full_name()} - {original_phone} -> {formatted_phone}'))
        
        # Summary
        self.stdout.write('\n' + '=' * 60)
        if invalid_patients:
            self.stdout.write(self.style.ERROR(f'\nFound {len(invalid_patients)} records with invalid phone numbers:'))
            for item in invalid_patients[:10]:
                self.stdout.write(f'  - {item["type"]}: {item["name"]} ({item["mrn"]}) - Phone: {item["phone"]} - {item["issue"]}')
        else:
            self.stdout.write(self.style.SUCCESS('✓ No invalid phone numbers found'))
        
        if not check_only:
            self.stdout.write(self.style.SUCCESS(f'\n✓ Fixed {fixed_count} phone number(s)'))
        else:
            self.stdout.write(self.style.WARNING(f'\n⚠ Run without --check-only to fix {fixed_count} phone number(s)'))
        
        self.stdout.write('=' * 60)




