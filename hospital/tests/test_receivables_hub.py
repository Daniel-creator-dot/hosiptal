"""Corporate & insurance receivables: allocation, invoice link, remittance validation."""
import uuid
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from hospital.models import Invoice, InvoiceLine, Payer, Patient, ServiceCode
from hospital.models_accounting import Account, Transaction
from hospital.models_accounting_advanced import AdvancedJournalEntry
from hospital.models_primecare_accounting import InsuranceReceivableEntry
from hospital.services.credit_revenue_service import resolve_payer_ar_account_code
from hospital.signals_accounting import _find_insurance_receivable_entry_for_payment


def _ensure_primecare_revenue_accounts():
    specs = [
        ('4100', 'Registration Revenue', 'revenue'),
        ('4110', 'Consultation Revenue', 'revenue'),
        ('4120', 'Laboratory Revenue', 'revenue'),
        ('4130', 'Pharmacy Revenue', 'revenue'),
        ('4140', 'Surgeries Revenue', 'revenue'),
        ('4150', 'Admissions Revenue', 'revenue'),
        ('4160', 'Radiology Revenue', 'revenue'),
        ('4170', 'Dental Revenue', 'revenue'),
        ('4180', 'Physiotherapy Revenue', 'revenue'),
        ('4190', 'Consumables Revenue', 'revenue'),
    ]
    for code, name, acct_type in specs:
        Account.objects.get_or_create(
            account_code=code,
            defaults={'account_name': name, 'account_type': acct_type},
        )


class MatchToRevenueTests(TestCase):
    def setUp(self):
        _ensure_primecare_revenue_accounts()
        self.user = User.objects.create_user(username=f'match_{uuid.uuid4().hex[:8]}', password='x')

    def _create_corporate_invoice(self, amount='100.00', desc='consultation visit'):
        payer = Payer.objects.create(name=f'Corp {uuid.uuid4().hex[:6]}', payer_type='corporate')
        patient = Patient.objects.create(
            first_name='M',
            last_name='T',
            mrn=f'MTR-{uuid.uuid4().hex[:10]}',
        )
        sc = ServiceCode.objects.create(
            code=f'MTRSC-{uuid.uuid4().hex[:8]}',
            description=desc,
            category='test',
        )
        inv = Invoice.objects.create(
            patient=patient,
            encounter=None,
            payer=payer,
            invoice_number=f'INV-MTR-{uuid.uuid4().hex[:8]}',
            status='issued',
        )
        InvoiceLine.objects.create(
            invoice=inv,
            service_code=sc,
            description=desc,
            quantity=Decimal('1'),
            unit_price=Decimal(amount),
            line_total=Decimal(amount),
        )
        inv.update_totals()
        inv.refresh_from_db()
        ire = InsuranceReceivableEntry.objects.get(invoice=inv)
        return ire, inv, payer

    def test_match_to_revenue_on_base_model_creates_balanced_je(self):
        ire, _inv, payer = self._create_corporate_invoice()
        self.assertIsNone(ire.journal_entry_id)

        je = ire.match_to_revenue(self.user)
        ire.refresh_from_db()

        self.assertEqual(ire.status, 'matched')
        self.assertIsNotNone(ire.journal_entry_id)
        self.assertEqual(je.id, ire.journal_entry_id)
        self.assertEqual(je.total_debit, ire.total_amount)
        self.assertEqual(je.total_credit, ire.total_amount)
        self.assertEqual(je.status, 'posted')

        ar_code = resolve_payer_ar_account_code(payer)
        ar_line = je.lines.filter(account__account_code=ar_code).first()
        self.assertIsNotNone(ar_line)
        self.assertEqual(ar_line.debit_amount, ire.total_amount)

        rev_credit = sum(
            line.credit_amount for line in je.lines.exclude(account__account_code=ar_code)
        )
        self.assertEqual(rev_credit, ire.total_amount)

    def test_match_to_revenue_is_idempotent(self):
        ire, _inv, _payer = self._create_corporate_invoice()
        je1 = ire.match_to_revenue(self.user)
        je2 = ire.match_to_revenue(self.user)
        self.assertEqual(je1.id, je2.id)
        self.assertEqual(
            AdvancedJournalEntry.objects.filter(reference=ire.entry_number).count(),
            1,
        )

    def test_partial_copay_matches_outstanding_credit_only(self):
        ire, _inv, payer = self._create_corporate_invoice(amount='100.00')
        ire.amount_received = Decimal('40.00')
        ire.outstanding_amount = Decimal('60.00')
        ire.status = 'partially_paid'
        ire.save()

        je = ire.match_to_revenue(self.user)
        ire.refresh_from_db()

        ar_code = resolve_payer_ar_account_code(payer)
        ar_line = je.lines.filter(account__account_code=ar_code).first()
        self.assertEqual(ar_line.debit_amount, Decimal('60.00'))
        self.assertEqual(je.total_debit, Decimal('60.00'))
        self.assertEqual(je.total_credit, Decimal('60.00'))
        self.assertEqual(ire.status, 'matched')


