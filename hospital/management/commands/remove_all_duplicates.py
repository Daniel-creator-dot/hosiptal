"""
Comprehensive Duplicate Removal Command
Finds and removes ALL duplicates from the system - patients, staff, encounters, etc.
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q, Count
from django.utils import timezone
from hospital.models import Patient, Staff, Encounter, Invoice, Admission
from django.contrib.auth.models import User
import logging

logger = logging.getLogger(__name__)


def normalize_phone(phone):
    """Normalize phone number for comparison"""
    if not phone:
        return ''
    phone = str(phone).strip()
    phone = phone.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
    if phone.startswith('0') and len(phone) == 10:
        phone = '233' + phone[1:]
    elif phone.startswith('+'):
        phone = phone[1:]
    return phone


class Command(BaseCommand):
    help = 'Find and remove ALL duplicates from the system'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting',
        )
        parser.add_argument(
            '--patients-only',
            action='store_true',
            help='Only fix patient duplicates',
        )
        parser.add_argument(
            '--staff-only',
            action='store_true',
            help='Only fix staff duplicates',
        )
        parser.add_argument(
            '--aggressive',
            action='store_true',
            help='Aggressive mode: delete duplicates even if they have data',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        patients_only = options['patients_only']
        staff_only = options['staff_only']
        aggressive = options['aggressive']

        self.stdout.write(self.style.WARNING('=' * 80))
        self.stdout.write(self.style.WARNING('COMPREHENSIVE DUPLICATE REMOVAL'))
        self.stdout.write(self.style.WARNING('=' * 80))
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))
        
        self.stdout.write('')

        # Fix patients
        if not staff_only:
            self.fix_patient_duplicates(dry_run, aggressive)
        
        # Fix staff
        if not patients_only:
            self.fix_staff_duplicates(dry_run, aggressive)
        
        # Fix encounters
        if not patients_only and not staff_only:
            self.fix_encounter_duplicates(dry_run, aggressive)
        
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=' * 80))
        self.stdout.write(self.style.SUCCESS('DUPLICATE REMOVAL COMPLETE'))
        self.stdout.write(self.style.SUCCESS('=' * 80))

    def fix_patient_duplicates(self, dry_run, aggressive):
        """Find and fix patient duplicates"""
        self.stdout.write(self.style.WARNING('Checking for duplicate patients...'))
        
        # Find duplicates by MRN
        mrn_duplicates = Patient.objects.filter(is_deleted=False).values('mrn').annotate(
            count=Count('id')
        ).filter(count__gt=1)
        
        if mrn_duplicates.exists():
            self.stdout.write(self.style.ERROR(f'Found {mrn_duplicates.count()} duplicate MRN groups'))
            for dup in mrn_duplicates:
                patients = Patient.objects.filter(mrn=dup['mrn'], is_deleted=False).order_by('created')
                primary = patients.first()
                duplicates = patients[1:]
                
                self.stdout.write(f'  MRN {dup["mrn"]}: {patients.count()} duplicates')
                for dup_patient in duplicates:
                    if not dry_run:
                        self.merge_patient_data(primary, dup_patient, aggressive)
                        dup_patient.is_deleted = True
                        dup_patient.save(update_fields=['is_deleted'])
                        self.stdout.write(f'    ✓ Deleted duplicate: {dup_patient.full_name} (ID: {dup_patient.id})')
                    else:
                        self.stdout.write(f'    [DRY RUN] Would delete: {dup_patient.full_name} (ID: {dup_patient.id})')
        
        # Find duplicates by name + phone
        all_patients = Patient.objects.filter(is_deleted=False).order_by('created')
        seen = {}
        duplicates_found = 0
        
        for patient in all_patients:
            if not patient.first_name or not patient.last_name:
                continue
            
            key = (
                patient.first_name.lower().strip(),
                patient.last_name.lower().strip(),
                normalize_phone(patient.phone_number)
            )
            
            if key in seen:
                duplicates_found += 1
                primary = seen[key]
                if not dry_run:
                    self.merge_patient_data(primary, patient, aggressive)
                    patient.is_deleted = True
                    patient.save(update_fields=['is_deleted'])
                    self.stdout.write(f'  ✓ Deleted duplicate: {patient.full_name} (MRN: {patient.mrn})')
                else:
                    self.stdout.write(f'  [DRY RUN] Would delete: {patient.full_name} (MRN: {patient.mrn})')
            else:
                seen[key] = patient
        
        # Find duplicates by email
        email_duplicates = Patient.objects.filter(
            is_deleted=False,
            email__isnull=False
        ).exclude(email='').values('email').annotate(
            count=Count('id')
        ).filter(count__gt=1)
        
        if email_duplicates.exists():
            self.stdout.write(self.style.ERROR(f'Found {email_duplicates.count()} duplicate email groups'))
            for dup in email_duplicates:
                patients = Patient.objects.filter(
                    email__iexact=dup['email'],
                    is_deleted=False
                ).order_by('created')
                primary = patients.first()
                duplicates = patients[1:]
                
                for dup_patient in duplicates:
                    if not dry_run:
                        self.merge_patient_data(primary, dup_patient, aggressive)
                        dup_patient.is_deleted = True
                        dup_patient.save(update_fields=['is_deleted'])
                        self.stdout.write(f'    ✓ Deleted duplicate: {dup_patient.full_name} (Email: {dup_patient.email})')
                    else:
                        self.stdout.write(f'    [DRY RUN] Would delete: {dup_patient.full_name} (Email: {dup_patient.email})')
        
        # Find duplicates by national_id
        national_id_duplicates = Patient.objects.filter(
            is_deleted=False,
            national_id__isnull=False
        ).exclude(national_id='').values('national_id').annotate(
            count=Count('id')
        ).filter(count__gt=1)
        
        if national_id_duplicates.exists():
            self.stdout.write(self.style.ERROR(f'Found {national_id_duplicates.count()} duplicate National ID groups'))
            for dup in national_id_duplicates:
                patients = Patient.objects.filter(
                    national_id=dup['national_id'],
                    is_deleted=False
                ).order_by('created')
                primary = patients.first()
                duplicates = patients[1:]
                
                for dup_patient in duplicates:
                    if not dry_run:
                        self.merge_patient_data(primary, dup_patient, aggressive)
                        dup_patient.is_deleted = True
                        dup_patient.save(update_fields=['is_deleted'])
                        self.stdout.write(f'    ✓ Deleted duplicate: {dup_patient.full_name} (National ID: {dup_patient.national_id})')
                    else:
                        self.stdout.write(f'    [DRY RUN] Would delete: {dup_patient.full_name} (National ID: {dup_patient.national_id})')
        
        if duplicates_found == 0 and not mrn_duplicates.exists() and not email_duplicates.exists() and not national_id_duplicates.exists():
            self.stdout.write(self.style.SUCCESS('  ✓ No patient duplicates found'))
        else:
            self.stdout.write(self.style.SUCCESS(f'  ✓ Fixed {duplicates_found + (mrn_duplicates.count() if mrn_duplicates.exists() else 0)} patient duplicate groups'))

    def merge_patient_data(self, primary, duplicate, aggressive):
        """Merge data from duplicate into primary patient"""
        # Merge encounters
        Encounter.objects.filter(patient=duplicate).update(patient=primary)
        
        # Merge invoices
        Invoice.objects.filter(patient=duplicate).update(patient=primary)
        
        # Merge admissions
        Admission.objects.filter(encounter__patient=duplicate).update(
            encounter=Encounter.objects.filter(patient=primary).first()
        )
        
        # Merge other related data if needed
        # Add more relationships as needed
        
        # Update primary with missing data from duplicate
        if not primary.email and duplicate.email:
            primary.email = duplicate.email
        if not primary.phone_number and duplicate.phone_number:
            primary.phone_number = duplicate.phone_number
        # Only copy national_id if primary doesn't have one AND duplicate's national_id is valid and unique
        if not primary.national_id and duplicate.national_id:
            # Check if this national_id would create a duplicate
            existing_with_nid = Patient.objects.filter(
                national_id=duplicate.national_id,
                is_deleted=False
            ).exclude(pk=primary.pk).exclude(pk=duplicate.pk).first()
            if not existing_with_nid:
                primary.national_id = duplicate.national_id
        # Clear invalid national_id values (like "Ghanaian" which is not a valid ID)
        if primary.national_id and primary.national_id.lower() in ['ghanaian', 'ghana', 'none', 'null', '']:
            primary.national_id = None
        if not primary.address and duplicate.address:
            primary.address = duplicate.address
        
        primary.save()

    def fix_staff_duplicates(self, dry_run, aggressive):
        """Find and fix staff duplicates"""
        self.stdout.write(self.style.WARNING('Checking for duplicate staff...'))
        
        # Find duplicates by user
        staff_with_users = Staff.objects.filter(is_deleted=False, user__isnull=False)
        user_ids = staff_with_users.values_list('user_id', flat=True)
        duplicate_users = User.objects.filter(id__in=user_ids).values('id').annotate(
            count=Count('staff')
        ).filter(count__gt=1)
        
        if duplicate_users.exists():
            self.stdout.write(self.style.ERROR(f'Found {duplicate_users.count()} users with multiple staff records'))
            for dup in duplicate_users:
                staffs = Staff.objects.filter(user_id=dup['id'], is_deleted=False).order_by('created')
                primary = staffs.first()
                duplicates = staffs[1:]
                
                for dup_staff in duplicates:
                    if not dry_run:
                        # Merge data
                        dup_staff.is_deleted = True
                        dup_staff.save(update_fields=['is_deleted'])
                        self.stdout.write(f'  ✓ Deleted duplicate staff: {dup_staff.user.get_full_name()}')
                    else:
                        self.stdout.write(f'  [DRY RUN] Would delete: {dup_staff.user.get_full_name()}')
        
        # Find duplicates by employee_id
        employee_id_duplicates = Staff.objects.filter(
            is_deleted=False,
            employee_id__isnull=False
        ).exclude(employee_id='').values('employee_id').annotate(
            count=Count('id')
        ).filter(count__gt=1)
        
        if employee_id_duplicates.exists():
            self.stdout.write(self.style.ERROR(f'Found {employee_id_duplicates.count()} duplicate employee ID groups'))
            for dup in employee_id_duplicates:
                staffs = Staff.objects.filter(
                    employee_id=dup['employee_id'],
                    is_deleted=False
                ).order_by('created')
                primary = staffs.first()
                duplicates = staffs[1:]
                
                for dup_staff in duplicates:
                    if not dry_run:
                        dup_staff.is_deleted = True
                        dup_staff.save(update_fields=['is_deleted'])
                        self.stdout.write(f'    ✓ Deleted duplicate: {dup_staff.user.get_full_name()} (Employee ID: {dup_staff.employee_id})')
                    else:
                        self.stdout.write(f'    [DRY RUN] Would delete: {dup_staff.user.get_full_name()} (Employee ID: {dup_staff.employee_id})')
        
        self.stdout.write(self.style.SUCCESS('  ✓ Staff duplicate check complete'))

    def fix_encounter_duplicates(self, dry_run, aggressive):
        """Find and fix encounter duplicates"""
        self.stdout.write(self.style.WARNING('Checking for duplicate encounters...'))
        
        # Find encounters with same patient, same time, same type
        from django.db.models import Count
        encounter_duplicates = Encounter.objects.filter(
            is_deleted=False
        ).values('patient', 'started_at', 'encounter_type').annotate(
            count=Count('id')
        ).filter(count__gt=1)
        
        if encounter_duplicates.exists():
            self.stdout.write(self.style.ERROR(f'Found {encounter_duplicates.count()} duplicate encounter groups'))
            for dup in encounter_duplicates:
                encounters = Encounter.objects.filter(
                    patient_id=dup['patient'],
                    started_at=dup['started_at'],
                    encounter_type=dup['encounter_type'],
                    is_deleted=False
                ).order_by('created')
                primary = encounters.first()
                duplicates = encounters[1:]
                
                for dup_encounter in duplicates:
                    if not dry_run:
                        # Merge related data
                        from hospital.models import VitalSign, Order, Prescription
                        VitalSign.objects.filter(encounter=dup_encounter).update(encounter=primary)
                        Order.objects.filter(encounter=dup_encounter).update(encounter=primary)
                        Prescription.objects.filter(encounter=dup_encounter).update(encounter=primary)
                        
                        dup_encounter.is_deleted = True
                        dup_encounter.save(update_fields=['is_deleted'])
                        self.stdout.write(f'  ✓ Deleted duplicate encounter: {dup_encounter.patient.full_name} at {dup_encounter.started_at}')
                    else:
                        self.stdout.write(f'  [DRY RUN] Would delete encounter: {dup_encounter.patient.full_name} at {dup_encounter.started_at}')
        else:
            self.stdout.write(self.style.SUCCESS('  ✓ No encounter duplicates found'))






