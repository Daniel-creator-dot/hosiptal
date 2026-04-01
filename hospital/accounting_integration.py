"""
Accounting Integration - Auto-sync Everything
Connects cashier, billing, procurement, pharmacy, lab to accounting
Real-time financial tracking and journal entry creation
"""

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.db import transaction
from decimal import Decimal
from django.utils import timezone

from .models import Invoice, Patient
from .models_accounting import Account, Transaction
from .models_accounting_advanced import (
    Revenue, RevenueCategory, Expense, ExpenseCategory,
    AdvancedJournalEntry, AdvancedJournalEntryLine,
    AdvancedAccountsReceivable, PaymentVoucher, ReceiptVoucher,
    Journal
)


# ==================== INVOICE & AR AUTO-CREATION ====================

@receiver(post_save, sender=Invoice)
def create_accounts_receivable(sender, instance, created, **kwargs):
    """
    Auto-create AR when invoice is issued
    """
    if created and instance.status == 'issued':
        try:
            # Create or update AR entry
            ar, ar_created = AdvancedAccountsReceivable.objects.get_or_create(
                invoice=instance,
                defaults={
                    'patient': instance.patient,
                    'invoice_amount': instance.total_amount,
                    'amount_paid': Decimal('0.00'),
                    'balance_due': instance.total_amount,
                    'due_date': instance.due_date or (timezone.now().date() + timezone.timedelta(days=30)),
                }
            )
            
            if ar_created:
                print(f"[AUTO] Created AR for invoice {instance.invoice_number}: GHS {instance.total_amount}")
        
        except Exception as e:
            print(f"[ERROR] Failed to create AR for {instance.invoice_number}: {e}")


# ==================== PAYMENT AUTO-POSTING ====================

@receiver(post_save, sender=Transaction)
def auto_post_payment_to_accounting(sender, instance, created, **kwargs):
    """
    Auto-create revenue entry and receipt voucher when payment is received
    Also creates journal entry and posts to GL.
    DISABLED for transaction_type='payment_received': only signals_accounting.py
    posts those (single source) to avoid double Revenue/GL. Deposit applications
    are handled by signals_patient_deposits only.
    """
    if not created:
        return
    
    if instance.transaction_type != 'payment_received':
        return

    # Single source: signals_accounting.py handles payment_received (and skips deposit)
    return


# ==================== PROCUREMENT TO EXPENSE AUTO-SYNC ====================

def create_expense_from_purchase(purchase_order):
    """
    Auto-create expense when purchase order is received/paid
    Call this from procurement views
    """
    try:
        with transaction.atomic():
            # Get expense account
            expense_account, _ = Account.objects.get_or_create(
                account_code='5100',
                defaults={
                    'account_name': 'Medical Supplies Expense',
                    'account_type': 'expense',
                }
            )
            
            # Get expense category
            expense_category, _ = ExpenseCategory.objects.get_or_create(
                code='EXP-SUPPLIES',
                defaults={
                    'name': 'Medical Supplies',
                    'account': expense_account,
                }
            )
            
            # Create expense
            expense = Expense.objects.create(
                expense_date=timezone.now().date(),
                category=expense_category,
                description=f"Purchase Order: {purchase_order.po_number if hasattr(purchase_order, 'po_number') else 'PO'}",
                amount=purchase_order.total_amount if hasattr(purchase_order, 'total_amount') else Decimal('0.00'),
                vendor_name=purchase_order.supplier_name if hasattr(purchase_order, 'supplier_name') else 'Supplier',
                vendor_invoice_number=purchase_order.invoice_number if hasattr(purchase_order, 'invoice_number') else '',
                status='approved',  # Auto-approve for POs
            )
            
            print(f"[AUTO-SYNC] Purchase Order → Expense GHS {expense.amount} ✓")
            return expense
    
    except Exception as e:
        print(f"[ERROR] Failed to create expense from PO: {e}")
        return None


# ==================== PHARMACY SALES TO REVENUE ====================

