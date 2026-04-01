"""
Seed general prices (cash, corporate, insurance) for consultation and imaging.
Use these as the central source; billing picks from here via the pricing engine.
- General consultation: cash 150, corporate/insurance from config (default 150)
- Specialist consultation: cash 300, corporate/insurance from config (default 300)
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from decimal import Decimal

from hospital.models import ServiceCode
from hospital.models_flexible_pricing import PricingCategory, ServicePrice


class Command(BaseCommand):
    help = 'Seed general prices (cash, corporate, insurance) for consultation and imaging'

    def add_arguments(self, parser):
        parser.add_argument(
            '--general-cash', type=float, default=150.0,
            help='General consultation cash price (default: 150)',
        )
        parser.add_argument(
            '--general-corp', type=float, default=None,
            help='General consultation corporate price (default: same as cash)',
        )
        parser.add_argument(
            '--general-ins', type=float, default=None,
            help='General consultation insurance price (default: same as cash)',
        )
        parser.add_argument(
            '--specialist-cash', type=float, default=300.0,
            help='Specialist consultation cash price (default: 300)',
        )
        parser.add_argument(
            '--specialist-corp', type=float, default=None,
            help='Specialist consultation corporate price (default: same as cash)',
        )
        parser.add_argument(
            '--specialist-ins', type=float, default=None,
            help='Specialist consultation insurance price (default: same as cash)',
        )

    def handle(self, *args, **options):
        today = timezone.now().date()
        gen_cash = Decimal(str(options['general_cash']))
        gen_corp = Decimal(str(options['general_corp'] or options['general_cash']))
        gen_ins = Decimal(str(options['general_ins'] or options['general_cash']))
        spec_cash = Decimal(str(options['specialist_cash']))
        spec_corp = Decimal(str(options['specialist_corp'] or options['specialist_cash']))
        spec_ins = Decimal(str(options['specialist_ins'] or options['specialist_cash']))

        # Ensure PricingCategories: Cash, Corporate, Insurance
        cash_cat, _ = PricingCategory.objects.get_or_create(
            code='CASH',
            defaults={'name': 'Cash', 'category_type': 'cash', 'is_active': True, 'priority': 1},
        )
        if not _:
            cash_cat.name = 'Cash'
            cash_cat.category_type = 'cash'
            cash_cat.is_active = True
            cash_cat.save(update_fields=['name', 'category_type', 'is_active'])

        corp_cat, _ = PricingCategory.objects.get_or_create(
            code='CORP',
            defaults={'name': 'Corporate', 'category_type': 'corporate', 'is_active': True, 'priority': 2},
        )
        if not _:
            corp_cat.name = 'Corporate'
            corp_cat.category_type = 'corporate'
            corp_cat.is_active = True
            corp_cat.save(update_fields=['name', 'category_type', 'is_active'])

        ins_cat, _ = PricingCategory.objects.get_or_create(
            code='INS',
            defaults={'name': 'Insurance', 'category_type': 'insurance', 'is_active': True, 'priority': 3},
        )
        if not _:
            ins_cat.name = 'Insurance'
            ins_cat.category_type = 'insurance'
            ins_cat.is_active = True
            ins_cat.save(update_fields=['name', 'category_type', 'is_active'])

        self.stdout.write('Pricing categories: Cash, Corporate, Insurance')

        def ensure_service_price(sc, cat, price):
            from django.db.models import Q
            sp = ServicePrice.objects.filter(
                service_code=sc,
                pricing_category=cat,
                is_active=True,
                effective_from__lte=today,
                is_deleted=False,
            ).filter(
                Q(effective_to__isnull=True) | Q(effective_to__gte=today)
            ).order_by('-effective_from').first()
            if sp:
                if sp.price != price:
                    sp.price = price
                    sp.save(update_fields=['price'])
                self.stdout.write(self.style.WARNING(
                    f'  Updated ServicePrice: {sc.code} / {cat.code} = GHS {price}'
                ))
            else:
                ServicePrice.objects.create(
                    service_code=sc,
                    pricing_category=cat,
                    price=price,
                    effective_from=today,
                    is_active=True,
                )
                self.stdout.write(self.style.SUCCESS(
                    f'  Created ServicePrice: {sc.code} / {cat.code} = GHS {price}'
                ))

        # CON001 General Consultation
        con001, _ = ServiceCode.objects.get_or_create(
            code='CON001',
            defaults={
                'description': 'General Consultation',
                'category': 'Clinical Services',
                'is_active': True,
            },
        )
        ensure_service_price(con001, cash_cat, gen_cash)
        ensure_service_price(con001, corp_cat, gen_corp)
        ensure_service_price(con001, ins_cat, gen_ins)
        self.stdout.write(self.style.SUCCESS(
            f'General Consultation (CON001): Cash GHS {gen_cash}, Corp GHS {gen_corp}, Ins GHS {gen_ins}'
        ))

        # CON002 Specialist Consultation
        con002, _ = ServiceCode.objects.get_or_create(
            code='CON002',
            defaults={
                'description': 'Specialist Consultation',
                'category': 'Clinical Services',
                'is_active': True,
            },
        )
        ensure_service_price(con002, cash_cat, spec_cash)
        ensure_service_price(con002, corp_cat, spec_corp)
        ensure_service_price(con002, ins_cat, spec_ins)
        self.stdout.write(self.style.SUCCESS(
            f'Specialist Consultation (CON002): Cash GHS {spec_cash}, Corp GHS {spec_corp}, Ins GHS {spec_ins}'
        ))

        self.stdout.write(self.style.SUCCESS('\nGeneral prices seeded. Billing picks from ServicePrice + PricingCategory.'))
