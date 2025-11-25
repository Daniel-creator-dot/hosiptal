"""
Financial System Validation and Helper Utilities
Ensures data consistency and synchronization across accounting modules
"""
from decimal import Decimal
from django.db.models import Sum, Q
from django.core.exceptions import ValidationError
from django.utils import timezone


class FinancialValidator:
    """Validate financial data consistency"""
    
    @staticmethod
    def validate_invoice_balance_vs_transactions(invoice):
        """Validate that invoice balance matches payments received"""
        from .models_accounting import Transaction
        
        # Calculate total payments for this invoice
        total_payments = Transaction.objects.filter(
            invoice=invoice,
            transaction_type='payment_received',
            is_deleted=False
        ).aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')
        
        # Calculate expected balance
        expected_balance = invoice.total_amount - total_payments
        
        if expected_balance != invoice.balance:
            return {
                'valid': False,
                'error': f'Invoice balance mismatch. Expected: GHS {expected_balance}, Actual: ${invoice.balance}',
                'expected_balance': expected_balance,
                'actual_balance': invoice.balance,
                'total_payments': total_payments
            }
        
        return {
            'valid': True,
            'balance': invoice.balance,
            'total_payments': total_payments
        }
    
    @staticmethod
    def validate_ar_vs_invoice(invoice):
        """Validate AR entry matches invoice balance"""
        from .models_accounting import AccountsReceivable
        
        ar_entry = AccountsReceivable.objects.filter(
            invoice=invoice,
            is_deleted=False
        ).first()
        
        if invoice.status in ['issued', 'partially_paid', 'overdue']:
            if not ar_entry:
                return {
                    'valid': False,
                    'error': f'Missing AR entry for invoice {invoice.invoice_number}'
                }
            
            if ar_entry.outstanding_amount != invoice.balance:
                return {
                    'valid': False,
                    'error': f'AR outstanding amount (GHS {ar_entry.outstanding_amount}) does not match invoice balance (${invoice.balance})'
                }
        elif invoice.status == 'paid':
            if ar_entry:
                return {
                    'valid': False,
                    'error': f'AR entry exists for paid invoice {invoice.invoice_number}'
                }
        
        return {'valid': True}
    
    @staticmethod
    def validate_bill_vs_invoice(bill):
        """Validate bill totals match invoice"""
        if not bill.invoice:
            return {'valid': True, 'note': 'No invoice linked'}
        
        if bill.total_amount != bill.invoice.total_amount:
            return {
                'valid': False,
                'error': f'Bill total (GHS {bill.total_amount}) does not match invoice total (${bill.invoice.total_amount})'
            }
        
        return {'valid': True}
    
    @staticmethod
    def validate_cashier_session(session):
        """Validate cashier session totals"""
        from .models_accounting import Transaction
        
        # Get all cash transactions for this session
        session_transactions = Transaction.objects.filter(
            processed_by=session.cashier,
            payment_method='cash',
            transaction_date__gte=session.opened_at,
            is_deleted=False
        )
        
        if session.status == 'closed' and session.closed_at:
            session_transactions = session_transactions.filter(
                transaction_date__lte=session.closed_at
            )
        
        # Calculate totals
        payments = session_transactions.filter(
            transaction_type='payment_received'
        ).aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')
        
        refunds = session_transactions.filter(
            transaction_type='refund_issued'
        ).aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')
        
        expected_cash = session.opening_cash + payments - refunds
        
        if session.total_payments != payments:
            return {
                'valid': False,
                'error': f'Session total payments (GHS {session.total_payments}) does not match actual (${payments})'
            }
        
        if session.expected_cash != expected_cash:
            return {
                'valid': False,
                'error': f'Session expected cash (GHS {session.expected_cash}) does not match calculated (${expected_cash})'
            }
        
        return {
            'valid': True,
            'payments': payments,
            'refunds': refunds,
            'expected_cash': expected_cash
        }
    
    @staticmethod
    def validate_general_ledger_balance():
        """Validate general ledger is balanced (total debits = total credits)"""
        from .models_accounting import GeneralLedger
        
        totals = GeneralLedger.objects.filter(
            is_deleted=False
        ).aggregate(
            total_debits=Sum('debit_amount'),
            total_credits=Sum('credit_amount')
        )
        
        total_debits = totals['total_debits'] or Decimal('0.00')
        total_credits = totals['total_credits'] or Decimal('0.00')
        
        if total_debits != total_credits:
            return {
                'valid': False,
                'error': f'General ledger is not balanced. Debits: GHS {total_debits}, Credits: ${total_credits}',
                'difference': abs(total_debits - total_credits)
            }
        
        return {
            'valid': True,
            'total_debits': total_debits,
            'total_credits': total_credits
        }
    
    @staticmethod
    def validate_journal_entry_balance(journal_entry):
        """Validate journal entry is balanced"""
        from decimal import Decimal
        
        total_debits = Decimal('0.00')
        total_credits = Decimal('0.00')
        
        for line in journal_entry.lines.all():
            total_debits += line.debit_amount
            total_credits += line.credit_amount
        
        if total_debits != total_credits:
            return {
                'valid': False,
                'error': f'Journal entry not balanced. Debits: GHS {total_debits}, Credits: ${total_credits}',
                'difference': abs(total_debits - total_credits)
            }
        
        return {
            'valid': True,
            'total_debits': total_debits,
            'total_credits': total_credits
        }


