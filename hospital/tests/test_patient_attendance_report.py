"""Tests for admin Patient Attendance Report."""
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.contrib.auth.models import User
from django.contrib.auth.signals import user_logged_in
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from hospital.auth_session_utils import create_user_session
from hospital.models import Admission, Department, Encounter, Invoice, Patient, Payer, Staff, Ward
from hospital.signals_login_tracking import track_successful_login
from hospital.views_patient_attendance import (
    REPORT_TZ,
    is_night_visit,
    night_shift_date,
)


def _force_login_without_login_signals(client, user):
    user_logged_in.disconnect(track_successful_login)
    user_logged_in.disconnect(create_user_session)
    try:
        client.force_login(user)
    finally:
        user_logged_in.connect(track_successful_login)
        user_logged_in.connect(create_user_session)


def _aware(y, m, d, hh, mm=0):
    """Build an aware datetime in Africa/Accra."""
    return datetime(y, m, d, hh, mm, tzinfo=REPORT_TZ)


class NightShiftHelpersTests(TestCase):
    def test_7pm_is_night_on_same_date(self):
        dt = _aware(2026, 7, 1, 19, 0)
        self.assertTrue(is_night_visit(dt))
        self.assertEqual(night_shift_date(dt), date(2026, 7, 1))

    def test_3am_belongs_to_previous_evening_night(self):
        dt = _aware(2026, 7, 2, 3, 0)
        self.assertTrue(is_night_visit(dt))
        self.assertEqual(night_shift_date(dt), date(2026, 7, 1))

    def test_6am_is_day_not_night(self):
        dt = _aware(2026, 7, 2, 6, 0)
        self.assertFalse(is_night_visit(dt))
        self.assertIsNone(night_shift_date(dt))

    def test_just_before_6am_is_night(self):
        dt = _aware(2026, 7, 2, 5, 59)
        self.assertTrue(is_night_visit(dt))
        self.assertEqual(night_shift_date(dt), date(2026, 7, 1))

    def test_noon_is_day(self):
        dt = _aware(2026, 7, 1, 12, 0)
        self.assertFalse(is_night_visit(dt))
        self.assertIsNone(night_shift_date(dt))


