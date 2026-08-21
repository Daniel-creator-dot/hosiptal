"""NHIS lab/scan panel: doctor search filter, cash billing, cashier still sees all."""
import uuid
from decimal import Decimal

from django.contrib.auth.models import User
from django.contrib.auth.signals import user_logged_in
from django.test import Client, TestCase
from django.urls import reverse

from hospital.auth_session_utils import create_user_session
from hospital.models import (
    Department,
    Encounter,
    Invoice,
    InvoiceLine,
    LabTest,
    Patient,
    Payer,
    ServiceCode,
    Staff,
)
from hospital.models_advanced import ImagingCatalog
from hospital.services.nhis_drug_formulary import (
    nhis_uncovered_patient_pay_reason,
    restrict_nhis_covered_queryset,
)
from hospital.signals_login_tracking import track_successful_login


def _force_login_without_login_signals(client, user):
    user_logged_in.disconnect(track_successful_login)
    user_logged_in.disconnect(create_user_session)
    try:
        client.force_login(user)
    finally:
        user_logged_in.connect(track_successful_login)
        user_logged_in.connect(create_user_session)


class NhisLabImagingServiceTests(TestCase):
    def setUp(self):
        suf = uuid.uuid4().hex[:8]
        self.nhis_payer = Payer.objects.create(name=f'NHIS {suf}', payer_type='nhis')
        self.cash_payer = Payer.objects.create(name=f'Cash {suf}', payer_type='cash')
        self.nhis_lab = LabTest.objects.create(
            code=f'NL{suf[:6]}',
            name=f'NhisFbc{suf}',
            specimen_type='Blood',
            price=Decimal('20.00'),
            nhis_covered=True,
        )
        self.cash_lab = LabTest.objects.create(
            code=f'CL{suf[:6]}',
            name=f'CashOnlyLab{suf}',
            specimen_type='Blood',
            price=Decimal('80.00'),
            nhis_covered=False,
        )
        self.nhis_scan = ImagingCatalog.objects.create(
            code=f'NS{suf[:6]}',
            name=f'NhisXray{suf}',
            modality='xray',
            price=Decimal('30.00'),
            nhis_covered=True,
        )
        self.cash_scan = ImagingCatalog.objects.create(
            code=f'CS{suf[:6]}',
            name=f'CashOnlyCt{suf}',
            modality='ct',
            price=Decimal('250.00'),
            nhis_covered=False,
        )

    def test_queryset_filters_labs_and_scans_for_nhis_only(self):
        nhis_labs = restrict_nhis_covered_queryset(LabTest.objects.all(), self.nhis_payer)
        self.assertIn(self.nhis_lab, nhis_labs)
        self.assertNotIn(self.cash_lab, nhis_labs)

        cash_labs = restrict_nhis_covered_queryset(LabTest.objects.all(), self.cash_payer)
        self.assertIn(self.nhis_lab, cash_labs)
        self.assertIn(self.cash_lab, cash_labs)

        nhis_scans = restrict_nhis_covered_queryset(ImagingCatalog.objects.all(), self.nhis_payer)
        self.assertIn(self.nhis_scan, nhis_scans)
        self.assertNotIn(self.cash_scan, nhis_scans)

    def test_uncovered_reason_only_for_nhis(self):
        self.assertIn('cash', nhis_uncovered_patient_pay_reason(
            payer=self.nhis_payer, lab_test=self.cash_lab
        ).lower())
        self.assertEqual(
            nhis_uncovered_patient_pay_reason(payer=self.nhis_payer, lab_test=self.nhis_lab),
            '',
        )
        self.assertEqual(
            nhis_uncovered_patient_pay_reason(payer=self.cash_payer, lab_test=self.cash_lab),
            '',
        )
        self.assertIn('cash', nhis_uncovered_patient_pay_reason(
            payer=self.nhis_payer, imaging_catalog=self.cash_scan
        ).lower())


