"""Tests for start/stat dose early pharmacy release during active consultations."""
import uuid
from decimal import Decimal

from django.contrib.auth.models import User
from django.contrib.auth.signals import user_logged_in
from django.test import Client, TestCase
from django.urls import reverse

from hospital.auth_session_utils import create_user_session
from hospital.models import (
    Department,
    Drug,
    Encounter,
    Order,
    Patient,
    Prescription,
    Staff,
)
from hospital.models_payment_verification import PharmacyDispensing
from hospital.services.auto_billing_service import AutoBillingService
from hospital.services.pharmacy_queue_service import enrich_pending_medication_orders
from hospital.signals_login_tracking import track_successful_login


def _force_login_without_login_signals(client, user):
    user_logged_in.disconnect(track_successful_login)
    user_logged_in.disconnect(create_user_session)
    try:
        client.force_login(user)
    finally:
        user_logged_in.connect(track_successful_login)
        user_logged_in.connect(create_user_session)


class PrescriptionStartDoseReleaseTests(TestCase):
    def setUp(self):
        suf = uuid.uuid4().hex[:8]
        self.dept = Department.objects.create(name=f'StatDept{suf}', code=f'S{suf[:4]}')
        self.doctor_user = User.objects.create_user(
            username=f'doc_stat_{suf}',
            password='test-pass-123',
        )
        self.doctor = Staff.objects.create(
            user=self.doctor_user,
            profession='doctor',
            department=self.dept,
        )
        self.patient = Patient.objects.create(
            first_name='Stat',
            last_name=f'Patient{suf}',
            mrn=f'PMC-STAT-{suf}',
        )
        self.encounter = Encounter.objects.create(
            patient=self.patient,
            encounter_type='outpatient',
            status='active',
            chief_complaint='Pain',
            provider=self.doctor,
        )
        self.drug = Drug.objects.create(
            name=f'StatDrug{suf}',
            strength='500mg',
            form='Tablet',
            pack_size='10',
            unit_price=Decimal('5.00'),
        )
        self.order = Order.objects.create(
            encounter=self.encounter,
            order_type='medication',
            status='pending',
            requested_by=self.doctor,
        )

    def test_release_true_for_start_dose_on_active_opd(self):
        rx = Prescription.objects.create(
            order=self.order,
            drug=self.drug,
            quantity=1,
            dose='1 tab',
            route='oral',
            frequency='stat',
            duration='1 day',
            prescribed_by=self.doctor,
            is_start_dose=True,
        )
        self.assertTrue(AutoBillingService.is_prescription_released_to_pharmacy(rx))

    def test_release_false_for_routine_on_active_opd(self):
        rx = Prescription.objects.create(
            order=self.order,
            drug=self.drug,
            quantity=5,
            dose='1 tab',
            route='oral',
            frequency='bd',
            duration='7 days',
            prescribed_by=self.doctor,
            is_start_dose=False,
        )
        self.assertFalse(AutoBillingService.is_prescription_released_to_pharmacy(rx))

    def test_prescribe_start_dose_creates_pharmacy_dispensing(self):
        client = Client()
        _force_login_without_login_signals(client, self.doctor_user)
        url = reverse('hospital:consultation_view', kwargs={'encounter_id': self.encounter.id})
        client.post(
            url,
            {
                'action': 'prescribe_drug',
                'drug_id': str(self.drug.id),
                'quantity': '1',
                'dose': '1 tab',
                'route': 'oral',
                'frequency': 'stat',
                'duration': '1 day',
                'start_dose': 'on',
            },
        )
        rx = Prescription.objects.filter(order__encounter=self.encounter, drug=self.drug).first()
        self.assertIsNotNone(rx)
        self.assertTrue(rx.is_start_dose)
        self.assertTrue(
            PharmacyDispensing.objects.filter(prescription=rx, is_deleted=False).exists()
        )

    def test_enrich_pending_orders_sets_has_start_dose(self):
        Prescription.objects.create(
            order=self.order,
            drug=self.drug,
            quantity=1,
            dose='1 tab',
            route='oral',
            frequency='stat',
            duration='1 day',
            prescribed_by=self.doctor,
            is_start_dose=True,
        )
        enrich_pending_medication_orders([self.order])
        self.assertTrue(self.order.has_start_dose)
        self.assertTrue(self.order.consultation_pending)


class DispenseStartDoseGuardTests(TestCase):
    def setUp(self):
        from datetime import date, timedelta

        from hospital.models import PharmacyStock

        suf = uuid.uuid4().hex[:8]
        self.dept = Department.objects.create(name=f'PhDept{suf}', code=f'P{suf[:4]}')
        self.pharm_user = User.objects.create_user(
            username=f'ph_stat_{suf}',
            password='test-pass-123',
            is_superuser=True,
        )
        self.pharm_staff = Staff.objects.create(
            user=self.pharm_user,
            profession='pharmacist',
            department=self.dept,
        )
        self.doctor = Staff.objects.create(
            user=User.objects.create_user(username=f'dr_{suf}', password='x'),
            profession='doctor',
            department=self.dept,
        )
        self.patient = Patient.objects.create(
            first_name='Disp',
            last_name=f'Stat{suf}',
            mrn=f'PMC-DSP-{suf}',
        )
        self.encounter = Encounter.objects.create(
            patient=self.patient,
            encounter_type='outpatient',
            status='active',
            chief_complaint='test',
            provider=self.doctor,
        )
        self.drug = Drug.objects.create(
            name=f'Drug{suf}',
            strength='250mg',
            form='Tablet',
            pack_size='10',
            unit_price=Decimal('3.00'),
        )
        exp = date.today() + timedelta(days=365)
        PharmacyStock.objects.create(
            drug=self.drug,
            batch_number=f'B-{suf}',
            expiry_date=exp,
            quantity_on_hand=100,
        )
        self.order = Order.objects.create(
            encounter=self.encounter,
            order_type='medication',
            status='pending',
            requested_by=self.doctor,
        )
        self.client = Client()
        _force_login_without_login_signals(self.client, self.pharm_user)

    def test_routine_gated_but_start_dose_queues_during_active_consultation(self):
        routine_drug = Drug.objects.create(
            name=f'RoutineDrug{uuid.uuid4().hex[:6]}',
            strength='250mg',
            form='Tablet',
            pack_size='10',
            unit_price=Decimal('3.00'),
        )
        stat_rx = Prescription.objects.create(
            order=self.order,
            drug=self.drug,
            quantity=1,
            dose='1',
            route='oral',
            frequency='stat',
            duration='1 day',
            prescribed_by=self.doctor,
            is_start_dose=True,
        )
        routine_rx = Prescription.objects.create(
            order=self.order,
            drug=routine_drug,
            quantity=5,
            dose='1',
            route='oral',
            frequency='od',
            duration='7 days',
            prescribed_by=self.doctor,
            is_start_dose=False,
        )
        stat_result = AutoBillingService.create_pharmacy_dispensing_record_only(stat_rx)
        routine_result = AutoBillingService.create_pharmacy_dispensing_record_only(routine_rx)
        self.assertTrue(stat_result.get('success'))
        self.assertTrue(routine_result.get('gated'))
        self.assertTrue(
            PharmacyDispensing.objects.filter(prescription=stat_rx, is_deleted=False).exists()
        )
        self.assertFalse(
            PharmacyDispensing.objects.filter(prescription=routine_rx, is_deleted=False).exists()
        )
