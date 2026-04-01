"""
Management command to fix ACACIA payer and ensure it appears in dropdowns
"""
from django.core.management.base import BaseCommand
from hospital.models import Payer
from hospital.models_insurance_companies import InsuranceCompany


class Command(BaseCommand):
    help = 'Fix ACACIA payer to ensure it appears in insurance company dropdowns'

    def handle(self, *args, **options):
        self.stdout.write('\nFixing ACACIA Payer...\n')
        
        # Find ACACIA InsuranceCompany
        acacia_ic = InsuranceCompany.objects.filter(name__icontains='acacia').first()
        if not acacia_ic:
            self.stdout.write(self.style.ERROR('ERROR: ACACIA InsuranceCompany not found!'))
            return
        
        self.stdout.write(f'Found InsuranceCompany: {acacia_ic.name}')
        
        # Check if Payer exists
        acacia_payer = Payer.objects.filter(name__icontains='acacia').first()
        if acacia_payer:
            self.stdout.write(f'Payer exists: {acacia_payer.name}')
            self.stdout.write(f'   Current Type: {acacia_payer.payer_type}')
            self.stdout.write(f'   Active: {acacia_payer.is_active}')
            
            # Update to 'insurance' type if it's 'private' or 'nhis'
            if acacia_payer.payer_type in ['private', 'nhis']:
                acacia_payer.payer_type = 'insurance'
                acacia_payer.is_active = True
                acacia_payer.save()
                self.stdout.write(self.style.SUCCESS(f'   Updated to type: insurance'))
            else:
                self.stdout.write(self.style.SUCCESS(f'   Already correct type'))
        else:
            self.stdout.write('Creating Payer...')
            payer = Payer.objects.create(
                name=acacia_ic.name,
                payer_type='insurance',
                is_active=True
            )
            self.stdout.write(self.style.SUCCESS(f'Created Payer: {payer.name}, Type: {payer.payer_type}'))

        # Verify it shows in the dropdown
        payers = Payer.objects.filter(
            payer_type__in=['insurance', 'corporate', 'nhis', 'private'],
            is_active=True,
            is_deleted=False
        ).order_by('name')
        
        self.stdout.write(f'\nTotal payers in dropdown: {payers.count()}')
        acacia_in_list = payers.filter(name__icontains='acacia')
        if acacia_in_list.exists():
            self.stdout.write(self.style.SUCCESS('SUCCESS: ACACIA will appear in dropdown!'))
        else:
            self.stdout.write(self.style.ERROR('ERROR: ACACIA still not in dropdown list'))
        
        self.stdout.write('\nDone!\n')

