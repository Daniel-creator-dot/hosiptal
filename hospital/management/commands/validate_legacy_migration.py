"""
Validate and Ensure Complete Legacy Patient Migration
This command validates that all legacy patients are properly migrated
and provides detailed reports on migration quality
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from django.db.models import Q, Count
from hospital.models import Patient
from hospital.models_legacy_patients import LegacyPatient
from hospital.models_legacy_mapping import LegacyIDMapping, MigrationLog
import re
from datetime import datetime


class Command(BaseCommand):
    help = 'Validate and ensure all legacy patients are properly migrated'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--fix',
            action='store_true',
            help='Automatically fix issues found during validation'
        )
        parser.add_argument(
            '--migrate-missing',
            action='store_true',
            help='Migrate any legacy patients that are not yet in Django'
        )
        parser.add_argument(
            '--report-only',
            action='store_true',
            help='Only generate a report without making changes'
        )
    
    def handle(self, *args, **options):
        fix_issues = options['fix']
        migrate_missing = options['migrate_missing']
        report_only = options['report_only']
        
        self.stdout.write(self.style.SUCCESS('\n' + '=' * 80))
        self.stdout.write(self.style.SUCCESS('LEGACY PATIENT MIGRATION VALIDATION REPORT'))
        self.stdout.write(self.style.SUCCESS('=' * 80 + '\n'))
        
        # Statistics
        stats = {
            'total_legacy': 0,
            'total_django': 0,
            'migrated': 0,
            'not_migrated': 0,
            'duplicates': 0,
            'data_quality_issues': 0,
            'fixed': 0
        }
        
        # 1. Count total patients
        stats['total_legacy'] = LegacyPatient.objects.count()
        stats['total_django'] = Patient.objects.filter(is_deleted=False).count()
        
        self.stdout.write(f'📊 Total Legacy Patients: {stats["total_legacy"]:,}')
        self.stdout.write(f'📊 Total Django Patients: {stats["total_django"]:,}')
        
        # 2. Check which legacy patients are migrated
        self.stdout.write('\n' + '-' * 80)
        self.stdout.write('Checking migration status...\n')
        
        not_migrated = []
        data_quality_issues = []
        
        for legacy_patient in LegacyPatient.objects.all():
            mrn = f'PMC-LEG-{str(legacy_patient.pid).zfill(6)}'
            
            # Check if migrated
            django_patient = Patient.objects.filter(mrn=mrn, is_deleted=False).first()
            
            if django_patient:
                stats['migrated'] += 1
                
                # Validate data quality
                issues = self.check_data_quality(legacy_patient, django_patient)
                if issues:
                    stats['data_quality_issues'] += 1
                    data_quality_issues.append({
                        'legacy_patient': legacy_patient,
                        'django_patient': django_patient,
                        'issues': issues
                    })
            else:
                stats['not_migrated'] += 1
                not_migrated.append(legacy_patient)
        
        # Display results
        self.stdout.write(self.style.SUCCESS(f'✓ Successfully Migrated: {stats["migrated"]:,}'))
        
        if stats['not_migrated'] > 0:
            self.stdout.write(self.style.WARNING(f'⚠ Not Yet Migrated: {stats["not_migrated"]:,}'))
        
        if stats['data_quality_issues'] > 0:
            self.stdout.write(self.style.WARNING(f'⚠ Data Quality Issues: {stats["data_quality_issues"]:,}'))
        
        # 3. Check for duplicates
        self.stdout.write('\n' + '-' * 80)
        self.stdout.write('Checking for duplicates...\n')
        
        duplicates = self.find_duplicates()
        stats['duplicates'] = len(duplicates)
        
        if duplicates:
            self.stdout.write(self.style.WARNING(f'⚠ Found {len(duplicates)} potential duplicates'))
            for dup in duplicates[:10]:  # Show first 10
                self.stdout.write(f'  • {dup["name"]} ({dup["count"]} records)')
        else:
            self.stdout.write(self.style.SUCCESS('✓ No duplicates found'))
        
        # 4. Display data quality issues
        if data_quality_issues and not report_only:
            self.stdout.write('\n' + '-' * 80)
            self.stdout.write('Data Quality Issues (first 10):\n')
            
            for issue in data_quality_issues[:10]:
                self.stdout.write(f'\n  Patient: {issue["legacy_patient"].full_name} (PID: {issue["legacy_patient"].pid})')
                for problem in issue['issues']:
                    self.stdout.write(f'    ⚠ {problem}')
        
        # 5. Migrate missing patients if requested
        if migrate_missing and not report_only:
            self.stdout.write('\n' + '-' * 80)
            self.stdout.write(f'Migrating {len(not_migrated)} missing patients...\n')
            
            migrated_count = 0
            error_count = 0
            
            for legacy_patient in not_migrated:
                try:
                    self.migrate_patient(legacy_patient)
                    migrated_count += 1
                    
                    if migrated_count % 100 == 0:
                        self.stdout.write(f'  Progress: {migrated_count}/{len(not_migrated)}...')
                        
                except Exception as e:
                    error_count += 1
                    self.stdout.write(self.style.ERROR(
                        f'  Error migrating PID {legacy_patient.pid}: {str(e)}'
                    ))
            
            stats['fixed'] = migrated_count
            self.stdout.write(self.style.SUCCESS(f'\n✓ Successfully migrated {migrated_count} patients'))
            
            if error_count > 0:
                self.stdout.write(self.style.ERROR(f'✗ Failed to migrate {error_count} patients'))
        
        # 6. Fix data quality issues if requested
        if fix_issues and data_quality_issues and not report_only:
            self.stdout.write('\n' + '-' * 80)
            self.stdout.write('Fixing data quality issues...\n')
            
            fixed_count = 0
            for issue_data in data_quality_issues:
                try:
                    self.fix_data_quality(issue_data['legacy_patient'], issue_data['django_patient'])
                    fixed_count += 1
                except Exception as e:
                    self.stdout.write(self.style.WARNING(
                        f'  Could not fix PID {issue_data["legacy_patient"].pid}: {str(e)}'
                    ))
            
            self.stdout.write(self.style.SUCCESS(f'✓ Fixed {fixed_count} data quality issues'))
            stats['fixed'] += fixed_count
        
        # Final Summary
        self.stdout.write('\n' + '=' * 80)
        self.stdout.write(self.style.SUCCESS('SUMMARY'))
        self.stdout.write('=' * 80)
        self.stdout.write(f'Total Legacy Patients:     {stats["total_legacy"]:,}')
        self.stdout.write(f'Successfully Migrated:     {stats["migrated"]:,}')
        self.stdout.write(f'Not Yet Migrated:          {stats["not_migrated"]:,}')
        self.stdout.write(f'Data Quality Issues:       {stats["data_quality_issues"]:,}')
        self.stdout.write(f'Duplicate Records:         {stats["duplicates"]:,}')
        
        if not report_only:
            self.stdout.write(f'Issues Fixed:              {stats["fixed"]:,}')
        
        # Migration completeness percentage
        if stats['total_legacy'] > 0:
            completeness = (stats['migrated'] / stats['total_legacy']) * 100
            self.stdout.write(f'\nMigration Completeness:    {completeness:.2f}%')
            
            if completeness == 100:
                self.stdout.write(self.style.SUCCESS('\n🎉 ALL LEGACY PATIENTS SUCCESSFULLY MIGRATED! 🎉'))
            else:
                self.stdout.write(self.style.WARNING(
                    f'\n⚠ {stats["not_migrated"]:,} patients still need migration'
                ))
        
        self.stdout.write('\n' + '=' * 80 + '\n')
        
        # Log this validation run
        self.log_validation_run(stats)
    
    def check_data_quality(self, legacy_patient, django_patient):
        """Check data quality between legacy and Django patient"""
        issues = []
        
        # Check name consistency
        legacy_name = f"{legacy_patient.fname} {legacy_patient.lname}".strip().lower()
        django_name = f"{django_patient.first_name} {django_patient.last_name}".strip().lower()
        
        if legacy_name != django_name:
            issues.append(f'Name mismatch: "{legacy_name}" vs "{django_name}"')
        
        # Check DOB
        if legacy_patient.DOB and str(legacy_patient.DOB) != '0000-00-00':
            try:
                legacy_dob = self.parse_date(legacy_patient.DOB)
                if legacy_dob and str(legacy_dob) != str(django_patient.date_of_birth):
                    issues.append(f'DOB mismatch: {legacy_dob} vs {django_patient.date_of_birth}')
            except:
                pass
        
        # Check phone
        legacy_phone = self.clean_phone(legacy_patient.phone_cell or '')
        django_phone = django_patient.phone_number
        
        if legacy_phone and django_phone and legacy_phone != django_phone:
            issues.append(f'Phone mismatch: {legacy_phone} vs {django_phone}')
        
        return issues
    
    def find_duplicates(self):
        """Find potential duplicate patients"""
        # Find patients with same name and phone
        duplicates = []
        
        seen = {}
        for patient in Patient.objects.filter(is_deleted=False):
            key = f"{patient.first_name.lower()}_{patient.last_name.lower()}_{patient.phone_number}"
            
            if key in seen:
                seen[key] += 1
            else:
                seen[key] = 1
        
        for key, count in seen.items():
            if count > 1:
                name = key.split('_')[0:2]
                duplicates.append({
                    'name': ' '.join(name),
                    'count': count
                })
        
        return duplicates
    
    def migrate_patient(self, legacy_patient):
        """Migrate a single legacy patient to Django"""
        mrn = f'PMC-LEG-{str(legacy_patient.pid).zfill(6)}'
        
        # Parse DOB
        dob = self.parse_date(legacy_patient.DOB) or '2000-01-01'
        
        # Parse gender
        gender = self.parse_gender(legacy_patient.sex)
        
        # Clean names
        first_name = self.clean_name(legacy_patient.fname or 'Unknown')
        last_name = self.clean_name(legacy_patient.lname or 'Patient')
        middle_name = self.clean_name(legacy_patient.mname or '')
        
        # Create Django patient
        with transaction.atomic():
            patient = Patient.objects.create(
                mrn=mrn,
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
                next_of_kin_relationship=legacy_patient.guardianrelationship or '',
            )
            
            # Create mapping record
            LegacyIDMapping.objects.create(
                legacy_table='patient_data',
                legacy_id=str(legacy_patient.pid),
                new_model='Patient',
                new_id=patient.id,
                migration_batch='validate_migration',
                notes=f'Migrated from PID {legacy_patient.pid}'
            )
        
        return patient
    
    def fix_data_quality(self, legacy_patient, django_patient):
        """Fix data quality issues in Django patient"""
        # Update Django patient with correct legacy data
        django_patient.first_name = self.clean_name(legacy_patient.fname or django_patient.first_name)
        django_patient.last_name = self.clean_name(legacy_patient.lname or django_patient.last_name)
        django_patient.middle_name = self.clean_name(legacy_patient.mname or '')
        
        if legacy_patient.DOB:
            dob = self.parse_date(legacy_patient.DOB)
            if dob:
                django_patient.date_of_birth = dob
        
        django_patient.save()
    
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
    
    def log_validation_run(self, stats):
        """Log this validation run for audit purposes"""
        try:
            batch_id = f'validation_{timezone.now().strftime("%Y%m%d_%H%M%S")}'
            
            MigrationLog.objects.create(
                batch_id=batch_id,
                migration_type='legacy_patient_validation',
                status='completed',
                total_records=stats['total_legacy'],
                successful_records=stats['migrated'],
                failed_records=stats['not_migrated'],
                skipped_records=0,
                started_at=timezone.now(),
                completed_at=timezone.now(),
                success_log=f"Validation completed. Migrated: {stats['migrated']}, Issues: {stats['data_quality_issues']}",
                error_log=''
            )
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'Could not log validation run: {str(e)}'))


















