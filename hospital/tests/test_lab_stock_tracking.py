"""Measurable kit / chemistry reagent tracking and diagnosis on lab orders."""
import uuid
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase

from hospital.lab_order_diagnosis import persist_lab_order_diagnosis
from hospital.lab_stock_catalog import name_matches_aliases
from hospital.models import Department, Encounter, LabResult, LabTest, Order, Patient, Staff
from hospital.models_lab_management import LabReagent, ReagentTransaction
from hospital.services.lab_reagent_usage_service import (
    consume_reagents_for_completed_lab_result,
    receive_reagent_pack,
)


class LabStockCatalogMatchTests(SimpleTestCase):
    def test_typhoid_and_not_widal_only_by_widal_word(self):
        self.assertTrue(name_matches_aliases('Typhoid Rapid Test', 'TYPH', ['typhoid', 'typhidot']))
        self.assertFalse(name_matches_aliases('Widal', 'WIDAL', ['typhoid', 'typhidot']))

    def test_ldl_does_not_use_bare_cholesterol_token_with_skip(self):
        from hospital.lab_stock_catalog import should_skip_kit_for_test

        row = {'skip_if_name_has': ['hdl', 'ldl']}
        self.assertTrue(should_skip_kit_for_test(row, 'LDL Cholesterol', 'LDL'))
        self.assertFalse(should_skip_kit_for_test(row, 'Total Cholesterol', 'CHOL'))


class MeasurableLabStockTests(TestCase):
    def setUp(self):
        suf = uuid.uuid4().hex[:8]
        self.dept = Department.objects.create(name=f'Lab{suf}', code=f'L{suf[:4]}')
        self.user = User.objects.create_user(username=f'lt_{suf}', password='pw')
        self.staff = Staff.objects.create(
            user=self.user, profession='lab_technician', department=self.dept
        )
        self.patient = Patient.objects.create(
            first_name='Kit', last_name=f'Pat{suf}', mrn=f'PMC-KIT-{suf}'
        )
        self.encounter = Encounter.objects.create(
            patient=self.patient,
            encounter_type='outpatient',
            status='active',
            chief_complaint='Fever',
            diagnosis='Malaria',
            provider=self.staff,
        )
        self.test = LabTest.objects.create(
            code=f'TYPH{suf[:4]}',
            name=f'Typhoid Rapid {suf}',
            specimen_type='Blood',
            price=Decimal('20'),
            stock_tracking='measurable',
            qty_per_box=25,
        )
        self.kit = LabReagent.objects.create(
            item_code=f'KIT-TYPH-{suf[:6]}',
            name='Typhoid IgG/IgM',
            category='consumable',
            quantity_on_hand=Decimal('0'),
            unit='pcs',
            stock_tracking='measurable',
            qty_per_box=25,
            qty_consumed_per_test=Decimal('1'),
        )
        self.kit.tests.add(self.test)
        self.order = Order.objects.create(
            encounter=self.encounter,
            order_type='lab',
            status='pending',
            requested_by=self.staff,
            clinical_indication='Malaria',
        )

    def test_receive_box_adds_pieces(self):
        receive_reagent_pack(reagent=self.kit, packs=2, performed_by=self.staff)
        self.kit.refresh_from_db()
        self.assertEqual(self.kit.quantity_on_hand, Decimal('50'))

    def test_completed_measurable_lab_uses_one_piece(self):
        receive_reagent_pack(reagent=self.kit, packs=1, performed_by=self.staff)
        result = LabResult.objects.create(order=self.order, test=self.test, status='pending')
        result.status = 'completed'
        result.save()
        self.kit.refresh_from_db()
        self.assertEqual(self.kit.quantity_on_hand, Decimal('24'))
        self.assertEqual(
            ReagentTransaction.objects.filter(
                reagent=self.kit, lab_result=result, transaction_type='used', is_deleted=False
            ).count(),
            1,
        )

    def test_chemistry_remaining_tests_and_fbc_skip(self):
        urea = LabReagent.objects.create(
            item_code=f'CHEM-UREA-{self.kit.item_code[-6:]}',
            name='Urea reagent',
            category='reagent',
            quantity_on_hand=Decimal('0'),
            unit='tests',
            stock_tracking='immeasurable',
            tests_per_kit=330,
            qty_consumed_per_test=Decimal('1'),
        )
        urea_test = LabTest.objects.create(
            code=f'UREA{self.test.code[-4:]}',
            name=f'Urea {self.test.code}',
            specimen_type='Blood',
            price=Decimal('15'),
            stock_tracking='immeasurable',
            tests_per_kit=330,
        )
        urea.tests.add(urea_test)
        receive_reagent_pack(reagent=urea, packs=1, performed_by=self.staff)
        urea.refresh_from_db()
        self.assertEqual(urea.quantity_on_hand, Decimal('330'))

        fbc_dil = LabReagent.objects.create(
            item_code=f'CHEM-FBC-{self.kit.item_code[-6:]}',
            name='FBC diluent',
            category='reagent',
            quantity_on_hand=Decimal('20'),
            unit='L',
            stock_tracking='immeasurable',
            qty_consumed_per_test=Decimal('0'),
        )
        fbc_test = LabTest.objects.create(
            code=f'FBC{self.test.code[-4:]}',
            name=f'FBC {self.test.code}',
            specimen_type='Blood',
            price=Decimal('40'),
            stock_tracking='immeasurable',
        )
        fbc_dil.tests.add(fbc_test)
        fbc_result = LabResult.objects.create(order=self.order, test=fbc_test, status='pending')
        fbc_result.status = 'completed'
        fbc_result.save()
        fbc_dil.refresh_from_db()
        self.assertEqual(fbc_dil.quantity_on_hand, Decimal('20'))

        urea_result = LabResult.objects.create(order=self.order, test=urea_test, status='pending')
        urea_result.status = 'completed'
        urea_result.save()
        urea.refresh_from_db()
        self.assertEqual(urea.quantity_on_hand, Decimal('329'))

    def test_persist_diagnosis_on_lab_order(self):
        bare = Order.objects.create(
            encounter=self.encounter,
            order_type='lab',
            status='pending',
            requested_by=self.staff,
            clinical_indication='',
        )
        text = persist_lab_order_diagnosis(bare, self.encounter)
        bare.refresh_from_db()
        self.assertIn('Malaria', text)
        self.assertIn('Malaria', bare.clinical_indication)

    def test_empty_stock_skips_without_blocking(self):
        result = LabResult.objects.create(order=self.order, test=self.test, status='pending')
        summary = consume_reagents_for_completed_lab_result(result, performed_by=self.staff)
        self.assertEqual(summary['consumed'], 0)
        result.status = 'completed'
        result.save()
        self.kit.refresh_from_db()
        self.assertEqual(self.kit.quantity_on_hand, Decimal('0'))
