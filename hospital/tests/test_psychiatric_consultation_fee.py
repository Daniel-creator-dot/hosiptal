"""Psychiatric / specialist consultation fees must post on visit create (new and subsequent)."""
import uuid
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from hospital.models import Department, Encounter, InvoiceLine, Patient, Payer, Staff
from hospital.utils_billing import (
    add_consultation_charge,
    should_waive_consultation_fee,
    visit_should_auto_mark_review,
    visit_should_charge_consultation,
)
from hospital.utils_doctor_pricing import DoctorPricingService


class PsychiatricConsultationFeeTests(TestCase):
    def setUp(self):
        suf = uuid.uuid4().hex[:6]
        self.cash = Payer.objects.create(name=f'Cash {suf}', payer_type='cash', is_active=True)
        self.dept = Department.objects.create(
            name='Psychiatry',
            code=f'PSY{suf[:3].upper()}',
        )
        self.gp_dept = Department.objects.create(
            name='General Medicine',
            code=f'GM{suf[:3].upper()}',
        )
        self.user = User.objects.create_user(
            username=f'psych_{suf}',
            password='pw',
            first_name='Rebecca',
            last_name='Abalo',
        )
        self.doctor = Staff.objects.create(
            user=self.user,
            profession='doctor',
            employee_id=f'P{suf.upper()}',
            department=self.dept,
            specialization='Psychiatrist',
        )
        self.patient = Patient.objects.create(
            first_name='Pat',
            last_name=f'Psych{suf}',
            mrn=f'MRN-PSY-{suf}',
            primary_insurance=self.cash,
        )

    def _encounter(self, provider=None, encounter_type='specialist', **kwargs):
        return Encounter.objects.create(
            patient=self.patient,
            encounter_type=encounter_type,
            status='active',
            started_at=timezone.now(),
            provider=provider or self.doctor,
            chief_complaint=kwargs.get('chief_complaint', 'Anxiety'),
            notes=kwargs.get('notes', ''),
        )

    def test_name_and_specialty_match_psychiatrist(self):
        info = DoctorPricingService.get_doctor_pricing_info(self.doctor)
        self.assertTrue(info['is_specialist'])
        self.assertIn('psychiatr', (info['specialty'] or '').lower())
        self.assertEqual(info['first_visit'], Decimal('358.00'))
        self.assertEqual(info['subsequent_visit'], Decimal('308.00'))

    def test_new_psych_visit_posts_new_fee(self):
        enc = self._encounter()
        invoice = add_consultation_charge(
            enc, consultation_type='specialist', doctor_staff=self.doctor
        )
        self.assertIsNotNone(invoice)
        line = InvoiceLine.objects.filter(invoice=invoice, is_deleted=False).first()
        self.assertIsNotNone(line)
        self.assertEqual(line.unit_price, Decimal('358.00'))
        self.assertIn('New', line.description)

    def test_subsequent_psych_visit_posts_subsequent_fee(self):
        prior = self._encounter()
        prior.started_at = timezone.now() - timedelta(days=2)
        prior.save(update_fields=['started_at'])
        enc = self._encounter(chief_complaint='Review anxiety')
        self.assertFalse(
            DoctorPricingService.is_first_visit_to_doctor(
                self.patient, self.doctor, exclude_encounter=enc
            )
        )
        invoice = add_consultation_charge(
            enc, consultation_type='specialist', doctor_staff=self.doctor
        )
        line = InvoiceLine.objects.filter(invoice=invoice, is_deleted=False).first()
        self.assertEqual(line.unit_price, Decimal('308.00'))
        self.assertIn('Subsequent', line.description)

    def test_six_day_window_does_not_waive_psychiatrist(self):
        prior = self._encounter()
        prior.started_at = timezone.now() - timedelta(days=2)
        prior.save(update_fields=['started_at'])
        enc = self._encounter()
        self.assertFalse(should_waive_consultation_fee(enc, doctor_staff=self.doctor))
        self.assertFalse(
            visit_should_auto_mark_review('new', self.patient, self.doctor, 'outpatient')
        )
        self.assertTrue(
            visit_should_charge_consultation('review', 'outpatient', self.doctor)
        )

    def test_psychiatrist_in_gp_department_keeps_specialist_tariff(self):
        self.doctor.department = self.gp_dept
        self.doctor.save(update_fields=['department'])
        enc = self._encounter(encounter_type='outpatient')
        invoice = add_consultation_charge(
            enc, consultation_type='specialist', doctor_staff=self.doctor
        )
        line = InvoiceLine.objects.filter(invoice=invoice, is_deleted=False).first()
        self.assertEqual(line.unit_price, Decimal('358.00'))

    def test_specialty_only_psychiatrist_without_name_match(self):
        user = User.objects.create_user(
            username=f'unk_{uuid.uuid4().hex[:6]}',
            password='pw',
            first_name='New',
            last_name='Psychdoc',
        )
        doc = Staff.objects.create(
            user=user,
            profession='doctor',
            employee_id=f'U{uuid.uuid4().hex[:6].upper()}',
            department=self.dept,
            specialization='Psychiatry',
        )
        info = DoctorPricingService.get_doctor_pricing_info(doc)
        self.assertTrue(info['is_specialist'])
        self.assertEqual(info['first_visit'], Decimal('358.00'))


class AntenatalVisitFeeTests(TestCase):
    def test_antenatal_visit_is_always_243(self):
        from hospital.utils_billing import ANC_VISIT, add_consultation_charge, get_mat_anc_consultation_price

        self.assertEqual(ANC_VISIT, Decimal('243.00'))
        suf = uuid.uuid4().hex[:6]
        cash = Payer.objects.create(name=f'CashA{suf}', payer_type='cash', is_active=True)
        patient = Patient.objects.create(
            first_name='Anc',
            last_name=f'Test{suf}',
            mrn=f'MRN-ANC-{suf}',
            primary_insurance=cash,
        )
        enc = Encounter.objects.create(
            patient=patient,
            encounter_type='antenatal',
            status='active',
            started_at=timezone.now(),
            chief_complaint='ANC',
        )
        self.assertEqual(get_mat_anc_consultation_price(patient, cash), Decimal('243.00'))
        invoice = add_consultation_charge(enc, consultation_type='general')
        line = InvoiceLine.objects.filter(invoice=invoice, is_deleted=False).first()
        self.assertEqual(line.service_code.code, 'MAT-ANC')
        self.assertEqual(line.unit_price, Decimal('243.00'))