def record_pharmacy_revenue(sale_amount, payment_method='cash', patient=None, reference=''):
    """
    Auto-record pharmacy sales as revenue
    Call this from pharmacy sales views
    """
    try:
        with transaction.atomic():
            # Get accounts
            cash_account, _ = Account.objects.get_or_create(
                account_code='1000',
                defaults={'account_name': 'Cash on Hand', 'account_type': 'asset'}
            )
            
            pharmacy_revenue_account, _ = Account.objects.get_or_create(
                account_code='4200',
                defaults={'account_name': 'Pharmacy Revenue', 'account_type': 'revenue'}
            )
            
            # Get category
            revenue_category, _ = RevenueCategory.objects.get_or_create(
                code='REV-PHARM',
                defaults={'name': 'Pharmacy Sales', 'account': pharmacy_revenue_account}
            )
            
            # Create revenue
            revenue = Revenue.objects.create(
                revenue_date=timezone.now().date(),
                category=revenue_category,
                description=f"Pharmacy sale - {reference}",
                amount=sale_amount,
                patient=patient,
                payment_method=payment_method,
                reference=reference,
            )
            
            # Create journal entry
            journal = Journal.objects.filter(journal_type='sales').first()
            je = AdvancedJournalEntry.objects.create(
                journal=journal,
                entry_date=revenue.revenue_date,
                description=revenue.description,
                reference=reference,
                status='posted',
                total_debit=sale_amount,
                total_credit=sale_amount,
            )
            
            # Dr: Cash
            AdvancedJournalEntryLine.objects.create(
                journal_entry=je,
                line_number=1,
                account=cash_account,
                description="Pharmacy cash sale",
                debit_amount=sale_amount,
                credit_amount=Decimal('0.00'),
                patient=patient,
            )
            
            # Cr: Pharmacy Revenue
            AdvancedJournalEntryLine.objects.create(
                journal_entry=je,
                line_number=2,
                account=pharmacy_revenue_account,
                description="Pharmacy sales revenue",
                debit_amount=Decimal('0.00'),
                credit_amount=sale_amount,
                patient=patient,
            )
            
            je.post(None)
            revenue.journal_entry = je
            revenue.save()
            
            print(f"[AUTO-SYNC] Pharmacy Sale GHS {sale_amount} → Revenue → GL ✓")
            return revenue
    
    except Exception as e:
        print(f"[ERROR] Pharmacy revenue recording failed: {e}")
        return None


# ==================== LAB REVENUE AUTO-RECORDING ====================

def record_lab_revenue(test_amount, payment_method='cash', patient=None, reference=''):
    """
    Auto-record lab test payments as revenue
    Call this from lab payment views
    """
    try:
        with transaction.atomic():
            # Get accounts
            cash_account, _ = Account.objects.get_or_create(
                account_code='1000',
                defaults={'account_name': 'Cash on Hand', 'account_type': 'asset'}
            )
            
            lab_revenue_account, _ = Account.objects.get_or_create(
                account_code='4100',
                defaults={'account_name': 'Laboratory Revenue', 'account_type': 'revenue'}
            )
            
            # Get category
            revenue_category, _ = RevenueCategory.objects.get_or_create(
                code='REV-LAB',
                defaults={'name': 'Laboratory Services', 'account': lab_revenue_account}
            )
            
            # Create revenue
            revenue = Revenue.objects.create(
                revenue_date=timezone.now().date(),
                category=revenue_category,
                description=f"Laboratory test - {reference}",
                amount=test_amount,
                patient=patient,
                payment_method=payment_method,
                reference=reference,
            )
            
            print(f"[AUTO-SYNC] Lab Test GHS {test_amount} → Revenue ✓")
            return revenue
    
    except Exception as e:
        print(f"[ERROR] Lab revenue recording failed: {e}")
        return None


# ==================== SALARY EXPENSE AUTO-RECORDING ====================

def record_salary_expense(staff_name, amount, period, user=None):
    """
    Auto-record salary payments as expenses
    Call this from payroll processing
    """
    try:
        with transaction.atomic():
            # Get accounts
            salary_account, _ = Account.objects.get_or_create(
                account_code='5000',
                defaults={'account_name': 'Salaries & Wages', 'account_type': 'expense'}
            )
            
            bank_account, _ = Account.objects.get_or_create(
                account_code='1010',
                defaults={'account_name': 'Bank Account - Main', 'account_type': 'asset'}
            )
            
            # Get category
            expense_category, _ = ExpenseCategory.objects.get_or_create(
                code='EXP-SALARY',
                defaults={'name': 'Salaries & Wages', 'account': salary_account}
            )
            
            # Create expense
            expense = Expense.objects.create(
                expense_date=timezone.now().date(),
                category=expense_category,
                description=f"Salary payment - {staff_name} - {period}",
                amount=amount,
                vendor_name=staff_name,
                status='paid',
                recorded_by=user,
            )
            
            # Create payment voucher
            payment_voucher = PaymentVoucher.objects.create(
                voucher_date=expense.expense_date,
                payment_type='salary',
                payee_name=staff_name,
                description=expense.description,
                amount=amount,
                payment_method='bank_transfer',
                status='paid',
                expense_account=salary_account,
                payment_account=bank_account,
                requested_by=user,
                paid_by=user,
            )
            
            expense.payment_voucher = payment_voucher
            expense.save()
            
            print(f"[AUTO-SYNC] Salary GHS {amount} for {staff_name} → Expense → Voucher ✓")
            return expense
    
    except Exception as e:
        print(f"[ERROR] Salary expense recording failed: {e}")
        return None


