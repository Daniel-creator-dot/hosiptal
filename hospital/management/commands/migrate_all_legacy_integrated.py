"""
Migrate ALL Legacy Patients to Main Patient System
Integrates legacy patients fully into HMS with regular MRNs
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from hospital.models import Patient
from hospital.models_legacy_patients import LegacyPatient
from hospital.models_legacy_mapping import LegacyIDMapping, MigrationLog
import re
from datetime import datetime


class Command(BaseCommand):
    help = 'Migrate ALL legacy patients to main HMS with regular MRNs (fully integrated)'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--batch-size',
            type=int,
            default=1000,
            help='Number of patients to migrate per batch (default: 1000)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be migrated without actually migrating'
        )
    
    def handle(self, *args, **options):
        batch_size = options['batch_size']
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('\n=== DRY RUN MODE - No changes will be made ===\n'))
        
        self.stdout.write(self.style.SUCCESS('\n' + '=' * 80))
        self.stdout.write(self.style.SUCCESS('MIGRATING ALL LEGACY PATIENTS TO MAIN HMS'))
        self.stdout.write(self.style.SUCCESS('Full Integration with Regular MRNs'))
        self.stdout.write(self.style.SUCCESS('=' * 80 + '\n'))
        
        # Get all legacy patients
        legacy_patients = LegacyPatient.objects.all().order_by('pid')
        total_legacy = legacy_patients.count()
        
        self.stdout.write(f'📊 Total legacy patients: {total_legacy:,}')
        
        # Check existing migrations
        existing_count = Patient.objects.filter(is_deleted=False).count()
        self.stdout.write(f'📊 Current HMS patients: {existing_count:,}')
        
        # Get the highest current MRN number
        last_mrn = self.get_last_mrn_number()
        self.stdout.write(f'📊 Last MRN number: PMC-{last_mrn:06d}')
        self.stdout.write(f'📊 New patients will start from: PMC-{last_mrn + 1:06d}\n')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('This is a DRY RUN - showing first 10 patients:\n'))
            for i, lp in enumerate(legacy_patients[:10], 1):
                new_mrn = f'PMC-{last_mrn + i:06d}'
                self.stdout.write(f'  {i}. {lp.full_name} (PID: {lp.pid}) → MRN: {new_mrn}')
            
            self.stdout.write(self.style.WARNING(f'\n... and {total_legacy - 10:,} more patients'))
            self.stdout.write(self.style.SUCCESS('\nTo perform actual migration, run without --dry-run'))
            return
        
        # Confirm migration
        self.stdout.write(self.style.WARNING(
            f'\n⚠️  This will migrate {total_legacy:,} legacy patients to main HMS'
        ))
        self.stdout.write('They will receive regular MRNs (PMC-XXXXXX) and be fully integrated.')
        
        confirm = input('\nProceed with migration? (yes/no): ')
        if confirm.lower() != 'yes':
            self.stdout.write(self.style.ERROR('\nMigration cancelled.'))
            return
        
        # Start migration
        self.stdout.write(self.style.SUCCESS('\n🚀 Starting migration...\n'))
        
        batch_id = f'full_integration_{timezone.now().strftime("%Y%m%d_%H%M%S")}'
        
        # Create migration log
        migration_log = MigrationLog.objects.create(
            batch_id=batch_id,
            migration_type='legacy_to_main_full_integration',
            status='in_progress',
            total_records=total_legacy,
            started_at=timezone.now(),
        )
        
        total_migrated = 0
        total_skipped = 0
        total_errors = 0
        batch_num = 0
        current_mrn = last_mrn
        
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
                    # Check if already migrated by name+phone
                    existing = self.find_existing_patient(legacy_patient)
                    
                    if existing:
                        batch_skipped += 1
                        continue
                    
                    # Generate next MRN
                    current_mrn += 1
                    new_mrn = f'PMC-{current_mrn:06d}'
                    
                    # Migrate patient
                    patient = self.migrate_patient(legacy_patient, new_mrn, batch_id)
                    
                    batch_migrated += 1
                    
                    if batch_migrated % 100 == 0:
                        self.stdout.write(f'  Progress: {batch_migrated} migrated in this batch...')
                        
                except Exception as e:
                    batch_errors += 1
                    self.stdout.write(self.style.ERROR(
                        f'  Error migrating PID {legacy_patient.pid}: {str(e)}'
                    ))
            
            # Batch summary
            total_migrated += batch_migrated
            total_skipped += batch_skipped
            total_errors += batch_errors
            
            self.stdout.write(self.style.SUCCESS(f'  ✓ Migrated: {batch_migrated}'))
            if batch_skipped > 0:
                self.stdout.write(self.style.WARNING(f'  ⊝ Skipped (existing): {batch_skipped}'))
            if batch_errors > 0:
                self.stdout.write(self.style.ERROR(f'  ✗ Errors: {batch_errors}'))
        
        # Update migration log
        migration_log.status = 'completed'
        migration_log.completed_at = timezone.now()
        migration_log.successful_records = total_migrated
        migration_log.failed_records = total_errors
        migration_log.skipped_records = total_skipped
        migration_log.success_log = f'Successfully migrated {total_migrated} legacy patients with regular MRNs'
        migration_log.save()
        
        # Final summary
        self.stdout.write(self.style.SUCCESS('\n\n' + '=' * 80))
        self.stdout.write(self.style.SUCCESS('MIGRATION COMPLETE'))
        self.stdout.write(self.style.SUCCESS('=' * 80))
        self.stdout.write(f'\nTotal Processed: {total_migrated + total_skipped + total_errors:,}')
        self.stdout.write(self.style.SUCCESS(f'✓ Successfully Migrated: {total_migrated:,}'))
        if total_skipped > 0:
            self.stdout.write(self.style.WARNING(f'⊝ Skipped (existing): {total_skipped:,}'))
        if total_errors > 0:
            self.stdout.write(self.style.ERROR(f'✗ Errors: {total_errors:,}'))
        
        # Final count
        final_count = Patient.objects.filter(is_deleted=False).count()
        self.stdout.write(f'\n📊 Total HMS Patients Now: {final_count:,}')
        self.stdout.write(f'📊 Highest MRN: PMC-{current_mrn:06d}')
        
        self.stdout.write(self.style.SUCCESS('\n🎉 All legacy patients are now fully integrated into HMS!'))
        self.stdout.write('✓ Regular MRNs assigned (PMC-XXXXXX)')
        self.stdout.write('✓ Accessible in normal patient flow')
        self.stdout.write('✓ No legacy prefixes')
        self.stdout.write('✓ Ready for encounters, orders, billing\n')
    
    def get_last_mrn_number(self):
        """Get the highest MRN number currently in use"""
        patients = Patient.objects.filter(
            mrn__startswith='PMC-',
            is_deleted=False
        ).exclude(
            mrn__contains='LEG'  # Exclude old legacy MRNs
        ).order_by('-mrn')
        
        if not patients.exists():
            return 0
        
        last_patient = patients.first()
        try:
            # Extract number from PMC-XXXXXX
            mrn_number = int(last_patient.mrn.split('-')[1])
            return mrn_number
        except (IndexError, ValueError):
            return 0
    
    def find_existing_patient(self, legacy_patient):
        """Check if patient already exists in HMS"""
        # Check by name and phone (most reliable)
        if legacy_patient.phone_cell:
            phone = self.clean_phone(legacy_patient.phone_cell)
            if phone:
                existing = Patient.objects.filter(
                    first_name__iexact=legacy_patient.fname or '',
                    last_name__iexact=legacy_patient.lname or '',
                    phone_number=phone,
                    is_deleted=False
                ).first()
                if existing:
                    return existing
        
        # Check by name and DOB
        if legacy_patient.DOB:
            dob = self.parse_date(legacy_patient.DOB)
            if dob:
                existing = Patient.objects.filter(
                    first_name__iexact=legacy_patient.fname or '',
                    last_name__iexact=legacy_patient.lname or '',
                    date_of_birth=dob,
                    is_deleted=False
                ).first()
                if existing:
                    return existing
        
        return None
    
    def migrate_patient(self, legacy_patient, new_mrn, batch_id):
        """Migrate a single legacy patient with regular MRN"""
        # Parse DOB
        dob = self.parse_date(legacy_patient.DOB) or '2000-01-01'
        
        # Parse gender
        gender = self.parse_gender(legacy_patient.sex)
        
        # Clean names
        first_name = self.clean_name(legacy_patient.fname or 'Unknown')
        last_name = self.clean_name(legacy_patient.lname or 'Patient')
        middle_name = self.clean_name(legacy_patient.mname or '')
        
        # Create Django patient with regular MRN
        with transaction.atomic():
            patient = Patient.objects.create(
                mrn=new_mrn,  # Regular MRN: PMC-XXXXXX
                first_name=first_name,
                last_name=last_name,
                middle_name=middle_name,
                date_of_birth=dob,
                gender=gender,
                phone_number=self.clean_phone(legacy_patient.phone_cell or legacy_patient.phone_home or ''),
                email=legacy_patient.email or '',
                address=self.build_address(legacy_patient),
                next_of_kin_name=legacy_patient.guardiansname or legacy_patient.mothersname or '',
                next_of_kin_phone=self.clean_phone(legacy_patient.guardianphone or ''),
                next_of_kin_relationship=legacy_patient.guardianrelationship or legacy_patient.contact_relationship or '',
            )
            
            # Create mapping record
            LegacyIDMapping.objects.create(
                legacy_table='patient_data',
                legacy_id=str(legacy_patient.pid),
                new_model='Patient',
                new_id=patient.id,
                migration_batch=batch_id,
                notes=f'Full integration: PID {legacy_patient.pid} → MRN {new_mrn}'
            )
        
        return patient
    
    def parse_date(self, date_str):
        """Parse various date formats"""
        if not date_str or str(date_str) in ['0000-00-00', '', 'None']:
            return None
        
        try:
            return datetime.strptime(str(date_str)[:10], '%Y-%m-%d').date()
        except:
            return None
    
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
    
    def clean_name(self, name):
        """Clean name field"""
        if not name:
            return ''
        name = re.sub(r'\d+', '', str(name))
        name = re.sub(r'[^\w\s\-]', '', name)
        return name.strip()
    
    def clean_phone(self, phone):
        """Clean phone number"""
        if not phone:
            return ''
        phone = re.sub(r'[^\d\+]', '', str(phone))
        return phone[:17]
    
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


















