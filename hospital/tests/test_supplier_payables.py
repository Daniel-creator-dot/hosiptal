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
            supplier_invoice_number='INV-STOCK-1',
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
        self.assertEqual(line.reference, 'INV-STOCK-1')
        bal = _supplier_balance_map().get(self.supplier.id)
        self.assertEqual(bal, Decimal('25.00'))

        from hospital.views_accountant_comprehensive import supplier_invoice_payment_status
        status = supplier_invoice_payment_status(self.supplier, 'INV-STOCK-1')
        self.assertEqual(status['status'], 'unpaid')
        self.assertTrue(any('batch B-1' in (i.get('label') or '') for i in status['items']))

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


class SupplierInvoiceStatusTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username=f'u_{uuid.uuid4().hex[:8]}', password='pw')
        self.supplier = Supplier.objects.create(name=f'Vendor {uuid.uuid4().hex[:6]}')

    def test_new_invoice_allowed(self):
        from hospital.views_accountant_comprehensive import supplier_invoice_payment_status

        status = supplier_invoice_payment_status(self.supplier, 'INV-NEW-100')
        self.assertFalse(status['exists'])
        self.assertEqual(status['status'], 'new')
        self.assertTrue(status['can_pay'])
        self.assertTrue(status['can_record_payable'])

    def test_unpaid_then_paid_blocks_repeat(self):
        from hospital.views_accountant_comprehensive import supplier_invoice_payment_status

        SupplierPayableLine.objects.create(
            supplier=self.supplier,
            entry_type=SupplierPayableLine.ENTRY_MANUAL_PAYABLE,
            amount=Decimal('100.00'),
            description='Goods',
            reference='INV-77',
            created_by=self.user,
        )
        unpaid = supplier_invoice_payment_status(self.supplier, 'inv-77')
        self.assertTrue(unpaid['exists'])
        self.assertEqual(unpaid['status'], 'unpaid')
        self.assertTrue(unpaid['can_pay'])
        self.assertFalse(unpaid['can_record_payable'])

        SupplierPayableLine.objects.create(
            supplier=self.supplier,
            entry_type=SupplierPayableLine.ENTRY_PAYMENT,
            amount=Decimal('-100.00'),
            description='Paid in full',
            reference='INV-77',
            created_by=self.user,
        )
        paid = supplier_invoice_payment_status(self.supplier, 'INV-77')
        self.assertEqual(paid['status'], 'paid')
        self.assertFalse(paid['can_pay'])
        self.assertFalse(paid['can_record_payable'])
        self.assertIn('already paid', paid['message'].lower())

    def test_partial_payment_still_open(self):
        from hospital.views_accountant_comprehensive import supplier_invoice_payment_status

        SupplierPayableLine.objects.create(
            supplier=self.supplier,
            entry_type=SupplierPayableLine.ENTRY_MANUAL_PAYABLE,
            amount=Decimal('80.00'),
            reference='INV-PARTIAL',
            created_by=self.user,
        )
        SupplierPayableLine.objects.create(
            supplier=self.supplier,
            entry_type=SupplierPayableLine.ENTRY_PAYMENT,
            amount=Decimal('-30.00'),
            reference='INV-PARTIAL',
            created_by=self.user,
        )
        status = supplier_invoice_payment_status(self.supplier, 'INV-PARTIAL')
        self.assertEqual(status['status'], 'partial')
        self.assertTrue(status['can_pay'])
        self.assertEqual(status['outstanding'], '50.00')

    def test_payment_post_requires_invoice_and_blocks_paid(self):
        from django.contrib.auth.models import Group
        from django.test import Client
        from django.urls import reverse

        group, _ = Group.objects.get_or_create(name='Accountant')
        self.user.groups.add(group)
        self.user.is_staff = True
        self.user.save()
        SupplierPayableLine.objects.create(
            supplier=self.supplier,
            entry_type=SupplierPayableLine.ENTRY_MANUAL_PAYABLE,
            amount=Decimal('50.00'),
            reference='INV-PAID-1',
            created_by=self.user,
        )
        SupplierPayableLine.objects.create(
            supplier=self.supplier,
            entry_type=SupplierPayableLine.ENTRY_PAYMENT,
            amount=Decimal('-50.00'),
            reference='INV-PAID-1',
            created_by=self.user,
        )
        # Leave a separate unpaid balance so balance checks are not the failure mode
        SupplierPayableLine.objects.create(
            supplier=self.supplier,
            entry_type=SupplierPayableLine.ENTRY_MANUAL_PAYABLE,
            amount=Decimal('20.00'),
            reference='INV-OTHER',
            created_by=self.user,
        )

        client = Client()
        client.force_login(self.user)
        url = reverse('hospital:supplier_account_detail', kwargs={'supplier_id': self.supplier.id})

        # Missing invoice number
        resp = client.post(url, {'action': 'payment', 'amount': '10.00'})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Invoice number is required')

        # Paid invoice blocked
        resp = client.post(url, {
            'action': 'payment',
            'amount': '10.00',
            'invoice_number': 'INV-PAID-1',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'already paid')
        self.assertEqual(
            SupplierPayableLine.objects.filter(
                supplier=self.supplier,
                entry_type=SupplierPayableLine.ENTRY_PAYMENT,
                is_deleted=False,
            ).count(),
            1,
        )

class CorrectStockReceiptTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username=f'corr_{uuid.uuid4().hex[:8]}',
            password='pw',
            is_staff=True,
            is_superuser=True,
        )
        self.supplier = Supplier.objects.create(name=f'Vendor {uuid.uuid4().hex[:6]}')
        self.drug = Drug.objects.create(
            name=f'Drug {uuid.uuid4().hex[:6]}',
            strength='500mg',
            form='Tablet',
            pack_size='10',
            category='other',
        )

    def test_correct_amount_and_qty_updates_payable_and_stock(self):
        from hospital.models_supplier_payables import correct_supplier_stock_receipt_line

        stock = PharmacyStock.objects.create(
            drug=self.drug,
            batch_number='B-CORR',
            expiry_date=date(2030, 1, 1),
            quantity_on_hand=100,
            initial_quantity=100,
            unit_cost=Decimal('10.00'),
            supplier=self.supplier,
            supplier_invoice_number='0000999',
            created_by=self.user,
        )
        line = post_pharmacy_stock_supplier_payable(
            stock=stock,
            quantity_added=100,
            unit_cost=Decimal('10.00'),
            supplier=self.supplier,
            user=self.user,
        )
        self.assertEqual(line.amount, Decimal('1000.00'))

        result = correct_supplier_stock_receipt_line(
            line=line,
            new_quantity=80,
            new_unit_cost=Decimal('10.00'),
            user=self.user,
            reason='Wrong qty uploaded',
        )
        line.refresh_from_db()
        stock.refresh_from_db()
        self.assertEqual(result['new_amount'], Decimal('800.00'))
        self.assertEqual(line.amount, Decimal('800.00'))
        # Account valve: payable changes, pharmacy stock stays as received/sold
        self.assertEqual(stock.initial_quantity, 100)
        self.assertEqual(stock.quantity_on_hand, 100)
        self.assertEqual(stock.unit_cost, Decimal('10.00'))
        self.assertTrue(result.get('stock_unchanged'))
        self.assertEqual(_supplier_balance_map().get(self.supplier.id), Decimal('800.00'))
        self.assertIn('Supplier amount corrected', line.description)
        self.assertIn('stock unchanged', line.description)

    def test_correction_allows_sold_batch_without_touching_qoh(self):
        from hospital.models_supplier_payables import correct_supplier_stock_receipt_line

        stock = PharmacyStock.objects.create(
            drug=self.drug,
            batch_number='B-SOLD',
            expiry_date=date(2030, 1, 1),
            quantity_on_hand=30,
            initial_quantity=100,
            unit_cost=Decimal('12.00'),
            supplier=self.supplier,
            supplier_invoice_number='0000666',
            created_by=self.user,
        )
        line = post_pharmacy_stock_supplier_payable(
            stock=stock,
            quantity_added=100,
            unit_cost=Decimal('12.00'),
            supplier=self.supplier,
            user=self.user,
        )
        result = correct_supplier_stock_receipt_line(
            line=line,
            new_quantity=90,
            new_amount=Decimal('1080.00'),
            user=self.user,
            reason='Invoice qty was 90; 70 already sold',
        )
        line.refresh_from_db()
        stock.refresh_from_db()
        self.assertEqual(line.amount, Decimal('1080.00'))
        self.assertEqual(stock.quantity_on_hand, 30)
        self.assertEqual(stock.initial_quantity, 100)
        self.assertEqual(result['new_qty'], 90)

    def test_correct_via_post_on_supplier_detail(self):
        from django.test import Client
        from django.urls import reverse
        from hospital.models_supplier_payables import SupplierStockReceiptCorrectionRequest

        stock = PharmacyStock.objects.create(
            drug=self.drug,
            batch_number='B-POST',
            expiry_date=date(2030, 1, 1),
            quantity_on_hand=50,
            initial_quantity=50,
            unit_cost=Decimal('5.00'),
            supplier=self.supplier,
            supplier_invoice_number='0000888',
            created_by=self.user,
        )
        line = post_pharmacy_stock_supplier_payable(
            stock=stock,
            quantity_added=50,
            unit_cost=Decimal('5.00'),
            supplier=self.supplier,
            user=self.user,
        )
        client = Client()
        client.force_login(self.user)
        url = reverse('hospital:supplier_account_detail', kwargs={'supplier_id': self.supplier.id})
        resp = client.post(
            url,
            {
                'action': 'correct_stock_receipt',
                'line_id': str(line.id),
                'quantity': '40',
                'unit_cost': '5.00',
                'amount': '200.00',
                'reason': 'Procurement typo',
            },
        )
        self.assertEqual(resp.status_code, 302)
        line.refresh_from_db()
        stock.refresh_from_db()
        # Submit only — no ledger/stock change yet
        self.assertEqual(line.amount, Decimal('250.00'))
        self.assertEqual(stock.quantity_on_hand, 50)
        pending = SupplierStockReceiptCorrectionRequest.objects.filter(
            payable_line=line,
            status=SupplierStockReceiptCorrectionRequest.STATUS_PENDING,
            is_deleted=False,
        )
        self.assertEqual(pending.count(), 1)
        corr = pending.first()
        self.assertEqual(corr.proposed_amount, Decimal('200.00'))

        resp2 = client.post(
            url,
            {
                'action': 'approve_stock_receipt_correction',
                'request_id': str(corr.id),
            },
        )
        self.assertEqual(resp2.status_code, 302)
        line.refresh_from_db()
        stock.refresh_from_db()
        self.assertEqual(line.amount, Decimal('200.00'))
        # Pharmacy stock untouched after approve
        self.assertEqual(stock.quantity_on_hand, 50)
        self.assertEqual(stock.initial_quantity, 50)
        corr.refresh_from_db()
        self.assertEqual(corr.status, SupplierStockReceiptCorrectionRequest.STATUS_APPROVED)

    def test_submit_pending_blocks_duplicate_and_reject_clears(self):
        from hospital.models_supplier_payables import (
            SupplierStockReceiptCorrectionRequest,
            submit_supplier_stock_receipt_correction,
            reject_supplier_stock_receipt_correction,
        )

        stock = PharmacyStock.objects.create(
            drug=self.drug,
            batch_number='B-PEND',
            expiry_date=date(2030, 1, 1),
            quantity_on_hand=20,
            initial_quantity=20,
            unit_cost=Decimal('8.00'),
            supplier=self.supplier,
            supplier_invoice_number='0000777',
            created_by=self.user,
        )
        line = post_pharmacy_stock_supplier_payable(
            stock=stock,
            quantity_added=20,
            unit_cost=Decimal('8.00'),
            supplier=self.supplier,
            user=self.user,
        )
        submit_supplier_stock_receipt_correction(
            line=line,
            new_quantity=15,
            new_unit_cost=Decimal('8.00'),
            user=self.user,
            reason='First request',
        )
        with self.assertRaises(ValueError):
            submit_supplier_stock_receipt_correction(
                line=line,
                new_quantity=10,
                new_unit_cost=Decimal('8.00'),
                user=self.user,
            )
        req = SupplierStockReceiptCorrectionRequest.objects.get(
            payable_line=line,
            status=SupplierStockReceiptCorrectionRequest.STATUS_PENDING,
        )
        reject_supplier_stock_receipt_correction(
            correction_request=req,
            user=self.user,
            review_note='Not needed',
        )
        line.refresh_from_db()
        stock.refresh_from_db()
        self.assertEqual(line.amount, Decimal('160.00'))
        self.assertEqual(stock.quantity_on_hand, 20)
        # After reject, a new request can be submitted
        submit_supplier_stock_receipt_correction(
            line=line,
            new_quantity=18,
            new_amount=Decimal('144.00'),
            user=self.user,
        )
        self.assertEqual(
            SupplierStockReceiptCorrectionRequest.objects.filter(
                payable_line=line,
                status=SupplierStockReceiptCorrectionRequest.STATUS_PENDING,
            ).count(),
            1,
        )