# ==================== UTILITY FUNCTIONS ====================

def get_or_create_default_accounts():
    """Ensure all default accounts exist"""
    default_accounts = {
        'cash': ('1000', 'Cash on Hand', 'asset'),
        'bank': ('1010', 'Bank Account - Main', 'asset'),
        'ar': ('1100', 'Accounts Receivable', 'asset'),
        'ap': ('2000', 'Accounts Payable', 'liability'),
        'revenue_patient': ('4000', 'Patient Services Revenue', 'revenue'),
        'revenue_lab': ('4100', 'Laboratory Revenue', 'revenue'),
        'revenue_pharmacy': ('4200', 'Pharmacy Revenue', 'revenue'),
        'expense_salary': ('5000', 'Salaries & Wages', 'expense'),
        'expense_supplies': ('5100', 'Medical Supplies', 'expense'),
        'expense_utilities': ('5200', 'Utilities', 'expense'),
    }
    
    accounts = {}
    for key, (code, name, acc_type) in default_accounts.items():
        account, _ = Account.objects.get_or_create(
            account_code=code,
            defaults={
                'account_name': name,
                'account_type': acc_type,
            }
        )
        accounts[key] = account
    
    return accounts


def create_journal_entry_for_transaction(
    description,
    amount,
    debit_account,
    credit_account,
    reference='',
    patient=None,
    invoice=None,
    user=None
):
    """
    Generic function to create a journal entry for any transaction
    """
    try:
        with transaction.atomic():
            # Get default journal
            journal = Journal.objects.filter(journal_type='general').first()
            if not journal:
                journal = Journal.objects.create(
                    code='GJ',
                    name='General Journal',
                    journal_type='general',
                )
            
            # Create journal entry
            je = AdvancedJournalEntry.objects.create(
                journal=journal,
                entry_date=timezone.now().date(),
                description=description,
                reference=reference,
                status='posted',
                total_debit=amount,
                total_credit=amount,
                created_by=user,
                posted_by=user,
                invoice=invoice,
            )
            
            # Debit line
            AdvancedJournalEntryLine.objects.create(
                journal_entry=je,
                line_number=1,
                account=debit_account,
                description=description,
                debit_amount=amount,
                credit_amount=Decimal('0.00'),
                patient=patient,
            )
            
            # Credit line
            AdvancedJournalEntryLine.objects.create(
                journal_entry=je,
                line_number=2,
                account=credit_account,
                description=description,
                debit_amount=Decimal('0.00'),
                credit_amount=amount,
                patient=patient,
            )
            
            # Post to GL
            je.post(user)
            
            return je
    
    except Exception as e:
        print(f"[ERROR] Journal entry creation failed: {e}")
        return None


# ==================== INTEGRATION HELPER FUNCTIONS ====================

def sync_invoice_to_accounting(invoice):
    """
    Manually sync an invoice to accounting
    Creates AR entry
    """
    try:
        ar, created = AdvancedAccountsReceivable.objects.get_or_create(
            invoice=invoice,
            defaults={
                'patient': invoice.patient,
                'invoice_amount': invoice.total_amount,
                'amount_paid': invoice.total_amount - invoice.balance,
                'balance_due': invoice.balance,
                'due_date': invoice.due_at.date() if invoice.due_at else (timezone.now().date() + timezone.timedelta(days=30)),
            }
        )
        
        if not created:
            # Update existing AR
            ar.invoice_amount = invoice.total_amount
            ar.amount_paid = invoice.total_amount - invoice.balance
            ar.save()
        
        print(f"[SYNC] Invoice {invoice.invoice_number} synced to AR")
        return ar
    
    except Exception as e:
        print(f"[ERROR] Invoice sync failed: {e}")
        return None


def batch_sync_all_invoices():
    """
    Sync all existing invoices to AR
    Run once to sync historical data
    """
    from .models import Invoice
    
    invoices = Invoice.objects.filter(is_deleted=False, status__in=['issued', 'partially_paid', 'overdue'])
    count = 0
    
    for invoice in invoices:
        try:
            sync_invoice_to_accounting(invoice)
            count += 1
        except:
            pass
    
    print(f"[BATCH-SYNC] Synced {count} invoices to AR")
    return count


