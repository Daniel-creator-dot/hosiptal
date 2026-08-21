"""
Pharmacy can dispense when the drug amount is paid even if other encounter
invoice services (consult/lab) remain unpaid. Total Bill must show pharmacy
as paid without inviting a duplicate pharmacy payment.
"""
import uuid
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from hospital.models import (
    Department,
    Drug,
    Encounter,
    Invoice,
    InvoiceLine,
    Order,
    Patient,
    Prescription,
    ServiceCode,
    Staff,
)
from hospital.models_accounting import PaymentReceipt, Transaction
from hospital.models_payment_verification import PharmacyDispensing
from hospital.services.pharmacy_invoice_payment_link import (
    link_pharmacy_dispensing_when_invoice_paid,
)
from hospital.utils_invoice_line import (
    invoice_breakdown_rows_for_display,
    invoice_pharmacy_lines_are_settled,
)
from hospital.views_departments import _evaluate_pharmacy_order_dispense


class PharmacyPortionPaymentDispenseTests(TestCase):
    def setUp(self):
        suf = uuid.uuid4().hex[:8]
        self.user = User.objects.create_user(
            username=f'pharm_portion_{suf}',
            password='x',
        )
        self.dept = Department.objects.create(name=f'OPD Portion {suf}', code=f'OP{suf[:4]}')
        self.staff = Staff.objects.create(
            user=self.user,
            profession='pharmacist',
            department=self.dept,
        )
        self.patient = Patient.objects.create(
            first_name='Cash',
            last_name=f'Patient{suf}',
            mrn=f'PMC-PP-{suf}',
        )
        self.encounter = Encounter.objects.create(
            patient=self.patient,
            encounter_type='outpatient',
            chief_complaint='test',
            provider=self.staff,
        )
        # Prefer encounter invoice created by signals; otherwise create one.
        self.invoice = Invoice.all_objects.filter(
            encounter=self.encounter, is_deleted=False
        ).order_by('-created').first()
        if not self.invoice:
            self.invoice = Invoice.objects.create(
                patient=self.patient,
                encounter=self.encounter,
                status='issued',
            )
        # Clear any auto lines so we control consult + pharmacy totals.
        InvoiceLine.objects.filter(invoice=self.invoice, is_deleted=False).update(is_deleted=True)

        self.consult_code = ServiceCode.objects.create(
            code=f'CONSULT-{suf}',
            description='Consultation',
            category='consultation',
        )
        self.drug = Drug.objects.create(
            name=f'Amoxicillin{suf}',
            strength='500mg',
            form='Tablet',
            pack_size='10',
            unit_price=Decimal('10.00'),
        )
        self.drug_code, _ = ServiceCode.objects.get_or_create(
            code=f'DRUG-{self.drug.id}',
            defaults={
                'description': self.drug.name,
                'category': 'pharmacy',
            },
        )
        InvoiceLine.objects.create(
            invoice=self.invoice,
            service_code=self.consult_code,
            description='Consultation',
            quantity=Decimal('1'),
            unit_price=Decimal('50.00'),
            line_total=Decimal('50.00'),
        )
        self.order = Order.objects.create(
            encounter=self.encounter,
            order_type='medication',
            status='pending',
            requested_by=self.staff,
        )
        self.rx = Prescription.objects.create(
            order=self.order,
            drug=self.drug,
            quantity=10,
            dose='1',
            route='oral',
            frequency='bd',
            duration='5d',
            prescribed_by=self.staff,
        )
        InvoiceLine.objects.create(
            invoice=self.invoice,
            service_code=self.drug_code,
            description=self.drug.name,
            quantity=Decimal('10'),
            unit_price=Decimal('10.00'),
            line_total=Decimal('100.00'),
            prescription=self.rx,
        )
        self.disp = PharmacyDispensing.objects.create(
            prescription=self.rx,
            patient=self.patient,
            quantity_ordered=10,
            dispensing_status='pending_payment',
        )
        self.invoice.update_totals()
        self.invoice.refresh_from_db()

    def _apply_payment(self, amount):
        trans = Transaction.objects.create(
            transaction_type='payment_received',
            invoice=self.invoice,
            patient=self.patient,
            amount=amount,
            payment_method='cash',
            processed_by=self.user,
            transaction_number=f'TXN-{uuid.uuid4().hex[:12]}',
        )
        PaymentReceipt.objects.create(
            transaction=trans,
            invoice=self.invoice,
            patient=self.patient,
            amount_paid=amount,
            payment_method='cash',
            received_by=self.user,
            service_type='pharmacy_prescription',
            service_details={
                'pharmacy_encounter': True,
                'prescriptions': [{'prescription_id': str(self.rx.id)}],
            },
        )
        self.invoice.update_totals()
        self.invoice.refresh_from_db()

    def test_pharmacy_settled_while_consult_unpaid(self):
        self._apply_payment(Decimal('100.00'))
        self.assertEqual(self.invoice.balance, Decimal('50.00'))
        self.assertTrue(invoice_pharmacy_lines_are_settled(self.invoice))

        link_pharmacy_dispensing_when_invoice_paid(
            self.invoice, refresh_invoice=False
        )
        self.disp.refresh_from_db()
        self.assertEqual(self.disp.dispensing_status, 'ready_to_dispense')
        self.assertIsNotNone(self.disp.payment_receipt_id)

    def test_dispense_allowed_when_pharmacy_paid_consult_open(self):
        self._apply_payment(Decimal('100.00'))
        link_pharmacy_dispensing_when_invoice_paid(self.invoice, refresh_invoice=False)
        self.disp.refresh_from_db()

        evaluation = _evaluate_pharmacy_order_dispense(self.order)
        self.assertTrue(evaluation['can_dispense'])
        self.assertFalse(evaluation['encounter_invoice_settled'])
        self.assertTrue(evaluation['pharmacy_portion_settled'])

    def test_partial_pharmacy_payment_does_not_clear(self):
        self._apply_payment(Decimal('40.00'))
        self.assertFalse(invoice_pharmacy_lines_are_settled(self.invoice))
        updated = link_pharmacy_dispensing_when_invoice_paid(
            self.invoice, refresh_invoice=False
        )
        self.assertEqual(updated, 0)
        self.disp.refresh_from_db()
        self.assertEqual(self.disp.dispensing_status, 'pending_payment')

    def test_total_bill_shows_pharmacy_paid_not_duplicate_due(self):
        self._apply_payment(Decimal('100.00'))
        rows = invoice_breakdown_rows_for_display(self.invoice)
        pharmacy_rows = [
            r for r in rows if 'Amoxicillin' in (r.get('description') or '')
        ]
        consult_rows = [
            r for r in rows if 'Consultation' in (r.get('description') or '')
        ]
        self.assertTrue(pharmacy_rows)
        self.assertTrue(
            all(r['is_paid'] and r['amount'] == Decimal('0.00') for r in pharmacy_rows)
        )
        self.assertTrue(consult_rows)
        consult_due = sum((r['amount'] for r in consult_rows), Decimal('0.00'))
        self.assertEqual(consult_due, Decimal('50.00'))

    def test_link_does_not_overwrite_existing_receipt(self):
        self._apply_payment(Decimal('100.00'))
        first = PaymentReceipt.objects.filter(invoice=self.invoice).first()
        link_pharmacy_dispensing_when_invoice_paid(
            self.invoice, receipt=first, refresh_invoice=False
        )
        self.disp.refresh_from_db()
        self.assertEqual(self.disp.payment_receipt_id, first.id)

        trans2 = Transaction.objects.create(
            transaction_type='payment_received',
            invoice=self.invoice,
            patient=self.patient,
            amount=Decimal('50.00'),
            payment_method='cash',
            processed_by=self.user,
            transaction_number=f'TXN-{uuid.uuid4().hex[:12]}',
        )
        second = PaymentReceipt.objects.create(
            transaction=trans2,
            invoice=self.invoice,
            patient=self.patient,
            amount_paid=Decimal('50.00'),
            payment_method='cash',
            received_by=self.user,
            service_type='combined',
        )
        link_pharmacy_dispensing_when_invoice_paid(
            self.invoice, receipt=second, refresh_invoice=False
        )
        self.disp.refresh_from_db()
        self.assertEqual(self.disp.payment_receipt_id, first.id)
