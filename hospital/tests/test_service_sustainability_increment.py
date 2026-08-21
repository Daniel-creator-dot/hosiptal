"""10% Sustainability and Insurance increment on drugs, lab, scans, and ward fees."""
from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace

from django.test import SimpleTestCase

from hospital.services.bed_billing_service import BedBillingService
from hospital.services.credit_revenue_service import prorate_ire_revenue_amounts
from hospital.services.pricing_engine_service import pricing_engine
from hospital.services.receipt_revenue_allocation import expand_consultation_with_sustainability
from hospital.utils_billing import (
    billed_lab_or_scan_catalog_price,
    invoice_uses_service_sustainability,
    service_sustainability_portion,
    with_service_sustainability,
)


class ServiceSustainabilityHelpersTests(SimpleTestCase):
    def test_with_service_sustainability_adds_ten_percent(self):
        self.assertEqual(with_service_sustainability(Decimal('100.00')), Decimal('110.00'))
        self.assertEqual(with_service_sustainability(Decimal('0.00')), Decimal('0.00'))

    def test_portion_is_ten_over_one_ten(self):
        self.assertEqual(service_sustainability_portion(Decimal('110.00')), Decimal('10.00'))
        self.assertEqual(service_sustainability_portion(Decimal('143.00')), Decimal('13.00'))

    def test_billed_lab_cash_is_catalog_plus_ten(self):
        self.assertEqual(
            billed_lab_or_scan_catalog_price(Decimal('100.00'), SimpleNamespace(payer_type='cash')),
            Decimal('110.00'),
        )

    def test_billed_lab_insurance_is_thirty_then_ten(self):
        self.assertEqual(
            billed_lab_or_scan_catalog_price(Decimal('100.00'), SimpleNamespace(payer_type='nhis')),
            Decimal('143.00'),
        )


class LabScanWardMarkupTests(SimpleTestCase):
    def test_cash_lab_includes_ten_percent(self):
        sc = SimpleNamespace(code='LAB-FBC', category='laboratory')
        price = pricing_engine._apply_lab_imaging_markup(
            Decimal('100.00'), sc, SimpleNamespace(payer_type='cash')
        )
        self.assertEqual(price, Decimal('110.00'))

    def test_insurance_lab_thirty_then_ten(self):
        sc = SimpleNamespace(code='LAB-FBC', category='laboratory')
        price = pricing_engine._apply_lab_imaging_markup(
            Decimal('100.00'), sc, SimpleNamespace(payer_type='nhis')
        )
        self.assertEqual(price, Decimal('143.00'))

    def test_scan_cash_includes_ten_percent(self):
        sc = SimpleNamespace(code='IMG-XRAY', category='imaging')
        price = pricing_engine._apply_lab_imaging_markup(
            Decimal('200.00'), sc, SimpleNamespace(payer_type='cash')
        )
        self.assertEqual(price, Decimal('220.00'))

    def test_consultation_not_incremented_by_ten_percent(self):
        sc = SimpleNamespace(code='CON001', category='consultation')
        price = pricing_engine._apply_lab_imaging_markup(
            Decimal('158.00'), sc, SimpleNamespace(payer_type='cash')
        )
        self.assertEqual(price, Decimal('158.00'))

    def test_ward_detention_includes_ten_percent(self):
        sc = SimpleNamespace(code='DETENTION', category='accommodation')
        price = pricing_engine._apply_lab_imaging_markup(
            Decimal('120.00'), sc, SimpleNamespace(payer_type='cash')
        )
        self.assertEqual(price, Decimal('132.00'))

    def test_bed_billing_rates_include_ten_percent(self):
        self.assertEqual(BedBillingService.DETENTION_RATE, Decimal('132.00'))
        self.assertEqual(BedBillingService.ADMISSION_NIGHTLY_RATE, Decimal('165.00'))
        self.assertEqual(BedBillingService.VIP_ADMISSION_NIGHTLY_RATE, Decimal('480.00'))
        self.assertEqual(BedBillingService.DOCTOR_CARE_PER_NIGHT, Decimal('88.00'))
        self.assertEqual(BedBillingService.NURSING_CARE_PER_NIGHT, Decimal('77.00'))
        self.assertEqual(BedBillingService.CONSUMABLES_PER_NIGHT, Decimal('55.00'))


