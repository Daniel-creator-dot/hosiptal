from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from hospital.models import Patient
from hospital.models_patient_deposits import PatientDeposit
from hospital.models_accounting import Transaction


User = get_user_model()


class DepositWithdrawalTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='cashier_dep', password='pass')
        # Grant cashier access via staff profile if required by is_cashier — use force_login + bypass if needed
        self.patient = Patient.objects.create(
            first_name='Martin',
            last_name='Agbo',
            mrn='TESTDEP001',
            phone_number='0540000000',
            gender='M',
            date_of_birth='1990-01-01',
        )
        self.deposit = PatientDeposit.objects.create(
            patient=self.patient,
            deposit_amount=Decimal('100.00'),
            available_balance=Decimal('100.00'),
            used_amount=Decimal('0.00'),
            payment_method='cash',
            status='active',
            received_by=self.user,
            created_by=self.user,
        )

    def test_partial_then_full_withdrawal_unique_transactions(self):
        t1 = self.deposit.refund(
            amount=Decimal('40.00'),
            refund_method='cash',
            refunded_by=self.user,
            notes='partial',
        )
        self.deposit.refresh_from_db()
        self.assertEqual(self.deposit.available_balance, Decimal('60.00'))
        self.assertEqual(t1.transaction_type, 'refund_issued')
        self.assertTrue((t1.reference_number or '').startswith('REFUND-'))

        t2 = self.deposit.refund(
            amount=Decimal('60.00'),
            refund_method='cash',
            refunded_by=self.user,
            notes='rest',
        )
        self.deposit.refresh_from_db()
        self.assertEqual(self.deposit.available_balance, Decimal('0.00'))
        self.assertEqual(self.deposit.status, 'refunded')
        self.assertNotEqual(t1.reference_number, t2.reference_number)
        self.assertEqual(t2.amount, Decimal('60.00'))

    def test_cannot_over_withdraw(self):
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            self.deposit.refund(
                amount=Decimal('150.00'),
                refund_method='cash',
                refunded_by=self.user,
            )
