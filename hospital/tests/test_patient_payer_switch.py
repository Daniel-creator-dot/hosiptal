"""Insurance/corporate → cash must stick: enrollments, snapshot name, invoices, visit sync."""
import uuid
from datetime import date
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from hospital.models import Encounter, Invoice, InvoiceLine, Patient, Payer, ServiceCode
from hospital.models_insurance_companies import InsuranceCompany, PatientInsurance
from hospital.patient_payer import switch_patient_to_cash_payer
from hospital.services.visit_payer_sync_service import visit_payer_sync_service
from hospital.utils_billing import get_patient_payer_info


class SwitchPatientToCashPayerTests(TestCase):
    def setUp(self):
        suf = uuid.uuid4().hex[:6]
        self.ins_payer = Payer.objects.create(
            name=f'NHIS Switch {suf}',
            payer_type='nhis',
            is_active=True,
        )
        self.patient = Patient.objects.create(
            first_name='Payer',
            last_name=f'Switch{suf}',
            mrn=f'PMC-PSW-{suf}',
            date_of_birth=date(1990, 1, 1),
            gender='F',
            primary_insurance=self.ins_payer,
            insurance_company=self.ins_payer.name,
        )
        self.company = InsuranceCompany.objects.create(
            name=self.ins_payer.name,
            code=f'SW{suf[:4].upper()}',
        )
        PatientInsurance.objects.create(
            patient=self.patient,
            insurance_company=self.company,
            policy_number=f'POL-{suf}',
            member_id=f'MEM-{suf}',
            effective_date=timezone.localdate(),
            status='active',
            is_primary=True,
        )
        self.encounter = Encounter.objects.create(
            patient=self.patient,
            encounter_type='outpatient',
            status='active',
            started_at=timezone.now(),
            chief_complaint='test',
        )
        self.invoice = (
            Invoice.all_objects.filter(encounter=self.encounter, is_deleted=False)
            .order_by('-created')
            .first()
        )
        if not self.invoice:
            self.invoice = Invoice.all_objects.create(
                patient=self.patient,
                encounter=self.encounter,
                payer=self.ins_payer,
                status='issued',
                total_amount=Decimal('50.00'),
                balance=Decimal('50.00'),
            )
        else:
            self.invoice.payer = self.ins_payer
            self.invoice.status = 'issued'
            self.invoice.total_amount = Decimal('50.00')
            self.invoice.balance = Decimal('50.00')
            self.invoice.save(update_fields=['payer', 'status', 'total_amount', 'balance'])
        sc = ServiceCode.objects.create(
            code=f'SW-{suf}',
            description='Consult',
            category='consultation',
        )
        InvoiceLine.objects.create(
            invoice=self.invoice,
            service_code=sc,
            description='Consult',
            quantity=Decimal('1'),
            unit_price=Decimal('50.00'),
            line_total=Decimal('50.00'),
        )

    def test_switch_cancels_enrollment_and_reports_cash(self):
        cash = switch_patient_to_cash_payer(self.patient)
        self.assertEqual(cash.payer_type, 'cash')
        self.patient.refresh_from_db()
        self.assertEqual(self.patient.primary_insurance_id, cash.pk)
        self.assertEqual((self.patient.insurance_company or '').strip(), '')

        enr = PatientInsurance.objects.get(patient=self.patient)
        self.assertEqual(enr.status, 'cancelled')
        self.assertFalse(enr.is_primary)

        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.payer_id, cash.pk)

        info = get_patient_payer_info(self.patient, self.encounter)
        self.assertEqual((info.get('type') or '').lower(), 'cash')
        self.assertFalse(info.get('is_insurance_or_corporate'))

    def test_visit_sync_explicit_cash_overrides_insurance(self):
        result = visit_payer_sync_service.verify_and_set_payer_type(
            encounter=self.encounter,
            payer_type='cash',
        )
        self.assertTrue(result['success'])
        self.assertEqual((result['payer_type'] or '').lower(), 'cash')
        self.patient.refresh_from_db()
        self.assertEqual(self.patient.primary_insurance.payer_type, 'cash')

        info = get_patient_payer_info(self.patient, self.encounter)
        self.assertFalse(info.get('is_insurance_or_corporate'))
        self.assertEqual((info.get('type') or '').lower(), 'cash')

    def test_visit_sync_auto_detect_does_not_clobber_insurance(self):
        result = visit_payer_sync_service.verify_and_set_payer_type(
            encounter=self.encounter,
            payer_type=None,
        )
        self.assertTrue(result['success'])
        self.patient.refresh_from_db()
        self.assertNotEqual(self.patient.primary_insurance.payer_type, 'cash')
