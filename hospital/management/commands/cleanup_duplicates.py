"""Clean up duplicate patients - keep oldest, merge data, soft-delete duplicates"""
from django.core.management.base import BaseCommand
from hospital.models import Patient
from django.db import transaction
from collections import defaultdict
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
    help = 'Clean up duplicate patients - keep oldest record, merge data, soft-delete duplicates'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without actually doing it',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('=== DRY RUN MODE - No changes will be made ===\n'))
        else:
            self.stdout.write(self.style.SUCCESS('=== Cleaning Up Duplicate Patients ===\n'))
        
        # Get all active patients
        patients = Patient.objects.filter(is_deleted=False).order_by('created')
        
        # Group by normalized phone + name
        phone_name_groups = defaultdict(list)
        
        for patient in patients:
            if patient.phone_number and patient.first_name and patient.last_name:
                key = (normalize_phone(patient.phone_number), 
                       patient.first_name.lower().strip(), 
                       patient.last_name.lower().strip())
                phone_name_groups[key].append(patient)
        
        # Find duplicates
        duplicates_found = 0
        records_to_delete = 0
        
        with transaction.atomic():
            for key, group in phone_name_groups.items():
                if len(group) > 1:
                    duplicates_found += 1
                    # Sort by creation date - keep oldest
                    group.sort(key=lambda p: p.created)
                    primary = group[0]
                    duplicates = group[1:]
                    
                    self.stdout.write(f'\n📋 Group: {key[1]} {key[2]} ({key[0]})')
                    self.stdout.write(f'  ✅ Keeping: {primary.mrn} (Created: {primary.created.date()})')
                    
                    # Merge data from duplicates into primary
                    for dup in duplicates:
                        records_to_delete += 1
                        self.stdout.write(f'  ❌ Merging: {dup.mrn} (Created: {dup.created.date()})')
                        
                        # Merge missing data
                        if not primary.email and dup.email:
                            primary.email = dup.email
                            self.stdout.write(f'    → Merged email: {dup.email}')
                        
                        if not primary.national_id and dup.national_id:
                            primary.national_id = dup.national_id
                            self.stdout.write(f'    → Merged national_id: {dup.national_id}')
                        
                        if not primary.address and dup.address:
                            primary.address = dup.address
                        
                        if not primary.next_of_kin_name and dup.next_of_kin_name:
                            primary.next_of_kin_name = dup.next_of_kin_name
                            primary.next_of_kin_phone = dup.next_of_kin_phone
                            primary.next_of_kin_relationship = dup.next_of_kin_relationship
                        
                        # Soft delete duplicate
                        if not dry_run:
                            dup.is_deleted = True
                            dup.save(update_fields=['is_deleted', 'modified'])
                    
                    # Save primary with merged data
                    if not dry_run:
                        primary.save()
        
        self.stdout.write(self.style.SUCCESS(f'\n\n📊 SUMMARY:'))
        self.stdout.write(f'  Duplicate groups found: {duplicates_found}')
        self.stdout.write(f'  Records to delete: {records_to_delete}')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('\n⚠️  This was a DRY RUN. Use without --dry-run to apply changes.'))
        else:
            self.stdout.write(self.style.SUCCESS('\n✅ Cleanup completed!'))

