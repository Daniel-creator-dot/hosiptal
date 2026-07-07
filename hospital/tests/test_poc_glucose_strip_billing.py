"""POC glucose strip (RBS/FBS) billing from nurse vitals."""
import uuid
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.utils import timezone

from hospital.models import (
    Department,
    Drug,
    Encounter,
    InvoiceLine,
    Patient,
    PharmacyStock,
    Staff,
    VitalSign,
)
from hospital.models_payment_verification import PharmacyStockDeductionLog
from hospital.services.auto_billing_service import AutoBillingService


class PocGlucoseStripBillingTests(TestCase):
    def setUp(self):
        self.dept = Department.objects.create(name='VitDept', code=f'VD-{uuid.uuid4().hex[:6]}')
        self.user = User.objects.create_user(username=f'nu_{uuid.uuid4().hex[:8]}', password='x')
        self.staff = Staff.objects.create(user=self.user, profession='nurse', department=self.dept)
        self.patient = Patient.objects.create(
            first_name='Glu',
            last_name='Strip',
            phone_number='233200000033',
            date_of_birth=timezone.now().date(),
        )
        self.encounter = Encounter.objects.create(
            patient=self.patient,
            encounter_type='outpatient',
            provider=self.staff,
            chief_complaint='vitals',
        )

    @override_settings(POC_GLUCOSE_STRIP_GHS=Decimal('20.00'))
    def test_rbs_creates_invoice_line(self):
        vital = VitalSign.objects.create(encounter=self.encounter, pulse=72, recorded_by=self.staff)
        result = AutoBillingService.bill_poc_glucose_strip(self.encounter, 'rbs', vital_sign=vital)
        self.assertTrue(result['success'], msg=result.get('message'))
        line = InvoiceLine.objects.filter(
            invoice__encounter=self.encounter,
            service_code__code='VITAL-POC-RBS',
            is_deleted=False,
        ).first()
        self.assertIsNotNone(line)
        self.assertEqual(line.quantity, Decimal('1'))
        self.assertEqual(line.unit_price, Decimal('20.00'))
        self.assertTrue(line.patient_pay_cash)
        self.assertTrue(line.is_insurance_excluded)

    @override_settings(POC_GLUCOSE_STRIP_GHS=Decimal('20.00'))
    def test_second_strip_merges_quantity(self):
        v1 = VitalSign.objects.create(encounter=self.encounter, pulse=70, recorded_by=self.staff)
        v2 = VitalSign.objects.create(encounter=self.encounter, pulse=71, recorded_by=self.staff)
        r1 = AutoBillingService.bill_poc_glucose_strip(self.encounter, 'fbs', vital_sign=v1)
        r2 = AutoBillingService.bill_poc_glucose_strip(self.encounter, 'fbs', vital_sign=v2)
        self.assertTrue(r1['success'])
        self.assertTrue(r2['success'])
        line = InvoiceLine.objects.filter(
            invoice__encounter=self.encounter,
            service_code__code='VITAL-POC-FBS',
            is_deleted=False,
        ).first()
        self.assertIsNotNone(line)
        self.assertEqual(line.quantity, Decimal('2'))

    @override_settings(POC_GLUCOSE_STRIP_GHS=Decimal('20.00'))
    def test_billing_closed_skips_line(self):
        self.encounter.billing_closed_at = timezone.now()
        self.encounter.save(update_fields=['billing_closed_at'])
        vital = VitalSign.objects.create(encounter=self.encounter, pulse=75, recorded_by=self.staff)
        result = AutoBillingService.bill_poc_glucose_strip(self.encounter, 'rbs', vital_sign=vital)
        self.assertFalse(result['success'])
        self.assertEqual(result.get('error'), 'billing_closed')
        exists = InvoiceLine.objects.filter(
            invoice__encounter=self.encounter,
            service_code__code='VITAL-POC-RBS',
            is_deleted=False,
        ).exists()
        self.assertFalse(exists)

    @override_settings(POC_GLUCOSE_STRIP_GHS=Decimal('20.00'))
    def test_invalid_strip_type(self):
        vital = VitalSign.objects.create(encounter=self.encounter, pulse=80, recorded_by=self.staff)
        result = AutoBillingService.bill_poc_glucose_strip(self.encounter, 'xyz', vital_sign=vital)
        self.assertFalse(result['success'])
        self.assertEqual(result.get('error'), 'invalid_strip_type')

    def test_stock_deducted_when_drug_id_configured(self):
        drug = Drug.objects.create(
            name='Glucose Test Strips',
            generic_name='',
            strength='50',
            form='Kit',
            pack_size='50 strips',
            category='other',
        )
        stock = PharmacyStock.objects.create(
            drug=drug,
            batch_number=f'B-{uuid.uuid4().hex[:8]}',
            expiry_date=timezone.now().date(),
            quantity_on_hand=10,
            initial_quantity=10,
        )
        with override_settings(
            POC_GLUCOSE_STRIP_GHS=Decimal('20.00'),
            POC_GLUCOSE_STRIP_DRUG_ID=str(drug.pk),
        ):
            vital = VitalSign.objects.create(encounter=self.encounter, pulse=68, recorded_by=self.staff)
            result = AutoBillingService.bill_poc_glucose_strip(self.encounter, 'rbs', vital_sign=vital)
        self.assertTrue(result['success'])
        stock.refresh_from_db()
        self.assertEqual(stock.quantity_on_hand, 9)
        log = PharmacyStockDeductionLog.objects.filter(
            source_type=PharmacyStockDeductionLog.SOURCE_VITAL_POC_GLUCOSE,
            source_id=vital.pk,
        ).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.quantity, 1)