class FinancialReconciliation:
    """Reconciliation utilities"""
    
    @staticmethod
    def reconcile_all_invoices():
        """Reconcile all invoices with transactions and AR"""
        from .models import Invoice
        
        issues = []
        invoices = Invoice.objects.filter(
            is_deleted=False
        ).exclude(status__in=['draft', 'cancelled'])
        
        for invoice in invoices:
            # Check invoice balance vs transactions
            balance_check = FinancialValidator.validate_invoice_balance_vs_transactions(invoice)
            if not balance_check['valid']:
                issues.append({
                    'invoice': invoice.invoice_number,
                    'issue': 'balance_mismatch',
                    'details': balance_check
                })
            
            # Check AR sync
            ar_check = FinancialValidator.validate_ar_vs_invoice(invoice)
            if not ar_check['valid']:
                issues.append({
                    'invoice': invoice.invoice_number,
                    'issue': 'ar_mismatch',
                    'details': ar_check
                })
        
        return {
            'total_invoices': invoices.count(),
            'issues_found': len(issues),
            'issues': issues
        }
    
    @staticmethod
    def fix_ar_sync():
        """Fix AR entries to match invoice balances"""
        from .models import Invoice
        from .models_accounting import AccountsReceivable
        
        fixed = 0
        invoices = Invoice.objects.filter(
            is_deleted=False
        ).exclude(status__in=['draft', 'cancelled'])
        
        for invoice in invoices:
            if invoice.status in ['issued', 'partially_paid', 'overdue']:
                ar_entry, created = AccountsReceivable.objects.update_or_create(
                    invoice=invoice,
                    defaults={
                        'patient': invoice.patient,
                        'outstanding_amount': invoice.balance,
                        'due_date': invoice.due_at.date(),
                    }
                )
                ar_entry.update_aging()
                fixed += 1
            elif invoice.status == 'paid':
                deleted_count = AccountsReceivable.objects.filter(invoice=invoice).delete()[0]
                if deleted_count > 0:
                    fixed += 1
        
        return {
            'invoices_processed': invoices.count(),
            'ar_entries_fixed': fixed
        }
    
    @staticmethod
    def update_all_ar_aging():
        """Update aging for all AR entries"""
        from .models_accounting import AccountsReceivable
        
        ar_entries = AccountsReceivable.objects.filter(is_deleted=False)
        count = 0
        
        for ar in ar_entries:
            ar.update_aging()
            count += 1
        
        return {
            'ar_entries_updated': count
        }
    
    @staticmethod
    def reconcile_cashier_sessions():
        """Reconcile all cashier sessions"""
        from .models_workflow import CashierSession
        
        issues = []
        sessions = CashierSession.objects.filter(is_deleted=False)
        
        for session in sessions:
            check = FinancialValidator.validate_cashier_session(session)
            if not check['valid']:
                issues.append({
                    'session': session.session_number,
                    'cashier': session.cashier.username,
                    'details': check
                })
        
        return {
            'total_sessions': sessions.count(),
            'issues_found': len(issues),
            'issues': issues
        }


class FinancialReports:
    """Generate financial reports"""
    
    @staticmethod
    def revenue_summary(start_date=None, end_date=None):
        """Generate revenue summary"""
        from .models_accounting import GeneralLedger, Account
        
        if not start_date:
            start_date = timezone.now().date().replace(month=1, day=1)
        if not end_date:
            end_date = timezone.now().date()
        
        revenue_accounts = Account.objects.filter(
            account_type='revenue',
            is_active=True,
            is_deleted=False
        )
        
        revenue_by_account = {}
        total_revenue = Decimal('0.00')
        
        for account in revenue_accounts:
            entries = GeneralLedger.objects.filter(
                account=account,
                transaction_date__gte=start_date,
                transaction_date__lte=end_date,
                is_deleted=False
            )
            
            credits = entries.aggregate(Sum('credit_amount'))['credit_amount__sum'] or Decimal('0.00')
            debits = entries.aggregate(Sum('debit_amount'))['debit_amount__sum'] or Decimal('0.00')
            net_revenue = credits - debits
            
            revenue_by_account[account.account_name] = net_revenue
            total_revenue += net_revenue
        
        return {
            'start_date': start_date,
            'end_date': end_date,
            'revenue_by_account': revenue_by_account,
            'total_revenue': total_revenue
        }
    
    @staticmethod
    def ar_aging_summary():
        """Generate AR aging summary"""
        from .models_accounting import AccountsReceivable
        
        ar_entries = AccountsReceivable.objects.filter(
            outstanding_amount__gt=0,
            is_deleted=False
        )
        
        summary = {
            'current': Decimal('0.00'),
            '31-60': Decimal('0.00'),
            '61-90': Decimal('0.00'),
            '90+': Decimal('0.00'),
        }
        
        for ar in ar_entries:
            ar.update_aging()
            summary[ar.aging_bucket] += ar.outstanding_amount
        
        total = sum(summary.values())
        
        return {
            'summary': summary,
            'total_outstanding': total,
            'total_invoices': ar_entries.count()
        }
































