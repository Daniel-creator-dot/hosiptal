"""Tests for consultation diagnosis requirement and pharmacy consultation-pending badge."""
import uuid
from datetime import date

from django.contrib.auth.models import User
from django.contrib.auth.signals import user_logged_in
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from hospital.auth_session_utils import create_user_session
from hospital.consultation_status import (
    encounter_consultation_complete,
    encounter_has_diagnosis,
)
from hospital.models import Department, Encounter, Order, Patient, Prescription, Staff
from hospital.models_advanced import Diagnosis, ProblemList
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


class EncounterHasDiagnosisTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.patient = Patient.objects.create(
            first_name='Dx',
            last_name='Gate',
            mrn=f'TST-DXG-{uuid.uuid4().hex[:6]}',
            date_of_birth=date(1990, 1, 1),
            gender='M',
        )
        cls.encounter = Encounter.objects.create(
            patient=cls.patient,
            encounter_type='outpatient',
            status='active',
            chief_complaint='Fever',
            diagnosis='',
        )

    def test_false_when_no_encounter_diagnosis(self):
        self.assertFalse(encounter_has_diagnosis(self.encounter))

    def test_true_when_encounter_diagnosis_text(self):
        self.encounter.diagnosis = 'Malaria'
        self.encounter.save(update_fields=['diagnosis'])
        self.assertTrue(encounter_has_diagnosis(self.encounter))

    def test_true_when_diagnosis_model_row(self):
        Diagnosis.objects.create(
            patient=self.patient,
            encounter=self.encounter,
            diagnosis='Hypertension',
            icd10_code='I10',
            diagnosis_type='primary',
        )
        self.assertTrue(encounter_has_diagnosis(self.encounter))

    def test_true_when_problem_list_for_encounter(self):
        ProblemList.objects.create(
            patient=self.patient,
            encounter=self.encounter,
            problem='Anemia',
            icd10_code='D64.9',
            status='active',
        )
        self.assertTrue(encounter_has_diagnosis(self.encounter))

    def test_prior_visit_problem_without_encounter_link_does_not_count(self):
        ProblemList.objects.create(
            patient=self.patient,
            encounter=None,
            problem='Old chronic condition',
            status='active',
        )
        self.assertFalse(encounter_has_diagnosis(self.encounter))


class EncounterConsultationCompleteTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.patient = Patient.objects.create(
            first_name='Cmp',
            last_name='Gate',
            mrn=f'TST-CMP-{uuid.uuid4().hex[:6]}',
            date_of_birth=date(1988, 3, 3),
            gender='F',
        )

    def test_active_opd_not_complete(self):
        enc = Encounter.objects.create(
            patient=self.patient,
            encounter_type='outpatient',
            status='active',
            chief_complaint='Cough',
        )
        self.assertFalse(encounter_consultation_complete(enc))

    def test_completed_opd_is_complete(self):
        enc = Encounter.objects.create(
            patient=self.patient,
            encounter_type='outpatient',
            status='completed',
            chief_complaint='Cough',
            ended_at=timezone.now(),
        )
        self.assertTrue(encounter_consultation_complete(enc))


class ConsultationViewDiagnosisGateTests(TestCase):
    def setUp(self):
        suf = uuid.uuid4().hex[:8]
        self.dept = Department.objects.create(name=f'DxDept{suf}', code=f'D{suf[:4]}')
        self.user = User.objects.create_user(
            username=f'doc_dx_{suf}',
            password='test-pass-123',
        )
        self.staff = Staff.objects.create(
            user=self.user,
            profession='doctor',
            department=self.dept,
        )
        self.patient = Patient.objects.create(
            first_name='Note',
            last_name=f'Patient{suf}',
            mrn=f'PMC-DX-{suf}',
        )
        self.encounter = Encounter.objects.create(
            patient=self.patient,
            encounter_type='outpatient',
            status='active',
            chief_complaint='Headache',
            provider=self.staff,
        )
        self.client = Client()
        _force_login_without_login_signals(self.client, self.user)
        self.url = reverse('hospital:consultation_view', kwargs={'encounter_id': self.encounter.id})

    def test_save_note_blocked_without_diagnosis(self):
        response = self.client.post(
            self.url,
            {
                'action': 'save_note',
                'note_type': 'consultation',
                'clinical_note': 'Patient presents with headache.',
                'auto_save': 'false',
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(
            self.encounter.clinical_notes.filter(is_deleted=False).exists()
        )

    def test_save_note_allowed_with_diagnosis(self):
        Diagnosis.objects.create(
            patient=self.patient,
            encounter=self.encounter,
            diagnosis='Tension headache',
            diagnosis_type='primary',
        )
        response = self.client.post(
            self.url,
            {
                'action': 'save_note',
                'note_type': 'consultation',
                'clinical_note': 'Patient presents with headache.',
                'auto_save': 'false',
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            self.encounter.clinical_notes.filter(is_deleted=False).exists()
        )

    def test_complete_consultation_blocked_without_diagnosis(self):
        response = self.client.post(
            self.url,
            {
                'action': 'complete_consultation',
                'chief_complaint': 'Headache',
            },
        )
        self.encounter.refresh_from_db()
        self.assertEqual(self.encounter.status, 'active')
        self.assertIsNone(self.encounter.ended_at)

    def test_complete_consultation_allowed_with_diagnosis(self):
        self.encounter.diagnosis = 'Tension headache'
        self.encounter.save(update_fields=['diagnosis'])
        response = self.client.post(
            self.url,
            {
                'action': 'complete_consultation',
                'chief_complaint': 'Headache',
            },
        )
        self.encounter.refresh_from_db()
        self.assertEqual(self.encounter.status, 'completed')
        self.assertIsNotNone(self.encounter.ended_at)


class EnrichPendingMedicationOrdersTests(TestCase):
    def setUp(self):
        suf = uuid.uuid4().hex[:8]
        self.dept = Department.objects.create(name=f'PhDept{suf}', code=f'P{suf[:4]}')
        self.staff = Staff.objects.create(
            user=User.objects.create_user(username=f'staff_{suf}', password='x'),
            profession='doctor',
            department=self.dept,
        )
        self.patient = Patient.objects.create(
            first_name='Rx',
            last_name=f'Queue{suf}',
            mrn=f'PMC-RX-{suf}',
        )

    def _make_order(self, encounter):
        return Order.objects.create(
            encounter=encounter,
            order_type='medication',
            status='pending',
            requested_by=self.staff,
        )

    def test_consultation_pending_for_active_opd(self):
        enc = Encounter.objects.create(
            patient=self.patient,
            encounter_type='outpatient',
            status='active',
            chief_complaint='test',
        )
        order = self._make_order(enc)
        enrich_pending_medication_orders([order])
        self.assertTrue(order.consultation_pending)

    def test_consultation_not_pending_when_completed(self):
        enc = Encounter.objects.create(
            patient=self.patient,
            encounter_type='outpatient',
            status='completed',
            chief_complaint='test',
            ended_at=timezone.now(),
        )
        order = self._make_order(enc)
        enrich_pending_medication_orders([order])
        self.assertFalse(order.consultation_pending)
