"""NHIS formulary: mark drugs at upload and restrict prescribing for NHIS patients."""
import uuid
from datetime import date
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
    Patient,
    Payer,
    PharmacyStock,
    Prescription,
    Staff,
)
from hospital.services.nhis_drug_formulary import (
    apply_nhis_flags_from_rows,
    is_nhis_payer,
    nhis_prescribe_block_reason,
    restrict_drug_queryset_for_payer,
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


class NhisDrugFormularyServiceTests(TestCase):
    def setUp(self):
        suf = uuid.uuid4().hex[:8]
        self.nhis_payer = Payer.objects.create(name=f'NHIS {suf}', payer_type='nhis')
        self.cash_payer = Payer.objects.create(name=f'Cash {suf}', payer_type='cash')
        self.nhis_drug = Drug.objects.create(
            name=f'NhisParacetamol{suf}',
            strength='500mg',
            form='Tablet',
            pack_size='10',
            unit_price=Decimal('2.00'),
            nhis_covered=True,
        )
        self.cash_drug = Drug.objects.create(
            name=f'CashOnlyMed{suf}',
            strength='250mg',
            form='Tablet',
            pack_size='10',
            unit_price=Decimal('8.00'),
            nhis_covered=False,
        )

    def test_is_nhis_payer(self):
        self.assertTrue(is_nhis_payer(self.nhis_payer))
        self.assertFalse(is_nhis_payer(self.cash_payer))
        self.assertFalse(is_nhis_payer(None))

    def test_queryset_filters_for_nhis_only(self):
        nhis_qs = restrict_drug_queryset_for_payer(Drug.objects.all(), self.nhis_payer)
        self.assertIn(self.nhis_drug, nhis_qs)
        self.assertNotIn(self.cash_drug, nhis_qs)

        cash_qs = restrict_drug_queryset_for_payer(Drug.objects.all(), self.cash_payer)
        self.assertIn(self.nhis_drug, cash_qs)
        self.assertIn(self.cash_drug, cash_qs)

    def test_prescribe_block_reason(self):
        self.assertEqual(
            nhis_prescribe_block_reason(drug=self.cash_drug, payer=self.nhis_payer)[:20],
            f'{self.cash_drug.name}: '[:20],
        )
        self.assertEqual(
            nhis_prescribe_block_reason(drug=self.nhis_drug, payer=self.nhis_payer),
            '',
        )
        self.assertEqual(
            nhis_prescribe_block_reason(drug=self.cash_drug, payer=self.cash_payer),
            '',
        )

    def test_import_marks_drugs_by_name(self):
        stats = apply_nhis_flags_from_rows([
            {'name': self.cash_drug.name, 'strength': '250mg', 'nhis': 'Yes'},
        ])
        self.cash_drug.refresh_from_db()
        self.assertEqual(stats['updated'], 1)
        self.assertTrue(self.cash_drug.nhis_covered)


class NhisDrugPrescribeSearchTests(TestCase):
    def setUp(self):
        suf = uuid.uuid4().hex[:8]
        self.dept = Department.objects.create(name=f'NhisDept{suf}', code=f'N{suf[:4]}')
        self.doctor_user = User.objects.create_user(
            username=f'doc_nhis_{suf}',
            password='test-pass-123',
        )
        self.doctor = Staff.objects.create(
            user=self.doctor_user,
            profession='doctor',
            department=self.dept,
        )
        self.nhis_payer = Payer.objects.create(
            name=f'NHIS Scheme {suf}',
            payer_type='nhis',
            is_active=True,
        )
        self.patient = Patient.objects.create(
            first_name='Nhis',
            last_name=f'Patient{suf}',
            mrn=f'PMC-NHIS-{suf}',
            primary_insurance=self.nhis_payer,
        )
        self.cash_patient = Patient.objects.create(
            first_name='Cash',
            last_name=f'Patient{suf}',
            mrn=f'PMC-CASH-{suf}',
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
        self.nhis_drug = Drug.objects.create(
            name=f'NhisAmox{unique}',
            strength='500mg',
            form='Tablet',
            pack_size='10',
            unit_price=Decimal('4.00'),
            nhis_covered=True,
        )
        self.private_drug = Drug.objects.create(
            name=f'NhisAmoxPriv{unique}',
            strength='500mg',
            form='Tablet',
            pack_size='10',
            unit_price=Decimal('12.00'),
            nhis_covered=False,
        )
        PharmacyStock.objects.create(
            drug=self.nhis_drug,
            batch_number=f'NH-{suf}',
            expiry_date=date(2031, 1, 1),
            quantity_on_hand=50,
        )
        PharmacyStock.objects.create(
            drug=self.private_drug,
            batch_number=f'PR-{suf}',
            expiry_date=date(2031, 1, 1),
            quantity_on_hand=50,
        )
        self.client = Client()
        _force_login_without_login_signals(self.client, self.doctor_user)

    def test_autocomplete_nhis_visit_only_returns_nhis_drugs(self):
        url = reverse('hospital:api_autocomplete_drugs')
        resp = self.client.get(url, {'q': 'NhisAmox', 'encounter_id': str(self.encounter.pk)})
        self.assertEqual(resp.status_code, 200)
        names = [r.get('name') for r in resp.json().get('results', [])]
        self.assertIn(self.nhis_drug.name, names)
        self.assertNotIn(self.private_drug.name, names)

    def test_autocomplete_cash_visit_returns_all_matching_drugs(self):
        url = reverse('hospital:api_autocomplete_drugs')
        resp = self.client.get(url, {'q': 'NhisAmox', 'encounter_id': str(self.cash_encounter.pk)})
        self.assertEqual(resp.status_code, 200)
        names = [r.get('name') for r in resp.json().get('results', [])]
        self.assertIn(self.nhis_drug.name, names)
        self.assertIn(self.private_drug.name, names)

    def test_prescribe_rejects_non_nhis_drug_for_nhis_patient(self):
        url = reverse('hospital:consultation_view', kwargs={'encounter_id': self.encounter.pk})
        resp = self.client.post(url, {
            'action': 'prescribe_drug',
            'drug_id': str(self.private_drug.pk),
            'quantity': '5',
            'dose': '1',
            'route': 'oral',
            'frequency': 'bd',
            'duration': '5 days',
        }, follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(
            Prescription.objects.filter(
                drug=self.private_drug,
                order__encounter=self.encounter,
                is_deleted=False,
            ).exists()
        )

    def test_prescribe_allows_nhis_drug_for_nhis_patient(self):
        url = reverse('hospital:consultation_view', kwargs={'encounter_id': self.encounter.pk})
        resp = self.client.post(url, {
            'action': 'prescribe_drug',
            'drug_id': str(self.nhis_drug.pk),
            'quantity': '5',
            'dose': '1',
            'route': 'oral',
            'frequency': 'bd',
            'duration': '5 days',
        }, follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(
            Prescription.objects.filter(
                drug=self.nhis_drug,
                order__encounter=self.encounter,
                is_deleted=False,
            ).exists()
        )
