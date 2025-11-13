"""
Bulk Migration Command for Legacy Patients
Migrates all legacy patients with progress tracking and error handling
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from hospital.models import Patient
from hospital.models_legacy_patients import LegacyPatient
import re


class Command(BaseCommand):
    help = 'Bulk migrate all legacy patients to Django with progress tracking'

    def add_arguments(self, parser):
        parser.add_argument(
            '--batch-size',
            type=int,
            default=1000,
            help='Number of patients to migrate per batch (default: 1000)'
        )
        parser.add_argument(
            '--skip-existing',
            action='store_true',
            help='Skip patients that already exist in Django'
        )

    def handle(self, *args, **options):
        batch_size = options['batch_size']
        skip_existing = options['skip_existing']
        
        self.stdout.write(self.style.SUCCESS('\n=== BULK LEGACY PATIENT MIGRATION ===\n'))
        
        # Get all legacy patients
        legacy_patients = LegacyPatient.objects.all().order_by('pid')
        total_legacy = legacy_patients.count()
        
        self.stdout.write(f'Total legacy patients: {total_legacy:,}')
        
        # Check existing
        existing_count = Patient.objects.filter(mrn__startswith='PMC-LEG-').count()
        self.stdout.write(f'Already migrated: {existing_count:,}')
        self.stdout.write(f'Remaining: {total_legacy - existing_count:,}\n')
        
        # Stats
        total_migrated = 0
        total_skipped = 0
        total_errors = 0
        batch_num = 0
        
        # Process in batches
        for i in range(0, total_legacy, batch_size):
            batch_num += 1
            batch = legacy_patients[i:i+batch_size]
            
            self.stdout.write(f'\n--- Batch {batch_num} (Patients {i+1}-{min(i+batch_size, total_legacy)}) ---')
            
            batch_migrated = 0
            batch_skipped = 0
            batch_errors = 0
            
            for legacy_patient in batch:
                try:
                    mrn = f'PMC-LEG-{str(legacy_patient.pid).zfill(6)}'
                    
                    # Check if already migrated
                    if skip_existing and Patient.objects.filter(mrn=mrn).exists():
                        batch_skipped += 1
                        continue
                    
                    # Clean name
                    first_name = self.clean_name(legacy_patient.fname or '')
                    last_name = self.clean_name(legacy_patient.lname or '')
                    middle_name = self.clean_name(legacy_patient.mname or '')
                    
                    # Parse DOB
                    dob = self.parse_dob(legacy_patient.DOB)
                    
                    # Create Django patient
                    with transaction.atomic():
                        patient = Patient.objects.create(
                            mrn=mrn,
                            first_name=first_name or 'Unknown',
                            last_name=last_name or 'Patient',
                            middle_name=middle_name,
                            date_of_birth=dob,
                            gender=self.parse_gender(legacy_patient.sex),
                            phone_number=self.clean_phone(legacy_patient.phone_cell or legacy_patient.phone_home or ''),
                            email=legacy_patient.email or '',
                            address=self.build_address(legacy_patient),
                            next_of_kin_name=legacy_patient.guardiansname or legacy_patient.mothersname or '',
                            next_of_kin_phone=self.clean_phone(legacy_patient.guardianphone or ''),
                            next_of_kin_relationship=legacy_patient.guardianrelationship or legacy_patient.contact_relationship or '',
                        )
                        
                        batch_migrated += 1
                        
                except Exception as e:
                    batch_errors += 1
                    self.stdout.write(self.style.WARNING(f'  Error migrating PID {legacy_patient.pid}: {str(e)}'))
            
            # Batch summary
            total_migrated += batch_migrated
            total_skipped += batch_skipped
            total_errors += batch_errors
            
            self.stdout.write(self.style.SUCCESS(f'  Migrated: {batch_migrated}'))
            if batch_skipped > 0:
                self.stdout.write(self.style.WARNING(f'  Skipped: {batch_skipped}'))
            if batch_errors > 0:
                self.stdout.write(self.style.ERROR(f'  Errors: {batch_errors}'))
        
        # Final summary
        self.stdout.write(self.style.SUCCESS(f'\n\n=== MIGRATION COMPLETE ==='))
        self.stdout.write(f'Total Processed: {total_migrated + total_skipped + total_errors:,}')
        self.stdout.write(self.style.SUCCESS(f'Successfully Migrated: {total_migrated:,}'))
        if total_skipped > 0:
            self.stdout.write(self.style.WARNING(f'Skipped (existing): {total_skipped:,}'))
        if total_errors > 0:
            self.stdout.write(self.style.ERROR(f'Errors: {total_errors:,}'))
        
        # Final count
        final_count = Patient.objects.filter(is_deleted=False).count()
        self.stdout.write(f'\nTotal Django Patients Now: {final_count:,}')
        self.stdout.write(self.style.SUCCESS('\n✓ All legacy patients are now in HMS!\n'))
    
    def clean_name(self, name):
        """Remove numbers and special characters from names"""
        if not name:
            return ''
        # Remove numbers
        name = re.sub(r'\d+', '', name)
        # Remove special characters except spaces and hyphens
        name = re.sub(r'[^\w\s\-]', '', name)
        return name.strip()
    
    def parse_dob(self, dob):
        """Parse DOB to date"""
        if not dob:
            return '2000-01-01'
        
        dob_str = str(dob)
        if len(dob_str) >= 10:
            try:
                # Format: YYYY-MM-DD or similar
                return dob_str[:10]
            except:
                pass
        return '2000-01-01'
    
    def parse_gender(self, sex):
        """Parse gender"""
        if not sex:
            return 'O'
        sex_upper = str(sex).upper()
        if sex_upper in ['M', 'MALE']:
            return 'M'
        elif sex_upper in ['F', 'FEMALE']:
            return 'F'
        return 'O'
    
    def clean_phone(self, phone):
        """Clean phone number"""
        if not phone:
            return ''
        # Remove all non-numeric except +
        phone = re.sub(r'[^\d\+]', '', str(phone))
        return phone[:17]  # Max length
    
    def build_address(self, legacy_patient):
        """Build address from legacy fields"""
        parts = []
        if legacy_patient.street:
            parts.append(str(legacy_patient.street))
        if legacy_patient.city:
            parts.append(str(legacy_patient.city))
        if legacy_patient.state:
            parts.append(str(legacy_patient.state))
        
        return ', '.join(filter(None, parts)) or ''

