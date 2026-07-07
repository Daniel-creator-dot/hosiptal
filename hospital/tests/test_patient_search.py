"""Tests for unified patient search helpers."""
from datetime import date
from types import SimpleNamespace

from django.db.models import Q
from django.test import SimpleTestCase, TestCase

from hospital.models import Patient
from hospital.patient_search import (
    normalize_query,
    patient_filter_q,
    patient_matches_search,
)


class NormalizeQueryTests(SimpleTestCase):
    def test_collapses_whitespace(self):
        self.assertEqual(normalize_query('  a   b  '), 'a b')

    def test_empty(self):
        self.assertEqual(normalize_query(''), '')
        self.assertEqual(normalize_query('   '), '')


class PatientFilterQTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.john = Patient.objects.create(
            first_name='John',
            middle_name='Kwame',
            last_name='Doe',
            mrn='TST-PSEARCH-1',
            date_of_birth=date(1990, 1, 1),
            gender='M',
        )
        cls.bob = Patient.objects.create(
            first_name='Bob',
            middle_name='',
            last_name='Brown',
            mrn='TST-PSEARCH-2',
            date_of_birth=date(1992, 1, 1),
            gender='M',
        )
        cls.alice = Patient.objects.create(
            first_name='Alice',
            middle_name='',
            last_name='Brown',
            mrn='TST-PSEARCH-3',
            date_of_birth=date(1991, 1, 1),
            gender='F',
        )

    def test_empty_query_matches_nothing(self):
        qs = Patient.objects.filter(patient_filter_q(''), is_deleted=False)
        self.assertEqual(qs.count(), 0)

    def test_mrn_match(self):
        qs = Patient.objects.filter(patient_filter_q('TST-PSEARCH-2'), is_deleted=False)
        self.assertEqual(list(qs), [self.bob])

    def test_two_word_first_last(self):
        qs = Patient.objects.filter(patient_filter_q('John Doe'), is_deleted=False)
        self.assertIn(self.john, qs)
        self.assertNotIn(self.bob, qs)

    def test_middle_and_last_tokens(self):
        qs = Patient.objects.filter(patient_filter_q('Kwame Doe'), is_deleted=False)
        self.assertIn(self.john, qs)
        self.assertNotIn(self.bob, qs)

    def test_alice_brown_excludes_bob_brown(self):
        qs = Patient.objects.filter(patient_filter_q('Alice Brown'), is_deleted=False)
        self.assertIn(self.alice, qs)
        self.assertNotIn(self.bob, qs)

    def test_prefixed_patient_filter(self):
        from hospital.models import Encounter

        enc = Encounter.objects.create(
            patient=self.john,
            encounter_type='outpatient',
            status='completed',
            chief_complaint='Test',
            is_deleted=False,
        )
        qs = Encounter.objects.filter(
            patient_filter_q('John Doe', prefix='patient__', include_email=False),
            is_deleted=False,
        )
        self.assertIn(enc, qs)


class PatientFilterQShapeTests(SimpleTestCase):
    def test_returns_q(self):
        self.assertIsInstance(patient_filter_q('John'), Q)

    def test_empty_query_returns_q(self):
        self.assertIsInstance(patient_filter_q(''), Q)


class PatientMatchesSearchTests(SimpleTestCase):
    def test_empty_search_always_true(self):
        p = SimpleNamespace(
            first_name='John',
            middle_name='',
            last_name='Doe',
            full_name='John Doe',
            mrn='m1',
            phone_number='',
        )
        self.assertTrue(patient_matches_search(p, ''))

    def test_reversed_name_tokens(self):
        p = SimpleNamespace(
            first_name='John',
            middle_name='Kwame',
            last_name='Doe',
            full_name='John Kwame Doe',
            mrn='X1',
            phone_number='',
        )
        self.assertTrue(patient_matches_search(p, 'Doe John'))

    def test_phone_digits_substring(self):
        p = SimpleNamespace(
            first_name='A',
            middle_name='',
            last_name='B',
            full_name='A B',
            mrn='m',
            phone_number='+233241234567',
        )
        self.assertTrue(patient_matches_search(p, '0241234567'))
