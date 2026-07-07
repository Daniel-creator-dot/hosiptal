"""Regression: Patient Bills list must not inflate totals with patient-wide deposit receipts."""
import uuid
from decimal import Decimal

from django.contrib.auth.models import User
from django.contrib.auth.signals import user_logged_in
from django.test import Client, TestCase
from django.urls import reverse

from hospital.models import Invoice, InvoiceLine, Payer, Patient, ServiceCode
from hospital.signals_login_tracking import track_successful_login
from hospital.services.deposit_payment_service import deposit_amount_applied_for_pending_services_list
from hospital.views_centralized_cashier import _get_patient_pending_services_for_payment


class DepositAppliedPendingServicesListTests(TestCase):
    def test_empty_services_returns_zero(self):
        self.assertEqual(deposit_amount_applied_for_pending_services_list([]), Decimal('0.00'))
        self.assertEqual(deposit_amount_applied_for_pending_services_list(None), Decimal('0.00'))

    def test_only_invoices_on_list_count_toward_deposit_sum(self):
        payer = Payer.objects.create(name='Cash PB', payer_type='cash')
        patient = Patient.objects.create(
            first_name='Dep',
            last_name='ScopeTest',
            mrn=f'PMC-PB-{uuid.uuid4().hex[:8]}',
        )
        sc = ServiceCode.objects.create(
            code=f'PB-SC-{uuid.uuid4().hex[:8]}',
            description='Line',
            category='test',
        )
        inv_paid = Invoice.objects.create(
            patient=patient,
            encounter=None,
            payer=payer,
            status='issued',
        )
        InvoiceLine.objects.create(
            invoice=inv_paid,
            service_code=sc,
            description='Old paid',
            quantity=Decimal('1'),
            unit_price=Decimal('2000.00'),
            line_total=Decimal('2000.00'),
        )
        inv_paid.update_totals()
        inv_paid.refresh_from_db()
        user = User.objects.create_user(username=f'u_{uuid.uuid4().hex[:8]}', password='x')
        inv_paid.mark_as_paid(
            amount=Decimal('2000.00'),
            payment_method='deposit',
            processed_by=user,
            validate=False,
        )
        inv_paid.refresh_from_db()
        self.assertLessEqual(inv_paid.balance, Decimal('0.00'))

        sc2 = ServiceCode.objects.create(
            code=f'PB-SC2-{uuid.uuid4().hex[:8]}',
            description='Line2',
            category='test',
        )
        inv_open = Invoice.objects.create(
            patient=patient,
            encounter=None,
            payer=payer,
            status='issued',
        )
        InvoiceLine.objects.create(
            invoice=inv_open,
            service_code=sc2,
            description='Open',
            quantity=Decimal('1'),
            unit_price=Decimal('100.00'),
            line_total=Decimal('100.00'),
        )
        inv_open.update_totals()
        inv_open.refresh_from_db()
        self.assertGreater(inv_open.balance, 0)

        services, total = _get_patient_pending_services_for_payment(patient)
        self.assertEqual(total, inv_open.balance)

        deposit_on_pending_only = deposit_amount_applied_for_pending_services_list(services)
        self.assertEqual(
            deposit_on_pending_only,
            Decimal('0.00'),
            'Deposit on a paid invoice must not be attributed to another open invoice on the list',
        )


class CashierPatientBillsViewTotalsTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username=f'cashier_pb_{uuid.uuid4().hex[:8]}',
            password='test-pass-123',
            is_superuser=True,
        )
        self.payer = Payer.objects.create(name='Cash PB View', payer_type='cash')
        suffix = uuid.uuid4().hex[:8]
        self.patient = Patient.objects.create(
            first_name='ListTot',
            last_name=f'BillsZ{suffix}',
            mrn=f'PMC-LT-{suffix}',
        )

    def test_patient_bills_initial_total_matches_pending_row_sum_not_patient_wide_deposit(self):
        sc = ServiceCode.objects.create(
            code=f'PBV-{uuid.uuid4().hex[:8]}',
            description='Paid line',
            category='test',
        )
        inv_paid = Invoice.objects.create(
            patient=self.patient,
            encounter=None,
            payer=self.payer,
            status='issued',
        )
        InvoiceLine.objects.create(
            invoice=inv_paid,
            service_code=sc,
            description='Settled',
            quantity=Decimal('1'),
            unit_price=Decimal('2000.00'),
            line_total=Decimal('2000.00'),
        )
        inv_paid.update_totals()
        inv_paid.mark_as_paid(
            amount=Decimal('2000.00'),
            payment_method='deposit',
            processed_by=self.user,
            validate=False,
        )

        sc2 = ServiceCode.objects.create(
            code=f'PBV2-{uuid.uuid4().hex[:8]}',
            description='Open line',
            category='test',
        )
        inv_open = Invoice.objects.create(
            patient=self.patient,
            encounter=None,
            payer=self.payer,
            status='issued',
        )
        InvoiceLine.objects.create(
            invoice=inv_open,
            service_code=sc2,
            description='Due',
            quantity=Decimal('1'),
            unit_price=Decimal('100.00'),
            line_total=Decimal('100.00'),
        )
        inv_open.update_totals()
        inv_open.refresh_from_db()

        user_logged_in.disconnect(track_successful_login, dispatch_uid=None)
        try:
            self.client.force_login(self.user)
            url = reverse('hospital:cashier_patient_bills')
            response = self.client.get(url, {'search': self.patient.last_name})
        finally:
            user_logged_in.connect(track_successful_login)
        self.assertEqual(response.status_code, 200)
        bills = response.context['patients_bills']
        self.assertEqual(len(bills), 1, 'Expected one patient row for search')
        row = bills[0]
        self.assertEqual(row['total'], inv_open.balance)
        self.assertEqual(row['initial_total'], inv_open.balance)
        self.assertEqual(row['deposit_applied_to_bill'], Decimal('0.00'))
