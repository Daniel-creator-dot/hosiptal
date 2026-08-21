"""Apply deposit to Total Bill must reduce this bill's balance and available deposit."""
import uuid
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from hospital.models import Invoice, InvoiceLine, Payer, Patient, ServiceCode
from hospital.models_patient_deposits import DepositApplication, PatientDeposit
from hospital.services.deposit_payment_service import (
    apply_deposit_to_all_patient_invoices,
    get_patient_deposit_balance_display,
)
from hospital.utils_invoice_line import invoice_breakdown_rows_for_display

User = get_user_model()


@override_settings(ALLOWED_HOSTS=['*', 'testserver'])
class ApplyDepositToTotalBillTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username=f'depbill_{uuid.uuid4().hex[:8]}',
            password='testpass123',
            is_staff=True,
            is_superuser=True,
        )
        self.patient = Patient.objects.create(
            first_name='Deposit',
            last_name='Bill',
            mrn=f'PMC-DEPBILL-{uuid.uuid4().hex[:8]}',
        )
        self.payer = Payer.objects.create(
            name=f'Cash {uuid.uuid4().hex[:6]}',
            payer_type='cash',
        )
        self.client = Client()

    def _open_invoice(self, amount, description='Charge'):
        sc = ServiceCode.objects.create(
            code=f'DPB-{uuid.uuid4().hex[:8]}',
            description=description,
            category='test',
        )
        inv = Invoice.objects.create(
            patient=self.patient,
            encounter=None,
            payer=self.payer,
            status='issued',
        )
        InvoiceLine.objects.create(
            invoice=inv,
            service_code=sc,
            description=description,
            quantity=Decimal('1'),
            unit_price=amount,
            line_total=amount,
        )
        inv.update_totals()
        inv.refresh_from_db()
        return inv

    def test_apply_reduces_bill_balance_and_available_deposit(self):
        inv = self._open_invoice(Decimal('300.00'), 'Lab panel')
        PatientDeposit.objects.create(
            patient=self.patient,
            deposit_amount=Decimal('500.00'),
            available_balance=Decimal('500.00'),
            payment_method='cash',
            received_by=self.user,
            status='active',
        )
        self.assertEqual(get_patient_deposit_balance_display(self.patient), Decimal('500.00'))

        applied = apply_deposit_to_all_patient_invoices(
            self.patient, create_receipt=True, invoice_pks=[inv.pk]
        )
        self.assertEqual(applied, Decimal('300.00'))

        inv.refresh_from_db()
        self.assertEqual(inv.balance, Decimal('0.00'))
        self.assertEqual(get_patient_deposit_balance_display(self.patient), Decimal('200.00'))
        self.assertTrue(
            DepositApplication.objects.filter(invoice=inv, is_deleted=False).exists()
        )

        rows = invoice_breakdown_rows_for_display(inv, prefer_pharmacy_first=False)
        self.assertTrue(all(r.get('is_paid') for r in rows))

    def test_apply_only_targets_bill_invoice_not_older_off_bill(self):
        older = self._open_invoice(Decimal('400.00'), 'Old charge')
        on_bill = self._open_invoice(Decimal('100.00'), 'Bill charge')
        PatientDeposit.objects.create(
            patient=self.patient,
            deposit_amount=Decimal('100.00'),
            available_balance=Decimal('100.00'),
            payment_method='cash',
            received_by=self.user,
            status='active',
        )

        applied = apply_deposit_to_all_patient_invoices(
            self.patient, create_receipt=True, invoice_pks=[on_bill.pk]
        )
        self.assertEqual(applied, Decimal('100.00'))
        on_bill.refresh_from_db()
        older.refresh_from_db()
        self.assertEqual(on_bill.balance, Decimal('0.00'))
        self.assertEqual(older.balance, Decimal('400.00'))
        self.assertEqual(get_patient_deposit_balance_display(self.patient), Decimal('0.00'))

    def test_cashier_apply_deposit_post_updates_total_bill(self):
        inv = self._open_invoice(Decimal('250.00'), 'Consult')
        PatientDeposit.objects.create(
            patient=self.patient,
            deposit_amount=Decimal('250.00'),
            available_balance=Decimal('250.00'),
            payment_method='cash',
            received_by=self.user,
            status='active',
        )
        self.client.force_login(self.user)
        url = reverse('hospital:cashier_apply_deposit_to_bill', args=[self.patient.id])
        resp = self.client.post(url, follow=False)
        self.assertEqual(resp.status_code, 302)

        inv.refresh_from_db()
        self.assertEqual(inv.balance, Decimal('0.00'))
        self.assertEqual(get_patient_deposit_balance_display(self.patient), Decimal('0.00'))

        bill_url = reverse('hospital:cashier_patient_total_bill', args=[self.patient.id])
        page = self.client.get(bill_url)
        self.assertEqual(page.status_code, 200)
        # Fully paid — either no pending or zero outstanding
        bill_out = page.context.get('bill_outstanding')
        self.assertEqual(bill_out, Decimal('0.00'))
        self.assertEqual(page.context.get('patient_deposit_balance'), Decimal('0.00'))
