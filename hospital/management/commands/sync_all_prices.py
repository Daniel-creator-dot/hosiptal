"""
Comprehensive price synchronization command
Syncs prices between ServiceCode/ServicePrice and LabTest, Drug, Imaging models
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from decimal import Decimal
from hospital.models import ServiceCode, LabTest, Drug
from hospital.models_flexible_pricing import PricingCategory, ServicePrice


class Command(BaseCommand):
    help = 'Sync prices between ServiceCode/ServicePrice and LabTest, Drug, Imaging models'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be synced without actually syncing'
        )
        parser.add_argument(
            '--direction',
            type=str,
            choices=['to_services', 'from_services', 'both'],
            default='both',
            help='Sync direction: to_services (ServicePrice -> LabTest/Drug), from_services (LabTest/Drug -> ServicePrice), or both'
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        direction = options.get('direction', 'both')
        
        self.stdout.write(self.style.SUCCESS('='*80))
        self.stdout.write(self.style.SUCCESS('PRICE SYNCHRONIZATION'))
        self.stdout.write(self.style.SUCCESS('='*80))
        
        if dry_run:
            self.stdout.write(self.style.WARNING('\nDRY RUN MODE - No changes will be made\n'))
        
        stats = {
            'lab_tests_synced': 0,
            'drugs_synced': 0,
            'service_codes_created': 0,
            'prices_created': 0,
            'prices_updated': 0,
        }
        
        # Get cash pricing category (primary reference)
        cash_category = PricingCategory.objects.filter(code='CASH', is_active=True).first()
        if not cash_category:
            self.stdout.write(self.style.ERROR('Cash pricing category not found!'))
            return
        
        # Sync Lab Tests
        if direction in ['to_services', 'both']:
            self.stdout.write('\n' + '-'*80)
            self.stdout.write('SYNCING LAB TESTS (ServicePrice -> LabTest.price)')
            self.stdout.write('-'*80)
            stats.update(self.sync_lab_tests(cash_category, dry_run))
        
        # Sync Drugs (ServicePrice -> Drug). Skip when direction is 'both' so pharmacy-set
        # Drug.unit_price is not overwritten; only push Drug -> ServicePrice in that case.
        if direction == 'to_services':
            self.stdout.write('\n' + '-'*80)
            self.stdout.write('SYNCING DRUGS (ServicePrice -> Drug.unit_price)')
            self.stdout.write('-'*80)
            stats.update(self.sync_drugs(cash_category, dry_run))
        elif direction == 'both':
            self.stdout.write('\n' + '-'*80)
            self.stdout.write('SKIPPING Drug.unit_price overwrite (direction=both keeps pharmacy as source of truth)')
            self.stdout.write('-'*80)
        
        # Sync from LabTest/Drug back to ServicePrice
        if direction in ['from_services', 'both']:
            self.stdout.write('\n' + '-'*80)
            self.stdout.write('SYNCING FROM SERVICES (LabTest/Drug -> ServicePrice)')
            self.stdout.write('-'*80)
            stats.update(self.sync_from_services(cash_category, dry_run))
        
        # Summary
        self.stdout.write('\n' + '='*80)
        self.stdout.write(self.style.SUCCESS('SYNCHRONIZATION SUMMARY'))
        self.stdout.write('='*80)
        self.stdout.write(f"Lab tests synced: {stats['lab_tests_synced']}")
        self.stdout.write(f"Drugs synced: {stats['drugs_synced']}")
        self.stdout.write(f"Service codes created: {stats['service_codes_created']}")
        self.stdout.write(f"Prices created: {stats['prices_created']}")
        self.stdout.write(f"Prices updated: {stats['prices_updated']}")
        
        if dry_run:
            self.stdout.write(self.style.WARNING('\nDRY RUN - No changes were made'))
        else:
            self.stdout.write(self.style.SUCCESS('\nSynchronization completed!'))

    def sync_lab_tests(self, cash_category, dry_run):
        """Sync ServicePrice prices to LabTest.price"""
        stats = {'lab_tests_synced': 0}
        
        # Get all lab-related ServiceCodes
        lab_service_codes = ServiceCode.objects.filter(
            category__icontains='Laboratory',
            is_active=True,
            is_deleted=False
        )
        
        self.stdout.write(f'Found {lab_service_codes.count()} lab ServiceCode entries')
        
        for service_code in lab_service_codes:
            # Get cash price from ServicePrice
            service_price = ServicePrice.objects.filter(
                service_code=service_code,
                pricing_category=cash_category,
                is_active=True,
                is_deleted=False
            ).first()
            
            if not service_price:
                continue
            
            # Try to find matching LabTest by code or name
            # Remove LAB- prefix if present
            test_code = service_code.code.replace('LAB-', '').strip()
            lab_test = LabTest.objects.filter(
                code=test_code
            ).first()
            
            if not lab_test:
                # Try by original code
                lab_test = LabTest.objects.filter(
                    code=service_code.code
                ).first()
            
            if not lab_test:
                # Try by name (exact)
                lab_test = LabTest.objects.filter(
                    name__iexact=service_code.description
                ).first()
            
            if not lab_test:
                # Try by name (contains)
                lab_test = LabTest.objects.filter(
                    name__icontains=service_code.description[:50]
                ).first()
            
            if lab_test:
                # Update LabTest price
                if not dry_run:
                    with transaction.atomic():
                        old_price = lab_test.price
                        lab_test.price = service_price.price
                        lab_test.save(update_fields=['price'])
                        
                        if old_price != service_price.price:
                            stats['lab_tests_synced'] += 1
                            self.stdout.write(
                                f"  Updated: {lab_test.code} - {lab_test.name} "
                                f"(GHS {old_price} -> GHS {service_price.price})"
                            )
                else:
                    stats['lab_tests_synced'] += 1
                    self.stdout.write(
                        f"  [DRY RUN] Would update: {service_code.code} - {service_code.description} "
                        f"(GHS {service_price.price})"
                    )
        
        return stats

    def sync_drugs(self, cash_category, dry_run):
        """Sync ServicePrice prices to Drug.unit_price"""
        stats = {'drugs_synced': 0}
        
        # Get all pharmacy-related ServiceCodes
        drug_service_codes = ServiceCode.objects.filter(
            category__icontains='Pharmacy',
            is_active=True,
            is_deleted=False
        )
        
        self.stdout.write(f'Found {drug_service_codes.count()} pharmacy ServiceCode entries')
        
        for service_code in drug_service_codes:
            # Get cash price from ServicePrice
            service_price = ServicePrice.objects.filter(
                service_code=service_code,
                pricing_category=cash_category,
                is_active=True,
                is_deleted=False
            ).first()
            
            if not service_price:
                continue
            
            # Try to find matching Drug by name
            # Match by description (drug name)
            drug = Drug.objects.filter(
                name__iexact=service_code.description
            ).first()
            
            if not drug:
                # Try partial match
                drug = Drug.objects.filter(
                    name__icontains=service_code.description[:50]
                ).first()
            
            if drug:
                # Only update Drug.unit_price when it's not already set, to avoid
                # overwriting stable pharmacy selling prices (prevents abnormal price changes)
                current = getattr(drug, 'unit_price', None)
                if current is None or current == 0:
                    if not dry_run:
                        with transaction.atomic():
                            drug.unit_price = service_price.price
                            drug.save(update_fields=['unit_price'])
                            stats['drugs_synced'] += 1
                            self.stdout.write(
                                f"  Updated: {drug.name} (was 0/unset -> GHS {service_price.price})"
                            )
                    else:
                        stats['drugs_synced'] += 1
                        self.stdout.write(
                            f"  [DRY RUN] Would set: {drug.name} -> GHS {service_price.price}"
                        )
                else:
                    if not dry_run and current != service_price.price:
                        self.stdout.write(
                            f"  Skipped (keep pharmacy price): {drug.name} "
                            f"(Drug.unit_price GHS {current} != ServicePrice GHS {service_price.price})"
                        )
        
        return stats

    def sync_from_services(self, cash_category, dry_run):
        """Sync LabTest.price and Drug.unit_price to ServicePrice"""
        stats = {
            'service_codes_created': 0,
            'prices_created': 0,
            'prices_updated': 0,
        }
        
        # Sync LabTests
        lab_tests = LabTest.objects.filter(is_active=True, is_deleted=False)
        self.stdout.write(f'\nSyncing {lab_tests.count()} lab tests...')
        
        for lab_test in lab_tests:
            if not lab_test.price or lab_test.price == 0:
                continue
            
            # Get or create ServiceCode
            service_code, created = ServiceCode.objects.get_or_create(
                code=f"LAB-{lab_test.code}",
                defaults={
                    'description': lab_test.name,
                    'category': 'Laboratory',
                    'is_active': True,
                }
            )
            
            if created:
                stats['service_codes_created'] += 1
            
            # Get or create ServicePrice
            service_price, price_created = ServicePrice.objects.get_or_create(
                service_code=service_code,
                pricing_category=cash_category,
                effective_from=timezone.now().date(),
                defaults={
                    'price': lab_test.price,
                    'is_active': True,
                }
            )
            
            if not price_created:
                # Update if price changed
                if service_price.price != lab_test.price:
                    if not dry_run:
                        service_price.price = lab_test.price
                        service_price.save(update_fields=['price'])
                    stats['prices_updated'] += 1
            else:
                stats['prices_created'] += 1
        
        # Sync Drugs
        drugs = Drug.objects.filter(is_active=True, is_deleted=False)
        self.stdout.write(f'\nSyncing {drugs.count()} drugs...')
        
        for drug in drugs:
            unit_price = getattr(drug, 'unit_price', None)
            if not unit_price or unit_price == 0:
                continue
            
            # Get or create ServiceCode
            service_code, created = ServiceCode.objects.get_or_create(
                code=f"DRUG-{drug.code if hasattr(drug, 'code') and drug.code else drug.id}",
                defaults={
                    'description': drug.name,
                    'category': 'Pharmacy',
                    'is_active': True,
                }
            )
            
            if created:
                stats['service_codes_created'] += 1
            
            # Get or create ServicePrice
            service_price, price_created = ServicePrice.objects.get_or_create(
                service_code=service_code,
                pricing_category=cash_category,
                effective_from=timezone.now().date(),
                defaults={
                    'price': unit_price,
                    'is_active': True,
                }
            )
            
            if not price_created:
                # Update if price changed
                if service_price.price != unit_price:
                    if not dry_run:
                        service_price.price = unit_price
                        service_price.save(update_fields=['price'])
                    stats['prices_updated'] += 1
            else:
                stats['prices_created'] += 1
        
        return stats
