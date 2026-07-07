"""Tests for pharmacy encounter clinical snapshot (diagnoses, SOAP, vitals)."""
from datetime import date

from django.test import TestCase
from django.utils import timezone

from hospital.models import Encounter, Patient, VitalSign
from hospital.models_advanced import ClinicalNote, Diagnosis, ProblemList
from hospital.pharmacy_clinical_context import encounter_clinical_snapshot_for_pharmacy


class EncounterClinicalSnapshotForPharmacyTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.patient = Patient.objects.create(
            first_name='Snap',
            last_name='Patient',
            mrn='TST-PHRX-CTX-1',
            date_of_birth=date(1985, 5, 5),
            gender='F',
            allergies='Penicillin',
        )
        cls.encounter = Encounter.objects.create(
            patient=cls.patient,
            encounter_type='outpatient',
            status='active',
            chief_complaint='Follow-up for chronic disease',
            diagnosis='',
            notes='',
        )

    def test_structured_diagnosis_fills_diagnosis_when_encounter_text_empty(self):
        Diagnosis.objects.create(
            patient=self.patient,
            encounter=self.encounter,
            diagnosis='Essential hypertension',
            icd10_code='I10',
            diagnosis_type='primary',
        )
        snap = encounter_clinical_snapshot_for_pharmacy(self.encounter, self.patient)
        self.assertEqual(len(snap['diagnosis_entries']), 1)
        self.assertIn('hypertension', snap['diagnosis'].lower())
        self.assertIn('I10', snap['diagnosis_summary'])

    def test_clinical_note_assessment_and_plan(self):
        ClinicalNote.objects.create(
            encounter=self.encounter,
            note_type='soap',
            notes='SOAP documentation body',
            subjective='',
            objective='',
            assessment='Type 2 diabetes mellitus — controlled on current therapy.',
            plan='Continue metformin 500 mg BID; lifestyle counseling.',
        )
        snap = encounter_clinical_snapshot_for_pharmacy(self.encounter, self.patient)
        self.assertIn('diabetes', snap['clinical_assessment'].lower())
        self.assertIn('metformin', snap['clinical_plan'].lower())

    def test_active_problems_list(self):
        ProblemList.objects.create(
            patient=self.patient,
            encounter=None,
            problem='Chronic kidney disease stage 3',
            icd10_code='N18.3',
            status='active',
        )
        snap = encounter_clinical_snapshot_for_pharmacy(self.encounter, self.patient)
        self.assertEqual(len(snap['active_problems']), 1)
        self.assertIn('kidney', snap['active_problems'][0].lower())

    def test_vitals_serialized_when_present(self):
        VitalSign.objects.create(
            encounter=self.encounter,
            systolic_bp=128,
            diastolic_bp=82,
            pulse=72,
            temperature=36.8,
            recorded_at=timezone.now(),
        )
        snap = encounter_clinical_snapshot_for_pharmacy(self.encounter, self.patient)
        self.assertEqual(snap['vitals_set_count'], 1)
        self.assertIsNotNone(snap['vitals'])
        self.assertEqual(snap['vitals']['systolic_bp'], 128)
        self.assertEqual(snap['vitals']['diastolic_bp'], 82)
        self.assertAlmostEqual(snap['vitals']['temperature'], 36.8, places=1)

    def test_patient_allergies_without_encounter(self):
        snap = encounter_clinical_snapshot_for_pharmacy(None, self.patient)
        self.assertIn('Penicillin', snap['patient_allergies'])