# ==================== LIVE FINANCIAL STATISTICS ====================

def get_live_financial_stats():
    """
    Get real-time financial statistics
    Used for dashboard updates
    """
    from django.db.models import Sum
    from datetime import datetime, timedelta
    
    today = timezone.now().date()
    start_of_month = today.replace(day=1)
    start_of_year = today.replace(month=1, day=1)
    
    stats = {}
    
    # Revenue
    try:
        stats['revenue_today'] = Revenue.objects.filter(
            revenue_date=today
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        stats['revenue_month'] = Revenue.objects.filter(
            revenue_date__gte=start_of_month
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        stats['revenue_year'] = Revenue.objects.filter(
            revenue_date__gte=start_of_year
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    except:
        stats['revenue_today'] = Decimal('0.00')
        stats['revenue_month'] = Decimal('0.00')
        stats['revenue_year'] = Decimal('0.00')
    
    # Expenses
    try:
        stats['expense_today'] = Expense.objects.filter(
            expense_date=today,
            status='paid'
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        stats['expense_month'] = Expense.objects.filter(
            expense_date__gte=start_of_month,
            status='paid'
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        stats['expense_year'] = Expense.objects.filter(
            expense_date__gte=start_of_year,
            status='paid'
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    except:
        stats['expense_today'] = Decimal('0.00')
        stats['expense_month'] = Decimal('0.00')
        stats['expense_year'] = Decimal('0.00')
    
    # Net Income
    stats['net_income_today'] = stats['revenue_today'] - stats['expense_today']
    stats['net_income_month'] = stats['revenue_month'] - stats['expense_month']
    stats['net_income_year'] = stats['revenue_year'] - stats['expense_year']
    
    # AR & AP
    try:
        stats['total_receivable'] = AdvancedAccountsReceivable.objects.filter(
            balance_due__gt=0
        ).aggregate(total=Sum('balance_due'))['total'] or Decimal('0.00')
        
        stats['overdue_receivable'] = AdvancedAccountsReceivable.objects.filter(
            is_overdue=True
        ).aggregate(total=Sum('balance_due'))['total'] or Decimal('0.00')
    except:
        stats['total_receivable'] = Decimal('0.00')
        stats['overdue_receivable'] = Decimal('0.00')
    
    # Payments (from Transaction model)
    try:
        from .models_accounting import Transaction
        
        stats['payments_today'] = Transaction.objects.filter(
            transaction_date__gte=today,
            transaction_type='payment_received'
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        stats['payments_month'] = Transaction.objects.filter(
            transaction_date__gte=start_of_month,
            transaction_type='payment_received'
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    except:
        stats['payments_today'] = Decimal('0.00')
        stats['payments_month'] = Decimal('0.00')
    
    return stats


# ==================== CASHIER INTEGRATION ====================

class CashierAccountingIntegration:
    """
    Integration class for cashier operations
    Use this in cashier views to auto-sync to accounting
    """
    
    @staticmethod
    def process_payment(invoice, amount, payment_method, user):
        """
        Process payment through cashier and auto-sync to accounting
        
        Args:
            invoice: Invoice object
            amount: Payment amount
            payment_method: Payment method (cash, card, etc.)
            user: User processing payment
        
        Returns:
            dict with transaction, revenue, journal_entry
        """
        try:
            with transaction.atomic():
                # Check for duplicate transaction before creating
                from datetime import timedelta
                from django.utils import timezone
                recent_cutoff = timezone.now() - timedelta(minutes=1)
                
                existing_transaction = Transaction.objects.filter(
                    transaction_type='payment_received',
                    invoice=invoice,
                    amount=amount,
                    payment_method=payment_method,
                    transaction_date__gte=recent_cutoff,
                    is_deleted=False
                ).first()
                
                if existing_transaction:
                    # Duplicate found - return existing transaction
                    return {
                        'success': True,
                        'transaction': existing_transaction,
                        'message': f'Payment already processed (duplicate prevented)'
                    }
                
                # Create transaction (existing model)
                txn = Transaction.objects.create(
                    transaction_type='payment_received',
                    invoice=invoice,
                    patient=invoice.patient,
                    amount=amount,
                    payment_method=payment_method,
                    processed_by=user,
                )
                
                # Update invoice
                invoice.balance -= amount
                if invoice.balance <= 0:
                    invoice.status = 'paid'
                elif invoice.status == 'issued':
                    invoice.status = 'partially_paid'
                invoice.save()
                
                # The post_save signal will auto-create:
                # - Revenue entry
                # - Receipt voucher
                # - Journal entry
                # - GL posting
                # - AR update
                
                return {
                    'success': True,
                    'transaction': txn,
                    'message': f'Payment processed and synced to accounting'
                }
        
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'message': 'Payment processing failed'
            }
    
    @staticmethod
    def get_todays_cash_summary(user=None):
        """Get today's cash summary for cashier"""
        from .models_accounting import Transaction
        
        today = timezone.now().date()
        
        # Payments received today
        payments = Transaction.objects.filter(
            transaction_date__gte=today,
            transaction_type='payment_received'
        )
        
        if user:
            payments = payments.filter(processed_by=user)
        
        summary = {
            'total_cash': payments.filter(payment_method='cash').aggregate(total=Sum('amount'))['total'] or Decimal('0.00'),
            'total_card': payments.filter(payment_method='card').aggregate(total=Sum('amount'))['total'] or Decimal('0.00'),
            'total_mobile': payments.filter(payment_method='mobile_money').aggregate(total=Sum('amount'))['total'] or Decimal('0.00'),
            'total_bank': payments.filter(payment_method='bank_transfer').aggregate(total=Sum('amount'))['total'] or Decimal('0.00'),
            'count': payments.count(),
        }
        
        summary['grand_total'] = (
            summary['total_cash'] +
            summary['total_card'] +
            summary['total_mobile'] +
            summary['total_bank']
        )
        
        return summary


# ==================== PROCUREMENT INTEGRATION ====================

class ProcurementAccountingIntegration:
    """
    Integration for procurement/purchasing
    Auto-creates expenses and payment vouchers
    """
    
    @staticmethod
    def create_bill_from_purchase(vendor_name, amount, description, invoice_number='', user=None):
        """
        Create accounts payable from purchase
        """
        try:
            from .models_accounting_advanced import AccountsPayable
            
            ap = AccountsPayable.objects.create(
                vendor_name=vendor_name,
                vendor_invoice=invoice_number or 'N/A',
                bill_date=timezone.now().date(),
                due_date=timezone.now().date() + timezone.timedelta(days=30),
                amount=amount,
                balance_due=amount,
                description=description,
            )
            
            print(f"[AUTO-SYNC] Purchase GHS {amount} from {vendor_name} → AP ✓")
            return ap
        
        except Exception as e:
            print(f"[ERROR] AP creation failed: {e}")
            return None
    
    @staticmethod
    def pay_supplier(vendor_name, amount, description, user):
        """
        Record supplier payment
        """
        try:
            # Get accounts
            expense_account = Account.objects.get(account_code='5100')
            bank_account = Account.objects.get(account_code='1010')
            
            # Create payment voucher
            voucher = PaymentVoucher.objects.create(
                payment_type='supplier',
                payee_name=vendor_name,
                description=description,
                amount=amount,
                payment_method='bank_transfer',
                status='approved',
                expense_account=expense_account,
                payment_account=bank_account,
                requested_by=user,
            )
            
            # Mark as paid (this creates journal entry automatically)
            voucher.mark_paid(user)
            
            print(f"[AUTO-SYNC] Supplier payment GHS {amount} → Voucher → JE → GL ✓")
            return voucher
        
        except Exception as e:
            print(f"[ERROR] Supplier payment failed: {e}")
            return None


# ==================== REAL-TIME SYNC STATUS ====================

def get_accounting_sync_status():
    """
    Check what's synced and what's not
    Returns status report
    """
    from .models import Invoice
    from .models_accounting import Transaction
    
    # Count invoices
    total_invoices = Invoice.objects.filter(is_deleted=False).count()
    
    # Count AR entries
    try:
        total_ar = AdvancedAccountsReceivable.objects.count()
    except:
        total_ar = 0
    
    # Count transactions
    total_transactions = Transaction.objects.count()
    
    # Count revenue entries
    try:
        total_revenue = Revenue.objects.count()
    except:
        total_revenue = 0
    
    # Count expenses
    try:
        total_expenses = Expense.objects.count()
    except:
        total_expenses = 0
    
    # Count journal entries
    try:
        total_je = AdvancedJournalEntry.objects.count()
    except:
        total_je = 0
    
    status = {
        'invoices': total_invoices,
        'ar_entries': total_ar,
        'transactions': total_transactions,
        'revenue_entries': total_revenue,
        'expenses': total_expenses,
        'journal_entries': total_je,
        'sync_percentage': round((total_revenue / max(total_transactions, 1)) * 100, 1) if total_transactions > 0 else 0,
    }
    
    return status




















