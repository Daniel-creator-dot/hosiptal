"""
Migrate patient insurance from old fields to new PatientInsurance model
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from hospital.models import Patient
from hospital.models_insurance_companies import InsuranceCompany, PatientInsurance


class Command(BaseCommand):
    help = 'Migrate patient insurance data from old fields to new PatientInsurance records'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Perform a dry run without actually migrating data'
        )
    
    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No data will be migrated\n'))
        
        self.stdout.write(self.style.SUCCESS('=== MIGRATING PATIENT INSURANCE DATA ===\n'))
        
        # Find patients with old insurance fields populated
        patients_with_insurance = Patient.objects.filter(
            is_deleted=False
        ).exclude(
            insurance_company='',
            insurance_id=''
        )
        
        total_found = patients_with_insurance.count()
        self.stdout.write(f'Found {total_found} patients with old insurance field data\n')
        
        if total_found == 0:
            self.stdout.write(self.style.WARNING('No patients found with old insurance data to migrate.'))
            self.stdout.write('\nYou need to import legacy patient data first:')
            self.stdout.write('  python manage.py import_legacy_patients\n')
            return
        
        created_count = 0
        skipped_count = 0
        error_count = 0
        
        for patient in patients_with_insurance:
            try:
                # Check if already has a PatientInsurance record
                existing = PatientInsurance.objects.filter(
                    patient=patient,
                    is_deleted=False
                ).exists()
                
                if existing:
                    skipped_count += 1
                    continue
                
                # Try to find insurance company by name
                insurance_company = None
                if patient.insurance_company:
                    insurance_company = InsuranceCompany.objects.filter(
                        name__icontains=patient.insurance_company,
                        is_deleted=False
                    ).first()
                
                if not insurance_company and patient.primary_insurance:
                    # Use the primary_insurance (Payer) if available
                    # Try to find matching InsuranceCompany by payer name
                    insurance_company = InsuranceCompany.objects.filter(
                        name__icontains=patient.primary_insurance.name,
                        is_deleted=False
                    ).first()
                
                if not insurance_company:
                    # Create a generic "Unknown Insurance" company
                    insurance_company, _ = InsuranceCompany.objects.get_or_create(
                        code='UNKNOWN',
                        defaults={
                            'name': 'Unknown Insurance Company',
                            'status': 'active',
                            'is_active': True,
                            'notes': 'Auto-created for legacy patient data migration'
                        }
                    )
                
                if not dry_run:
                    with transaction.atomic():
                        # Check for existing enrollment to prevent duplicates
                        existing_enrollment = PatientInsurance.objects.filter(
                            patient=patient,
                            insurance_company=insurance_company,
                            is_deleted=False
                        ).first()
                        
                        if existing_enrollment:
                            # Update existing enrollment instead of creating duplicate
                            self.stdout.write(f'  [SKIP] Patient {patient.mrn} already has insurance enrollment')
                            skipped_count += 1
                            continue
                        
                        # Create PatientInsurance record
                        enrollment = PatientInsurance.objects.create(
                            patient=patient,
                            insurance_company=insurance_company,
                            policy_number=patient.insurance_policy_number or patient.insurance_id or f'MIGRATED-{patient.mrn}',
                            member_id=patient.insurance_member_id or patient.insurance_id or f'MEM-{patient.mrn}',
                            group_number=patient.insurance_group_number or '',
                            is_primary_subscriber=True,
                            relationship_to_subscriber='self',
                            effective_date=patient.created.date(),
                            status='active',
                            is_primary=True,
                            notes=f'Migrated from old patient.insurance_company field: {patient.insurance_company}'
                        )
                        
                        created_count += 1
                        self.stdout.write(
                            f'  ✓ Migrated: {patient.full_name} -> {insurance_company.name} '
                            f'(Policy: {enrollment.policy_number})'
                        )
                else:
                    created_count += 1
                    self.stdout.write(
                        f'  [DRY RUN] Would migrate: {patient.full_name} -> {insurance_company.name if insurance_company else "Unknown"}'
                    )
                    
            except Exception as e:
                error_count += 1
                self.stdout.write(self.style.ERROR(
                    f'  ✗ Error migrating {patient.full_name}: {str(e)}'
                ))
        
        self.stdout.write(self.style.SUCCESS(
            f'\n\nSummary: {created_count} migrated, {skipped_count} skipped, {error_count} errors'
        ))
        
        if not dry_run and created_count > 0:
            self.stdout.write(self.style.SUCCESS(
                f'\n✓ Successfully migrated {created_count} patient insurance records!'
            ))



















