"""Regression tests for centralized cashier total-bill view."""
import uuid
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client, SimpleTestCase, TestCase
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


class MedicalReportAddableServicesTests(SimpleTestCase):
    def test_medical_report_prices(self):
        from hospital.views_centralized_cashier import ADDABLE_SERVICES, SERVICE_CODE_MAP

        by_code = {row[0]: row for row in ADDABLE_SERVICES}
        expected = {
            'medical_report_school': ('Medical Report (School)', Decimal('400.00'), 'RPT-SCHOOL'),
            'medical_report_gp': ('Medical Report (GP)', Decimal('600.00'), 'RPT-GP'),
            'medical_report_extensive': ('Medical Report (Extensive)', Decimal('800.00'), 'RPT-EXT'),
            'medical_report_international': ('Medical Report (International)', Decimal('1200.00'), 'RPT-INTL'),
        }
        for key, (label, amount, billing_code) in expected.items():
            self.assertIn(key, by_code)
            self.assertEqual(by_code[key][1], label)
            self.assertEqual(by_code[key][2], amount)
            self.assertEqual(by_code[key][3], amount)
            self.assertEqual(SERVICE_CODE_MAP[key], billing_code)


class MedicalReportFrontDeskRequestTests(TestCase):
    def setUp(self):
        from django.contrib.auth.models import Group
        from django.contrib.auth.signals import user_logged_in

        from hospital.auth_session_utils import create_user_session
        from hospital.models import Department, Staff
        from hospital.signals_login_tracking import track_successful_login

        user_logged_in.disconnect(track_successful_login)
        user_logged_in.disconnect(create_user_session)

        self.client = Client()
        self.superuser = User.objects.create_user(
            username=f'rpt_admin_{uuid.uuid4().hex[:8]}',
            password='test-pass-123',
            is_superuser=True,
            is_staff=True,
        )
        self.reception_user = User.objects.create_user(
            username=f'rpt_fd_{uuid.uuid4().hex[:8]}',
            password='test-pass-123',
            is_staff=True,
        )
        group, _ = Group.objects.get_or_create(name='Receptionist')
        self.reception_user.groups.add(group)
        dept = Department.objects.create(
            name=f'Front Desk {uuid.uuid4().hex[:4]}',
            code=f'FD{uuid.uuid4().hex[:4].upper()}',
        )
        Staff.objects.create(
            user=self.reception_user,
            profession='receptionist',
            employee_id=f'R{uuid.uuid4().hex[:6].upper()}',
            department=dept,
        )
        self.patient = Patient.objects.create(
            first_name='Report',
            last_name='Patient',
            mrn=f'PMC-RPT-{uuid.uuid4().hex[:8]}',
        )

    def test_request_form_lists_medical_reports(self):
        self.client.force_login(self.superuser)
        url = reverse('hospital:cashier_add_manual_payment')
        response = self.client.get(url, {'focus': 'medical_report'})
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('Medical Report', content)
        self.assertIn('medical_report_school', content)
        self.assertContains(response, 'School')
        self.assertContains(response, 'International')

    def test_short_add_manual_payment_url_opens_report_form(self):
        """Front-desk sidebar used /hms/cashier/add-manual-payment/ (without /central/)."""
        self.client.force_login(self.reception_user)
        response = self.client.get('/hms/cashier/add-manual-payment/', {'focus': 'medical_report'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Medical Report')
        self.assertContains(response, 'Send to Cashier')

    def test_charge_only_creates_pending_payment_request(self):
        from hospital.models import Invoice
        from hospital.models_workflow import PaymentRequest

        self.client.force_login(self.superuser)
        url = reverse('hospital:cashier_add_manual_payment')
        response = self.client.post(url, {
            'patient_id': str(self.patient.pk),
            'service_type': 'medical_report_school',
            'amount': '400.00',
            'charge_only': '1',
            'payment_method': 'cash',
        })
        self.assertEqual(response.status_code, 302)
        invoices = Invoice.objects.filter(patient=self.patient, is_deleted=False)
        self.assertEqual(invoices.count(), 1)
        invoice = invoices.get()
        self.assertEqual(invoice.status, 'issued')
        pr = PaymentRequest.objects.filter(patient=self.patient, invoice=invoice, is_deleted=False)
        self.assertEqual(pr.count(), 1)
        self.assertEqual(pr.get().requested_amount, Decimal('400.00'))
        self.assertEqual(pr.get().status, 'pending')
        line = invoice.lines.filter(is_deleted=False).first()
        self.assertIsNotNone(line)
        self.assertIn('Medical Report (School)', line.description)
        self.assertEqual(line.service_code.code, 'RPT-SCHOOL')

    def test_front_desk_request_is_always_charge_only(self):
        from hospital.models import Invoice
        from hospital.models_accounting import PaymentReceipt
        from hospital.models_workflow import PaymentRequest

        self.client.force_login(self.reception_user)
        url = reverse('hospital:cashier_add_manual_payment')
        response = self.client.post(url, {
            'patient_id': str(self.patient.pk),
            'service_type': 'medical_report_gp',
            'amount': '600.00',
            'payment_method': 'cash',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Invoice.objects.filter(patient=self.patient, is_deleted=False).count(), 1)
        self.assertEqual(PaymentRequest.objects.filter(patient=self.patient, is_deleted=False).count(), 1)
        self.assertEqual(PaymentReceipt.objects.filter(patient=self.patient, is_deleted=False).count(), 0)

    def test_front_desk_charges_page_lists_reports(self):
        self.client.force_login(self.reception_user)
        response = self.client.get(reverse('hospital:frontdesk_service_charges'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Medical Report (School)')
        self.assertContains(response, 'RPT-INTL')
        self.assertContains(response, 'Request Medical Report')

