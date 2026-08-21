from decimal import Decimal
from django.test import SimpleTestCase

from hospital.services.receipt_revenue_allocation import (
    _peel_sustainability_from_amount,
    expand_consultation_with_sustainability,
)
from hospital.utils_billing import is_consultation_like_charge, with_sustainability_fee


class SustainabilityPeelTests(SimpleTestCase):
    def test_full_consult_payment_takes_exact_eight(self):
        sust, consult = _peel_sustainability_from_amount(Decimal('156.00'), Decimal('8.00'))
        self.assertEqual(sust, Decimal('8.00'))
        self.assertEqual(consult, Decimal('148.00'))

    def test_near_full_no_longer_proportional_under_eight(self):
        # Old bug: 156 * 8 / 158 = 7.90
        sust, consult = _peel_sustainability_from_amount(Decimal('156.00'), Decimal('8.00'))
        self.assertEqual(sust, Decimal('8.00'))
        self.assertNotEqual(sust, Decimal('7.90'))

    def test_expand_without_invoice_peels_eight_from_consultation(self):
        splits = expand_consultation_with_sustainability(
            [('consultation', Decimal('158.00'))],
            invoice=None,
        )
        by_svc = {s: a for s, a in splits}
        self.assertEqual(by_svc.get('sustainability'), Decimal('8.00'))
        self.assertEqual(by_svc.get('consultation'), Decimal('150.00'))

    def test_small_partial_takes_all_available_toward_fee(self):
        sust, rest = _peel_sustainability_from_amount(Decimal('5.00'), Decimal('8.00'))
        self.assertEqual(sust, Decimal('5.00'))
        self.assertEqual(rest, Decimal('0.00'))

    def test_zero_remaining_leaves_consultation_intact(self):
        sust, consult = _peel_sustainability_from_amount(Decimal('158.00'), Decimal('0.00'))
        self.assertEqual(sust, Decimal('0.00'))
        self.assertEqual(consult, Decimal('158.00'))

    def test_consultation_like_detects_dietician_psych_surgical_consult(self):
        self.assertTrue(is_consultation_like_charge(code='SP-34', label='DIETICIAN CONSULTATION'))
        self.assertTrue(is_consultation_like_charge(code='SP003-PSYCH', label='Psychiatric'))
        self.assertTrue(is_consultation_like_charge(code='SERG-87', label='surgical consult'))
        self.assertFalse(is_consultation_like_charge(code='SUR-23', label='SURGICAL FEE MAJOR'))
        self.assertFalse(is_consultation_like_charge(code='TH-002', label='Theatre fees'))
        self.assertFalse(is_consultation_like_charge(code='RPT-GP', label='Medical Report (GP)'))
        self.assertFalse(is_consultation_like_charge(code='RPT-SCHOOL', label='Medical Report (School)'))
        self.assertEqual(with_sustainability_fee(Decimal('150.00')), Decimal('158.00'))
        self.assertEqual(with_sustainability_fee(Decimal('300.00')), Decimal('308.00'))
        self.assertEqual(with_sustainability_fee(Decimal('260.00')), Decimal('268.00'))
