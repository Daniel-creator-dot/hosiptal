"""
Django management command to check and fix all patient records
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from hospital.models import Patient
from hospital.utils_data_validation import validate_patient_data
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Check and fix all patient records in the database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be fixed without making changes',
        )
        parser.add_argument(
            '--fix-missing-mrn',
            action='store_true',
            help='Generate MRN for patients missing it',
        )
        parser.add_argument(
            '--fix-empty-names',
            action='store_true',
            help='Fix patients with empty first_name or last_name',
        )
        parser.add_argument(
            '--fix-invalid-dob',
            action='store_true',
            help='Fix patients with invalid date of birth',
        )
        parser.add_argument(
            '--fix-all',
            action='store_true',
            help='Apply all fixes',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        fix_all = options['fix_all']
        
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS('CHECKING AND FIXING ALL PATIENT RECORDS'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write('')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))
            self.stdout.write('')
        
        # Get all patients
        all_patients = Patient.objects.filter(is_deleted=False)
        total_count = all_patients.count()
        
        self.stdout.write(f'Total patients to check: {total_count}')
        self.stdout.write('')
        
        fixed_count = 0
        error_count = 0
        issues_found = []
        
        # Statistics
        stats = {
            'missing_mrn': 0,
            'empty_first_name': 0,
            'empty_last_name': 0,
            'invalid_dob': 0,
            'future_dob': 0,
            'invalid_phone': 0,
            'missing_id': 0,
        }
        
        for patient in all_patients:
            patient_fixed = False
            patient_issues = []
            
            # Check for missing ID
            if not patient.id:
                stats['missing_id'] += 1
                patient_issues.append('Missing ID')
                if not dry_run:
                    # This shouldn't happen, but log it
                    logger.error(f"Patient has no ID: MRN={patient.mrn}")
            
            # Check and fix missing MRN
            if not patient.mrn or patient.mrn.strip() == '':
                stats['missing_mrn'] += 1
                patient_issues.append('Missing MRN')
                if (fix_all or options['fix_missing_mrn']) and not dry_run:
                    try:
                        patient.mrn = patient.generate_mrn()
                        patient.save(update_fields=['mrn'])
                        patient_fixed = True
                        self.stdout.write(f'  ✅ Fixed MRN for patient: {patient.full_name} -> {patient.mrn}')
                    except Exception as e:
                        error_count += 1
                        logger.error(f"Error fixing MRN for patient {patient.id}: {e}")
            
            # Check and fix empty first name
            if not patient.first_name or not patient.first_name.strip():
                stats['empty_first_name'] += 1
                patient_issues.append('Empty first name')
                if (fix_all or options['fix_empty_names']) and not dry_run:
                    try:
                        patient.first_name = patient.first_name.strip() if patient.first_name else 'Unknown'
                        if not patient.first_name:
                            patient.first_name = 'Unknown'
                        patient.save(update_fields=['first_name'])
                        patient_fixed = True
                        self.stdout.write(f'  ✅ Fixed first name for patient: MRN={patient.mrn}')
                    except Exception as e:
                        error_count += 1
                        logger.error(f"Error fixing first name for patient {patient.id}: {e}")
            
            # Check and fix empty last name
            if not patient.last_name or not patient.last_name.strip():
                stats['empty_last_name'] += 1
                patient_issues.append('Empty last name')
                if (fix_all or options['fix_empty_names']) and not dry_run:
                    try:
                        patient.last_name = patient.last_name.strip() if patient.last_name else 'Unknown'
                        if not patient.last_name:
                            patient.last_name = f'Patient-{patient.mrn}' if patient.mrn else 'Unknown'
                        patient.save(update_fields=['last_name'])
                        patient_fixed = True
                        self.stdout.write(f'  ✅ Fixed last name for patient: MRN={patient.mrn}')
                    except Exception as e:
                        error_count += 1
                        logger.error(f"Error fixing last name for patient {patient.id}: {e}")
            
            # Check and fix invalid date of birth
            if patient.date_of_birth:
                today = timezone.now().date()
                age = (today - patient.date_of_birth).days / 365.25
                
                if patient.date_of_birth > today:
                    stats['future_dob'] += 1
                    patient_issues.append('Date of birth in future')
                    if (fix_all or options['fix_invalid_dob']) and not dry_run:
                        try:
                            # Set to a reasonable default (2000-01-01)
                            patient.date_of_birth = timezone.datetime(2000, 1, 1).date()
                            patient.save(update_fields=['date_of_birth'])
                            patient_fixed = True
                            self.stdout.write(f'  ✅ Fixed future DOB for patient: MRN={patient.mrn}')
                        except Exception as e:
                            error_count += 1
                            logger.error(f"Error fixing DOB for patient {patient.id}: {e}")
                elif age > 150:
                    stats['invalid_dob'] += 1
                    patient_issues.append(f'Age too old ({age:.0f} years)')
                    if (fix_all or options['fix_invalid_dob']) and not dry_run:
                        try:
                            # Set to a reasonable default
                            patient.date_of_birth = timezone.datetime(1950, 1, 1).date()
                            patient.save(update_fields=['date_of_birth'])
                            patient_fixed = True
                            self.stdout.write(f'  ✅ Fixed invalid DOB for patient: MRN={patient.mrn}')
                        except Exception as e:
                            error_count += 1
                            logger.error(f"Error fixing DOB for patient {patient.id}: {e}")
            
            # Check phone number (validation errors will be caught by model)
            if patient.phone_number:
                try:
                    # Try to validate phone number
                    patient.clean_fields()
                except Exception as e:
                    if 'phone_number' in str(e):
                        stats['invalid_phone'] += 1
                        patient_issues.append('Invalid phone number format')
                        if fix_all and not dry_run:
                            try:
                                # Clear invalid phone number
                                patient.phone_number = ''
                                patient.save(update_fields=['phone_number'])
                                patient_fixed = True
                                self.stdout.write(f'  ✅ Cleared invalid phone for patient: MRN={patient.mrn}')
                            except Exception as e2:
                                error_count += 1
                                logger.error(f"Error fixing phone for patient {patient.id}: {e2}")
            
            # Normalize national_id (empty string to None)
            if patient.national_id == '':
                if not dry_run:
                    try:
                        patient.national_id = None
                        patient.save(update_fields=['national_id'])
                        patient_fixed = True
                    except Exception as e:
                        error_count += 1
                        logger.error(f"Error normalizing national_id for patient {patient.id}: {e}")
            
            if patient_fixed:
                fixed_count += 1
            
            if patient_issues:
                issues_found.append({
                    'mrn': patient.mrn or 'N/A',
                    'name': patient.full_name or 'N/A',
                    'id': str(patient.id) if patient.id else 'N/A',
                    'issues': patient_issues
                })
        
        # Print summary
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS('SUMMARY'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write('')
        
        self.stdout.write(f'Total patients checked: {total_count}')
        self.stdout.write(f'Patients fixed: {fixed_count}')
        self.stdout.write(f'Errors encountered: {error_count}')
        self.stdout.write('')
        
        self.stdout.write(self.style.WARNING('Issues Found:'))
        self.stdout.write(f'  - Missing MRN: {stats["missing_mrn"]}')
        self.stdout.write(f'  - Empty first name: {stats["empty_first_name"]}')
        self.stdout.write(f'  - Empty last name: {stats["empty_last_name"]}')
        self.stdout.write(f'  - Invalid DOB (too old): {stats["invalid_dob"]}')
        self.stdout.write(f'  - Future DOB: {stats["future_dob"]}')
        self.stdout.write(f'  - Invalid phone: {stats["invalid_phone"]}')
        self.stdout.write(f'  - Missing ID: {stats["missing_id"]}')
        self.stdout.write('')
        
        if issues_found:
            self.stdout.write(self.style.WARNING(f'Patients with issues ({len(issues_found)}):'))
            for issue in issues_found[:20]:  # Show first 20
                self.stdout.write(f'  - MRN: {issue["mrn"]}, Name: {issue["name"]}, Issues: {", ".join(issue["issues"])}')
            if len(issues_found) > 20:
                self.stdout.write(f'  ... and {len(issues_found) - 20} more')
            self.stdout.write('')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN - No changes were made. Run without --dry-run to apply fixes.'))
        else:
            self.stdout.write(self.style.SUCCESS('✅ Patient database check and fix complete!'))
        
        self.stdout.write('')





