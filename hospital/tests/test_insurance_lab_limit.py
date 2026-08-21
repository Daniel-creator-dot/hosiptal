"""Insurance lab request cap: 3 tests; extras need reason and diagnosis."""
import uuid
from datetime import date

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from hospital.insurance_lab_limit import (
    INSURANCE_LAB_TEST_LIMIT,
    count_encounter_lab_tests,
    require_insurance_extra_lab_justification,
)
from hospital.models import Department, Encounter, LabResult, LabTest, Order, Patient, Payer, Staff
from hospital.tests.test_consultation_diagnosis_gate import _force_login_without_login_signals


class InsuranceLabLimitHelperTests(TestCase):
    def setUp(self):
        suf = uuid.uuid4().hex[:6]
        self.payer = Payer.objects.create(
            name=f'NHIS {suf}',
            payer_type='nhis',
            is_active=True,
        )
        self.patient = Patient.objects.create(
            first_name='Ins',
            last_name=f'Lab{suf}',
            mrn=f'PMC-IL-{suf}',
            date_of_birth=date(1990, 1, 1),
            gender='F',
            primary_insurance=self.payer,
        )
        self.encounter = Encounter.objects.create(
            patient=self.patient,
            encounter_type='outpatient',
            status='active',
            diagnosis='Malaria',
        )
        dept = Department.objects.create(name=f'Dept {suf}', code=f'D{suf[:4].upper()}')
        user = User.objects.create_user(username=f'doc_il_{suf}', password='x')
        self.staff = Staff.objects.create(
            user=user,
            profession='doctor',
            employee_id=f'D{suf}',
            department=dept,
        )

    def _make_tests(self, n):
        tests = []
        for i in range(n):
            tests.append(
                LabTest.objects.create(
                    name=f'Test {i} {uuid.uuid4().hex[:4]}',
                    code=f'T{uuid.uuid4().hex[:6].upper()}',
                    specimen_type='Blood',
                    is_active=True,
                )
            )
        return tests

    def _order_tests(self, tests):
        order = Order.objects.create(
            encounter=self.encounter,
            order_type='lab',
            status='pending',
            requested_by=self.staff,
            clinical_indication='Malaria',
        )
        for t in tests:
            LabResult.objects.create(order=order, test=t, status='pending')
        return order

    def test_three_allowed_without_reason(self):
        ok, msg = require_insurance_extra_lab_justification(self.encounter, 3)
        self.assertTrue(ok, msg)

    def test_fourth_blocked_without_reason(self):
        ok, msg = require_insurance_extra_lab_justification(self.encounter, 4)
        self.assertFalse(ok)
        self.assertIn('reason', msg.lower())
        self.assertIn('diagnosis', msg.lower())

    def test_fourth_allowed_with_reason_and_diagnosis(self):
        ok, msg = require_insurance_extra_lab_justification(
            self.encounter,
            4,
            extra_reason='Persistent fever after first-line workup',
            extra_diagnosis='Acute febrile illness',
        )
        self.assertTrue(ok, msg)

    def test_existing_three_then_one_more_needs_reason(self):
        self._order_tests(self._make_tests(3))
        self.assertEqual(count_encounter_lab_tests(self.encounter), 3)
        ok, _ = require_insurance_extra_lab_justification(self.encounter, 1)
        self.assertFalse(ok)
        ok2, _ = require_insurance_extra_lab_justification(
            self.encounter,
            1,
            extra_reason='Need CRP for suspected sepsis',
            extra_diagnosis='Sepsis',
        )
        self.assertTrue(ok2)

    def test_cash_patient_not_capped(self):
        cash = Patient.objects.create(
            first_name='Cash',
            last_name='Lab',
            mrn=f'PMC-CL-{uuid.uuid4().hex[:6]}',
        )
        enc = Encounter.objects.create(
            patient=cash,
            encounter_type='outpatient',
            status='active',
            diagnosis='UTI',
        )
        ok, msg = require_insurance_extra_lab_justification(enc, 6)
        self.assertTrue(ok, msg)


class InsuranceLabLimitConsultationTests(TestCase):
    def setUp(self):
        suf = uuid.uuid4().hex[:6]
        self.dept = Department.objects.create(name=f'OPD {suf}', code=f'O{suf[:4].upper()}')
        self.user = User.objects.create_user(username=f'doc_ilc_{suf}', password='test-pass-123')
        self.staff = Staff.objects.create(
            user=self.user,
            profession='doctor',
            employee_id=f'E{suf}',
            department=self.dept,
        )
        self.payer = Payer.objects.create(name=f'Acme Ins {suf}', payer_type='insurance', is_active=True)
        self.patient = Patient.objects.create(
            first_name='Ins',
            last_name=f'Consult{suf}',
            mrn=f'PMC-ILC-{suf}',
            primary_insurance=self.payer,
        )
        self.encounter = Encounter.objects.create(
            patient=self.patient,
            encounter_type='outpatient',
            status='active',
            chief_complaint='Fever',
            diagnosis='Malaria',
            provider=self.staff,
        )
        self.tests = []
        for i in range(4):
            self.tests.append(
                LabTest.objects.create(
                    name=f'ILC Test {i} {suf}',
                    code=f'ILC{suf}{i}',
                    specimen_type='Blood',
                    is_active=True,
                )
            )
        self.client = Client()
        _force_login_without_login_signals(self.client, self.user)
        self.url = reverse('hospital:consultation_view', kwargs={'encounter_id': self.encounter.id})

    def test_four_tests_blocked_without_extra_reason(self):
        response = self.client.post(
            self.url,
            {
                'action': 'order_lab_test',
                'test_ids': [str(t.id) for t in self.tests],
                'priority': 'routine',
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(count_encounter_lab_tests(self.encounter), 0)

    def test_four_tests_allowed_with_reason_and_diagnosis(self):
        response = self.client.post(
            self.url,
            {
                'action': 'order_lab_test',
                'test_ids': [str(t.id) for t in self.tests],
                'priority': 'routine',
                'extra_lab_reason': 'Need full septic workup after 3 days fever',
                'extra_lab_diagnosis': 'Acute febrile illness',
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(count_encounter_lab_tests(self.encounter), 4)
        order = Order.objects.filter(encounter=self.encounter, order_type='lab', is_deleted=False).first()
        self.assertIsNotNone(order)
        self.assertIn('extra labs', (order.notes or '').lower())
        self.assertIn('Acute febrile illness', order.clinical_indication or '')

    def test_three_tests_do_not_need_extra_reason(self):
        response = self.client.post(
            self.url,
            {
                'action': 'order_lab_test',
                'test_ids': [str(t.id) for t in self.tests[:INSURANCE_LAB_TEST_LIMIT]],
                'priority': 'routine',
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(count_encounter_lab_tests(self.encounter), 3)
