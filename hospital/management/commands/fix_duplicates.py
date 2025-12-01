"""
Management command to find and fix duplicate patients and staff in the database.
This command will:
1. Find all duplicate patients (by name+DOB+phone, email, national_id)
2. Find all duplicate staff (by username, email, employee_id)
3. Merge duplicates, keeping the oldest record
4. Report all changes
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q, Count
from hospital.models import Patient, Staff
from django.contrib.auth.models import User
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Find and fix duplicate patients and staff in the database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making changes',
        )
        parser.add_argument(
            '--fix',
            action='store_true',
            help='Actually fix duplicates (merge them)',
        )
        parser.add_argument(
            '--patients-only',
            action='store_true',
            help='Only check patients',
        )
        parser.add_argument(
            '--staff-only',
            action='store_true',
            help='Only check staff',
        )

    def normalize_phone(self, phone):
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

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        fix = options['fix']
        patients_only = options['patients_only']
        staff_only = options['staff_only']

        if not dry_run and not fix:
            self.stdout.write(self.style.ERROR(
                'Please specify --dry-run to see what would be done, or --fix to actually fix duplicates.'
            ))
            return

        self.stdout.write(self.style.WARNING('=' * 70))
        self.stdout.write(self.style.WARNING('DUPLICATE DETECTION AND FIX'))
        self.stdout.write(self.style.WARNING('=' * 70))

        if dry_run:
            self.stdout.write(self.style.WARNING('\n🔍 DRY RUN MODE - No changes will be made\n'))
        else:
            self.stdout.write(self.style.SUCCESS('\n🔧 FIX MODE - Duplicates will be merged\n'))

        # Fix patients
        if not staff_only:
            self.fix_patient_duplicates(dry_run)

        # Fix staff
        if not patients_only:
            self.fix_staff_duplicates(dry_run)

        self.stdout.write(self.style.SUCCESS('\n✅ Duplicate check complete!'))

    def fix_patient_duplicates(self, dry_run):
        """Find and fix duplicate patients"""
        self.stdout.write(self.style.WARNING('\n' + '=' * 70))
        self.stdout.write(self.style.WARNING('CHECKING PATIENT DUPLICATES'))
        self.stdout.write(self.style.WARNING('=' * 70))

        all_patients = Patient.objects.filter(is_deleted=False).order_by('created')
        total_patients = all_patients.count()
        self.stdout.write(f'\nTotal active patients: {total_patients}')

        duplicates_found = []
        duplicates_to_merge = []

        # Group 1: By name + DOB + phone
        self.stdout.write('\n📋 Checking duplicates by Name + Date of Birth + Phone...')
        processed = set()
        
        for patient in all_patients:
            if patient.id in processed:
                continue
            
            # Find potential duplicates
            normalized_phone = self.normalize_phone(patient.phone_number)
            if not (patient.first_name and patient.last_name and patient.date_of_birth and normalized_phone):
                continue

            duplicates = []
            for other in all_patients:
                if other.id == patient.id or other.id in processed:
                    continue
                
                if (other.first_name.lower() == patient.first_name.lower() and
                    other.last_name.lower() == patient.last_name.lower() and
                    other.date_of_birth == patient.date_of_birth and
                    self.normalize_phone(other.phone_number) == normalized_phone):
                    duplicates.append(other)
            
            if duplicates:
                # Keep the oldest (first created)
                all_dups = [patient] + duplicates
                all_dups.sort(key=lambda p: p.created)
                primary = all_dups[0]
                to_merge = all_dups[1:]
                
                duplicates_found.append({
                    'type': 'name_dob_phone',
                    'primary': primary,
                    'duplicates': to_merge,
                    'count': len(to_merge) + 1
                })
                
                for dup in all_dups:
                    processed.add(dup.id)

        # Group 2: By email
        self.stdout.write('📋 Checking duplicates by Email...')
        for patient in all_patients:
            if patient.id in processed or not patient.email:
                continue

            duplicates = list(all_patients.filter(
                email__iexact=patient.email,
                is_deleted=False
            ).exclude(id=patient.id).exclude(id__in=processed))
            
            if duplicates:
                all_dups = [patient] + duplicates
                all_dups.sort(key=lambda p: p.created)
                primary = all_dups[0]
                to_merge = all_dups[1:]
                
                duplicates_found.append({
                    'type': 'email',
                    'primary': primary,
                    'duplicates': to_merge,
                    'count': len(to_merge) + 1
                })
                
                for dup in all_dups:
                    processed.add(dup.id)

        # Group 3: By national_id
        self.stdout.write('📋 Checking duplicates by National ID...')
        for patient in all_patients:
            if patient.id in processed or not patient.national_id:
                continue

            duplicates = list(all_patients.filter(
                national_id=patient.national_id,
                is_deleted=False
            ).exclude(id=patient.id).exclude(id__in=processed))
            
            if duplicates:
                all_dups = [patient] + duplicates
                all_dups.sort(key=lambda p: p.created)
                primary = all_dups[0]
                to_merge = all_dups[1:]
                
                duplicates_found.append({
                    'type': 'national_id',
                    'primary': primary,
                    'duplicates': to_merge,
                    'count': len(to_merge) + 1
                })
                
                for dup in all_dups:
                    processed.add(dup.id)

        # Report findings
        total_duplicate_sets = len(duplicates_found)
        total_duplicate_records = sum(d['count'] - 1 for d in duplicates_found)
        
        self.stdout.write(f'\n📊 DUPLICATE SUMMARY:')
        self.stdout.write(f'   Sets of duplicates found: {total_duplicate_sets}')
        self.stdout.write(f'   Total duplicate records: {total_duplicate_records}')
        self.stdout.write(f'   Records to keep: {total_duplicate_sets}')
        self.stdout.write(f'   Records to merge/delete: {total_duplicate_records}')

        if duplicates_found:
            self.stdout.write(f'\n📝 DETAILED DUPLICATES:')
            for i, dup_set in enumerate(duplicates_found, 1):
                primary = dup_set['primary']
                duplicates = dup_set['duplicates']
                dup_type = dup_set['type']
                
                self.stdout.write(f'\n   Group {i} ({dup_type}):')
                self.stdout.write(f'   ✅ KEEP: {primary.full_name} (MRN: {primary.mrn}, Created: {primary.created.date()})')
                for dup in duplicates:
                    self.stdout.write(f'   ❌ MERGE: {dup.full_name} (MRN: {dup.mrn}, Created: {dup.created.date()})')

            # Fix duplicates if not dry run
            if not dry_run:
                self.stdout.write(f'\n🔧 Merging duplicates...')
                with transaction.atomic():
                    merged_count = 0
                    for dup_set in duplicates_found:
                        primary = dup_set['primary']
                        duplicates = dup_set['duplicates']
                        
                        # Merge data from duplicates into primary (keep most complete data)
                        for dup in duplicates:
                            # Merge fields if primary is empty but duplicate has value
                            if not primary.phone_number and dup.phone_number:
                                primary.phone_number = dup.phone_number
                            if not primary.email and dup.email:
                                primary.email = dup.email
                            if not primary.address and dup.address:
                                primary.address = dup.address
                            if not primary.national_id and dup.national_id:
                                primary.national_id = dup.national_id
                            # Merge medical info
                            if dup.allergies and (not primary.allergies or dup.allergies not in primary.allergies):
                                primary.allergies = (primary.allergies or '') + '\n' + dup.allergies if primary.allergies else dup.allergies
                            if dup.chronic_conditions and (not primary.chronic_conditions or dup.chronic_conditions not in primary.chronic_conditions):
                                primary.chronic_conditions = (primary.chronic_conditions or '') + '\n' + dup.chronic_conditions if primary.chronic_conditions else dup.chronic_conditions
                        
                        primary.save()
                        
                        # Mark duplicates as deleted
                        for dup in duplicates:
                            dup.is_deleted = True
                            dup.save(update_fields=['is_deleted'])
                            merged_count += 1
                        
                        self.stdout.write(f'   ✅ Merged {len(duplicates)} duplicates into {primary.mrn}')
                    
                    self.stdout.write(self.style.SUCCESS(f'\n✅ Successfully merged {merged_count} duplicate patient records!'))
        else:
            self.stdout.write(self.style.SUCCESS('\n✅ No patient duplicates found!'))

    def fix_staff_duplicates(self, dry_run):
        """Find and fix duplicate staff"""
        self.stdout.write(self.style.WARNING('\n' + '=' * 70))
        self.stdout.write(self.style.WARNING('CHECKING STAFF DUPLICATES'))
        self.stdout.write(self.style.WARNING('=' * 70))

        all_staff = Staff.objects.filter(is_deleted=False).select_related('user').order_by('created')
        total_staff = all_staff.count()
        self.stdout.write(f'\nTotal active staff: {total_staff}')

        duplicates_found = []
        processed = set()

        # Group 1: By username (User model)
        self.stdout.write('\n📋 Checking duplicates by Username...')
        usernames_seen = {}
        for staff in all_staff:
            if staff.id in processed:
                continue
            
            username = staff.user.username if hasattr(staff, 'user') and staff.user else None
            if not username:
                continue

            if username in usernames_seen:
                # Found duplicate username
                primary = usernames_seen[username]
                duplicates_found.append({
                    'type': 'username',
                    'primary': primary,
                    'duplicates': [staff],
                    'count': 2
                })
                processed.add(staff.id)
            else:
                usernames_seen[username] = staff

        # Group 2: By email (User model)
        self.stdout.write('📋 Checking duplicates by Email...')
        emails_seen = {}
        for staff in all_staff:
            if staff.id in processed:
                continue
            
            email = staff.user.email if hasattr(staff, 'user') and staff.user else None
            if not email:
                continue

            if email.lower() in emails_seen:
                primary = emails_seen[email.lower()]
                if staff not in [d['duplicates'] for d in duplicates_found if d['primary'] == primary]:
                    if any(d['primary'] == primary for d in duplicates_found):
                        # Add to existing group
                        for d in duplicates_found:
                            if d['primary'] == primary:
                                d['duplicates'].append(staff)
                                d['count'] += 1
                    else:
                        duplicates_found.append({
                            'type': 'email',
                            'primary': primary,
                            'duplicates': [staff],
                            'count': 2
                        })
                processed.add(staff.id)
            else:
                emails_seen[email.lower()] = staff

        # Group 3: By employee_id
        self.stdout.write('📋 Checking duplicates by Employee ID...')
        employee_ids_seen = {}
        for staff in all_staff:
            if staff.id in processed or not staff.employee_id:
                continue

            if staff.employee_id in employee_ids_seen:
                primary = employee_ids_seen[staff.employee_id]
                duplicates_found.append({
                    'type': 'employee_id',
                    'primary': primary,
                    'duplicates': [staff],
                    'count': 2
                })
                processed.add(staff.id)
            else:
                employee_ids_seen[staff.employee_id] = staff

        # Report findings
        total_duplicate_sets = len(duplicates_found)
        total_duplicate_records = sum(d['count'] - 1 for d in duplicates_found)
        
        self.stdout.write(f'\n📊 DUPLICATE SUMMARY:')
        self.stdout.write(f'   Sets of duplicates found: {total_duplicate_sets}')
        self.stdout.write(f'   Total duplicate records: {total_duplicate_records}')

        if duplicates_found:
            self.stdout.write(f'\n📝 DETAILED DUPLICATES:')
            for i, dup_set in enumerate(duplicates_found, 1):
                primary = dup_set['primary']
                duplicates = dup_set['duplicates']
                dup_type = dup_set['type']
                
                self.stdout.write(f'\n   Group {i} ({dup_type}):')
                primary_name = primary.user.get_full_name() if hasattr(primary, 'user') and primary.user else 'Unknown'
                self.stdout.write(f'   ✅ KEEP: {primary_name} (ID: {primary.employee_id}, Created: {primary.created.date()})')
                for dup in duplicates:
                    dup_name = dup.user.get_full_name() if hasattr(dup, 'user') and dup.user else 'Unknown'
                    self.stdout.write(f'   ❌ MERGE: {dup_name} (ID: {dup.employee_id}, Created: {dup.created.date()})')

            # Fix duplicates if not dry run
            if not dry_run:
                self.stdout.write(f'\n🔧 Merging duplicates...')
                with transaction.atomic():
                    merged_count = 0
                    for dup_set in duplicates_found:
                        primary = dup_set['primary']
                        duplicates = dup_set['duplicates']
                        
                        # Mark duplicates as deleted
                        for dup in duplicates:
                            dup.is_deleted = True
                            dup.save(update_fields=['is_deleted'])
                            # Also mark user as inactive
                            if hasattr(dup, 'user') and dup.user:
                                dup.user.is_active = False
                                dup.user.save(update_fields=['is_active'])
                            merged_count += 1
                        
                        primary_name = primary.user.get_full_name() if hasattr(primary, 'user') and primary.user else 'Unknown'
                        self.stdout.write(f'   ✅ Merged {len(duplicates)} duplicates into {primary_name}')
                    
                    self.stdout.write(self.style.SUCCESS(f'\n✅ Successfully merged {merged_count} duplicate staff records!'))
        else:
            self.stdout.write(self.style.SUCCESS('\n✅ No staff duplicates found!'))

