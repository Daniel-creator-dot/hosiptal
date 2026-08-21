"""Bill discount (combined payment) and waiver persistence."""
import uuid
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.contrib.auth.signals import user_logged_in
from django.core.exceptions import ValidationError
from django.test import Client, TestCase
from django.urls import reverse

from hospital.auth_session_utils import create_user_session
from hospital.models import Drug, Invoice, InvoiceLine, Payer, Patient, ServiceCode
from hospital.services.combined_bill_discount_service import (
    BillDiscountResult,
    distribute_combined_bill_discount_across_invoices,
)
from hospital.services.pharmacy_invoice_payment_link import (
    waive_invoice_lines_for_prescribe_sale_item,
)
from hospital.signals_login_tracking import track_successful_login
from hospital.views_centralized_cashier import _get_patient_pending_services_for_payment


def _open_invoice(patient, unit_price=Decimal('100.00')):
    payer = Payer.objects.create(name=f'Cash {uuid.uuid4().hex[:6]}', payer_type='cash')
    sc = ServiceCode.objects.create(
        code=f'DISC-{uuid.uuid4().hex[:8]}',
        description='Test service',
        category='test',
    )
    inv = Invoice.objects.create(
        patient=patient,
        encounter=None,
        payer=payer,
        status='issued',
    )
    InvoiceLine.objects.create(
        invoice=inv,
        service_code=sc,
        description='Consultation fee',
        quantity=Decimal('1'),
        unit_price=unit_price,
        line_total=unit_price,
    )
    inv.update_totals()
    inv.refresh_from_db()
    return inv


def _force_login_without_login_signals(client, user):
    user_logged_in.disconnect(track_successful_login)
    user_logged_in.disconnect(create_user_session)
    try:
        client.force_login(user)
    finally:
        user_logged_in.connect(track_successful_login)
        user_logged_in.connect(create_user_session)


class BillDiscountServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username=f'disc_{uuid.uuid4().hex[:8]}',
            password='testpass123',
        )
        self.patient = Patient.objects.create(
            first_name='Discount',
            last_name='Patient',
            mrn=f'PMC-DISC-{uuid.uuid4().hex[:8]}',
        )
        self.invoice = _open_invoice(self.patient, Decimal('100.00'))

    def test_discount_applies_when_gl_post_fails(self):
        with patch(
            'hospital.services.combined_bill_discount_service.post_patient_bill_discount_to_general_ledger',
            side_effect=ValidationError('GL unavailable'),
        ):
            result = distribute_combined_bill_discount_across_invoices(
                [self.invoice],
                Decimal('25.00'),
                patient=self.patient,
                user=self.user,
            )
        self.assertIsInstance(result, BillDiscountResult)
        self.assertEqual(result.applied, Decimal('25.00'))
        self.assertFalse(result.gl_posted)
        self.assertIn('GL unavailable', result.gl_error)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.balance, Decimal('75.00'))

    def test_discount_gl_success(self):
        with patch(
            'hospital.services.combined_bill_discount_service.post_patient_bill_discount_to_general_ledger',
            return_value=object(),
        ):
            result = distribute_combined_bill_discount_across_invoices(
                [self.invoice],
                Decimal('10.00'),
                patient=self.patient,
                user=self.user,
            )
        self.assertTrue(result.gl_posted)
        self.assertEqual(result.applied, Decimal('10.00'))


class CombinedPaymentDiscountViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username=f'cpay_{uuid.uuid4().hex[:8]}',
            password='testpass123',
            is_superuser=True,
        )
        _force_login_without_login_signals(self.client, self.user)
        self.patient = Patient.objects.create(
            first_name='Combined',
            last_name='Pay',
            mrn=f'PMC-CP-{uuid.uuid4().hex[:8]}',
        )
        self.invoice = _open_invoice(self.patient, Decimal('100.00'))

    def test_post_with_bill_discount_does_not_500_when_gl_fails(self):
        url = reverse(
            'hospital:cashier_process_patient_combined_payment',
            kwargs={'patient_id': self.patient.pk},
        )
        with patch(
            'hospital.services.combined_bill_discount_service.post_patient_bill_discount_to_general_ledger',
            side_effect=ValidationError('GL unavailable'),
        ):
            response = self.client.post(
                url,
                {
                    'bill_discount': '10.00',
                    'amount': '90.00',
                    'payment_method': 'cash',
                    'payment_idempotency_token': uuid.uuid4().hex,
                },
            )
        self.assertNotEqual(response.status_code, 500)
        self.assertIn(response.status_code, (200, 302))


class WaiverPersistenceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username=f'waive_{uuid.uuid4().hex[:8]}',
            password='testpass123',
            is_superuser=True,
        )
        self.client = Client()
        _force_login_without_login_signals(self.client, self.user)
        self.patient = Patient.objects.create(
            first_name='Waive',
            last_name='Patient',
            mrn=f'PMC-WV-{uuid.uuid4().hex[:8]}',
        )

    def test_waive_invoice_line_reduces_pending_total(self):
        inv = _open_invoice(self.patient, Decimal('80.00'))
        line = inv.lines.filter(is_deleted=False).first()
        self.assertGreater(inv.balance, Decimal('0'))
        url = reverse('hospital:waive_invoice_line')
        response = self.client.post(
            url,
            {
                'line_id': str(line.pk),
                'waiver_reason': 'Test waiver',
                'redirect_url': reverse(
                    'hospital:cashier_patient_total_bill',
                    kwargs={'patient_id': self.patient.pk},
                ),
            },
        )
        self.assertIn(response.status_code, (200, 302))
        inv.refresh_from_db()
        line.refresh_from_db()
        self.assertIsNotNone(line.waived_at)
        self.assertEqual(inv.balance, Decimal('0.00'))
        self.assertEqual(inv.status, 'paid')
        _, after = _get_patient_pending_services_for_payment(self.patient)
        self.assertEqual(after, Decimal('0.00'))

    def test_waive_one_line_on_multi_line_invoice_tallies(self):
        """Removing one line must leave invoice total = sum of remaining lines."""
        from hospital.views_centralized_cashier import _total_bill_services_to_display

        inv = _open_invoice(self.patient, Decimal('100.00'))
        sc2 = ServiceCode.objects.create(
            code=f'WV2-{uuid.uuid4().hex[:8]}',
            description='Second service',
            category='test',
        )
        InvoiceLine.objects.create(
            invoice=inv,
            service_code=sc2,
            description='Second line',
            quantity=Decimal('1'),
            unit_price=Decimal('50.00'),
            line_total=Decimal('50.00'),
        )
        inv.update_totals()
        inv.refresh_from_db()
        self.assertEqual(inv.total_amount, Decimal('150.00'))
        line_a = inv.lines.filter(description='Consultation fee').first()
        url = reverse('hospital:waive_invoice_line')
        response = self.client.post(
            url,
            {
                'line_id': str(line_a.pk),
                'waiver_reason': 'Remove one item',
                'redirect_url': reverse(
                    'hospital:cashier_patient_total_bill',
                    kwargs={'patient_id': self.patient.pk},
                ),
            },
        )
        self.assertIn(response.status_code, (200, 302))
        inv.refresh_from_db()
        self.assertEqual(inv.total_amount, Decimal('50.00'))
        self.assertEqual(inv.balance, Decimal('50.00'))
        remaining = inv.lines.filter(is_deleted=False, waived_at__isnull=True)
        self.assertEqual(
            sum(l.effective_line_total() for l in remaining),
            inv.total_amount,
        )
        services, total = _get_patient_pending_services_for_payment(self.patient)
        display = _total_bill_services_to_display(services)
        self.assertEqual(total, Decimal('50.00'))
        for row in display:
            bd_sum = sum((r.get('amount') or Decimal('0')) for r in (row.get('breakdown') or []))
            self.assertEqual(row['price'], bd_sum)

    def test_waive_prescribe_sale_item_syncs_invoice_line(self):
        from hospital.models_pharmacy_walkin import WalkInPharmacySale, WalkInPharmacySaleItem

        drug = Drug.objects.create(
            name=f'WaiveDrug {uuid.uuid4().hex[:6]}',
            strength='500mg',
            form='Tablet',
            pack_size='10',
            category='other',
            unit_price=Decimal('15.00'),
        )
        sale = WalkInPharmacySale.objects.create(
            customer_name=self.patient.full_name,
            patient=self.patient,
            customer_type='registered',
            total_amount=Decimal('30.00'),
            subtotal=Decimal('30.00'),
            amount_due=Decimal('30.00'),
        )
        item = WalkInPharmacySaleItem.objects.create(
            sale=sale,
            drug=drug,
            quantity=2,
            unit_price=Decimal('15.00'),
            line_total=Decimal('30.00'),
        )
        inv = _open_invoice(self.patient, Decimal('0.00'))
        sc = ServiceCode.objects.create(
            code=f'PS-{uuid.uuid4().hex[:8]}',
            description='Pharmacy',
            category='pharmacy',
        )
        inv_line = InvoiceLine.objects.create(
            invoice=inv,
            service_code=sc,
            description=f'{drug.name} {drug.strength} (Sale {sale.sale_number})',
            quantity=Decimal('2'),
            unit_price=Decimal('15.00'),
            line_total=Decimal('30.00'),
        )
        inv.update_totals()
        inv.refresh_from_db()
        self.assertEqual(inv.balance, Decimal('30.00'))

        if not hasattr(item, 'waived_at'):
            self.skipTest('WalkInPharmacySaleItem.waived_at migration not applied')

        n = waive_invoice_lines_for_prescribe_sale_item(
            item, waived_by_user=self.user, reason='Test line waive'
        )
        self.assertEqual(n, 1)
        inv_line.refresh_from_db()
        inv.refresh_from_db()
        self.assertIsNotNone(inv_line.waived_at)
        self.assertEqual(inv.balance, Decimal('0.00'))


