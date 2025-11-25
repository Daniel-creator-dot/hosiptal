"""
Management command to regenerate all patient QR codes with the new simplified format.
Run this after updating the QR code system to ensure all existing cards work.
"""
from django.core.management.base import BaseCommand
from hospital.models import Patient, PatientQRCode
from django.db import transaction


class Command(BaseCommand):
    help = 'Regenerate all patient QR codes with simplified format (just patient UUID)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force regeneration even if QR code already exists',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=None,
            help='Limit the number of patients to process (for testing)',
        )

    def handle(self, *args, **options):
        force = options['force']
        limit = options['limit']
        
        self.stdout.write(self.style.SUCCESS('Starting QR code regeneration...'))
        
        # Get all patients
        patients = Patient.objects.filter(is_deleted=False)
        if limit:
            patients = patients[:limit]
        
        total = patients.count()
        self.stdout.write(f'Found {total} patients to process')
        
        updated = 0
        created = 0
        errors = 0
        
        with transaction.atomic():
            for i, patient in enumerate(patients, 1):
                try:
                    qr_profile, created_new = PatientQRCode.objects.get_or_create(
                        patient=patient
                    )
                    
                    # Regenerate if forced or if QR data is missing/old format
                    should_regenerate = (
                        force or 
                        not qr_profile.qr_code_data or
                        '|' in qr_profile.qr_code_data  # Old format
                    )
                    
                    if should_regenerate:
                        qr_profile.refresh_qr(force_token=True, save=True)
                        if created_new:
                            created += 1
                        else:
                            updated += 1
                        
                        if i % 100 == 0:
                            self.stdout.write(f'Processed {i}/{total} patients...')
                    else:
                        self.stdout.write(
                            f'Skipping {patient.mrn} - QR code already in new format'
                        )
                        
                except Exception as e:
                    errors += 1
                    self.stdout.write(
                        self.style.ERROR(f'Error processing {patient.mrn}: {str(e)}')
                    )
        
        self.stdout.write(self.style.SUCCESS('\n' + '='*50))
        self.stdout.write(self.style.SUCCESS(f'QR Code Regeneration Complete!'))
        self.stdout.write(self.style.SUCCESS(f'Total patients: {total}'))
        self.stdout.write(self.style.SUCCESS(f'Created: {created}'))
        self.stdout.write(self.style.SUCCESS(f'Updated: {updated}'))
        self.stdout.write(self.style.SUCCESS(f'Errors: {errors}'))
        self.stdout.write(self.style.SUCCESS('='*50))
        self.stdout.write(
            self.style.WARNING(
                '\nNote: Patients will need to reprint their cards for the new QR codes to work.'
            )
        )