class ServiceSustainabilityGlPeelTests(SimpleTestCase):
    def test_lab_only_invoice_peels_ten_to_4115(self):
        splits = expand_consultation_with_sustainability(
            [('lab', Decimal('110.00'))],
            invoice=None,
        )
        by_svc = {s: a for s, a in splits}
        self.assertEqual(by_svc.get('lab'), Decimal('100.00'))
        self.assertEqual(by_svc.get('sustainability'), Decimal('10.00'))

    def test_pharmacy_and_imaging_and_admission_peel(self):
        splits = expand_consultation_with_sustainability(
            [
                ('pharmacy', Decimal('110.00')),
                ('imaging', Decimal('220.00')),
                ('admission', Decimal('132.00')),
            ],
            invoice=None,
        )
        by_svc = {s: a for s, a in splits}
        self.assertEqual(by_svc.get('pharmacy'), Decimal('100.00'))
        self.assertEqual(by_svc.get('imaging'), Decimal('200.00'))
        self.assertEqual(by_svc.get('admission'), Decimal('120.00'))
        self.assertEqual(by_svc.get('sustainability'), Decimal('42.00'))

    def test_consultation_still_peels_fixed_eight_not_ten_percent(self):
        splits = expand_consultation_with_sustainability(
            [('consultation', Decimal('158.00'))],
            invoice=None,
        )
        by_svc = {s: a for s, a in splits}
        self.assertEqual(by_svc.get('consultation'), Decimal('150.00'))
        self.assertEqual(by_svc.get('sustainability'), Decimal('8.00'))

    def test_mixed_consult_and_lab_peels_eight_plus_ten(self):
        splits = expand_consultation_with_sustainability(
            [
                ('consultation', Decimal('158.00')),
                ('lab', Decimal('110.00')),
            ],
            invoice=None,
        )
        by_svc = {s: a for s, a in splits}
        self.assertEqual(by_svc.get('consultation'), Decimal('150.00'))
        self.assertEqual(by_svc.get('lab'), Decimal('100.00'))
        self.assertEqual(by_svc.get('sustainability'), Decimal('18.00'))

    def test_old_invoice_does_not_peel_embedded_ten_percent(self):
        class _Lines:
            def filter(self, **kwargs):
                return self

            def only(self, *args):
                return []

        old_invoice = SimpleNamespace(
            issued_at=datetime(2026, 3, 1, 8, 0, 0),
            created=datetime(2026, 3, 1, 8, 0, 0),
            modified=datetime(2026, 3, 1, 8, 0, 0),
            lines=_Lines(),
        )
        self.assertFalse(invoice_uses_service_sustainability(old_invoice))
        splits = expand_consultation_with_sustainability(
            [('lab', Decimal('110.00'))],
            invoice=old_invoice,
        )
        by_svc = {s: a for s, a in splits}
        self.assertEqual(by_svc.get('lab'), Decimal('110.00'))
        self.assertNotIn('sustainability', by_svc)


class CreditRevenueSustainabilityPeelTests(SimpleTestCase):
    def test_prorate_peels_lab_pharmacy_radiology_admissions(self):
        ire = SimpleNamespace(
            total_amount=Decimal('605.00'),
            entry_date=date(2026, 8, 18),
            registration_amount=Decimal('0.00'),
            consultation_amount=Decimal('0.00'),
            laboratory_amount=Decimal('110.00'),
            pharmacy_amount=Decimal('143.00'),
            surgeries_amount=Decimal('0.00'),
            admissions_amount=Decimal('132.00'),
            radiology_amount=Decimal('220.00'),
            dental_amount=Decimal('0.00'),
            physiotherapy_amount=Decimal('0.00'),
        )
        result = prorate_ire_revenue_amounts(ire, Decimal('605.00'))
        self.assertEqual(result.get('laboratory'), Decimal('100.00'))
        self.assertEqual(result.get('pharmacy'), Decimal('130.00'))
        self.assertEqual(result.get('admissions'), Decimal('120.00'))
        self.assertEqual(result.get('radiology'), Decimal('200.00'))
        self.assertEqual(result.get('sustainability'), Decimal('55.00'))
        self.assertEqual(sum(result.values()), Decimal('605.00'))

    def test_old_ire_entry_does_not_peel_ten_percent(self):
        ire = SimpleNamespace(
            total_amount=Decimal('110.00'),
            entry_date=date(2026, 3, 1),
            registration_amount=Decimal('0.00'),
            consultation_amount=Decimal('0.00'),
            laboratory_amount=Decimal('110.00'),
            pharmacy_amount=Decimal('0.00'),
            surgeries_amount=Decimal('0.00'),
            admissions_amount=Decimal('0.00'),
            radiology_amount=Decimal('0.00'),
            dental_amount=Decimal('0.00'),
            physiotherapy_amount=Decimal('0.00'),
        )
        result = prorate_ire_revenue_amounts(ire, Decimal('110.00'))
        self.assertEqual(result.get('laboratory'), Decimal('110.00'))
        self.assertNotIn('sustainability', result)

    def test_consultation_credit_is_not_ten_percent_peeled(self):
        ire = SimpleNamespace(
            total_amount=Decimal('158.00'),
            registration_amount=Decimal('0.00'),
            consultation_amount=Decimal('158.00'),
            laboratory_amount=Decimal('0.00'),
            pharmacy_amount=Decimal('0.00'),
            surgeries_amount=Decimal('0.00'),
            admissions_amount=Decimal('0.00'),
            radiology_amount=Decimal('0.00'),
            dental_amount=Decimal('0.00'),
            physiotherapy_amount=Decimal('0.00'),
        )
        result = prorate_ire_revenue_amounts(ire, Decimal('158.00'))
        self.assertEqual(result.get('consultation'), Decimal('158.00'))
        self.assertNotIn('sustainability', result)
