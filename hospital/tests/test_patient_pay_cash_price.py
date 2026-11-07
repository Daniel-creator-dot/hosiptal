"""Insurance excess labs and drugs collected at the cashier use the cash tariff."""
import uuid
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

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
from hospital.models_payment_verification import PharmacyDispensing
from hospital.services.auto_billing_service import AutoBillingService
from hospital.services.patient_pay_cash_pricing import (
    reprice_invoice_patient_pay_lines,
    reprice_patient_pay_lines_for_patient,
)
from hospital.utils_billing import (
    billed_lab_or_scan_catalog_price,
    get_drug_price_for_prescription,
    with_service_sustainability,
)


class PatientPayCashTariffTests(TestCase):
    def setUp(self):
        suf = uuid.uuid4().hex[:8]
        self.dept = Department.objects.create(name=f'Excess{suf}', code=f'EX{suf[:4]}')
        self.user = User.objects.create_user(username=f'ex_{suf}', password='x')
        self.staff = Staff.objects.create(
            user=self.user,
            profession='doctor',
            department=self.dept,
        )
        self.nhis = Payer.objects.create(name=f'NHIS Excess {suf}', payer_type='nhis', is_active=True)
        self.patient = Patient.objects.create(
            first_name='Ama',
            last_name=f'Excess{suf}',
            mrn=f'PMC-EX-{suf}',
            primary_insurance=self.nhis,
        )
        self.encounter = Encounter.objects.create(
            patient=self.patient,
            encounter_type='outpatient',
            provider=self.staff,
            chief_complaint='excess',
        )
        self.invoice = Invoice.all_objects.filter(encounter=self.encounter, is_deleted=False).first()
        self.assertIsNotNone(self.invoice)
        self.invoice.payer = self.nhis
        self.invoice.save(update_fields=['payer'])

        self.excluded_drug = Drug.objects.create(
            name=f'ExcessMed{suf}',
            strength='500mg',
            form='Tablet',
            pack_size='10',
            unit_price=Decimal('100.00'),
            exclude_from_insurance=True,
            insurance_exclusion_reason='Not on the insurance list',
        )
        self.covered_drug = Drug.objects.create(
            name=f'CoveredMed{suf}',
            strength='250mg',
            form='Tablet',
            pack_size='10',
            unit_price=Decimal('100.00'),
            nhis_covered=True,
        )
        self.excluded_lab = LabTest.objects.create(
            code=f'XL{suf[:6]}',
            name=f'Excess Lab {suf}',
            specimen_type='Blood',
            price=Decimal('80.00'),
            nhis_covered=False,
        )
        self.covered_lab = LabTest.objects.create(
            code=f'CL{suf[:6]}',
            name=f'Covered Lab {suf}',
            specimen_type='Blood',
            price=Decimal('80.00'),
            nhis_covered=True,
        )
        self.cash_drug_price = get_drug_price_for_prescription(self.excluded_drug, payer=None)
        self.insurance_drug_price = get_drug_price_for_prescription(self.excluded_drug, payer=self.nhis)
        self.cash_lab_price = billed_lab_or_scan_catalog_price(self.excluded_lab.price, payer=None, kind='lab')
        self.insurance_lab_price = billed_lab_or_scan_catalog_price(
            self.excluded_lab.price, payer=self.nhis, kind='lab',
        )

    def _order(self, order_type):
        return Order.objects.create(
            encounter=self.encounter,
            order_type=order_type,
            status='pending',
            requested_by=self.staff,
        )

    def _prescription(self, drug):
        return Prescription.objects.create(
            order=self._order('medication'),
            drug=drug,
            quantity=2,
            dose='1',
            route='oral',
            frequency='bd',
            duration='5d',
            prescribed_by=self.staff,
        )

    def test_cash_tariff_is_lower_than_insurance_tariff(self):
        self.assertEqual(self.cash_drug_price, with_service_sustainability(Decimal('100.00')))
        self.assertEqual(self.cash_drug_price, Decimal('110.00'))
        self.assertEqual(self.insurance_drug_price, Decimal('143.00'))
        self.assertEqual(self.cash_lab_price, Decimal('88.00'))
        self.assertGreater(self.insurance_lab_price, self.cash_lab_price)

    def _service_code(self, code, description, category):
        sc, _ = ServiceCode.objects.get_or_create(
            code=code[:80],
            defaults={'description': description[:200], 'category': category, 'is_active': True},
        )
        return sc

    def test_excluded_drug_line_is_stored_at_cash_price(self):
        rx = self._prescription(self.excluded_drug)
        sc = self._service_code(
            f'DRUG-{self.excluded_drug.pk}',
            self.excluded_drug.name,
            'Pharmacy',
        )
        line = InvoiceLine(
            invoice=self.invoice,
            service_code=sc,
            prescription=rx,
            description=self.excluded_drug.name,
            quantity=Decimal('2'),
            unit_price=self.insurance_drug_price,
            line_total=self.insurance_drug_price * 2,
        )
        line.save()
        line.refresh_from_db()
        self.assertTrue(line.patient_pay_cash)
        self.assertTrue(line.is_insurance_excluded)
        self.assertEqual(line.unit_price, self.cash_drug_price)
        self.assertEqual(line.line_total, self.cash_drug_price * 2)

    def test_covered_drug_line_keeps_insurance_price(self):
        rx = self._prescription(self.covered_drug)
        sc = self._service_code(
            f'DRUG-{self.covered_drug.pk}',
            self.covered_drug.name,
            'Pharmacy',
        )
        line = InvoiceLine(
            invoice=self.invoice,
            service_code=sc,
            prescription=rx,
            description=self.covered_drug.name,
            quantity=Decimal('1'),
            unit_price=self.insurance_drug_price,
            line_total=self.insurance_drug_price,
        )
        line.save()
        line.refresh_from_db()
        self.assertFalse(line.patient_pay_cash)
        self.assertEqual(line.unit_price, self.insurance_drug_price)

    def test_excluded_lab_line_is_stored_at_cash_price(self):
        sc = self._service_code(
            f'LAB-{self.excluded_lab.code}',
            self.excluded_lab.name,
            'Laboratory',
        )
        line = InvoiceLine(
            invoice=self.invoice,
            service_code=sc,
            description=self.excluded_lab.name,
            quantity=Decimal('1'),
            unit_price=self.insurance_lab_price,
            line_total=self.insurance_lab_price,
        )
        line.save()
        line.refresh_from_db()
        self.assertTrue(line.patient_pay_cash)
        self.assertEqual(line.unit_price, self.cash_lab_price)
        self.assertEqual(line.line_total, self.cash_lab_price)

    def test_covered_lab_line_is_not_repriced(self):
        sc = self._service_code(
            f'LAB-{self.covered_lab.code}',
            self.covered_lab.name,
            'Laboratory',
        )
        line = InvoiceLine(
            invoice=self.invoice,
            service_code=sc,
            description=self.covered_lab.name,
            quantity=Decimal('1'),
            unit_price=self.insurance_lab_price,
            line_total=self.insurance_lab_price,
        )
        line.save()
        line.refresh_from_db()
        self.assertFalse(line.patient_pay_cash)
        self.assertEqual(line.unit_price, self.insurance_lab_price)

    def test_cashier_reprice_fixes_an_existing_excess_line(self):
        rx = self._prescription(self.excluded_drug)
        sc = self._service_code(
            f'DRUG-OLD-{self.excluded_drug.pk}',
            self.excluded_drug.name,
            'Pharmacy',
        )
        line = InvoiceLine.objects.create(
            invoice=self.invoice,
            service_code=sc,
            prescription=rx,
            description=self.excluded_drug.name,
            quantity=Decimal('1'),
            unit_price=self.cash_drug_price,
            line_total=self.cash_drug_price,
        )
        InvoiceLine.objects.filter(pk=line.pk).update(
            unit_price=self.insurance_drug_price,
            line_total=self.insurance_drug_price,
        )
        changed = reprice_patient_pay_lines_for_patient(self.patient)
        self.assertGreaterEqual(changed, 1)
        line.refresh_from_db()
        self.assertEqual(line.unit_price, self.cash_drug_price)
        self.invoice.refresh_from_db()
        self.assertGreater(self.invoice.balance, Decimal('0'))

    def test_pharmacy_send_of_excess_drug_bills_cash_and_waits_for_cashier(self):
        rx = self._prescription(self.excluded_drug)
        PharmacyDispensing.objects.create(
            prescription=rx,
            patient=self.patient,
            quantity_ordered=2,
            dispensing_status='pending_payment',
        )
        result = AutoBillingService.create_pharmacy_bill(rx, payer=self.nhis, invoice=self.invoice)
        self.assertTrue(result.get('success'), result)
        line = result['invoice_line']
        line.refresh_from_db()
        self.assertTrue(line.patient_pay_cash)
        self.assertEqual(line.unit_price, self.cash_drug_price)
        disp = result['dispensing_record']
        disp.refresh_from_db()
        self.assertEqual(disp.dispensing_status, 'pending_payment')
        self.assertIsNone(disp.payment_verified_at)

    def test_reprice_skips_paid_invoice(self):
        rx = self._prescription(self.excluded_drug)
        sc = self._service_code(
            f'DRUG-PAID-{self.excluded_drug.pk}',
            self.excluded_drug.name,
            'Pharmacy',
        )
        line = InvoiceLine.objects.create(
            invoice=self.invoice,
            service_code=sc,
            prescription=rx,
            description=self.excluded_drug.name,
            quantity=Decimal('1'),
            unit_price=self.cash_drug_price,
            line_total=self.cash_drug_price,
        )
        InvoiceLine.objects.filter(pk=line.pk).update(
            unit_price=self.insurance_drug_price,
            line_total=self.insurance_drug_price,
        )
        Invoice.all_objects.filter(pk=self.invoice.pk).update(
            status='paid',
            balance=Decimal('0.00'),
            total_amount=self.insurance_drug_price,
        )
        self.invoice.refresh_from_db()
        changed = reprice_invoice_patient_pay_lines(self.invoice)
        self.assertEqual(changed, 0)
        line.refresh_from_db()
        self.assertEqual(line.unit_price, self.insurance_drug_price)
