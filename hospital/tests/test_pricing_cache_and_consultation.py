"""CON001 cash walk-in uses policy flat rate; pricing engine still reads ServicePrice; cache invalidation."""
import uuid
from decimal import Decimal

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone

from hospital.models import Patient, Payer, ServiceCode
from hospital.models_flexible_pricing import PricingCategory, ServicePrice
from hospital.services.pricing_engine_service import pricing_engine
from hospital.utils_billing import (
    GENERAL_CONSULTATION_CASH,
    get_general_consultation_price_for_patient_and_payer,
)


@override_settings(
    CACHES={
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'pricing-consult-test',
        }
    }
)
class ConsultationPricingFromDbTests(TestCase):
    """Cash general OPD stays at policy flat (150); engine may still expose catalog cash ServicePrice."""

    def setUp(self):
        cache.clear()
        suffix = uuid.uuid4().hex[:8]
        self.cash_payer = Payer.objects.create(
            name=f'Cash payer {suffix}',
            payer_type='cash',
            is_active=True,
        )
        self.patient = Patient.objects.create(
            first_name='Price',
            last_name='Test',
            mrn=f'PMC-PT-{suffix}',
            primary_insurance=self.cash_payer,
        )
        self.cash_cat, _ = PricingCategory.objects.get_or_create(
            code='CASH',
            defaults={
                'name': 'Cash',
                'category_type': 'cash',
                'priority': 1,
                'is_active': True,
            },
        )
        self.sc_con001, _ = ServiceCode.objects.get_or_create(
            code='CON001',
            defaults={
                'description': 'General Consultation',
                'category': 'Consultation',
                'is_active': True,
            },
        )
        today = timezone.now().date()
        self.target_price = Decimal('199.99')
        ServicePrice.objects.update_or_create(
            service_code=self.sc_con001,
            pricing_category=self.cash_cat,
            effective_from=today,
            defaults={
                'price': self.target_price,
                'is_active': True,
                'is_deleted': False,
            },
        )

    def test_pricing_engine_returns_service_price_for_con001_cash(self):
        out = pricing_engine.get_service_price(
            self.sc_con001,
            self.patient,
            payer=self.cash_payer,
        )
        self.assertEqual(out, self.target_price)

    def test_get_general_consultation_cash_ignores_flexible_cash_service_price(self):
        """Walk-in cash CON001 uses GENERAL_CONSULTATION_CASH, not PricingCategory cash row."""
        out = get_general_consultation_price_for_patient_and_payer(
            self.patient,
            self.cash_payer,
        )
        self.assertEqual(out, GENERAL_CONSULTATION_CASH)


@override_settings(
    CACHES={
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'pricing-cache-test',
        }
    }
)
class ServicePriceCacheInvalidationTests(TestCase):
    """Saving ServicePrice must clear Redis/locmem catalog keys so UI cannot show stale prices."""

    def setUp(self):
        cache.clear()
        suffix = uuid.uuid4().hex[:8]
        self.cash_cat, _ = PricingCategory.objects.get_or_create(
            code='CASH',
            defaults={
                'name': 'Cash',
                'category_type': 'cash',
                'priority': 1,
                'is_active': True,
            },
        )
        self.sc, _ = ServiceCode.objects.get_or_create(
            code=f'TSTSP-{suffix}',
            defaults={
                'description': 'Cache invalidation test service',
                'category': 'Test',
                'is_active': True,
            },
        )
        self.sp = ServicePrice.objects.create(
            service_code=self.sc,
            pricing_category=self.cash_cat,
            price=Decimal('10.00'),
            effective_from=timezone.now().date(),
            is_active=True,
        )

    def test_service_price_save_clears_catalog_cache_keys(self):
        cache.set('hms:active_drugs', 'stale')
        cache.set('hms:active_imaging_studies', 'stale')
        self.sp.price = Decimal('11.00')
        self.sp.save(update_fields=['price'])
        self.assertIsNone(cache.get('hms:active_drugs'))
        self.assertIsNone(cache.get('hms:active_imaging_studies'))
