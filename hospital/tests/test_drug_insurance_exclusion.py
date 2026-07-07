"""Drug-level insurance exclusion (formulary flag + billing integration)."""
import uuid
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from hospital.models import (
    Department,
    Drug,
    Encounter,
    Invoice,
    InvoiceLine,
    LabTest,
    Order,
    Patient,
    Payer,
    Prescription,
    ServiceCode,
    Staff,
)
from hospital.models_insurance_companies import (
    InsuranceCompany,
    InsuranceExclusionRule,
    PatientInsurance,
)
from hospital.services.insurance_exclusion_service import InsuranceExclusionService, catalog_exclusion_info
from hospital.services.drug_formulary_insurance_exclusion import sync_drug_formulary_insurance_exclusions


class DrugInsuranceExclusionTests(TestCase):
    def setUp(self):
        suf = uuid.uuid4().hex[:8]
        self.dept = Department.objects.create(name=f'InsEx{suf}', code=f'IE{suf[:4]}')
        self.user = User.objects.create_user(username=f'doc_{suf}', password='x')
        self.staff = Staff.objects.create(
            user=self.user,
            profession='doctor',
            department=self.dept,
        )

        self.patient = Patient.objects.create(
            first_name='Ins',
            last_name=f'Patient{suf}',
            mrn=f'PMC-IE-{suf}',
        )
        self.cash_payer = Payer.objects.create(name=f'Cash{suf}', payer_type='cash')
        self.ins_payer = Payer.objects.create(name=f'NHIS Test{suf}', payer_type='nhis')

        self.company = InsuranceCompany.objects.create(
            name=f'NHIS Test{suf}',
            code=f'NH{suf[:4]}',
        )
        PatientInsurance.objects.create(
            patient=self.patient,
            insurance_company=self.company,
            policy_number=f'POL-{suf}',
            member_id=f'MEM-{suf}',
            effective_date=timezone.now().date(),
            status='active',
            is_primary=True,
        )

        self.drug = Drug.objects.create(
            name=f'ExcludedMed{suf}',
            strength='500mg',
            form='Tablet',
            pack_size='10',
            unit_price=Decimal('10.00'),
        )
        self.other_drug = Drug.objects.create(
            name=f'CoveredMed{suf}',
            strength='250mg',
            form='Tablet',
            pack_size='10',
            unit_price=Decimal('5.00'),
        )
        self.service_code = ServiceCode.objects.create(
            code=f'RX-{suf}',
            description='Pharmacy',
            category='pharmacy',
        )

    def test_drug_flag_requires_patient_pay_for_insurance_payer(self):
        self.drug.exclude_from_insurance = True
        self.drug.insurance_exclusion_reason = 'Not on NHIS formulary'
        self.drug.save(update_fields=['exclude_from_insurance', 'insurance_exclusion_reason'])

        result = InsuranceExclusionService(
            patient=self.patient,
            payer=self.ins_payer,
            drug=self.drug,
        ).evaluate()

        self.assertTrue(result.is_excluded)
        self.assertTrue(result.requires_patient_pay)
        self.assertFalse(result.should_block)
        self.assertEqual(result.reason, 'Not on NHIS formulary')
        self.assertIsNone(result.rule)

    def test_drug_flag_skipped_for_cash_payer(self):
        self.drug.exclude_from_insurance = True
        self.drug.save(update_fields=['exclude_from_insurance'])

        result = InsuranceExclusionService(
            patient=self.patient,
            payer=self.cash_payer,
            drug=self.drug,
        ).evaluate()

        self.assertFalse(result.is_excluded)
        self.assertFalse(result.requires_patient_pay)

    def test_drug_flag_skipped_for_corporate_payer(self):
        corporate_payer = Payer.objects.create(
            name=f'Corp{uuid.uuid4().hex[:8]}',
            payer_type='corporate',
        )
        self.drug.exclude_from_insurance = True
        self.drug.save(update_fields=['exclude_from_insurance'])

        result = InsuranceExclusionService(
            patient=self.patient,
            payer=corporate_payer,
            drug=self.drug,
        ).evaluate()

        self.assertFalse(result.is_excluded)
        self.assertFalse(result.requires_patient_pay)

    def test_drug_flag_default_reason_when_blank(self):
        self.drug.exclude_from_insurance = True
        self.drug.save(update_fields=['exclude_from_insurance'])

        result = InsuranceExclusionService(
            patient=self.patient,
            payer=self.ins_payer,
            drug=self.drug,
        ).evaluate()

        self.assertIn(self.drug.name, result.reason)
        self.assertIn('pay cash', result.reason.lower())

    def test_invoice_line_marks_patient_pay_without_company_rule(self):
        self.drug.exclude_from_insurance = True
        self.drug.insurance_exclusion_reason = 'OTC not covered'
        self.drug.save(update_fields=['exclude_from_insurance', 'insurance_exclusion_reason'])

        encounter = Encounter.objects.create(
            patient=self.patient,
            encounter_type='outpatient',
            provider=self.staff,
            chief_complaint='rx',
        )
        order = Order.objects.create(
            encounter=encounter,
            order_type='medication',
            status='pending',
            requested_by=self.staff,
        )
        rx = Prescription.objects.create(
            order=order,
            drug=self.drug,
            quantity=5,
            dose='1',
            route='oral',
            frequency='od',
            duration='5d',
            prescribed_by=self.staff,
        )
        invoice = Invoice.all_objects.filter(encounter=encounter).first()
        self.assertIsNotNone(invoice, 'Encounter should have an auto-created invoice')
        invoice.payer = self.ins_payer
        invoice.save(update_fields=['payer'])
        line = InvoiceLine(
            invoice=invoice,
            service_code=self.service_code,
            prescription=rx,
            description=self.drug.name,
            quantity=Decimal('5'),
            unit_price=Decimal('10.00'),
            line_total=Decimal('50.00'),
        )
        line.save()

        line.refresh_from_db()
        self.assertTrue(line.is_insurance_excluded)
        self.assertTrue(line.patient_pay_cash)
        self.assertEqual(line.insurance_exclusion_reason, 'OTC not covered')
        self.assertIsNone(line.insurance_exclusion_rule_id)

    def test_company_rule_still_applies_when_drug_flag_off(self):
        InsuranceExclusionRule.objects.create(
            insurance_company=self.company,
            rule_type='drug',
            drug=self.other_drug,
            enforcement_action='patient_pay',
            reason='Company list exclusion',
            is_active=True,
            apply_to_all_plans=True,
        )

        result = InsuranceExclusionService(
            patient=self.patient,
            payer=self.ins_payer,
            drug=self.other_drug,
        ).evaluate()

        self.assertTrue(result.is_excluded)
        self.assertTrue(result.requires_patient_pay)
        self.assertEqual(result.reason, 'Company list exclusion')
        self.assertIsNotNone(result.rule)


