"""
Management command to generate item codes for existing InventoryItem records that don't have codes
"""
from django.core.management.base import BaseCommand
from django.db import models
from hospital.models_procurement import InventoryItem


class Command(BaseCommand):
    help = 'Generate item codes for existing InventoryItem records that are missing codes'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without actually generating codes',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))
        
        # Find all items without codes or with empty codes
        from django.db.models import Q
        items_without_codes = InventoryItem.objects.filter(
            is_deleted=False
        ).filter(
            Q(item_code__isnull=True) | Q(item_code='') | Q(item_code__startswith='DRUG-')
        )
        
        total_count = items_without_codes.count()
        
        if total_count == 0:
            self.stdout.write(self.style.SUCCESS('All inventory items already have proper item codes!'))
            return
        
        self.stdout.write(f'Found {total_count} items without proper item codes')
        
        updated_count = 0
        error_count = 0
        
        for item in items_without_codes:
            try:
                old_code = item.item_code or '(empty)'
                
                if dry_run:
                    # Generate code but don't save
                    code = item.generate_item_code()
                    self.stdout.write(f'  Would generate: {item.item_name} -> {code} (Current: {old_code})')
                else:
                    # Clear code and save to trigger generation
                    item.item_code = ''
                    item.save()
                    new_code = item.item_code
                    self.stdout.write(f'  Generated: {item.item_name} -> {new_code} (was: {old_code})')
                    updated_count += 1
                    
            except Exception as e:
                error_count += 1
                self.stdout.write(
                    self.style.ERROR(f'  Error generating code for {item.item_name}: {str(e)}')
                )
        
        if dry_run:
            self.stdout.write(self.style.WARNING(
                f'\nDry run completed. Would update {total_count} items.'
                f'\nRun without --dry-run to apply changes.'
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'\nCode generation completed!'
                f'\n  Total items processed: {total_count}'
                f'\n  Successfully updated: {updated_count}'
                f'\n  Errors: {error_count}'
            ))

