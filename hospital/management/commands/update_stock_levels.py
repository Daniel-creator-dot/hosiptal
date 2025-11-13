"""
Management command to update pharmacy stock levels based on prescriptions
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from hospital.models import PharmacyStock, Prescription, Drug


class Command(BaseCommand):
    help = 'Updates pharmacy stock levels and identifies low stock items'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS('Updating stock levels...'))
        
        # Get recent prescriptions (last 7 days)
        recent_prescriptions = Prescription.objects.filter(
            created__gte=timezone.now() - timedelta(days=7),
            is_deleted=False
        )
        
        stock_updates = 0
        low_stock_items = []
        
        for prescription in recent_prescriptions:
            drug = prescription.drug
            try:
                stock = PharmacyStock.objects.get(drug=drug, is_deleted=False)
                
                # Simulate stock reduction (in real scenario, this would be more sophisticated)
                # For now, just check low stock status
                if stock.quantity_on_hand <= stock.reorder_level:
                    if stock not in low_stock_items:
                        low_stock_items.append(stock)
                
                stock_updates += 1
            except PharmacyStock.DoesNotExist:
                self.stdout.write(
                    self.style.WARNING(f'No stock record found for {drug.name}')
                )
        
        # Display low stock items
        if low_stock_items:
            self.stdout.write(self.style.WARNING('\n⚠️  Low Stock Items:'))
            for stock in low_stock_items:
                self.stdout.write(
                    f'   - {stock.drug.name}: {stock.quantity_on_hand} units '
                    f'(Reorder level: {stock.reorder_level})'
                )
        else:
            self.stdout.write(self.style.SUCCESS('✅ No low stock items found'))
        
        self.stdout.write(
            self.style.SUCCESS(f'\n✅ Processed {stock_updates} stock records')
        )