class DrugSelectiveInsuranceExclusionTests(TestCase):
    def setUp(self):
        suf = uuid.uuid4().hex[:8]
        self.nhis_payer = Payer.objects.create(name=f'NHIS Select{suf}', payer_type='nhis')
        self.other_payer = Payer.objects.create(name=f'Other Ins{suf}', payer_type='private')
        self.company_nhis = InsuranceCompany.objects.create(
            name=f'NHIS Select{suf}',
            code=f'NS{suf[:4]}',
        )
        self.company_other = InsuranceCompany.objects.create(
            name=f'Other Ins{suf}',
            code=f'OI{suf[:4]}',
        )
        self.drug = Drug.objects.create(
            name=f'SelectiveMed{suf}',
            strength='500mg',
            form='Tablet',
            pack_size='10',
            unit_price=Decimal('10.00'),
        )

    def test_selective_exclusion_applies_only_to_selected_company(self):
        sync_drug_formulary_insurance_exclusions(
            drug=self.drug,
            exclude_all=False,
            company_ids=[self.company_nhis.id],
            reason='Not on NHIS list',
        )
        self.assertFalse(self.drug.exclude_from_insurance)

        nhis_result = InsuranceExclusionService(
            patient=None,
            payer=self.nhis_payer,
            drug=self.drug,
        ).evaluate()
        self.assertTrue(nhis_result.requires_patient_pay)
        self.assertEqual(nhis_result.reason, 'Not on NHIS list')

        other_result = InsuranceExclusionService(
            patient=None,
            payer=self.other_payer,
            drug=self.drug,
        ).evaluate()
        self.assertFalse(other_result.is_excluded)

    def test_catalog_exclusion_info_respects_selective_companies(self):
        sync_drug_formulary_insurance_exclusions(
            drug=self.drug,
            exclude_all=False,
            company_ids=[self.company_nhis.id],
            reason='NHIS only',
        )
        nhis_info = catalog_exclusion_info(item=self.drug, payer=self.nhis_payer)
        other_info = catalog_exclusion_info(item=self.drug, payer=self.other_payer)

        self.assertTrue(nhis_info['is_insurance_excluded'])
        self.assertEqual(nhis_info['insurance_exclusion_reason'], 'NHIS only')
        self.assertFalse(other_info['is_insurance_excluded'])
        self.assertTrue(other_info['exclude_from_insurance'])

    def test_exclude_all_clears_selective_rules(self):
        sync_drug_formulary_insurance_exclusions(
            drug=self.drug,
            exclude_all=False,
            company_ids=[self.company_nhis.id],
            reason='NHIS only',
        )
        sync_drug_formulary_insurance_exclusions(
            drug=self.drug,
            exclude_all=True,
            company_ids=[],
            reason='All insurers',
        )
        self.drug.refresh_from_db()
        self.assertTrue(self.drug.exclude_from_insurance)

        other_result = InsuranceExclusionService(
            patient=None,
            payer=self.other_payer,
            drug=self.drug,
        ).evaluate()
        self.assertTrue(other_result.requires_patient_pay)