class FindInsuranceReceivableEntryForPaymentTests(TestCase):
    def test_prefers_invoice_fk_over_other_open_line_same_payer(self):
        payer = Payer.objects.create(name='Corp AR Test', payer_type='corporate')
        patient = Patient.objects.create(
            first_name='A',
            last_name='B',
            mrn=f'AR-{uuid.uuid4().hex[:10]}',
        )
        sc = ServiceCode.objects.create(
            code=f'ARSC-{uuid.uuid4().hex[:8]}',
            description='svc',
            category='test',
        )
        inv1 = Invoice.objects.create(
            patient=patient,
            encounter=None,
            payer=payer,
            invoice_number=f'INV-AR1-{uuid.uuid4().hex[:8]}',
            status='issued',
        )
        InvoiceLine.objects.create(
            invoice=inv1,
            service_code=sc,
            description='L1',
            quantity=Decimal('1'),
            unit_price=Decimal('100.00'),
            line_total=Decimal('100.00'),
        )
        inv1.update_totals()
        inv2 = Invoice.objects.create(
            patient=patient,
            encounter=None,
            payer=payer,
            invoice_number=f'INV-AR2-{uuid.uuid4().hex[:8]}',
            status='issued',
        )
        InvoiceLine.objects.create(
            invoice=inv2,
            service_code=sc,
            description='L2',
            quantity=Decimal('1'),
            unit_price=Decimal('200.00'),
            line_total=Decimal('200.00'),
        )
        inv2.update_totals()

        ire1 = InsuranceReceivableEntry.objects.get(invoice=inv1)
        ire2 = InsuranceReceivableEntry.objects.get(invoice=inv2)

        found = _find_insurance_receivable_entry_for_payment(inv2, payer)
        self.assertEqual(found.id, ire2.id)
        self.assertNotEqual(found.id, ire1.id)


class InsuranceReceivableInvoiceSignalTests(TestCase):
    def test_auto_created_ire_has_invoice_fk(self):
        payer = Payer.objects.create(name='Corp IRE Link', payer_type='corporate')
        patient = Patient.objects.create(
            first_name='C',
            last_name='D',
            mrn=f'IREL-{uuid.uuid4().hex[:10]}',
        )
        sc = ServiceCode.objects.create(
            code=f'IRELSC-{uuid.uuid4().hex[:8]}',
            description='consultation test line',
            category='test',
        )
        inv = Invoice.objects.create(
            patient=patient,
            encounter=None,
            payer=payer,
            invoice_number=f'INV-IREL-{uuid.uuid4().hex[:8]}',
            status='issued',
        )
        InvoiceLine.objects.create(
            invoice=inv,
            service_code=sc,
            description='consultation',
            quantity=Decimal('1'),
            unit_price=Decimal('50.00'),
            line_total=Decimal('50.00'),
        )
        inv.update_totals()
        inv.refresh_from_db()

        ire = InsuranceReceivableEntry.objects.filter(invoice=inv).first()
        self.assertIsNotNone(ire)
        self.assertEqual(ire.payer_id, payer.id)


