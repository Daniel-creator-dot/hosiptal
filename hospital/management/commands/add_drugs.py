"""
Management command to add common drugs to the formulary
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from hospital.models import Drug, PharmacyStock


class Command(BaseCommand):
    help = 'Add common drugs to the formulary with prices'

    def handle(self, *args, **options):
        self.stdout.write('Adding drugs to formulary...')
        
        # List of common drugs with their details
        drugs_data = [
            {
                'name': 'Paracetamol',
                'generic_name': 'Acetaminophen',
                'strength': '500mg',
                'form': 'tablet',
                'pack_size': '20 tablets',
                'price': 20.00,
                'is_controlled': False,
            },
            {
                'name': 'Ibuprofen',
                'generic_name': 'Ibuprofen',
                'strength': '400mg',
                'form': 'tablet',
                'pack_size': '20 tablets',
                'price': 15.00,
                'is_controlled': False,
            },
            {
                'name': 'Amoxicillin',
                'generic_name': 'Amoxicillin',
                'strength': '500mg',
                'form': 'capsule',
                'pack_size': '21 capsules',
                'price': 25.00,
                'is_controlled': False,
            },
            {
                'name': 'Metronidazole',
                'generic_name': 'Metronidazole',
                'strength': '400mg',
                'form': 'tablet',
                'pack_size': '14 tablets',
                'price': 18.00,
                'is_controlled': False,
            },
            {
                'name': 'Ciprofloxacin',
                'generic_name': 'Ciprofloxacin',
                'strength': '500mg',
                'form': 'tablet',
                'pack_size': '10 tablets',
                'price': 30.00,
                'is_controlled': False,
            },
            {
                'name': 'Azithromycin',
                'generic_name': 'Azithromycin',
                'strength': '500mg',
                'form': 'tablet',
                'pack_size': '6 tablets',
                'price': 45.00,
                'is_controlled': False,
            },
            {
                'name': 'Cetirizine',
                'generic_name': 'Cetirizine',
                'strength': '10mg',
                'form': 'tablet',
                'pack_size': '10 tablets',
                'price': 12.00,
                'is_controlled': False,
            },
            {
                'name': 'Loratadine',
                'generic_name': 'Loratadine',
                'strength': '10mg',
                'form': 'tablet',
                'pack_size': '10 tablets',
                'price': 14.00,
                'is_controlled': False,
            },
            {
                'name': 'Omeprazole',
                'generic_name': 'Omeprazole',
                'strength': '20mg',
                'form': 'capsule',
                'pack_size': '14 capsules',
                'price': 22.00,
                'is_controlled': False,
            },
            {
                'name': 'Salbutamol',
                'generic_name': 'Salbutamol',
                'strength': '100mcg',
                'form': 'inhaler',
                'pack_size': '1 inhaler',
                'price': 35.00,
                'is_controlled': False,
            },
            {
                'name': 'Prednisolone',
                'generic_name': 'Prednisolone',
                'strength': '5mg',
                'form': 'tablet',
                'pack_size': '30 tablets',
                'price': 28.00,
                'is_controlled': False,
            },
            {
                'name': 'Furosemide',
                'generic_name': 'Furosemide',
                'strength': '40mg',
                'form': 'tablet',
                'pack_size': '30 tablets',
                'price': 16.00,
                'is_controlled': False,
            },
            {
                'name': 'Amlodipine',
                'generic_name': 'Amlodipine',
                'strength': '5mg',
                'form': 'tablet',
                'pack_size': '30 tablets',
                'price': 24.00,
                'is_controlled': False,
            },
            {
                'name': 'Atorvastatin',
                'generic_name': 'Atorvastatin',
                'strength': '20mg',
                'form': 'tablet',
                'pack_size': '30 tablets',
                'price': 50.00,
                'is_controlled': False,
            },
            {
                'name': 'Metformin',
                'generic_name': 'Metformin',
                'strength': '500mg',
                'form': 'tablet',
                'pack_size': '30 tablets',
                'price': 20.00,
                'is_controlled': False,
            },
            {
                'name': 'Glibenclamide',
                'generic_name': 'Glibenclamide',
                'strength': '5mg',
                'form': 'tablet',
                'pack_size': '30 tablets',
                'price': 18.00,
                'is_controlled': False,
            },
            {
                'name': 'Artemether-Lumefantrine',
                'generic_name': 'Artemether-Lumefantrine',
                'strength': '20/120mg',
                'form': 'tablet',
                'pack_size': '24 tablets',
                'price': 40.00,
                'is_controlled': False,
            },
            {
                'name': 'Co-trimoxazole',
                'generic_name': 'Trimethoprim-Sulfamethoxazole',
                'strength': '160/800mg',
                'form': 'tablet',
                'pack_size': '20 tablets',
                'price': 22.00,
                'is_controlled': False,
            },
            {
                'name': 'Doxycycline',
                'generic_name': 'Doxycycline',
                'strength': '100mg',
                'form': 'capsule',
                'pack_size': '10 capsules',
                'price': 32.00,
                'is_controlled': False,
            },
            {
                'name': 'Ferrous Sulfate',
                'generic_name': 'Iron',
                'strength': '200mg',
                'form': 'tablet',
                'pack_size': '30 tablets',
                'price': 15.00,
                'is_controlled': False,
            },
            {
                'name': 'Folic Acid',
                'generic_name': 'Folic Acid',
                'strength': '5mg',
                'form': 'tablet',
                'pack_size': '30 tablets',
                'price': 8.00,
                'is_controlled': False,
            },
            {
                'name': 'Multivitamin',
                'generic_name': 'Multivitamin',
                'strength': 'Compound',
                'form': 'tablet',
                'pack_size': '30 tablets',
                'price': 25.00,
                'is_controlled': False,
            },
            {
                'name': 'Diphenhydramine',
                'generic_name': 'Diphenhydramine',
                'strength': '25mg',
                'form': 'tablet',
                'pack_size': '20 tablets',
                'price': 10.00,
                'is_controlled': False,
            },
        ]
        
        created_count = 0
        updated_count = 0
        
        for drug_data in drugs_data:
            price = drug_data.pop('price')
            drug_name = drug_data['name']
            
            # Check if drug already exists
            drug, created = Drug.objects.get_or_create(
                name=drug_name,
                strength=drug_data['strength'],
                form=drug_data['form'],
                defaults=drug_data
            )
            
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'✓ Created: {drug_name} {drug_data["strength"]} {drug_data["form"]}')
                )
            else:
                # Update existing drug
                for key, value in drug_data.items():
                    setattr(drug, key, value)
                drug.save()
                updated_count += 1
                self.stdout.write(
                    self.style.WARNING(f'↻ Updated: {drug_name} {drug_data["strength"]} {drug_data["form"]}')
                )
            
            # Create or update pharmacy stock with price
            expiry_date = timezone.now().date() + timedelta(days=730)  # 2 years from now
            
            stock, stock_created = PharmacyStock.objects.get_or_create(
                drug=drug,
                batch_number=f'BATCH-{drug.name[:3].upper()}-001',
                defaults={
                    'expiry_date': expiry_date,
                    'quantity_on_hand': 100,
                    'reorder_level': 20,
                    'unit_cost': price,
                    'location': 'Main Pharmacy',
                }
            )
            
            if not stock_created:
                # Update price if stock exists
                stock.unit_cost = price
                stock.save()
        
        self.stdout.write('')
        self.stdout.write(
            self.style.SUCCESS(
                f'✓ Successfully processed {len(drugs_data)} drugs\n'
                f'  - Created: {created_count}\n'
                f'  - Updated: {updated_count}'
            )
        )


