"""
Management command to add common UK generic drugs to pharmacy inventory
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from hospital.models import Drug, PharmacyStock


class Command(BaseCommand):
    help = 'Add common UK generic drugs to pharmacy formulary and stock'

    def handle(self, *args, **options):
        self.stdout.write('Adding UK generic drugs to pharmacy...')
        
        # Comprehensive list of common UK generic drugs
        uk_drugs = [
            # Analgesics & Anti-inflammatories
            {'name': 'Paracetamol', 'generic_name': 'Paracetamol', 'strength': '500mg', 'form': 'Tablet', 'pack_size': '100', 'unit_price': Decimal('0.50'), 'cost_price': Decimal('0.30')},
            {'name': 'Ibuprofen', 'generic_name': 'Ibuprofen', 'strength': '400mg', 'form': 'Tablet', 'pack_size': '84', 'unit_price': Decimal('0.80'), 'cost_price': Decimal('0.50')},
            {'name': 'Aspirin', 'generic_name': 'Acetylsalicylic Acid', 'strength': '75mg', 'form': 'Tablet', 'pack_size': '28', 'unit_price': Decimal('0.60'), 'cost_price': Decimal('0.35')},
            {'name': 'Naproxen', 'generic_name': 'Naproxen', 'strength': '250mg', 'form': 'Tablet', 'pack_size': '28', 'unit_price': Decimal('1.20'), 'cost_price': Decimal('0.80')},
            {'name': 'Diclofenac', 'generic_name': 'Diclofenac Sodium', 'strength': '50mg', 'form': 'Tablet', 'pack_size': '84', 'unit_price': Decimal('1.50'), 'cost_price': Decimal('1.00')},
            {'name': 'Codeine Phosphate', 'generic_name': 'Codeine Phosphate', 'strength': '30mg', 'form': 'Tablet', 'pack_size': '28', 'unit_price': Decimal('2.00'), 'cost_price': Decimal('1.30'), 'is_controlled': True},
            
            # Antibiotics
            {'name': 'Amoxicillin', 'generic_name': 'Amoxicillin', 'strength': '500mg', 'form': 'Capsule', 'pack_size': '21', 'unit_price': Decimal('1.50'), 'cost_price': Decimal('1.00')},
            {'name': 'Co-Amoxiclav', 'generic_name': 'Amoxicillin/Clavulanic Acid', 'strength': '500/125mg', 'form': 'Tablet', 'pack_size': '21', 'unit_price': Decimal('2.50'), 'cost_price': Decimal('1.80')},
            {'name': 'Flucloxacillin', 'generic_name': 'Flucloxacillin', 'strength': '500mg', 'form': 'Capsule', 'pack_size': '28', 'unit_price': Decimal('2.00'), 'cost_price': Decimal('1.40')},
            {'name': 'Clarithromycin', 'generic_name': 'Clarithromycin', 'strength': '500mg', 'form': 'Tablet', 'pack_size': '14', 'unit_price': Decimal('3.00'), 'cost_price': Decimal('2.20')},
            {'name': 'Doxycycline', 'generic_name': 'Doxycycline', 'strength': '100mg', 'form': 'Capsule', 'pack_size': '8', 'unit_price': Decimal('2.50'), 'cost_price': Decimal('1.80')},
            {'name': 'Metronidazole', 'generic_name': 'Metronidazole', 'strength': '400mg', 'form': 'Tablet', 'pack_size': '21', 'unit_price': Decimal('1.80'), 'cost_price': Decimal('1.20')},
            {'name': 'Ciprofloxacin', 'generic_name': 'Ciprofloxacin', 'strength': '500mg', 'form': 'Tablet', 'pack_size': '10', 'unit_price': Decimal('2.80'), 'cost_price': Decimal('2.00')},
            {'name': 'Trimethoprim', 'generic_name': 'Trimethoprim', 'strength': '200mg', 'form': 'Tablet', 'pack_size': '6', 'unit_price': Decimal('1.50'), 'cost_price': Decimal('1.00')},
            {'name': 'Azithromycin', 'generic_name': 'Azithromycin', 'strength': '250mg', 'form': 'Capsule', 'pack_size': '6', 'unit_price': Decimal('3.50'), 'cost_price': Decimal('2.50')},
            
            # Cardiovascular
            {'name': 'Amlodipine', 'generic_name': 'Amlodipine', 'strength': '5mg', 'form': 'Tablet', 'pack_size': '28', 'unit_price': Decimal('1.20'), 'cost_price': Decimal('0.80')},
            {'name': 'Ramipril', 'generic_name': 'Ramipril', 'strength': '5mg', 'form': 'Capsule', 'pack_size': '28', 'unit_price': Decimal('1.50'), 'cost_price': Decimal('1.00')},
            {'name': 'Bisoprolol', 'generic_name': 'Bisoprolol', 'strength': '5mg', 'form': 'Tablet', 'pack_size': '28', 'unit_price': Decimal('1.80'), 'cost_price': Decimal('1.20')},
            {'name': 'Atorvastatin', 'generic_name': 'Atorvastatin', 'strength': '20mg', 'form': 'Tablet', 'pack_size': '28', 'unit_price': Decimal('1.50'), 'cost_price': Decimal('1.00')},
            {'name': 'Simvastatin', 'generic_name': 'Simvastatin', 'strength': '40mg', 'form': 'Tablet', 'pack_size': '28', 'unit_price': Decimal('1.30'), 'cost_price': Decimal('0.90')},
            {'name': 'Clopidogrel', 'generic_name': 'Clopidogrel', 'strength': '75mg', 'form': 'Tablet', 'pack_size': '30', 'unit_price': Decimal('2.00'), 'cost_price': Decimal('1.40')},
            {'name': 'Furosemide', 'generic_name': 'Furosemide', 'strength': '40mg', 'form': 'Tablet', 'pack_size': '28', 'unit_price': Decimal('0.80'), 'cost_price': Decimal('0.50')},
            {'name': 'Bendroflumethiazide', 'generic_name': 'Bendroflumethiazide', 'strength': '2.5mg', 'form': 'Tablet', 'pack_size': '28', 'unit_price': Decimal('0.70'), 'cost_price': Decimal('0.45')},
            {'name': 'Lisinopril', 'generic_name': 'Lisinopril', 'strength': '10mg', 'form': 'Tablet', 'pack_size': '28', 'unit_price': Decimal('1.20'), 'cost_price': Decimal('0.80')},
            {'name': 'Losartan', 'generic_name': 'Losartan', 'strength': '50mg', 'form': 'Tablet', 'pack_size': '28', 'unit_price': Decimal('1.50'), 'cost_price': Decimal('1.00')},
            
            # Diabetes
            {'name': 'Metformin', 'generic_name': 'Metformin', 'strength': '500mg', 'form': 'Tablet', 'pack_size': '84', 'unit_price': Decimal('0.80'), 'cost_price': Decimal('0.50')},
            {'name': 'Gliclazide', 'generic_name': 'Gliclazide', 'strength': '80mg', 'form': 'Tablet', 'pack_size': '60', 'unit_price': Decimal('1.50'), 'cost_price': Decimal('1.00')},
            {'name': 'Insulin Aspart', 'generic_name': 'Insulin Aspart', 'strength': '100 units/ml', 'form': 'Injection', 'pack_size': '5x3ml', 'unit_price': Decimal('25.00'), 'cost_price': Decimal('18.00')},
            {'name': 'Insulin Glargine', 'generic_name': 'Insulin Glargine', 'strength': '100 units/ml', 'form': 'Injection', 'pack_size': '5x3ml', 'unit_price': Decimal('28.00'), 'cost_price': Decimal('20.00')},
            {'name': 'Sitagliptin', 'generic_name': 'Sitagliptin', 'strength': '100mg', 'form': 'Tablet', 'pack_size': '28', 'unit_price': Decimal('3.50'), 'cost_price': Decimal('2.50')},
            
            # Respiratory
            {'name': 'Salbutamol Inhaler', 'generic_name': 'Salbutamol', 'strength': '100mcg', 'form': 'Inhaler', 'pack_size': '200 doses', 'unit_price': Decimal('4.50'), 'cost_price': Decimal('3.00')},
            {'name': 'Beclometasone Inhaler', 'generic_name': 'Beclometasone', 'strength': '100mcg', 'form': 'Inhaler', 'pack_size': '200 doses', 'unit_price': Decimal('5.50'), 'cost_price': Decimal('4.00')},
            {'name': 'Prednisolone', 'generic_name': 'Prednisolone', 'strength': '5mg', 'form': 'Tablet', 'pack_size': '28', 'unit_price': Decimal('1.20'), 'cost_price': Decimal('0.80')},
            {'name': 'Montelukast', 'generic_name': 'Montelukast', 'strength': '10mg', 'form': 'Tablet', 'pack_size': '28', 'unit_price': Decimal('2.50'), 'cost_price': Decimal('1.80')},
            {'name': 'Cetirizine', 'generic_name': 'Cetirizine', 'strength': '10mg', 'form': 'Tablet', 'pack_size': '30', 'unit_price': Decimal('0.80'), 'cost_price': Decimal('0.50')},
            
            # Gastrointestinal
            {'name': 'Omeprazole', 'generic_name': 'Omeprazole', 'strength': '20mg', 'form': 'Capsule', 'pack_size': '28', 'unit_price': Decimal('1.20'), 'cost_price': Decimal('0.80')},
            {'name': 'Lansoprazole', 'generic_name': 'Lansoprazole', 'strength': '30mg', 'form': 'Capsule', 'pack_size': '28', 'unit_price': Decimal('1.50'), 'cost_price': Decimal('1.00')},
            {'name': 'Ranitidine', 'generic_name': 'Ranitidine', 'strength': '150mg', 'form': 'Tablet', 'pack_size': '60', 'unit_price': Decimal('1.00'), 'cost_price': Decimal('0.65')},
            {'name': 'Loperamide', 'generic_name': 'Loperamide', 'strength': '2mg', 'form': 'Capsule', 'pack_size': '30', 'unit_price': Decimal('1.50'), 'cost_price': Decimal('1.00')},
            {'name': 'Senna', 'generic_name': 'Sennosides', 'strength': '7.5mg', 'form': 'Tablet', 'pack_size': '60', 'unit_price': Decimal('0.80'), 'cost_price': Decimal('0.50')},
            {'name': 'Lactulose', 'generic_name': 'Lactulose', 'strength': '3.3g/5ml', 'form': 'Solution', 'pack_size': '300ml', 'unit_price': Decimal('2.50'), 'cost_price': Decimal('1.80')},
            
            # Mental Health
            {'name': 'Sertraline', 'generic_name': 'Sertraline', 'strength': '50mg', 'form': 'Tablet', 'pack_size': '28', 'unit_price': Decimal('1.80'), 'cost_price': Decimal('1.20')},
            {'name': 'Citalopram', 'generic_name': 'Citalopram', 'strength': '20mg', 'form': 'Tablet', 'pack_size': '28', 'unit_price': Decimal('1.50'), 'cost_price': Decimal('1.00')},
            {'name': 'Fluoxetine', 'generic_name': 'Fluoxetine', 'strength': '20mg', 'form': 'Capsule', 'pack_size': '30', 'unit_price': Decimal('1.60'), 'cost_price': Decimal('1.10')},
            {'name': 'Amitriptyline', 'generic_name': 'Amitriptyline', 'strength': '25mg', 'form': 'Tablet', 'pack_size': '28', 'unit_price': Decimal('1.20'), 'cost_price': Decimal('0.80')},
            {'name': 'Diazepam', 'generic_name': 'Diazepam', 'strength': '5mg', 'form': 'Tablet', 'pack_size': '28', 'unit_price': Decimal('1.50'), 'cost_price': Decimal('1.00'), 'is_controlled': True},
            {'name': 'Zopiclone', 'generic_name': 'Zopiclone', 'strength': '7.5mg', 'form': 'Tablet', 'pack_size': '28', 'unit_price': Decimal('1.80'), 'cost_price': Decimal('1.20'), 'is_controlled': True},
            
            # Vitamins & Supplements
            {'name': 'Vitamin D', 'generic_name': 'Cholecalciferol', 'strength': '800 IU', 'form': 'Capsule', 'pack_size': '30', 'unit_price': Decimal('1.20'), 'cost_price': Decimal('0.80')},
            {'name': 'Vitamin B12', 'generic_name': 'Cyanocobalamin', 'strength': '50mcg', 'form': 'Tablet', 'pack_size': '50', 'unit_price': Decimal('1.00'), 'cost_price': Decimal('0.65')},
            {'name': 'Folic Acid', 'generic_name': 'Folic Acid', 'strength': '5mg', 'form': 'Tablet', 'pack_size': '28', 'unit_price': Decimal('0.70'), 'cost_price': Decimal('0.45')},
            {'name': 'Ferrous Sulfate', 'generic_name': 'Ferrous Sulfate', 'strength': '200mg', 'form': 'Tablet', 'pack_size': '60', 'unit_price': Decimal('0.80'), 'cost_price': Decimal('0.50')},
            {'name': 'Calcium Carbonate', 'generic_name': 'Calcium Carbonate', 'strength': '600mg', 'form': 'Tablet', 'pack_size': '60', 'unit_price': Decimal('1.00'), 'cost_price': Decimal('0.65')},
            
            # Topical & Others
            {'name': 'Hydrocortisone Cream', 'generic_name': 'Hydrocortisone', 'strength': '1%', 'form': 'Cream', 'pack_size': '30g', 'unit_price': Decimal('2.50'), 'cost_price': Decimal('1.80')},
            {'name': 'Betamethasone Cream', 'generic_name': 'Betamethasone', 'strength': '0.1%', 'form': 'Cream', 'pack_size': '30g', 'unit_price': Decimal('3.00'), 'cost_price': Decimal('2.20')},
            {'name': 'Chloramphenicol Eye Drops', 'generic_name': 'Chloramphenicol', 'strength': '0.5%', 'form': 'Eye Drops', 'pack_size': '10ml', 'unit_price': Decimal('3.50'), 'cost_price': Decimal('2.50')},
            {'name': 'Levothyroxine', 'generic_name': 'Levothyroxine Sodium', 'strength': '100mcg', 'form': 'Tablet', 'pack_size': '28', 'unit_price': Decimal('1.20'), 'cost_price': Decimal('0.80')},
            {'name': 'Warfarin', 'generic_name': 'Warfarin Sodium', 'strength': '5mg', 'form': 'Tablet', 'pack_size': '28', 'unit_price': Decimal('1.50'), 'cost_price': Decimal('1.00')},
            {'name': 'GTN Spray', 'generic_name': 'Glyceryl Trinitrate', 'strength': '400mcg/dose', 'form': 'Sublingual Spray', 'pack_size': '180 doses', 'unit_price': Decimal('5.50'), 'cost_price': Decimal('4.00')},
            
            # Antivirals
            {'name': 'Aciclovir', 'generic_name': 'Aciclovir', 'strength': '400mg', 'form': 'Tablet', 'pack_size': '35', 'unit_price': Decimal('2.50'), 'cost_price': Decimal('1.80')},
            {'name': 'Oseltamivir', 'generic_name': 'Oseltamivir', 'strength': '75mg', 'form': 'Capsule', 'pack_size': '10', 'unit_price': Decimal('4.50'), 'cost_price': Decimal('3.30')},
            
            # Antimalarials
            {'name': 'Artemether/Lumefantrine', 'generic_name': 'Artemether/Lumefantrine', 'strength': '20/120mg', 'form': 'Tablet', 'pack_size': '24', 'unit_price': Decimal('3.50'), 'cost_price': Decimal('2.50')},
            {'name': 'Quinine Sulfate', 'generic_name': 'Quinine Sulfate', 'strength': '300mg', 'form': 'Tablet', 'pack_size': '28', 'unit_price': Decimal('2.00'), 'cost_price': Decimal('1.40')},
        ]
        
        created_count = 0
        updated_count = 0
        stock_created = 0
        
        for drug_data in uk_drugs:
            # Create or update drug
            drug, created = Drug.objects.update_or_create(
                name=drug_data['name'],
                strength=drug_data['strength'],
                form=drug_data['form'],
                defaults={
                    'generic_name': drug_data['generic_name'],
                    'pack_size': drug_data['pack_size'],
                    'unit_price': drug_data['unit_price'],
                    'cost_price': drug_data['cost_price'],
                    'is_controlled': drug_data.get('is_controlled', False),
                    'is_active': True,
                    'is_deleted': False,
                }
            )
            
            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f'✅ Created: {drug.name} {drug.strength}'))
                
                # Create initial stock
                expiry_date = timezone.now().date() + timedelta(days=730)  # 2 years
                PharmacyStock.objects.create(
                    drug=drug,
                    batch_number=f'UK-{drug.id}-{timezone.now().strftime("%Y%m")}',
                    expiry_date=expiry_date,
                    quantity_on_hand=100,  # Initial stock
                    reorder_level=20,
                    unit_cost=drug.cost_price,
                    location='Main Pharmacy'
                )
                stock_created += 1
            else:
                updated_count += 1
                self.stdout.write(f'📝 Updated: {drug.name} {drug.strength}')
        
        self.stdout.write(self.style.SUCCESS(
            f'\n✅ Complete! Created {created_count} drugs, Updated {updated_count} drugs, '
            f'Created {stock_created} stock entries'
        ))
        self.stdout.write(self.style.SUCCESS(f'Total UK generic drugs in system: {Drug.objects.filter(is_active=True).count()}'))






