class TransactionUpdatesCorrectIRETests(TestCase):
    def test_payment_applies_to_invoice_linked_ire(self):
        payer = Payer.objects.create(name='Corp Pay', payer_type='corporate')
        patient = Patient.objects.create(
            first_name='E',
            last_name='F',
            mrn=f'PAY-{uuid.uuid4().hex[:10]}',
        )
        user = User.objects.create_user(username=f'u_{uuid.uuid4().hex[:8]}', password='x')
        sc = ServiceCode.objects.create(
            code=f'PAYSC-{uuid.uuid4().hex[:8]}',
            description='consultation pay',
            category='test',
        )
        inv_keep = Invoice.objects.create(
            patient=patient,
            encounter=None,
            payer=payer,
            invoice_number=f'INV-K-{uuid.uuid4().hex[:8]}',
            status='issued',
        )
        InvoiceLine.objects.create(
            invoice=inv_keep,
            service_code=sc,
            description='consultation',
            quantity=Decimal('1'),
            unit_price=Decimal('300.00'),
            line_total=Decimal('300.00'),
        )
        inv_keep.update_totals()

        inv_pay = Invoice.objects.create(
            patient=patient,
            encounter=None,
            payer=payer,
            invoice_number=f'INV-P-{uuid.uuid4().hex[:8]}',
            status='issued',
        )
        InvoiceLine.objects.create(
            invoice=inv_pay,
            service_code=sc,
            description='consultation',
            quantity=Decimal('1'),
            unit_price=Decimal('100.00'),
            line_total=Decimal('100.00'),
        )
        inv_pay.update_totals()

        ire_keep = InsuranceReceivableEntry.objects.get(invoice=inv_keep)
        ire_pay = InsuranceReceivableEntry.objects.get(invoice=inv_pay)

        Transaction.objects.create(
            transaction_type='payment_received',
            invoice=inv_pay,
            patient=patient,
            amount=Decimal('40.00'),
            payment_method='cash',
            processed_by=user,
        )

        ire_keep.refresh_from_db()
        ire_pay.refresh_from_db()
        self.assertEqual(ire_keep.amount_received, Decimal('0.00'))
        self.assertEqual(ire_pay.amount_received, Decimal('40.00'))


class ReceivablesHubViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username=f'acct_{uuid.uuid4().hex[:8]}',
            password='pass-12345',
        )
        from django.contrib.auth.models import Group

        g, _ = Group.objects.get_or_create(name='Accountant')
        self.user.groups.add(g)

    def _force_login_without_login_signals(self):
        """Test client has no REMOTE_ADDR; login signals may write LoginHistory and break tests."""
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

    def test_hub_requires_login(self):
        r = self.client.get(reverse('hospital:receivables_hub'))
        self.assertEqual(r.status_code, 302)

    def test_hub_200_for_accountant(self):
        self._force_login_without_login_signals()
        r = self.client.get(reverse('hospital:receivables_hub'))
        self.assertEqual(r.status_code, 200)

    def test_remittance_post_without_receivable_redirects_with_message(self):
        self._force_login_without_login_signals()
        from hospital.views_accountant_comprehensive import FINANCE_SENSITIVE_SESSION_KEY
        from django.utils import timezone

        s = self.client.session
        s[FINANCE_SENSITIVE_SESSION_KEY] = timezone.now().timestamp()
        s.save()

        r = self.client.post(
            reverse('hospital:receivable_record_remittance'),
            {
                'entry_date': '2026-04-01',
                'payer': str(Payer.objects.create(name='P', payer_type='corporate').id),
                'receivable_entry': '',
                'bank_account': '',
                'total_amount': '10',
                'amount_received': '10',
                'amount_rejected': '0',
                'withholding_tax': '0',
            },
        )
        self.assertEqual(r.status_code, 302)
