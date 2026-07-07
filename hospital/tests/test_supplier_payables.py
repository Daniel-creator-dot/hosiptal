"""Supplier payable sub-ledger: pharmacy stock receipt posting and balance math."""
import uuid
from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.db.models import Sum
from django.test import TestCase

from hospital.models import Drug, PharmacyStock
from hospital.models_missing_features import Supplier
from hospital.models_supplier_payables import (
    SupplierPayableLine,
    post_pharmacy_stock_supplier_payable,
)
from hospital.views_accountant_comprehensive import _supplier_balance_map


class SupplierPayablePharmacyTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username=f'u_{uuid.uuid4().hex[:8]}', password='pw')
        self.supplier = Supplier.objects.create(name=f'Vendor {uuid.uuid4().hex[:6]}')
        self.drug = Drug.objects.create(
            name=f'Drug {uuid.uuid4().hex[:6]}',
            strength='500mg',
            form='Tablet',
            pack_size='10',
            category='other',
        )

    def test_post_pharmacy_stock_creates_receipt_line(self):
        stock = PharmacyStock.objects.create(
            drug=self.drug,
            batch_number='B-1',
            expiry_date=date(2030, 1, 1),
            quantity_on_hand=10,
            unit_cost=Decimal('2.50'),
            supplier=self.supplier,
            created_by=self.user,
        )
        line = post_pharmacy_stock_supplier_payable(
            stock=stock,
            quantity_added=10,
            unit_cost=Decimal('2.50'),
            supplier=self.supplier,
            user=self.user,
        )
        self.assertIsNotNone(line)
        self.assertEqual(line.amount, Decimal('25.00'))
        self.assertEqual(line.entry_type, SupplierPayableLine.ENTRY_STOCK_RECEIPT)
        bal = _supplier_balance_map().get(self.supplier.id)
        self.assertEqual(bal, Decimal('25.00'))

    def test_post_pharmacy_idempotent(self):
        stock = PharmacyStock.objects.create(
            drug=self.drug,
            batch_number='B-2',
            expiry_date=date(2030, 1, 1),
            quantity_on_hand=5,
            unit_cost=Decimal('4.00'),
            supplier=self.supplier,
            created_by=self.user,
        )
        post_pharmacy_stock_supplier_payable(
            stock=stock,
            quantity_added=5,
            unit_cost=Decimal('4.00'),
            supplier=self.supplier,
            user=self.user,
        )
        post_pharmacy_stock_supplier_payable(
            stock=stock,
            quantity_added=5,
            unit_cost=Decimal('4.00'),
            supplier=self.supplier,
            user=self.user,
        )
        self.assertEqual(
            SupplierPayableLine.objects.filter(pharmacy_stock=stock, is_deleted=False).count(),
            1,
        )
        self.assertEqual(_supplier_balance_map().get(self.supplier.id), Decimal('20.00'))

    def test_manual_and_payment_balance(self):
        SupplierPayableLine.objects.create(
            supplier=self.supplier,
            entry_type=SupplierPayableLine.ENTRY_MANUAL_PAYABLE,
            amount=Decimal('100.00'),
            description='Opening',
            created_by=self.user,
        )
        SupplierPayableLine.objects.create(
            supplier=self.supplier,
            entry_type=SupplierPayableLine.ENTRY_PAYMENT,
            amount=Decimal('-30.00'),
            description='Paid',
            reference='CHQ-1',
            created_by=self.user,
        )
        self.assertEqual(_supplier_balance_map().get(self.supplier.id), Decimal('70.00'))

    def test_payment_cannot_exceed_balance(self):
        SupplierPayableLine.objects.create(
            supplier=self.supplier,
            entry_type=SupplierPayableLine.ENTRY_MANUAL_PAYABLE,
            amount=Decimal('40.00'),
            description='Opening',
            created_by=self.user,
        )
        balance = (
            SupplierPayableLine.objects.filter(supplier=self.supplier, is_deleted=False)
            .aggregate(total=Sum('amount'))['total']
            or Decimal('0')
        )
        self.assertEqual(balance, Decimal('40.00'))
        self.assertGreater(Decimal('100.00'), balance)
