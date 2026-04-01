"""
Management command to fix all patients with invalid payer data
"""
from django.core.management.base import BaseCommand
from hospital.models import Patient, Payer


class Command(BaseCommand):
    help = 'Fix all patients with invalid payer types'

    def handle(self, *args, **options):
        # Get or create Cash payer
        cash_payer, _ = Payer.objects.get_or_create(
            name='Cash',
            defaults={'payer_type': 'cash', 'is_active': True}
        )
        
        # Find all patients
        patients = Patient.objects.filter(is_deleted=False)
        
        self.stdout.write(f'Checking {patients.count()} patients...\n')
        
        fixed_count = 0
        invalid_count = 0
        
        for patient in patients:
            payer = patient.primary_insurance
            
            # If no payer, set to cash
            if not payer:
                patient.primary_insurance = cash_payer
                patient.save(update_fields=['primary_insurance'])
                fixed_count += 1
                continue
            
            # Check if payer has valid payer_type
            payer_type = getattr(payer, 'payer_type', None)
            payer_name = getattr(payer, 'name', 'Unknown')
            
            valid_types = ['cash', 'insurance', 'private', 'nhis', 'corporate']
            
            # Check if invalid
            if not payer_type or payer_type.strip() == '' or payer_type not in valid_types:
                invalid_count += 1
                self.stdout.write(
                    self.style.WARNING(
                        f'Fixing {patient.mrn}: Invalid payer "{payer_name}" '
                        f'(type: "{payer_type}")'
                    )
                )
                
                # Fix it
                patient.primary_insurance = cash_payer
                patient.save(update_fields=['primary_insurance'])
                fixed_count += 1
        
        self.stdout.write(self.style.SUCCESS(
            f'\n✅ Fixed {fixed_count} patients ({invalid_count} had invalid payers)'
        ))
