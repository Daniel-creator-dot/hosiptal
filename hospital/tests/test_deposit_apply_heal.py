"""Deposit apply must use remaining credit when available_balance was out of sync with used_amount."""
import uuid
from decimal import Decimal

from django.test import TestCase

from hospital.models import Invoice, InvoiceLine, Payer, Patient, ServiceCode
from hospital.models_patient_deposits import PatientDeposit
from hospital.services.deposit_payment_service import apply_deposit_to_all_patient_invoices


class DepositApplyHealTests(TestCase):
    def test_apply_uses_remaining_when_available_balance_was_zeroed(self):
        """
        If available_balance was incorrectly 0 while used_amount < deposit_amount, the old
        queryset excluded the row; UI could still show remaining credit via deposit_amount - used.
        """
        patient = Patient.objects.create(
            first_name='Dep',
            last_name='Test',
            mrn=f'PMC-DEP-{uuid.uuid4().hex[:8]}',
        )
        payer = Payer.objects.create(name='Cash Dep', payer_type='cash')
        sc = ServiceCode.objects.create(
            code=f'DEP-SVC-{uuid.uuid4().hex[:8]}',
            description='Svc',
            category='test',
        )
        inv = Invoice.objects.create(
            patient=patient,
            encounter=None,
            payer=payer,
            status='issued',
        )
        InvoiceLine.objects.create(
            invoice=inv,
            service_code=sc,
            description='Line',
            quantity=Decimal('1'),
            unit_price=Decimal('500.00'),
            line_total=Decimal('500.00'),
        )
        inv.update_totals()
        inv.refresh_from_db()

        dep = PatientDeposit.objects.create(
            patient=patient,
            deposit_amount=Decimal('1000.00'),
            payment_method='cash',
            deposit_date=inv.issued_at,
        )
        dep.refresh_from_db()
        self.assertEqual(dep.available_balance, Decimal('1000.00'))

        # Simulate bad row: half applied in applications but available_balance not updated
        PatientDeposit.objects.filter(pk=dep.pk).update(
            used_amount=Decimal('500.00'),
            available_balance=Decimal('0.00'),
        )

        total_applied = apply_deposit_to_all_patient_invoices(patient, create_receipt=True)
        self.assertEqual(total_applied, Decimal('500.00'))

        dep.refresh_from_db()
        inv.refresh_from_db()
        self.assertEqual(dep.available_balance, Decimal('0.00'))
        self.assertEqual(dep.used_amount, Decimal('1000.00'))
        self.assertLessEqual(inv.balance, Decimal('0.00'))
