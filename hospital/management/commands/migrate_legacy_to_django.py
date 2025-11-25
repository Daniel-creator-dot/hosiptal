"""
Migrate Legacy Patients to Django Patient Model
Converts read-only legacy patient records to editable Django patients
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from datetime import datetime
from hospital.models import Patient
from hospital.models_legacy_patients import LegacyPatient
from hospital.models_insurance_companies import InsuranceCompany, PatientInsurance


class Command(BaseCommand):
    help = 'Migrate legacy patients to Django Patient model'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--pid',
            type=int,
            help='Migrate a specific patient by PID'
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=None,
            help='Limit number of patients to migrate'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be migrated without actually migrating'
        )
        parser.add_argument(
            '--skip-duplicates',
            action='store_true',
            help='Skip patients that already exist in Django'
        )
        parser.add_argument(
            '--link-insurance',
            action='store_true',
            help='Also link patients to their insurance companies'
        )
    
    def handle(self, *args, **options):
        pid = options['pid']
        limit = options['limit']
        dry_run = options['dry_run']
        skip_duplicates = options['skip_duplicates']
        link_insurance = options['link_insurance']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made\n'))
        
        self.stdout.write(self.style.SUCCESS('=== MIGRATING LEGACY PATIENTS TO DJANGO ===\n'))
        
        # Get legacy patients to migrate
        if pid:
            legacy_patients = LegacyPatient.objects.filter(pid=pid)
            if not legacy_patients.exists():
                self.stdout.write(self.style.ERROR(f'Legacy patient with PID {pid} not found'))
                return
        else:
            legacy_patients = LegacyPatient.objects.all()
            if limit:
                legacy_patients = legacy_patients[:limit]
        
        total = legacy_patients.count()
        self.stdout.write(f'Found {total:,} legacy patients to migrate\n')
        
        migrated_count = 0
        skipped_count = 0
        error_count = 0
        
        for idx, legacy_patient in enumerate(legacy_patients, 1):
            try:
                result = self.migrate_patient(legacy_patient, dry_run, skip_duplicates)
                
                if result == 'migrated':
                    migrated_count += 1
                    if migrated_count % 100 == 0:
                        self.stdout.write(f'  Progress: {migrated_count}/{total} migrated...')
                elif result == 'skipped':
                    skipped_count += 1
                else:
                    error_count += 1
                    
            except Exception as e:
                error_count += 1
                self.stdout.write(self.style.ERROR(
                    f'  Error migrating PID {legacy_patient.pid}: {str(e)}'
                ))
        
        # Summary
        self.stdout.write(self.style.SUCCESS(
            f'\n\nMigration Summary:'
        ))
        self.stdout.write(f'  Total processed: {total:,}')
        self.stdout.write(f'  Successfully migrated: {migrated_count:,}')
        self.stdout.write(f'  Skipped (duplicates): {skipped_count:,}')
        self.stdout.write(f'  Errors: {error_count:,}')
        
        if not dry_run and migrated_count > 0:
            self.stdout.write(self.style.SUCCESS(
                f'\n✓ Successfully migrated {migrated_count:,} legacy patients to Django!'
            ))
        
        # Link to insurance if requested
        if link_insurance and migrated_count > 0 and not dry_run:
            self.stdout.write('\nLinking patients to insurance...')
            self.link_patients_to_insurance()
    
    def migrate_patient(self, legacy_patient, dry_run=False, skip_duplicates=True):
        """Migrate a single legacy patient to Django"""
        
        # Check if already migrated (by MRN or phone+name)
        legacy_mrn = legacy_patient.mrn_display
        
        existing = Patient.objects.filter(
            Q(mrn=legacy_mrn) |
            Q(
                first_name__iexact=legacy_patient.fname,
                last_name__iexact=legacy_patient.lname,
                phone_number=legacy_patient.phone_cell[:17] if legacy_patient.phone_cell else ''
            )
        ).filter(is_deleted=False).first()
        
        if existing and skip_duplicates:
            return 'skipped'
        
        # Parse DOB
        dob = self.parse_date(legacy_patient.DOB) or datetime(2000, 1, 1).date()
        
        # Map gender
        gender_map = {
            'Male': 'M',
            'Female': 'F',
            'male': 'M',
            'female': 'F',
            'M': 'M',
            'F': 'F',
        }
        gender = gender_map.get(legacy_patient.sex, 'M')
        
        # Clean phone number (max 17 chars)
        phone = legacy_patient.phone_cell or legacy_patient.phone_home or legacy_patient.phone_contact or ''
        phone = phone[:17]
        
        # Build address
        address_parts = [
            legacy_patient.street,
            legacy_patient.city,
            legacy_patient.state,
            legacy_patient.postal_code,
        ]
        address = ', '.join(p for p in address_parts if p)
        
        if dry_run:
            self.stdout.write(
                f'  [DRY RUN] Would migrate PID {legacy_patient.pid}: '
                f'{legacy_patient.full_name} ({legacy_mrn})'
            )
            return 'migrated'
        
        # Create or update Django patient
        with transaction.atomic():
            patient, created = Patient.objects.update_or_create(
                mrn=legacy_mrn,
                defaults={
                    'first_name': self.clean_name(legacy_patient.fname),
                    'last_name': self.clean_name(legacy_patient.lname),
                    'middle_name': self.clean_name(legacy_patient.mname),
                    'date_of_birth': dob,
                    'gender': gender,
                    'phone_number': phone,
                    'email': legacy_patient.email or '',
                    'address': address,
                    'next_of_kin_name': legacy_patient.guardiansname or legacy_patient.mothersname or '',
                    'next_of_kin_phone': (legacy_patient.guardianphone or '')[:17],
                    'next_of_kin_relationship': legacy_patient.guardianrelationship or legacy_patient.contact_relationship or '',
                }
            )
            
            if created:
                self.stdout.write(
                    f'  ✓ Migrated PID {legacy_patient.pid} -> {patient.full_name} (MRN: {patient.mrn})'
                )
            else:
                self.stdout.write(
                    f'  ⟳ Updated PID {legacy_patient.pid} -> {patient.full_name} (MRN: {patient.mrn})'
                )
        
        return 'migrated'
    
    def link_patients_to_insurance(self):
        """Link migrated patients to their insurance companies"""
        # This would use the insurance_data.sql import logic
        self.stdout.write('  Insurance linking not yet implemented')
        self.stdout.write('  Use: python manage.py import_legacy_patients --insurance-only')
    
    def parse_date(self, date_str):
        """Parse various date formats"""
        if not date_str or str(date_str) in ['0000-00-00', '', 'None']:
            return None
        
        try:
            # Try YYYY-MM-DD
            return datetime.strptime(str(date_str), '%Y-%m-%d').date()
        except:
            try:
                # Try YYYY-MM-DD HH:MM:SS
                return datetime.strptime(str(date_str), '%Y-%m-%d %H:%M:%S').date()
            except:
                try:
                    # Try to extract year if it's just a year
                    year = int(str(date_str)[:4])
                    if 1900 <= year <= 2100:
                        return datetime(year, 1, 1).date()
                except:
                    pass
        
        return None
    
    def clean_name(self, name):
        """Clean a name string"""
        if not name:
            return ''
        
        import re
        
        # Remove numbers
        name = re.sub(r'[0-9]+', '', name)
        
        # Remove excessive special characters (keep hyphens, apostrophes, spaces)
        name = re.sub(r'[^a-zA-Z\s\-\'\.]', '', name)
        
        # Remove multiple spaces
        name = re.sub(r'\s+', ' ', name)
        
        # Proper case for all-caps names
        if name.isupper() and len(name) > 3:
            name = name.title()
        
        # Trim
        name = name.strip()
        
        return name


# Import Q for filtering
from django.db.models import Q


















