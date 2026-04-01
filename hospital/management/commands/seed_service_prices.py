"""
Management command to seed default prices for common services in Ghana
"""
from django.core.management.base import BaseCommand
from hospital.models_pricing import DefaultPrice
from decimal import Decimal


class Command(BaseCommand):
    help = 'Seed default prices for common services used in Ghanaian healthcare facilities'

    def handle(self, *args, **options):
        # Common service prices in Ghana Cedis (GHS)
        # Prices are typical for private healthcare facilities in Ghana
        service_prices = [
            # Registration & Consultation
            {
                'service_code': 'registration',
                'description': 'Patient Registration Fee',
                'default_price': Decimal('10.00'),
                'currency': 'GHS'
            },
            {
                'service_code': 'consultation_general',
                'description': 'General Consultation Fee',
                'default_price': Decimal('50.00'),
                'currency': 'GHS'
            },
            {
                'service_code': 'consultation_specialist',
                'description': 'Specialist Consultation Fee',
                'default_price': Decimal('300.00'),  # Updated to 300 for cash patients
                'currency': 'GHS'
            },
            {
                'service_code': 'vital_signs',
                'description': 'Vital Signs Recording',
                'default_price': Decimal('5.00'),
                'currency': 'GHS'
            },
            
            # Laboratory (prices are typically per test, but this is a base charge)
            {
                'service_code': 'lab_test',
                'description': 'Laboratory Test Processing Fee',
                'default_price': Decimal('10.00'),
                'currency': 'GHS'
            },
            
            # Imaging
            {
                'service_code': 'imaging',
                'description': 'Imaging Study Fee',
                'default_price': Decimal('80.00'),
                'currency': 'GHS'
            },
            
            # Pharmacy
            {
                'service_code': 'pharmacy',
                'description': 'Pharmacy Dispensing Fee',
                'default_price': Decimal('5.00'),
                'currency': 'GHS'
            },
            
            # Admission & Bed Charges
            {
                'service_code': 'admission',
                'description': 'Hospital Admission Fee',
                'default_price': Decimal('50.00'),
                'currency': 'GHS'
            },
            {
                'service_code': 'bed_day',
                'description': 'Daily Bed Charge',
                'default_price': Decimal('30.00'),
                'currency': 'GHS'
            },
        ]
        
        created_count = 0
        updated_count = 0
        
        for price_data in service_prices:
            price_obj, created = DefaultPrice.objects.update_or_create(
                service_code=price_data['service_code'],
                defaults={
                    'description': price_data['description'],
                    'default_price': price_data['default_price'],
                    'currency': price_data['currency'],
                    'is_active': True,
                }
            )
            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f'Created: {price_obj.get_service_code_display()} - GHS {price_obj.default_price}'))
            else:
                updated_count += 1
                self.stdout.write(self.style.WARNING(f'Updated: {price_obj.get_service_code_display()} - GHS {price_obj.default_price}'))
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\nSuccessfully seeded service prices!\n'
                f'Created: {created_count}\n'
                f'Updated: {updated_count}\n'
                f'Total: {len(service_prices)}'
            )
        )





































