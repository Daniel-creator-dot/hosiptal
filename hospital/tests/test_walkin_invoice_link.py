"""Tests for prescribe-sale / invoice linking helpers."""
from decimal import Decimal
from unittest.mock import MagicMock

from django.test import TestCase

from hospital.services.pharmacy_invoice_payment_link import (
    WALKIN_SALE_REF_RE,
    link_walkin_sales_when_invoice_paid,
)


class WalkinSaleRefRegexTests(TestCase):
    def test_extracts_sale_number(self):
        m = WALKIN_SALE_REF_RE.search('Paracetamol 500 (Sale PS202603221818070009)')
        self.assertIsNotNone(m)
        self.assertEqual(m.group(1).upper(), 'PS202603221818070009')


class LinkWalkinSalesWhenInvoicePaidTests(TestCase):
    def test_skips_when_balance_positive(self):
        inv = MagicMock()
        inv.pk = '00000000-0000-0000-0000-000000000001'
        inv.refresh_from_db = MagicMock()
        inv.update_totals = MagicMock()
        inv.balance = Decimal('10.00')
        self.assertEqual(link_walkin_sales_when_invoice_paid(inv), 0)