class LabTestInsuranceExclusionTests(TestCase):
    def setUp(self):
        suf = uuid.uuid4().hex[:8]
        self.ins_payer = Payer.objects.create(name=f'NHISLab{suf}', payer_type='nhis')
        self.corporate_payer = Payer.objects.create(name=f'CorpLab{suf}', payer_type='corporate')
        self.cash_payer = Payer.objects.create(name=f'CashLab{suf}', payer_type='cash')
        self.lab_test = LabTest.objects.create(
            code=f'LB{suf}',
            name=f'Premium Lab{suf}',
            specimen_type='Blood',
            price=Decimal('50.00'),
        )
        self.service_code = ServiceCode.objects.get(code=f'LAB-LB{suf}')

    def test_lab_flag_requires_patient_pay(self):
        self.lab_test.exclude_from_insurance = True
        self.lab_test.insurance_exclusion_reason = 'Not on panel'
        self.lab_test.save(update_fields=['exclude_from_insurance', 'insurance_exclusion_reason'])

        result = InsuranceExclusionService(
            patient=None,
            payer=self.ins_payer,
            service_code=self.service_code,
            lab_test=self.lab_test,
        ).evaluate()

        self.assertTrue(result.is_excluded)
        self.assertTrue(result.requires_patient_pay)
        self.assertEqual(result.reason, 'Not on panel')

    def test_lab_flag_via_service_code_resolution(self):
        self.lab_test.exclude_from_insurance = True
        self.lab_test.save(update_fields=['exclude_from_insurance'])

        result = InsuranceExclusionService(
            patient=None,
            payer=self.ins_payer,
            service_code=self.service_code,
        ).evaluate()

        self.assertTrue(result.requires_patient_pay)

    def test_lab_flag_skipped_for_cash(self):
        self.lab_test.exclude_from_insurance = True
        self.lab_test.save(update_fields=['exclude_from_insurance'])

        result = InsuranceExclusionService(
            patient=None,
            payer=self.cash_payer,
            lab_test=self.lab_test,
        ).evaluate()

        self.assertFalse(result.is_excluded)

    def test_lab_flag_skipped_for_corporate(self):
        self.lab_test.exclude_from_insurance = True
        self.lab_test.save(update_fields=['exclude_from_insurance'])

        result = InsuranceExclusionService(
            patient=None,
            payer=self.corporate_payer,
            lab_test=self.lab_test,
        ).evaluate()

        self.assertFalse(result.is_excluded)
        self.assertFalse(result.requires_patient_pay)