class NhisLabImagingSearchAndBillingTests(TestCase):
    def setUp(self):
        suf = uuid.uuid4().hex[:8]
        self.dept = Department.objects.create(name=f'NhisLabDept{suf}', code=f'L{suf[:4]}')
        self.doctor_user = User.objects.create_user(
            username=f'doc_lab_{suf}',
            password='test-pass-123',
        )
        self.doctor = Staff.objects.create(
            user=self.doctor_user,
            profession='doctor',
            department=self.dept,
        )
        self.cashier_user = User.objects.create_superuser(
            username=f'cash_lab_{suf}',
            email=f'cash_{suf}@example.com',
            password='test-pass-123',
        )
        self.nhis_payer = Payer.objects.create(
            name=f'NHIS Scheme {suf}',
            payer_type='nhis',
            is_active=True,
        )
        self.patient = Patient.objects.create(
            first_name='Nhis',
            last_name=f'LabPat{suf}',
            mrn=f'PMC-NHLAB-{suf}',
            primary_insurance=self.nhis_payer,
        )
        self.cash_patient = Patient.objects.create(
            first_name='Cash',
            last_name=f'LabPat{suf}',
            mrn=f'PMC-CASHLAB-{suf}',
        )
        self.encounter = Encounter.objects.create(
            patient=self.patient,
            encounter_type='outpatient',
            status='active',
            chief_complaint='Fever',
            provider=self.doctor,
        )
        self.cash_encounter = Encounter.objects.create(
            patient=self.cash_patient,
            encounter_type='outpatient',
            status='active',
            chief_complaint='Cough',
            provider=self.doctor,
        )
        unique = suf[:6]
        self.nhis_lab = LabTest.objects.create(
            code=f'NL{unique}',
            name=f'NhisMps{unique}',
            specimen_type='Blood',
            price=Decimal('15.00'),
            nhis_covered=True,
        )
        self.private_lab = LabTest.objects.create(
            code=f'PL{unique}',
            name=f'NhisMpsPriv{unique}',
            specimen_type='Blood',
            price=Decimal('90.00'),
            nhis_covered=False,
        )
        self.nhis_scan = ImagingCatalog.objects.create(
            code=f'NX{unique}',
            name=f'NhisChest{unique}',
            modality='xray',
            price=Decimal('40.00'),
            nhis_covered=True,
        )
        self.private_scan = ImagingCatalog.objects.create(
            code=f'PX{unique}',
            name=f'NhisChestPriv{unique}',
            modality='xray',
            price=Decimal('120.00'),
            nhis_covered=False,
        )
        self.client = Client()
        _force_login_without_login_signals(self.client, self.doctor_user)

    def test_lab_autocomplete_nhis_visit_only_returns_nhis_tests(self):
        url = reverse('hospital:api_autocomplete_lab_tests')
        resp = self.client.get(url, {'q': 'NhisMps', 'encounter_id': str(self.encounter.pk)})
        self.assertEqual(resp.status_code, 200)
        names = [r.get('name') for r in resp.json().get('results', [])]
        self.assertIn(self.nhis_lab.name, names)
        self.assertNotIn(self.private_lab.name, names)

    def test_lab_autocomplete_cash_visit_returns_all_matching_tests(self):
        url = reverse('hospital:api_autocomplete_lab_tests')
        resp = self.client.get(url, {'q': 'NhisMps', 'encounter_id': str(self.cash_encounter.pk)})
        self.assertEqual(resp.status_code, 200)
        names = [r.get('name') for r in resp.json().get('results', [])]
        self.assertIn(self.nhis_lab.name, names)
        self.assertIn(self.private_lab.name, names)

    def test_imaging_autocomplete_nhis_visit_only_returns_nhis_scans(self):
        url = reverse('hospital:api_autocomplete_imaging_studies')
        resp = self.client.get(url, {'q': 'NhisChest', 'encounter_id': str(self.encounter.pk)})
        self.assertEqual(resp.status_code, 200)
        names = [r.get('name') for r in resp.json().get('results', [])]
        self.assertIn(self.nhis_scan.name, names)
        self.assertNotIn(self.private_scan.name, names)

    def test_uncovered_lab_on_nhis_invoice_is_patient_pay_cash(self):
        invoice = Invoice.all_objects.filter(encounter=self.encounter).first()
        self.assertIsNotNone(invoice)
        invoice.payer = self.nhis_payer
        invoice.save(update_fields=['payer'])
        sc = ServiceCode.objects.create(
            code=f'LABTEST-{self.private_lab.id}',
            description=self.private_lab.name,
            category='Laboratory',
        )
        line = InvoiceLine(
            invoice=invoice,
            service_code=sc,
            description=self.private_lab.name,
            quantity=Decimal('1'),
            unit_price=self.private_lab.price,
            line_total=self.private_lab.price,
        )
        line.save()
        line.refresh_from_db()
        self.assertTrue(line.patient_pay_cash)
        self.assertTrue(line.is_insurance_excluded)
        self.assertIn('NHIS', line.insurance_exclusion_reason)

    def test_uncovered_scan_on_nhis_invoice_is_patient_pay_cash(self):
        invoice = Invoice.all_objects.filter(encounter=self.encounter).first()
        self.assertIsNotNone(invoice)
        invoice.payer = self.nhis_payer
        invoice.save(update_fields=['payer'])
        sc = ServiceCode.objects.create(
            code=f'IMGCAT-{self.private_scan.id}',
            description=self.private_scan.name,
            category='Imaging',
        )
        line = InvoiceLine(
            invoice=invoice,
            service_code=sc,
            description=self.private_scan.name,
            quantity=Decimal('1'),
            unit_price=self.private_scan.price,
            line_total=self.private_scan.price,
        )
        line.save()
        line.refresh_from_db()
        self.assertTrue(line.patient_pay_cash)
        self.assertTrue(line.is_insurance_excluded)

    def test_covered_lab_on_nhis_invoice_is_not_forced_cash(self):
        invoice = Invoice.all_objects.filter(encounter=self.encounter).first()
        self.assertIsNotNone(invoice)
        invoice.payer = self.nhis_payer
        invoice.save(update_fields=['payer'])
        sc = ServiceCode.objects.create(
            code=f'LABTEST-{self.nhis_lab.id}',
            description=self.nhis_lab.name,
            category='Laboratory',
        )
        line = InvoiceLine(
            invoice=invoice,
            service_code=sc,
            description=self.nhis_lab.name,
            quantity=Decimal('1'),
            unit_price=self.nhis_lab.price,
            line_total=self.nhis_lab.price,
        )
        line.save()
        line.refresh_from_db()
        self.assertFalse(line.patient_pay_cash)

    def test_cashier_search_still_returns_uncovered_items(self):
        _force_login_without_login_signals(self.client, self.cashier_user)
        url = reverse('hospital:cashier_search_billable_items')
        resp = self.client.get(url, {'q': 'NhisMpsPriv'})
        self.assertEqual(resp.status_code, 200)
        names = [r.get('display_name') for r in resp.json().get('results', [])]
        self.assertTrue(any(self.private_lab.name in (n or '') for n in names))

    def test_cashier_nhis_cash_pay_page_loads(self):
        _force_login_without_login_signals(self.client, self.cashier_user)
        url = reverse('hospital:cashier_nhis_cash_pay')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'NHIS')
