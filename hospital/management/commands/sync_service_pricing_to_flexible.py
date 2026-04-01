"""
Sync ServicePricing (enterprise billing) to ServicePrice + PricingCategory (flexible pricing).
Ensures all insurance, cash, and corporate prices in the system are available to the pricing engine.
Run after import_billing_prices or when you have prices in ServicePricing.
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from decimal import Decimal

from hospital.models import ServiceCode
from hospital.models_flexible_pricing import PricingCategory, ServicePrice
from hospital.models_enterprise_billing import ServicePricing


class Command(BaseCommand):
    help = 'Sync ServicePricing (cash/corporate/insurance) to ServicePrice so pricing engine uses all your prices'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be synced without making changes',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        today = timezone.now().date()

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN - no changes will be made\n'))

        # Ensure pricing categories exist
        cash_cat, _ = PricingCategory.objects.get_or_create(
            code='CASH',
            defaults={'name': 'Cash', 'category_type': 'cash', 'is_active': True, 'priority': 1},
        )
        corp_cat, _ = PricingCategory.objects.get_or_create(
            code='CORP',
            defaults={'name': 'Corporate', 'category_type': 'corporate', 'is_active': True, 'priority': 2},
        )
        ins_cat, _ = PricingCategory.objects.get_or_create(
            code='INS',
            defaults={'name': 'Insurance', 'category_type': 'insurance', 'is_active': True, 'priority': 3},
        )

        from django.db.models import Q
        # Default tiers only (payer__isnull=True) - these are the main cash/corp/ins tiers
        pricing_list = ServicePricing.objects.filter(
            payer__isnull=True,
            is_active=True,
            is_deleted=False,
            effective_from__lte=today,
        ).filter(Q(effective_to__isnull=True) | Q(effective_to__gte=today)).select_related('service_code')

        def sync_price_for_service_code(sc, cash_val, corp_val, ins_val, dry_run, created_updated):
            c, u = created_updated
            for cat, price_val, cat_obj in [
                ('CASH', cash_val, cash_cat),
                ('CORP', corp_val, corp_cat),
                ('INS', ins_val, ins_cat),
            ]:
                if price_val is None or price_val < 0:
                    continue
                price_val = Decimal(str(price_val))
                sp = ServicePrice.objects.filter(
                    service_code=sc,
                    pricing_category=cat_obj,
                    is_active=True,
                    is_deleted=False,
                    effective_from__lte=today,
                ).filter(Q(effective_to__isnull=True) | Q(effective_to__gte=today)).order_by('-effective_from').first()
                if dry_run:
                    c += 1
                    continue
                if sp:
                    if sp.price != price_val:
                        sp.price = price_val
                        sp.save(update_fields=['price'])
                        u += 1
                        self.stdout.write(self.style.WARNING(f"  Updated {sc.code} / {cat}: GHS {price_val}"))
                else:
                    ServicePrice.objects.create(
                        service_code=sc,
                        pricing_category=cat_obj,
                        price=price_val,
                        effective_from=today,
                        is_active=True,
                    )
                    c += 1
                    self.stdout.write(self.style.SUCCESS(f"  Created {sc.code} / {cat}: GHS {price_val}"))
            return (c, u)

        created = updated = 0
        for pricing in pricing_list:
            sc = pricing.service_code
            if not sc or sc.is_deleted:
                continue
            cash_val = getattr(pricing, 'cash_price', None)
            corp_val = getattr(pricing, 'corporate_price', None)
            ins_val = getattr(pricing, 'insurance_price', None)
            if dry_run:
                self.stdout.write(f"  Would sync: {sc.code} {sc.description} -> Cash {cash_val} Corp {corp_val} Ins {ins_val}")
                created += 3
                continue
            with transaction.atomic():
                (created, updated) = sync_price_for_service_code(sc, cash_val, corp_val, ins_val, dry_run, (created, updated))
            # Consultation: also sync S00023 prices to CON001 so primary path works
            if sc.code == 'S00023' and (cash_val or corp_val or ins_val):
                con001 = ServiceCode.objects.filter(code='CON001', is_deleted=False).first()
                if con001:
                    with transaction.atomic():
                        (created, updated) = sync_price_for_service_code(
                            con001, cash_val, corp_val, ins_val, dry_run, (created, updated)
                        )

        self.stdout.write(self.style.SUCCESS(f"\nSync complete. Created: {created}, Updated: {updated}"))
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN - no changes were made. Run without --dry-run to apply.'))
