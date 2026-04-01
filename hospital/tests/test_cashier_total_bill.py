"""Regression tests for centralized cashier total-bill view."""
import uuid
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from hospital.models import Invoice, InvoiceLine, Payer, Patient, ServiceCode
from hospital.views_centralized_cashier import _get_patient_pending_services_for_payment


class CashierPatientTotalBillViewTests(TestCase):
    """GET /hms/cashier/central/patient/<uuid>/total-bill/ must not raise (e.g. UnboundLocalError on Invoice)."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='cashier_total_bill_test',
            password='test-pass-123',
            is_superuser=True,
        )
        self.patient = Patient.objects.create(
            first_name='Test',
            last_name='Patient',
            mrn=f'PMC-TB-{uuid.uuid4().hex[:8]}',
        )

    def test_get_total_bill_with_filter_date_returns_200(self):
        self.client.force_login(self.user)
        url = reverse('hospital:cashier_patient_total_bill', kwargs={'patient_id': self.patient.pk})
        response = self.client.get(url, {'filter_date': '2026-03-23'})
        self.assertEqual(response.status_code, 200)

    def test_pending_services_does_not_double_count_invoice_and_lines(self):
        """Open invoice must count once (balance), not invoice + each line again."""
        payer = Payer.objects.create(name='Cash Test', payer_type='cash')
        sc = ServiceCode.objects.create(
            code=f'TB-LINE-{uuid.uuid4().hex[:8]}',
            description='Test line',
            category='test',
        )
        inv = Invoice.objects.create(
            patient=self.patient,
            encounter=None,
            payer=payer,
            status='issued',
        )
        InvoiceLine.objects.create(
            invoice=inv,
            service_code=sc,
            description='Service A',
            quantity=Decimal('1'),
            unit_price=Decimal('100.00'),
            line_total=Decimal('100.00'),
        )
        InvoiceLine.objects.create(
            invoice=inv,
            service_code=ServiceCode.objects.create(
                code=f'TB-LINE2-{uuid.uuid4().hex[:8]}',
                description='Service B',
                category='test',
            ),
            description='Service B',
            quantity=Decimal('1'),
            unit_price=Decimal('50.00'),
            line_total=Decimal('50.00'),
        )
        inv.update_totals()
        inv.refresh_from_db()
        self.assertGreater(inv.balance, 0)

        services, total = _get_patient_pending_services_for_payment(self.patient)
        invoice_rows = [s for s in services if s.get('type') == 'invoice']
        line_rows = [s for s in services if s.get('type') == 'invoice_line']
        self.assertEqual(len(invoice_rows), 1, 'Expected one aggregate row per open invoice')
        self.assertEqual(len(line_rows), 0, 'Per-line rows must not duplicate invoice balance')
        self.assertEqual(total, inv.balance)