@override_settings(ALLOWED_HOSTS=['*'])
class PatientAttendanceReportViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(
            username='att_admin', password='pass', is_superuser=True, is_staff=True
        )
        cls.normal = User.objects.create_user(username='att_nurse', password='pass')
        cls.dept = Department.objects.create(name='OPD Att', code='OPDATT')
        cls.ward = Ward.objects.create(
            name=f'Ward-{uuid.uuid4().hex[:6]}',
            code=f'W{uuid.uuid4().hex[:4].upper()}',
            ward_type='general',
            department=cls.dept,
        )
        cls.cash = Payer.objects.create(name='Cash Desk', payer_type='cash')
        cls.nhis = Payer.objects.create(name='NHIS Scheme', payer_type='nhis')
        cls.corp = Payer.objects.create(name='Acme Corp', payer_type='corporate')

        cls.patient_a = Patient.objects.create(
            first_name='Night',
            last_name='Walker',
            mrn=f'TST-ATT-A-{uuid.uuid4().hex[:6]}',
            date_of_birth=date(1990, 1, 1),
            gender='M',
            address='Accra',
            next_of_kin_name='Kin',
            primary_insurance=cls.nhis,
        )
        cls.patient_b = Patient.objects.create(
            first_name='Day',
            last_name='Visitor',
            mrn=f'TST-ATT-B-{uuid.uuid4().hex[:6]}',
            date_of_birth=date(1985, 5, 5),
            gender='F',
            address='Accra',
            next_of_kin_name='Kin',
        )

        # Night visit 20:00 Accra on Jul 1 → night of Jul 1
        cls.night_enc = Encounter.objects.create(
            patient=cls.patient_a,
            encounter_type='outpatient',
            status='completed',
            chief_complaint='Fever',
            started_at=_aware(2026, 7, 1, 20, 0),
        )
        # Early morning 02:00 Accra Jul 2 → night of Jul 1
        cls.morning_night_enc = Encounter.objects.create(
            patient=cls.patient_a,
            encounter_type='er',
            status='completed',
            chief_complaint='Pain',
            started_at=_aware(2026, 7, 2, 2, 0),
        )
        # Day visit Jul 1 noon
        cls.day_enc = Encounter.objects.create(
            patient=cls.patient_b,
            encounter_type='outpatient',
            status='completed',
            chief_complaint='Checkup',
            started_at=_aware(2026, 7, 1, 12, 0),
        )
        # Cancelled — excluded
        cls.cancelled = Encounter.objects.create(
            patient=cls.patient_b,
            encounter_type='outpatient',
            status='cancelled',
            chief_complaint='Cancel me',
            started_at=_aware(2026, 7, 1, 15, 0),
        )
        # Inpatient with admission
        cls.ip_enc = Encounter.objects.create(
            patient=cls.patient_b,
            encounter_type='inpatient',
            status='active',
            chief_complaint='Admit',
            started_at=_aware(2026, 7, 1, 10, 0),
        )
        Admission.objects.create(
            encounter=cls.ip_enc,
            ward=cls.ward,
            admit_date=_aware(2026, 7, 1, 10, 0),
            status='admitted',
            admitting_doctor=None,
        )

        # Visit-payer sync may auto-create an invoice; update payer for report tests.
        inv_night = Invoice.all_objects.filter(encounter=cls.night_enc, is_deleted=False).first()
        if inv_night:
            inv_night.payer = cls.cash
            inv_night.total_amount = Decimal('50.00')
            inv_night.balance = Decimal('50.00')
            inv_night.status = 'issued'
            inv_night.save(update_fields=['payer', 'total_amount', 'balance', 'status', 'modified'])
        else:
            Invoice.all_objects.create(
                patient=cls.patient_a,
                encounter=cls.night_enc,
                payer=cls.cash,
                invoice_number=f'INV-ATT-{uuid.uuid4().hex[:8]}',
                status='issued',
                total_amount=Decimal('50.00'),
                balance=Decimal('50.00'),
                issued_at=_aware(2026, 7, 1, 21, 0),
            )

        inv_day = Invoice.all_objects.filter(encounter=cls.day_enc, is_deleted=False).first()
        if inv_day:
            inv_day.payer = cls.corp
            inv_day.total_amount = Decimal('80.00')
            inv_day.balance = Decimal('80.00')
            inv_day.status = 'issued'
            inv_day.save(update_fields=['payer', 'total_amount', 'balance', 'status', 'modified'])
        else:
            Invoice.all_objects.create(
                patient=cls.patient_b,
                encounter=cls.day_enc,
                payer=cls.corp,
                invoice_number=f'INV-ATT-{uuid.uuid4().hex[:8]}',
                status='issued',
                total_amount=Decimal('80.00'),
                balance=Decimal('80.00'),
                issued_at=_aware(2026, 7, 1, 13, 0),
            )

    def setUp(self):
        self.client = Client()

    def test_requires_login(self):
        url = reverse('hospital:patient_attendance_report')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 302)

    def test_non_admin_denied(self):
        _force_login_without_login_signals(self.client, self.normal)
        url = reverse('hospital:patient_attendance_report')
        resp = self.client.get(url, {'date_from': '2026-07-01', 'date_to': '2026-07-02'})
        self.assertIn(resp.status_code, (302, 403))

    def test_it_staff_can_access_report(self):
        it_user = User.objects.create_user(username='att_it', password='pass')
        from django.contrib.auth.models import Group
        group, _ = Group.objects.get_or_create(name='IT Operations')
        it_user.groups.add(group)
        _force_login_without_login_signals(self.client, it_user)
        url = reverse('hospital:patient_attendance_report')
        resp = self.client.get(url, {'date_from': '2026-07-01', 'date_to': '2026-07-02'})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Patient Attendance Report')
        self.assertIn('specialist_unit_rows', resp.context)
        self.assertIn('specialist_clinician_rows', resp.context)

    def test_payer_mix_merges_corporate_aliases(self):
        from hospital.views_patient_attendance import _payer_mix_group, _summarize

        gk1, label1 = _payer_mix_group('ECG / Power Distribution Service', 'corporate')
        gk2, label2 = _payer_mix_group('Electricity Company of Ghana old', 'corporate')
        self.assertEqual(gk1, gk2)
        self.assertEqual(label1, 'Electricity Company of Ghana')

        gk_a, _ = _payer_mix_group('ACE MEDICAL INSURANCE', 'private')
        gk_b, label_b = _payer_mix_group('Ace Medical Insurance', 'private')
        self.assertEqual(gk_a, gk_b)

        rows = [
            {
                'patient_id': uuid.uuid4(),
                'is_inpatient': False,
                'is_night': False,
                'started_local': _aware(2026, 7, 1, 10, 0),
                'payer_category': 'corporate',
                'payer_type': 'corporate',
                'payer_name': 'ECG / Power Distribution Service',
                'encounter_type_display': 'Outpatient',
                'department': 'Medicine',
                'status_display': 'Completed',
                'care_setting': 'Outpatient',
            },
            {
                'patient_id': uuid.uuid4(),
                'is_inpatient': False,
                'is_night': False,
                'started_local': _aware(2026, 7, 1, 11, 0),
                'payer_category': 'corporate',
                'payer_type': 'corporate',
                'payer_name': 'ECG Electricity Company of Ghana',
                'encounter_type_display': 'Outpatient',
                'department': 'Medicine',
                'status_display': 'Completed',
                'care_setting': 'Outpatient',
            },
        ]
        aggregates = _summarize(rows)
        self.assertEqual(len(aggregates['payer_name_rows']), 1)
        self.assertEqual(aggregates['payer_name_rows'][0]['count'], 2)
        self.assertEqual(aggregates['payer_name_rows'][0]['label'], 'Electricity Company of Ghana')
        self.assertEqual(aggregates['payer_name_rows'][0]['pct'], 100.0)

    def test_specialist_services_breakdown_amounts(self):
        from hospital.models import InvoiceLine, ServiceCode
        from hospital.views_patient_attendance import _specialist_services_breakdown

        code, _ = ServiceCode.objects.get_or_create(
            code='CON002',
            defaults={
                'description': 'Specialist Consultation',
                'category': 'Consultation',
                'is_active': True,
            },
        )
        doctor_user = User.objects.create_user(
            username='att_spec_doc', password='pass', first_name='Spec', last_name='Doc'
        )
        doctor = Staff.objects.create(
            user=doctor_user,
            profession='doctor',
            department=self.dept,
            employee_id=f'EMP-{uuid.uuid4().hex[:6]}',
        )
        enc = Encounter.objects.create(
            patient=self.patient_b,
            encounter_type='outpatient',
            status='completed',
            chief_complaint='SP visit',
            started_at=_aware(2026, 7, 1, 14, 0),
            provider=doctor,
        )
        inv = Invoice.all_objects.filter(encounter=enc, is_deleted=False).first()
        if not inv:
            inv = Invoice.all_objects.create(
                patient=self.patient_b,
                encounter=enc,
                payer=self.cash,
                invoice_number=f'INV-SP-{uuid.uuid4().hex[:8]}',
                status='issued',
                total_amount=Decimal('300.00'),
                balance=Decimal('300.00'),
                issued_at=_aware(2026, 7, 1, 14, 30),
            )
        InvoiceLine.objects.create(
            invoice=inv,
            service_code=code,
            description='Specialist Consultation',
            quantity=1,
            unit_price=Decimal('300.00'),
            line_total=Decimal('300.00'),
        )
        breakdown = _specialist_services_breakdown(date(2026, 7, 1), date(2026, 7, 2))
        self.assertGreaterEqual(breakdown['total_lines'], 1)
        self.assertGreaterEqual(breakdown['total_amount'], Decimal('300.00'))
        self.assertTrue(any(r['label'] == 'OPD Att' for r in breakdown['unit_rows']))
        unit = next(r for r in breakdown['unit_rows'] if r['label'] == 'OPD Att')
        self.assertIn('pct', unit)
        self.assertGreater(unit['pct'], 0)
    def test_admin_report_loads_with_summary(self):
        _force_login_without_login_signals(self.client, self.admin)
        url = reverse('hospital:patient_attendance_report')
        resp = self.client.get(url, {'date_from': '2026-07-01', 'date_to': '2026-07-02'})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Patient Attendance Report')
        summary = resp.context['summary']
        # night + morning_night + day + ip = 4 (cancelled excluded)
        self.assertEqual(summary['total_visits'], 4)
        self.assertEqual(summary['unique_patients'], 2)
        self.assertEqual(summary['night_visits'], 2)
        self.assertEqual(summary['inpatient_visits'], 1)
        self.assertGreaterEqual(summary['cash'], 1)
        self.assertGreaterEqual(summary['corporate'], 1)

    def test_night_filter(self):
        _force_login_without_login_signals(self.client, self.admin)
        url = reverse('hospital:patient_attendance_report')
        resp = self.client.get(url, {
            'date_from': '2026-07-01',
            'date_to': '2026-07-02',
            'shift': 'night',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['summary']['total_visits'], 2)
        self.assertEqual(resp.context['summary']['night_visits'], 2)
        for row in resp.context['detail_rows']:
            self.assertTrue(row['is_night'])
            self.assertEqual(row['night_shift_date'], date(2026, 7, 1))

    def test_inpatient_filter(self):
        _force_login_without_login_signals(self.client, self.admin)
        url = reverse('hospital:patient_attendance_report')
        resp = self.client.get(url, {
            'date_from': '2026-07-01',
            'date_to': '2026-07-02',
            'care': 'inpatient',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['summary']['total_visits'], 1)
        self.assertEqual(resp.context['summary']['inpatient_visits'], 1)

    def test_cash_payer_category_filter(self):
        _force_login_without_login_signals(self.client, self.admin)
        url = reverse('hospital:patient_attendance_report')
        resp = self.client.get(url, {
            'date_from': '2026-07-01',
            'date_to': '2026-07-02',
            'payer_category': 'cash',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertGreaterEqual(resp.context['summary']['total_visits'], 1)
        self.assertEqual(
            resp.context['summary']['cash'],
            resp.context['summary']['total_visits'],
        )
        row_ids = {r['id'] for r in resp.context['detail_rows']}
        self.assertIn(self.night_enc.pk, row_ids)

    def test_month_filter(self):
        _force_login_without_login_signals(self.client, self.admin)
        url = reverse('hospital:patient_attendance_report')
        resp = self.client.get(url, {'month': '2026-07'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['date_from'], date(2026, 7, 1))
        self.assertEqual(resp.context['date_to'], date(2026, 7, 31))
        self.assertGreaterEqual(resp.context['summary']['total_visits'], 4)

    def test_excel_export(self):
        _force_login_without_login_signals(self.client, self.admin)
        url = reverse('hospital:patient_attendance_report')
        resp = self.client.get(url, {
            'date_from': '2026-07-01',
            'date_to': '2026-07-02',
            'export': 'excel',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertIn(
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            resp['Content-Type'],
        )
        self.assertIn('attachment', resp.get('Content-Disposition', ''))

    def test_pdf_export(self):
        _force_login_without_login_signals(self.client, self.admin)
        url = reverse('hospital:patient_attendance_report')
        resp = self.client.get(url, {
            'date_from': '2026-07-01',
            'date_to': '2026-07-02',
            'export': 'pdf',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')
        self.assertTrue(resp.content.startswith(b'%PDF'))

    def test_csv_export(self):
        _force_login_without_login_signals(self.client, self.admin)
        url = reverse('hospital:patient_attendance_report')
        resp = self.client.get(url, {
            'date_from': '2026-07-01',
            'date_to': '2026-07-02',
            'export': 'csv',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertIn('text/csv', resp['Content-Type'])
        body = resp.content.decode('utf-8-sig')
        self.assertIn('Patient Attendance Report', body)
        self.assertIn(self.patient_a.mrn, body)

    def test_pagination(self):
        _force_login_without_login_signals(self.client, self.admin)
        # Create enough visits for page 2
        for i in range(55):
            Encounter.objects.create(
                patient=self.patient_b,
                encounter_type='outpatient',
                status='completed',
                chief_complaint=f'Extra {i}',
                started_at=_aware(2026, 7, 1, 11, 0) + timedelta(minutes=i),
            )
        url = reverse('hospital:patient_attendance_report')
        resp = self.client.get(url, {
            'date_from': '2026-07-01',
            'date_to': '2026-07-02',
            'page': '2',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.context['page_obj'].has_previous())