class RemovePrescribeInvoiceSticksTests(TestCase):
    """Removing a prescribe invoice must drop the amount and not recreate on Total Bill reload."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_superuser(
            username=f'rem_{uuid.uuid4().hex[:8]}',
            email=f'rem_{uuid.uuid4().hex[:8]}@test.local',
            password='testpass123',
        )
        self.patient = Patient.objects.create(
            first_name='Remove',
            last_name='Stick',
            mrn=f'PMC-RS-{uuid.uuid4().hex[:8]}',
        )

    def test_remove_invoice_cancels_sale_and_amount_leaves_bill(self):
        from hospital.models_pharmacy_walkin import WalkInPharmacySale, WalkInPharmacySaleItem
        from hospital.services.pharmacy_walkin_service import WalkInPharmacyService
        from hospital.views_centralized_cashier import _total_bill_services_to_display

        drug = Drug.objects.create(
            name=f'RemDrug {uuid.uuid4().hex[:6]}',
            strength='0',
            form='Inj',
            pack_size='1',
            category='other',
            unit_price=Decimal('40.00'),
        )
        sale = WalkInPharmacySale.objects.create(
            customer_name=self.patient.full_name,
            patient=self.patient,
            customer_type='registered',
            total_amount=Decimal('40.00'),
            subtotal=Decimal('40.00'),
            amount_due=Decimal('40.00'),
        )
        WalkInPharmacySaleItem.objects.create(
            sale=sale,
            drug=drug,
            quantity=1,
            unit_price=Decimal('40.00'),
            line_total=Decimal('40.00'),
        )
        inv = WalkInPharmacyService.ensure_sale_invoice(sale, self.patient)
        self.assertIsNotNone(inv)
        inv.update_totals()
        inv.refresh_from_db()
        self.assertEqual(inv.balance, Decimal('40.00'))

        services, total = _get_patient_pending_services_for_payment(self.patient)
        self.assertEqual(total, Decimal('40.00'))

        user_logged_in.disconnect(track_successful_login, dispatch_uid=None)
        try:
            self.client.force_login(self.user)
            url = reverse('hospital:remove_invoice_from_bill')
            response = self.client.post(
                url,
                {
                    'invoice_id': str(inv.pk),
                    'redirect_url': reverse(
                        'hospital:cashier_patient_total_bill',
                        kwargs={'patient_id': self.patient.pk},
                    ),
                },
            )
        finally:
            user_logged_in.connect(track_successful_login)
        self.assertIn(response.status_code, (302, 200))

        inv.refresh_from_db()
        self.assertEqual(inv.status, 'cancelled')
        sale.refresh_from_db()
        self.assertIsNotNone(sale.waived_at)
        self.assertEqual(sale.payment_status, 'cancelled')

        # Reloading Total Bill must not recreate the charge
        again = WalkInPharmacyService.ensure_sale_invoice(sale, self.patient)
        self.assertIsNone(again)
        services2, total2 = _get_patient_pending_services_for_payment(self.patient)
        self.assertEqual(total2, Decimal('0.00'))
        display = _total_bill_services_to_display(services2)
        self.assertEqual(sum((s.get('price') or 0) for s in display), Decimal('0.00'))

    def test_waive_line_reduces_sale_and_bill_totals(self):
        from hospital.models_pharmacy_walkin import WalkInPharmacySale, WalkInPharmacySaleItem
        from hospital.services.pharmacy_walkin_service import WalkInPharmacyService

        drug_a = Drug.objects.create(
            name=f'LineA {uuid.uuid4().hex[:6]}',
            strength='10mg',
            form='Tab',
            pack_size='10',
            category='other',
            unit_price=Decimal('10.00'),
        )
        drug_b = Drug.objects.create(
            name=f'LineB {uuid.uuid4().hex[:6]}',
            strength='20mg',
            form='Tab',
            pack_size='10',
            category='other',
            unit_price=Decimal('20.00'),
        )
        sale = WalkInPharmacySale.objects.create(
            customer_name=self.patient.full_name,
            patient=self.patient,
            customer_type='registered',
            total_amount=Decimal('30.00'),
            subtotal=Decimal('30.00'),
            amount_due=Decimal('30.00'),
        )
        item_a = WalkInPharmacySaleItem.objects.create(
            sale=sale, drug=drug_a, quantity=1, unit_price=Decimal('10.00'), line_total=Decimal('10.00')
        )
        WalkInPharmacySaleItem.objects.create(
            sale=sale, drug=drug_b, quantity=1, unit_price=Decimal('20.00'), line_total=Decimal('20.00')
        )
        inv = WalkInPharmacyService.ensure_sale_invoice(sale, self.patient)
        inv.update_totals()
        self.assertEqual(inv.balance, Decimal('30.00'))

        if not hasattr(item_a, 'waived_at'):
            self.skipTest('WalkInPharmacySaleItem.waived_at migration not applied')

        user_logged_in.disconnect(track_successful_login, dispatch_uid=None)
        try:
            self.client.force_login(self.user)
            response = self.client.post(
                reverse('hospital:waive_prescribe_sale_line'),
                {
                    'sale_item_id': str(item_a.pk),
                    'waiver_reason': 'Remove one item',
                    'redirect_url': reverse(
                        'hospital:cashier_patient_total_bill',
                        kwargs={'patient_id': self.patient.pk},
                    ),
                },
            )
        finally:
            user_logged_in.connect(track_successful_login)
        self.assertIn(response.status_code, (302, 200))

        sale.refresh_from_db()
        self.assertEqual(sale.total_amount, Decimal('20.00'))
        inv.refresh_from_db()
        self.assertEqual(inv.balance, Decimal('20.00'))
        # ensure must not restore waived line
        WalkInPharmacyService.ensure_sale_invoice(sale, self.patient)
        inv.refresh_from_db()
        self.assertEqual(inv.balance, Decimal('20.00'))
        services, total = _get_patient_pending_services_for_payment(self.patient)
        self.assertEqual(total, Decimal('20.00'))


class PartialCombinedInvoiceLineDisplayTests(TestCase):
    """FIFO line remaining after partial payment on a multi-line invoice."""

    def setUp(self):
        self.user = User.objects.create_user(
            username=f'part_{uuid.uuid4().hex[:8]}',
            password='testpass123',
        )
        self.patient = Patient.objects.create(
            first_name='Partial',
            last_name='Pay',
            mrn=f'PMC-PP-{uuid.uuid4().hex[:8]}',
        )
        self.invoice = _open_invoice(self.patient, Decimal('100.00'))
        sc2 = ServiceCode.objects.create(
            code=f'PP2-{uuid.uuid4().hex[:8]}',
            description='Lab test',
            category='lab',
        )
        InvoiceLine.objects.create(
            invoice=self.invoice,
            service_code=sc2,
            description='Lab line',
            quantity=Decimal('1'),
            unit_price=Decimal('50.00'),
            line_total=Decimal('50.00'),
        )
        sc3 = ServiceCode.objects.create(
            code=f'PP3-{uuid.uuid4().hex[:8]}',
            description='Pharmacy item',
            category='pharmacy',
        )
        InvoiceLine.objects.create(
            invoice=self.invoice,
            service_code=sc3,
            description='Pharmacy line',
            quantity=Decimal('1'),
            unit_price=Decimal('50.00'),
            line_total=Decimal('50.00'),
        )
        self.invoice.update_totals()
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.total_amount, Decimal('200.00'))
        self.assertEqual(self.invoice.balance, Decimal('200.00'))

    def _allocate_partial(self, amount):
        from hospital.models_accounting import PaymentAllocation, Transaction

        trans = Transaction.objects.create(
            transaction_type='payment_received',
            invoice=self.invoice,
            patient=self.patient,
            amount=amount,
            payment_method='cash',
            processed_by=self.user,
            transaction_number=f'TXN-{uuid.uuid4().hex[:12]}',
        )
        PaymentAllocation.allocate_payment(trans, [(self.invoice, amount)])
        self.invoice.refresh_from_db()

    def test_fifo_line_remaining_after_partial_payment(self):
        from hospital.utils_invoice_line import invoice_line_remaining_balances

        self._allocate_partial(Decimal('100.00'))
        self.assertEqual(self.invoice.balance, Decimal('100.00'))

        rows = invoice_line_remaining_balances(self.invoice)
        self.assertEqual(len(rows), 3)
        self.assertTrue(rows[0]['is_fully_paid'])
        self.assertEqual(rows[0]['amount_remaining'], Decimal('0.00'))
        self.assertFalse(rows[1]['is_fully_paid'])
        self.assertEqual(rows[1]['amount_remaining'], Decimal('50.00'))
        self.assertFalse(rows[2]['is_fully_paid'])
        self.assertEqual(rows[2]['amount_remaining'], Decimal('50.00'))
        self.assertEqual(
            sum(r['amount_remaining'] for r in rows),
            self.invoice.balance,
        )

    def test_total_bill_breakdown_sums_to_invoice_balance(self):
        from hospital.views_centralized_cashier import _total_bill_services_to_display

        self._allocate_partial(Decimal('100.00'))
        services, total = _get_patient_pending_services_for_payment(self.patient)
        display = _total_bill_services_to_display(services)
        self.assertEqual(total, Decimal('100.00'))
        self.assertEqual(len(display), 1)
        row = display[0]
        self.assertEqual(row['price'], Decimal('100.00'))
        self.assertTrue(row.get('invoice_partially_paid'))
        bd_sum = sum(
            (r.get('amount') or Decimal('0'))
            for r in (row.get('breakdown') or [])
            if not r.get('is_paid')
        )
        self.assertEqual(bd_sum, self.invoice.balance)
        paid_lines = [r for r in row['breakdown'] if r.get('is_paid')]
        self.assertEqual(len(paid_lines), 1)
        self.assertEqual(paid_lines[0]['description'], 'Consultation fee')

    def test_open_balance_due_when_total_amount_exceeds_line_sum(self):
        """Row price must follow invoice balance, not inflated invoice.total_amount."""
        from hospital.utils_invoice_line import invoice_open_balance_due
        from hospital.views_centralized_cashier import _total_bill_services_to_display

        self._allocate_partial(Decimal('100.00'))
        # Simulate stale header total (e.g. discount/waiver drift on total_amount only)
        Invoice.objects.filter(pk=self.invoice.pk).update(total_amount=Decimal('500.00'))
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.balance, Decimal('100.00'))
        self.assertEqual(invoice_open_balance_due(self.invoice), Decimal('100.00'))

        services, total = _get_patient_pending_services_for_payment(self.patient)
        display = _total_bill_services_to_display(services)
        self.assertEqual(total, Decimal('100.00'))
        self.assertEqual(display[0]['price'], Decimal('100.00'))
        unpaid_sum = sum(
            (r.get('amount') or Decimal('0'))
            for r in (display[0].get('breakdown') or [])
            if not r.get('is_paid')
        )
        self.assertEqual(unpaid_sum, Decimal('100.00'))

    def test_registration_fee_paid_not_earlier_lab(self):
        """
        GHS 50 paid after Registration Fee is added must mark Registration paid,
        not an earlier lab line (Atta Duodu-style front-desk collection).
        """
        from datetime import timedelta
        from django.utils import timezone
        from hospital.models_accounting import PaymentReceipt, Transaction
        from hospital.utils_invoice_line import invoice_breakdown_rows_for_display

        lab_sc = ServiceCode.objects.create(
            code=f'LAB-REG-{uuid.uuid4().hex[:6]}',
            description='URINE RE',
            category='lab',
        )
        inv = _open_invoice(self.patient, Decimal('158.00'))
        # Backdate consultation so it predates lab
        consult = inv.lines.first()
        t0 = timezone.now() - timedelta(hours=2)
        InvoiceLine.objects.filter(pk=consult.pk).update(created=t0)

        lab = InvoiceLine.objects.create(
            invoice=inv,
            service_code=lab_sc,
            description='URINE RE',
            quantity=Decimal('1'),
            unit_price=Decimal('65.00'),
            line_total=Decimal('65.00'),
        )
        InvoiceLine.objects.filter(pk=lab.pk).update(created=t0 + timedelta(minutes=20))

        # First payment: consultation only (before registration exists)
        pay1 = t0 + timedelta(minutes=30)
        t1 = Transaction.objects.create(
            transaction_type='payment_received',
            invoice=inv,
            patient=self.patient,
            amount=Decimal('158.00'),
            payment_method='cash',
            processed_by=self.user,
            transaction_number=f'TXN-{uuid.uuid4().hex[:12]}',
        )
        r1 = PaymentReceipt.objects.create(
            receipt_number=f'RCP-T1-{uuid.uuid4().hex[:10]}',
            transaction=t1,
            invoice=inv,
            patient=self.patient,
            amount_paid=Decimal('158.00'),
            payment_method='cash',
            received_by=self.user,
            notes=f'Payment for Invoice {inv.invoice_number}',
        )
        PaymentReceipt.objects.filter(pk=r1.pk).update(created=pay1)
        Transaction.objects.filter(pk=t1.pk).update(created=pay1)

        reg_sc = ServiceCode.objects.create(
            code=f'REG-{uuid.uuid4().hex[:6]}',
            description='REGISTRATION',
            category='registration',
        )
        reg = InvoiceLine.objects.create(
            invoice=inv,
            service_code=reg_sc,
            description='Registration Fee',
            quantity=Decimal('1'),
            unit_price=Decimal('50.00'),
            line_total=Decimal('50.00'),
        )
        InvoiceLine.objects.filter(pk=reg.pk).update(created=pay1 + timedelta(minutes=1))

        t2 = Transaction.objects.create(
            transaction_type='payment_received',
            invoice=inv,
            patient=self.patient,
            amount=Decimal('50.00'),
            payment_method='cash',
            processed_by=self.user,
            transaction_number=f'TXN-{uuid.uuid4().hex[:12]}',
        )
        r2 = PaymentReceipt.objects.create(
            receipt_number=f'RCP-T2-{uuid.uuid4().hex[:10]}',
            transaction=t2,
            invoice=inv,
            patient=self.patient,
            amount_paid=Decimal('50.00'),
            payment_method='cash',
            received_by=self.user,
            notes=f'Payment for Invoice {inv.invoice_number}',
        )
        pay2 = pay1 + timedelta(minutes=2)
        PaymentReceipt.objects.filter(pk=r2.pk).update(created=pay2)
        Transaction.objects.filter(pk=t2.pk).update(created=pay2)

        inv.update_totals()
        inv.refresh_from_db()
        self.assertEqual(inv.amount_paid, Decimal('208.00'))

        rows = invoice_breakdown_rows_for_display(inv, prefer_pharmacy_first=False)
        by_desc = {r['description']: r for r in rows}
        self.assertTrue(by_desc['Consultation fee']['is_paid'])
        self.assertEqual(by_desc['Consultation fee']['amount'], Decimal('0.00'))
        self.assertTrue(by_desc['Registration Fee']['is_paid'])
        self.assertEqual(by_desc['Registration Fee']['amount'], Decimal('0.00'))
        self.assertFalse(by_desc['URINE RE']['is_paid'])
        self.assertEqual(by_desc['URINE RE']['amount'], Decimal('65.00'))
