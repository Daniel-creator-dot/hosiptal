"""Management reports: billed revenue by ServiceCode (invoice lines)."""
import uuid
from datetime import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.utils import timezone

from hospital.models import Invoice, InvoiceLine, Payer, Patient, ServiceCode

User = get_user_model()


class ManagementServiceRevenueTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_superuser(
            username='mgmtrep_admin',
            email='a@example.com',
            password='pass',
        )
        self.staff = User.objects.create_user(
            username='mgmtrep_staff',
            email='s@example.com',
            password='pass',
        )

    def _issue_date(self):
        return timezone.make_aware(datetime(2026, 4, 10, 10, 0, 0))

    def test_superuser_sees_aggregated_billed_and_excludes_waived(self):
        patient = Patient.objects.create(
            first_name='M',
            last_name='R',
            mrn=f'MR-{uuid.uuid4().hex[:8]}',
        )
        payer = Payer.objects.create(name='Cash MR', payer_type='cash')
        sc_a = ServiceCode.objects.create(
            code=f'MR-A-{uuid.uuid4().hex[:6]}',
            description='Alpha svc',
            category='Lab',
        )
        sc_b = ServiceCode.objects.create(
            code=f'MR-B-{uuid.uuid4().hex[:6]}',
            description='Beta svc',
            category='Pharmacy',
        )
        sc_w = ServiceCode.objects.create(
            code=f'MR-W-{uuid.uuid4().hex[:6]}',
            description='Waived svc',
            category='Other',
        )
        inv = Invoice.objects.create(
            patient=patient,
            encounter=None,
            payer=payer,
            status='issued',
            issued_at=self._issue_date(),
        )
        InvoiceLine.objects.create(
            invoice=inv,
            service_code=sc_a,
            description='Alpha svc',
            quantity=Decimal('1'),
            unit_price=Decimal('100.00'),
            line_total=Decimal('100.00'),
        )
        InvoiceLine.objects.create(
            invoice=inv,
            service_code=sc_b,
            description='Beta svc',
            quantity=Decimal('2'),
            unit_price=Decimal('50.00'),
            line_total=Decimal('100.00'),
        )
        InvoiceLine.objects.create(
            invoice=inv,
            service_code=sc_w,
            description='Waived',
            quantity=Decimal('1'),
            unit_price=Decimal('999.00'),
            line_total=Decimal('999.00'),
            waived_at=timezone.now(),
        )
        inv.update_totals()
        inv.refresh_from_db()

        self.client.force_login(self.admin)
        url = (
            '/hms/accountant/management-reports/service-revenue/'
            '?date_from=2026-04-01&date_to=2026-04-30'
        )
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, sc_a.code)
        self.assertContains(resp, sc_b.code)
        self.assertNotContains(resp, sc_w.code)
        self.assertContains(resp, '200.00')

    def test_payer_filter_nhis(self):
        patient = Patient.objects.create(
            first_name='N',
            last_name='H',
            mrn=f'NH-{uuid.uuid4().hex[:8]}',
        )
        cash_p = Payer.objects.create(name='Cash NH', payer_type='cash')
        nhis_p = Payer.objects.create(name='NHIS NH', payer_type='nhis')
        sc = ServiceCode.objects.create(
            code=f'NH-SC-{uuid.uuid4().hex[:6]}',
            description='Test',
            category='X',
        )
        inv_cash = Invoice.objects.create(
            patient=patient,
            encounter=None,
            payer=cash_p,
            status='issued',
            issued_at=self._issue_date(),
        )
        InvoiceLine.objects.create(
            invoice=inv_cash,
            service_code=sc,
            description='Line',
            quantity=Decimal('1'),
            unit_price=Decimal('10.00'),
            line_total=Decimal('10.00'),
        )
        inv_cash.update_totals()

        inv_nhis = Invoice.objects.create(
            patient=patient,
            encounter=None,
            payer=nhis_p,
            status='issued',
            issued_at=self._issue_date(),
        )
        InvoiceLine.objects.create(
            invoice=inv_nhis,
            service_code=sc,
            description='Line',
            quantity=Decimal('1'),
            unit_price=Decimal('50.00'),
            line_total=Decimal('50.00'),
        )
        inv_nhis.update_totals()

        self.client.force_login(self.admin)
        url = (
            '/hms/accountant/management-reports/service-revenue/'
            '?date_from=2026-04-01&date_to=2026-04-30&payer_type=nhis'
        )
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, '50.00')
        self.assertNotContains(resp, '10.00')

    def test_non_finance_user_forbidden(self):
        self.client.force_login(self.staff)
        resp = self.client.get('/hms/accountant/management-reports/')
        self.assertEqual(resp.status_code, 403)

    def test_revenue_streams_requires_finance_access(self):
        self.client.force_login(self.staff)
        resp = self.client.get('/hms/accounting/revenue-streams/')
        self.assertIn(resp.status_code, (302, 403))
