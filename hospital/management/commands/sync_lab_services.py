"""
Management command to sync ServiceCode lab services to LabTest entries
This allows doctors to see and order lab services that were added as ServiceCode entries
"""
from django.core.management.base import BaseCommand
from django.db.models import Q
from decimal import Decimal
from hospital.models import ServiceCode, LabTest, PriceBook


class Command(BaseCommand):
    help = 'Sync ServiceCode lab services to LabTest entries so doctors can order them'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be created without actually creating',
        )
        parser.add_argument(
            '--category',
            type=str,
            help='Only sync services with this category (default: any containing "lab")',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        category_filter = options.get('category')
        
        # Find all ServiceCode entries that are lab services
        if category_filter:
            lab_services = ServiceCode.objects.filter(
                category__icontains=category_filter,
                is_active=True,
                is_deleted=False
            )
        else:
            # Common lab category patterns
            lab_services = ServiceCode.objects.filter(
                Q(category__icontains='lab') |
                Q(category__icontains='Laboratory') |
                Q(category__icontains='laboratory') |
                Q(code__startswith='L') |
                Q(description__icontains='lab test') |
                Q(description__icontains='laboratory')
            ).filter(
                is_active=True,
                is_deleted=False
            ).distinct()
        
        total = lab_services.count()
        self.stdout.write(f'\n📋 Found {total} lab ServiceCode entries')
        
        if total == 0:
            self.stdout.write(self.style.WARNING('No lab services found to sync'))
            return
        
        created_count = 0
        updated_count = 0
        skipped_count = 0
        
        for service in lab_services:
            # Get price from PriceBook or ServicePrice
            price = Decimal('0.00')
            
            # Try to get price from PriceBook (default/cash payer)
            price_book = PriceBook.objects.filter(
                service_code=service,
                is_active=True
            ).first()
            
            if price_book:
                price = price_book.unit_price
            else:
                # Try ServicePrice (flexible pricing)
                try:
                    from hospital.models_flexible_pricing import ServicePrice as FlexServicePrice
                    flex_price = FlexServicePrice.objects.filter(
                        service_code=service,
                        is_active=True
                    ).first()
                    if flex_price:
                        price = flex_price.price
                except ImportError:
                    pass
            
            # Determine specimen type from description or use default
            specimen_type = 'Blood'  # Default
            description_lower = service.description.lower()
            if 'urine' in description_lower or 'urinalysis' in description_lower:
                specimen_type = 'Urine'
            elif 'stool' in description_lower or 'feces' in description_lower:
                specimen_type = 'Stool'
            elif 'sputum' in description_lower:
                specimen_type = 'Sputum'
            elif 'swab' in description_lower:
                specimen_type = 'Swab'
            elif 'csf' in description_lower or 'cerebrospinal' in description_lower:
                specimen_type = 'CSF'
            elif 'pus' in description_lower or 'fluid' in description_lower:
                specimen_type = 'Fluid'
            
            # Use service code as lab test code, or generate one
            lab_code = service.code
            if not lab_code or len(lab_code) > 20:
                # Generate code from description
                lab_code = service.description[:20].upper().replace(' ', '_')
            
            # Check if LabTest already exists
            existing_test = LabTest.objects.filter(code=lab_code).first()
            
            if existing_test:
                # Update existing
                if not dry_run:
                    existing_test.name = service.description
                    existing_test.price = price
                    existing_test.specimen_type = specimen_type
                    existing_test.is_active = service.is_active
                    existing_test.save()
                    updated_count += 1
                    self.stdout.write(
                        self.style.WARNING(f'↻ Updated: {lab_code} - {service.description} (GHS {price})')
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(f'[DRY RUN] Would update: {lab_code} - {service.description}')
                    )
            else:
                # Create new
                if not dry_run:
                    LabTest.objects.create(
                        code=lab_code,
                        name=service.description,
                        specimen_type=specimen_type,
                        tat_minutes=60,  # Default turnaround time
                        price=price,
                        is_active=service.is_active
                    )
                    created_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(f'✓ Created: {lab_code} - {service.description} (GHS {price})')
                    )
                else:
                    self.stdout.write(
                        self.style.SUCCESS(f'[DRY RUN] Would create: {lab_code} - {service.description}')
                    )
        
        self.stdout.write(self.style.SUCCESS(
            f'\n✅ Sync complete! Created: {created_count}, Updated: {updated_count}, Skipped: {skipped_count}'
        ))
        self.stdout.write(
            self.style.SUCCESS(
                f'Total LabTest entries: {LabTest.objects.filter(is_active=True).count()}'
            )
        )

