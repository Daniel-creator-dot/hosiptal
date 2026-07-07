"""
Regression tests for bug fixes: URL routing, remittance caps, discount GL, month parsing.
"""
import uuid
from datetime import date
from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from hospital.models import Invoice, InvoiceLine, Patient, Payer, ServiceCode
from hospital.models_accounting import Account, JournalEntryLine
from hospital.models_accounting_advanced import BankAccount
from hospital.models_primecare_accounting import InsurancePaymentReceived, InsuranceReceivableEntry
from hospital.models_supplier_payables import SupplierPayableLine
from hospital.models_missing_features import Supplier
from hospital.services.combined_bill_discount_service import (
    distribute_combined_bill_discount_across_invoices,
)
from hospital.services.receivable_grouping_service import (
    apply_payment_to_entry,
    month_bounds,
    parse_month_key,
    record_company_month_remittance,
)
from hospital.views_accountant_comprehensive import FINANCE_SENSITIVE_SESSION_KEY


class ReceivableUrlRoutingTests(TestCase):
    def test_accountant_and_billing_entry_urls_are_distinct(self):
        entry_id = '00000000-0000-0000-0000-000000000099'
        accountant_url = reverse(
            'hospital:accountant_receivable_entry_detail',
            kwargs={'entry_id': entry_id},
        )
        billing_url = reverse(
            'billing_receivable_entry_detail',
            kwargs={'entry_id': entry_id},
        )
        self.assertIn('/accountant/receivables/', accountant_url)
        self.assertIn('/billing/receivable-entry/', billing_url)
        self.assertNotEqual(accountant_url, billing_url)

    def test_withholding_list_resolves_to_management_crud_path(self):
        url = reverse('hospital:withholding_receivable_list')
        self.assertIn('/withholding-receivables/', url)


class MonthKeyParsingTests(TestCase):
    def test_parse_month_key_valid(self):
        self.assertEqual(parse_month_key('2026-04'), (2026, 4))

    def test_parse_month_key_invalid_raises(self):
        with self.assertRaises(ValueError):
            parse_month_key('2026-13')
        with self.assertRaises(ValueError):
            parse_month_key('not-a-month')

    def test_month_bounds(self):
        start, end = month_bounds('2026-04')
        self.assertEqual(start, date(2026, 4, 1))
        self.assertEqual(end, date(2026, 4, 30))


class RemittanceCapTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username=f'u_{uuid.uuid4().hex[:8]}', password='pw')
        self.payer = Payer.objects.create(name=f'Corp {uuid.uuid4().hex[:6]}', payer_type='corporate')
        gl = Account.objects.create(
            account_code=f'1010-{uuid.uuid4().hex[:6]}',
            account_name='Test Bank GL',
            account_type='asset',
        )
        self.bank = BankAccount.objects.create(
            account_name='Test Bank',
            account_number=f'TBN-{uuid.uuid4().hex[:8]}',
            bank_name='Test',
            gl_account=gl,
        )

    def _make_entry(self, amount, entry_date=None):
        return InsuranceReceivableEntry.objects.create(
            payer=self.payer,
            total_amount=amount,
            outstanding_amount=amount,
            entry_date=entry_date or date(2026, 4, 15),
        )

    def test_apply_payment_clamps_outstanding_at_zero(self):
        entry = self._make_entry(Decimal('100.00'))
        apply_payment_to_entry(
            entry,
            amount_received=Decimal('80.00'),
            amount_rejected=Decimal('30.00'),
        )
        entry.refresh_from_db()
        self.assertEqual(entry.outstanding_amount, Decimal('0.00'))
        self.assertEqual(entry.status, 'paid')

    def test_batch_remittance_rejects_over_outstanding(self):
        self._make_entry(Decimal('50.00'), entry_date=date(2026, 4, 10))
        with self.assertRaises(ValueError) as ctx:
            record_company_month_remittance(
                user=self.user,
                payer=self.payer,
                month_key='2026-04',
                entry_date=date(2026, 4, 20),
                bank_account=self.bank,
                total_amount=Decimal('100.00'),
                amount_received=Decimal('100.00'),
                amount_rejected=Decimal('0'),
                withholding_tax=Decimal('0'),
            )
        self.assertIn('exceeds outstanding', str(ctx.exception).lower())


class SingleLineRemittanceViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username=f'acct_{uuid.uuid4().hex[:8]}',
            password='pass-12345',
        )
        g, _ = Group.objects.get_or_create(name='Accountant')
        self.user.groups.add(g)
        self.payer = Payer.objects.create(name=f'View Corp {uuid.uuid4().hex[:6]}', payer_type='corporate')
        self.entry = InsuranceReceivableEntry.objects.create(
            payer=self.payer,
            total_amount=Decimal('100.00'),
            outstanding_amount=Decimal('100.00'),
            entry_date=date(2026, 5, 1),
        )
        gl = Account.objects.create(
            account_code=f'1011-{uuid.uuid4().hex[:6]}',
            account_name='View Bank GL',
            account_type='asset',
        )
        self.bank = BankAccount.objects.create(
            account_name='View Bank',
            account_number=f'VBN-{uuid.uuid4().hex[:8]}',
            bank_name='Test',
            gl_account=gl,
        )

    def _login(self):
        from django.contrib.auth.signals import user_logged_in

        from hospital.auth_session_utils import create_user_session
        from hospital.signals_login_tracking import track_successful_login

        user_logged_in.disconnect(track_successful_login)
        user_logged_in.disconnect(create_user_session)
        try:
            self.client.force_login(self.user)
        finally:
            user_logged_in.connect(track_successful_login)
            user_logged_in.connect(create_user_session)
        s = self.client.session
        s[FINANCE_SENSITIVE_SESSION_KEY] = timezone.now().timestamp()
        s.save()

    def test_single_line_remittance_over_outstanding_rejected(self):
        self._login()
        r = self.client.post(
            reverse('hospital:receivable_record_remittance'),
            {
                'entry_date': '2026-05-10',
                'payer': str(self.payer.id),
                'receivable_entry': str(self.entry.id),
                'bank_account': str(self.bank.id),
                'total_amount': '150.00',
                'amount_received': '150.00',
                'amount_rejected': '0',
                'withholding_tax': '0',
            },
        )
        self.assertEqual(r.status_code, 302)
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.outstanding_amount, Decimal('100.00'))
        self.assertEqual(
            InsurancePaymentReceived.objects.filter(receivable_entry=self.entry).count(),
            0,
        )


class CombinedBillDiscountTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username=f'u_{uuid.uuid4().hex[:8]}', password='pw')
        self.patient = Patient.objects.create(
            first_name='Disc',
            last_name='Patient',
            mrn=f'DISC-{uuid.uuid4().hex[:8]}',
        )
        self.payer = Payer.objects.create(name=f'Cash {uuid.uuid4().hex[:6]}', payer_type='cash')
        self.sc = ServiceCode.objects.create(
            code=f'DSC-{uuid.uuid4().hex[:8]}',
            description='Consult',
            category='test',
        )

    def _invoice_with_balance(self, amount):
        inv = Invoice.objects.create(
            patient=self.patient,
            encounter=None,
            payer=self.payer,
            invoice_number=f'INV-D-{uuid.uuid4().hex[:8]}',
            status='issued',
        )
        InvoiceLine.objects.create(
            invoice=inv,
            service_code=self.sc,
            description='Line',
            quantity=Decimal('1'),
            unit_price=amount,
            line_total=amount,
        )
        inv.update_totals()
        inv.refresh_from_db()
        return inv

    def test_discount_applied_matches_line_totals_and_gl(self):
        inv1 = self._invoice_with_balance(Decimal('50.00'))
        inv2 = self._invoice_with_balance(Decimal('50.00'))
        result = distribute_combined_bill_discount_across_invoices(
            [inv1, inv2],
            Decimal('15.00'),
            patient=self.patient,
            user=self.user,
        )
        line_discount_sum = sum(
            Decimal(str(v or 0))
            for v in InvoiceLine.objects.filter(
                invoice__in=[inv1, inv2],
                is_deleted=False,
            ).values_list('discount_amount', flat=True)
        )
        self.assertEqual(result.applied, line_discount_sum)
        self.assertGreater(result.applied, Decimal('0'))
        if result.gl_posted:
            from django.db.models import Sum

            gl_debit = (
                JournalEntryLine.objects.filter(
                    journal_entry__reference_number__startswith='PBD-',
                )
                .aggregate(t=Sum('debit_amount'))['t']
                or Decimal('0')
            )
            self.assertEqual(gl_debit, result.applied)


class SupplierPaymentValidationTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username=f'acct_{uuid.uuid4().hex[:8]}',
            password='pass-12345',
        )
        g, _ = Group.objects.get_or_create(name='Accountant')
        self.user.groups.add(g)
        self.supplier = Supplier.objects.create(name=f'Sup {uuid.uuid4().hex[:6]}')
        SupplierPayableLine.objects.create(
            supplier=self.supplier,
            entry_type=SupplierPayableLine.ENTRY_MANUAL_PAYABLE,
            amount=Decimal('40.00'),
            description='Opening',
            created_by=self.user,
        )

    def _login(self):
        from django.contrib.auth.signals import user_logged_in

        from hospital.auth_session_utils import create_user_session
        from hospital.signals_login_tracking import track_successful_login

        user_logged_in.disconnect(track_successful_login)
        user_logged_in.disconnect(create_user_session)
        try:
            self.client.force_login(self.user)
        finally:
            user_logged_in.connect(track_successful_login)
            user_logged_in.connect(create_user_session)

    def test_supplier_overpayment_rejected(self):
        self._login()
        url = reverse('hospital:supplier_account_detail', kwargs={'supplier_id': self.supplier.id})
        before = SupplierPayableLine.objects.filter(supplier=self.supplier, is_deleted=False).count()
        r = self.client.post(
            url,
            {
                'action': 'payment',
                'amount': '100.00',
                'description': 'Too much',
                'reference': 'X',
            },
        )
        self.assertEqual(r.status_code, 200)
        after = SupplierPayableLine.objects.filter(supplier=self.supplier, is_deleted=False).count()
        self.assertEqual(before, after)
        self.assertEqual(
            SupplierPayableLine.objects.filter(
                supplier=self.supplier,
                entry_type=SupplierPayableLine.ENTRY_PAYMENT,
                is_deleted=False,
            ).count(),
            0,
        )
