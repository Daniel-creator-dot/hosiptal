"""Drug payer markup: insurance 30%, corporate 50%, cash none."""
import uuid
from decimal import Decimal
from types import SimpleNamespace

from django.test import TestCase

from hospital.models import Drug, Payer
from hospital.utils_billing import (
    DRUG_CORPORATE_MARKUP,
    DRUG_INSURANCE_MARKUP,
    get_drug_markup_for_payer,
    get_drug_price_for_prescription,
)


class DrugMarkupTests(TestCase):
    def setUp(self):
        suffix = uuid.uuid4().hex[:8]
        self.base_price = Decimal('100.00')
        self.drug = Drug.objects.create(
            name=f'MarkupDrug{suffix}',
            strength='500mg',
            form='Tablet',
            pack_size='10',
            unit_price=self.base_price,
        )
        self.cash_payer = Payer.objects.create(
            name=f'Cash {suffix}',
            payer_type='cash',
            is_active=True,
        )
        self.corporate_payer = Payer.objects.create(
            name=f'Corporate {suffix}',
            payer_type='corporate',
            is_active=True,
        )
        self.nhis_payer = Payer.objects.create(
            name=f'NHIS {suffix}',
            payer_type='nhis',
            is_active=True,
        )
        self.private_payer = Payer.objects.create(
            name=f'Private {suffix}',
            payer_type='private',
            is_active=True,
        )

    def test_get_drug_markup_for_payer_rates(self):
        self.assertEqual(get_drug_markup_for_payer(self.cash_payer), Decimal('0'))
        self.assertEqual(get_drug_markup_for_payer(self.corporate_payer), DRUG_CORPORATE_MARKUP)
        self.assertEqual(get_drug_markup_for_payer(self.nhis_payer), DRUG_INSURANCE_MARKUP)
        self.assertEqual(get_drug_markup_for_payer(self.private_payer), DRUG_INSURANCE_MARKUP)
        legacy_insurance = SimpleNamespace(payer_type='insurance')
        self.assertEqual(get_drug_markup_for_payer(legacy_insurance), DRUG_INSURANCE_MARKUP)

    def test_cash_payer_no_markup(self):
        price = get_drug_price_for_prescription(self.drug, payer=self.cash_payer)
        self.assertEqual(price, self.base_price)

    def test_no_payer_no_markup(self):
        price = get_drug_price_for_prescription(self.drug, payer=None)
        self.assertEqual(price, self.base_price)

    def test_insurance_payers_30_percent_markup(self):
        expected = self.base_price * (1 + DRUG_INSURANCE_MARKUP)
        for payer in (self.nhis_payer, self.private_payer):
            with self.subTest(payer_type=payer.payer_type):
                price = get_drug_price_for_prescription(self.drug, payer=payer)
                self.assertEqual(price, expected)

        legacy_insurance = SimpleNamespace(payer_type='insurance')
        price = get_drug_price_for_prescription(self.drug, payer=legacy_insurance)
        self.assertEqual(price, expected)

    def test_corporate_payer_50_percent_markup(self):
        expected = self.base_price * (1 + DRUG_CORPORATE_MARKUP)
        price = get_drug_price_for_prescription(self.drug, payer=self.corporate_payer)
        self.assertEqual(price, expected)
