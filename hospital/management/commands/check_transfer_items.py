"""
Management command to check if transferred items are visible in inventory
"""
from django.core.management.base import BaseCommand
from hospital.models_procurement import StoreTransfer, InventoryItem, Store


class Command(BaseCommand):
    help = 'Check if transferred items are visible in the destination store'

    def handle(self, *args, **options):
        # Get the most recent completed transfer
        transfer = StoreTransfer.objects.filter(
            status='completed',
            is_deleted=False
        ).order_by('-created').first()
        
        if not transfer:
            self.stdout.write(self.style.WARNING('No completed transfers found'))
            return
        
        self.stdout.write(self.style.SUCCESS(f'\nTransfer: {transfer.transfer_number}'))
        self.stdout.write(f'From: {transfer.from_store.name} (Code: {transfer.from_store.code})')
        self.stdout.write(f'To: {transfer.to_store.name} (Code: {transfer.to_store.code})')
        self.stdout.write(f'Status: {transfer.status}')
        self.stdout.write(f'Completed: {transfer.received_at}')
        
        # Check transfer lines
        lines = transfer.lines.filter(is_deleted=False)
        self.stdout.write(f'\nTransfer Lines: {lines.count()}')
        
        for line in lines:
            self.stdout.write(f'\n  Item: {line.item_name}')
            self.stdout.write(f'    Code: {line.item_code}')
            self.stdout.write(f'    Quantity: {line.quantity}')
            
            # Check if item exists in destination store
            items = InventoryItem.objects.filter(
                store=transfer.to_store,
                is_deleted=False
            )
            
            # Try to find by item_code
            if line.item_code:
                item = items.filter(item_code=line.item_code).first()
                if item:
                    self.stdout.write(self.style.SUCCESS(f'    ✓ Found by code: {item.item_name}'))
                    self.stdout.write(f'      Quantity: {item.quantity_on_hand}')
                    self.stdout.write(f'      Active: {item.is_active}')
                    continue
            
            # Try to find by item_name
            item = items.filter(item_name__iexact=line.item_name).first()
            if item:
                self.stdout.write(self.style.SUCCESS(f'    ✓ Found by name: {item.item_name}'))
                self.stdout.write(f'      Quantity: {item.quantity_on_hand}')
                self.stdout.write(f'      Active: {item.is_active}')
            else:
                self.stdout.write(self.style.ERROR(f'    ✗ NOT FOUND in {transfer.to_store.name}'))
        
        # Summary
        total_items = InventoryItem.objects.filter(
            store=transfer.to_store,
            is_deleted=False,
            is_active=True
        ).count()
        
        self.stdout.write(self.style.SUCCESS(f'\nTotal active items in {transfer.to_store.name}: {total_items}'))
        
        # Check if this is the dispensing hub
        pharmacy_store = Store.get_pharmacy_store_for_prescriptions()
        if pharmacy_store and transfer.to_store.pk == pharmacy_store.pk:
            self.stdout.write(self.style.SUCCESS(f'\n✓ This is the active dispensing hub store'))
        else:
            self.stdout.write(self.style.WARNING(f'\n⚠ This is NOT the active dispensing hub'))
            if pharmacy_store:
                self.stdout.write(f'  Active hub: {pharmacy_store.name} (Code: {pharmacy_store.code})')
