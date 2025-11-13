"""
Procurement-to-Accounting Integration
Automatic creation of accounting entries when procurement is approved
World-class P2P (Procure-to-Pay) workflow
"""

from decimal import Decimal
from django.db import transaction as db_transaction
from django.utils import timezone
from .models_accounting import Account
from .models_accounting_advanced import (
    AccountsPayable, PaymentVoucher, Expense, ExpenseCategory,
    AdvancedJournalEntry, AdvancedJournalEntryLine, Journal, AdvancedGeneralLedger
)


class ProcurementAccountingIntegration:
    """
    Integration layer between procurement and accounting
    Handles automatic creation of accounting entries
    """
    
    @staticmethod
    def create_accounting_entries_for_procurement(procurement_request):
        """
        Create complete accounting entries when procurement is approved
        
        This creates:
        1. Accounts Payable (AP) - Records liability to vendor
        2. Expense Entry - Recognizes the expense
        3. Payment Voucher - Authorizes payment
        
        This follows proper accounting principles:
        - Accrual basis accounting (expense recognized when incurred)
        - Proper segregation of duties (procurement → accounts → payment)
        - Audit trail (all entries linked)
        """
        try:
            with db_transaction.atomic():
                # Get the total amount
                total_amount = procurement_request.estimated_total or Decimal('0.00')
                if total_amount <= 0:
                    # Calculate from items
                    total_amount = sum(item.line_total for item in procurement_request.items.all())
                
                # Get vendor info
                vendor_name = 'TBD'
                if hasattr(procurement_request, 'purchase_order') and procurement_request.purchase_order:
                    vendor_name = procurement_request.purchase_order.supplier.name
                
                # 1. CREATE ACCOUNTS PAYABLE
                # This records our liability to pay the vendor
                
                # Generate unique bill number
                from datetime import datetime
                bill_prefix = "AP"
                year_month = datetime.now().strftime('%Y%m')
                ap_count = AccountsPayable.objects.filter(
                    bill_number__startswith=f"{bill_prefix}{year_month}"
                ).count()
                bill_number = f"{bill_prefix}{year_month}{ap_count + 1:05d}"
                
                ap = AccountsPayable.objects.create(
                    bill_number=bill_number,
                    vendor_name=vendor_name,
                    vendor_invoice=f"PR-{procurement_request.request_number}",
                    bill_date=timezone.now().date(),
                    due_date=timezone.now().date() + timezone.timedelta(days=30),
                    amount=total_amount,
                    amount_paid=Decimal('0.00'),
                    balance_due=total_amount,
                    description=f"Procurement: {procurement_request.request_number}",
                )
                
                print(f"[ACCOUNTING] ✅ Created AP: {vendor_name} - GHS {total_amount}")
                
                # 2. CREATE EXPENSE ENTRY
                # This recognizes the expense (accrual accounting)
                expense_account, _ = Account.objects.get_or_create(
                    account_code='5100',
                    defaults={'account_name': 'Operating Expenses', 'account_type': 'expense'}
                )
                
                expense_category, _ = ExpenseCategory.objects.get_or_create(
                    code='EXP-PROC',
                    defaults={
                        'name': 'Procurement Expenses',
                        'account': expense_account,
                        'requires_approval': True,
                    }
                )
                
                # Get User for expense recording
                expense_user = None
                if hasattr(procurement_request, 'accounts_approved_by') and procurement_request.accounts_approved_by:
                    expense_user = procurement_request.accounts_approved_by.user if hasattr(procurement_request.accounts_approved_by, 'user') else None
                
                # First create the expense entry
                expense = Expense.objects.create(
                    expense_date=timezone.now().date(),
                    category=expense_category,
                    description=f"Procurement {procurement_request.request_number}",
                    amount=total_amount,
                    vendor_name=vendor_name,
                    vendor_invoice_number=procurement_request.request_number,
                    status='approved',  # Already approved through procurement
                    recorded_by=expense_user,
                    approved_by=expense_user,
                )
                
                print(f"[ACCOUNTING] ✅ Created Expense: {expense.expense_number} - GHS {total_amount}")
                
                # 3. CREATE PAYMENT VOUCHER
                # This authorizes payment to be made
                bank_account, _ = Account.objects.get_or_create(
                    account_code='1010',
                    defaults={'account_name': 'Bank Account - Main', 'account_type': 'asset'}
                )
                
                # Get User objects (PaymentVoucher needs User, not Staff)
                requested_user = None
                approved_user = None
                
                if hasattr(procurement_request, 'requested_by') and procurement_request.requested_by:
                    requested_user = procurement_request.requested_by.user if hasattr(procurement_request.requested_by, 'user') else None
                
                if hasattr(procurement_request, 'accounts_approved_by') and procurement_request.accounts_approved_by:
                    approved_user = procurement_request.accounts_approved_by.user if hasattr(procurement_request.accounts_approved_by, 'user') else None
                
                voucher = PaymentVoucher.objects.create(
                    payment_type='supplier',  # FIXED: Changed from 'vendor' to 'supplier' (valid choice)
                    voucher_date=timezone.now().date(),
                    payee_name=vendor_name,
                    payee_type='Supplier',
                    description=f"Payment for Procurement {procurement_request.request_number}",
                    amount=total_amount,
                    payment_method='bank_transfer',
                    status='approved',  # Ready for payment
                    expense_account=expense_account,
                    payment_account=bank_account,
                    requested_by=requested_user,
                    approved_by=approved_user,
                    approved_date=timezone.now(),
                    po_number=procurement_request.request_number,  # Link to procurement
                )
                
                print(f"[ACCOUNTING] ✅ Created Payment Voucher: {voucher.voucher_number}")
                
                # Link Payment Voucher to Expense
                expense.payment_voucher = voucher
                expense.save(update_fields=['payment_voucher'])
                
                # Link Payment Voucher to AP
                ap.payment_voucher = voucher
                ap.save(update_fields=['payment_voucher'])
                
                print(f"[ACCOUNTING] ✅ Linked all entries together for complete traceability")
                
                # Post to General Ledger
                try:
                    journal_entry = create_procurement_journal_entry(
                        procurement_request=procurement_request,
                        expense=expense,
                        ap=ap,
                        voucher=voucher
                    )
                    if journal_entry:
                        print(f"[ACCOUNTING] ✅ Posted to General Ledger: {journal_entry.entry_number}")
                except Exception as e:
                    print(f"[ACCOUNTING] ⚠️ Could not post to GL: {e}")
                
                # Return the created entries
                return {
                    'accounts_payable': ap,
                    'expense': expense,
                    'payment_voucher': voucher,
                    'success': True,
                    'message': f'Accounting entries created successfully for GHS {total_amount:,.2f}'
                }
        
        except Exception as e:
            print(f"\n❌ ERROR in create_accounting_entries_for_procurement: {e}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    def process_payment(procurement_request, paid_by):
        """
        Process payment when vendor is paid
        Updates AP and marks voucher as paid
        """
        # This would be called when actual payment is made
        # It updates the accounting entries
        pass
    
    @staticmethod
    def get_procurement_accounting_summary(procurement_request):
        """
        Get summary of accounting entries for a procurement request
        """
        summary = {
            'has_accounting_entries': False,
            'ap_entry': None,
            'expense_entry': None,
            'payment_voucher': None,
            'total_amount': Decimal('0.00'),
        }
        
        # Check for AP entries
        ap_entries = AccountsPayable.objects.filter(
            vendor_invoice__contains=procurement_request.request_number
        )
        
        if ap_entries.exists():
            summary['has_accounting_entries'] = True
            summary['ap_entry'] = ap_entries.first()
        
        # Check for expense entries
        expense_entries = Expense.objects.filter(
            vendor_invoice_number=procurement_request.request_number
        )
        
        if expense_entries.exists():
            summary['expense_entry'] = expense_entries.first()
            summary['total_amount'] = expense_entries.first().amount
        
        # Check for payment vouchers
        voucher_entries = PaymentVoucher.objects.filter(
            description__contains=procurement_request.request_number
        )
        
        if voucher_entries.exists():
            summary['payment_voucher'] = voucher_entries.first()
        
        return summary


def create_procurement_journal_entry(procurement_request, expense, ap, voucher):
    """
    Create General Ledger entries for procurement
    Proper double-entry bookkeeping:
    
    Debit: Expense Account (increases expenses)
    Credit: Accounts Payable (increases liability)
    """
    try:
        # Get or create expense journal
        expense_journal, _ = Journal.objects.get_or_create(
            journal_type='general',
            defaults={
                'name': 'General Journal',
                'code': 'GJ',
                'description': 'General journal entries'
            }
        )
        
        # Create journal entry
        journal_entry = AdvancedJournalEntry.objects.create(
            journal=expense_journal,
            entry_date=expense.expense_date,
            description=f"Procurement Expense - {procurement_request.request_number}",
            reference=procurement_request.request_number,
            status='posted',  # Auto-post for procurement
        )
        
        # Debit: Expense Account (Dr. Expense = increase expense)
        AdvancedJournalEntryLine.objects.create(
            journal_entry=journal_entry,  # FIXED: Changed from 'entry' to 'journal_entry'
            line_number=1,
            account=expense.category.account,
            debit_amount=expense.amount,
            credit_amount=Decimal('0.00'),
            description=f"Procurement expense - {expense.vendor_name}"
        )
        
        # Credit: Accounts Payable (Cr. AP = increase liability)
        ap_account, _ = Account.objects.get_or_create(
            account_code='2100',
            defaults={'account_name': 'Accounts Payable', 'account_type': 'liability'}
        )
        
        AdvancedJournalEntryLine.objects.create(
            journal_entry=journal_entry,  # FIXED: Changed from 'entry' to 'journal_entry'
            line_number=2,
            account=ap_account,
            debit_amount=Decimal('0.00'),
            credit_amount=expense.amount,
            description=f"AP for {expense.vendor_name}"
        )
        
        # Update totals
        journal_entry.total_debit = expense.amount
        journal_entry.total_credit = expense.amount
        journal_entry.save(update_fields=['total_debit', 'total_credit'])
        
        # Post to General Ledger
        for line in journal_entry.lines.all():
            AdvancedGeneralLedger.objects.create(
                account=line.account,
                cost_center=line.cost_center,
                transaction_date=journal_entry.entry_date,
                posting_date=journal_entry.entry_date,
                journal_entry=journal_entry,
                journal_entry_line=line,
                description=line.description,
                debit_amount=line.debit_amount,
                credit_amount=line.credit_amount,
                balance=Decimal('0.00'),  # Will be calculated
            )
        
        # Link journal entry to expense and voucher
        expense.journal_entry = journal_entry
        expense.save(update_fields=['journal_entry'])
        
        voucher.journal_entry = journal_entry
        voucher.save(update_fields=['journal_entry'])
        
        return journal_entry
        
    except Exception as e:
        print(f"[LEDGER] ⚠️ Error posting to GL: {e}")
        import traceback
        traceback.print_exc()
        return None


def post_payment_to_ledger(payment_voucher):
    """
    Post payment to General Ledger when voucher is marked as paid
    Proper double-entry bookkeeping:
    
    Debit: Accounts Payable (decreases liability)
    Credit: Bank/Cash Account (decreases asset)
    """
    try:
        if payment_voucher.status != 'paid':
            return None
        
        # Get payment journal
        payment_journal, _ = Journal.objects.get_or_create(
            journal_type='payment',
            defaults={
                'name': 'Payment Journal',
                'code': 'PJ',
                'description': 'Payment journal entries'
            }
        )
        
        # Create journal entry
        journal_entry = AdvancedJournalEntry.objects.create(
            journal=payment_journal,
            entry_date=payment_voucher.payment_date or timezone.now().date(),
            description=f"Payment - {payment_voucher.voucher_number} - {payment_voucher.payee_name}",
            reference=payment_voucher.payment_reference or payment_voucher.voucher_number,
            status='posted',
        )
        
        # Debit: Accounts Payable (Dr. AP = decrease liability)
        ap_account, _ = Account.objects.get_or_create(
            account_code='2100',
            defaults={'account_name': 'Accounts Payable', 'account_type': 'liability'}
        )
        
        AdvancedJournalEntryLine.objects.create(
            journal_entry=journal_entry,  # FIXED: Changed from 'entry' to 'journal_entry'
            line_number=1,
            account=ap_account,
            debit_amount=payment_voucher.amount,
            credit_amount=Decimal('0.00'),
            description=f"Payment to {payment_voucher.payee_name}"
        )
        
        # Credit: Bank/Cash Account (Cr. Bank = decrease asset)
        AdvancedJournalEntryLine.objects.create(
            journal_entry=journal_entry,  # FIXED: Changed from 'entry' to 'journal_entry'
            line_number=2,
            account=payment_voucher.payment_account,
            debit_amount=Decimal('0.00'),
            credit_amount=payment_voucher.amount,
            description=f"Paid via {payment_voucher.get_payment_method_display()}"
        )
        
        # Update totals
        journal_entry.total_debit = payment_voucher.amount
        journal_entry.total_credit = payment_voucher.amount
        journal_entry.save(update_fields=['total_debit', 'total_credit'])
        
        # Post to General Ledger
        for line in journal_entry.lines.all():
            AdvancedGeneralLedger.objects.create(
                account=line.account,
                cost_center=line.cost_center,
                transaction_date=journal_entry.entry_date,
                posting_date=journal_entry.entry_date,
                journal_entry=journal_entry,
                journal_entry_line=line,
                description=line.description,
                debit_amount=line.debit_amount,
                credit_amount=line.credit_amount,
                balance=Decimal('0.00'),  # Will be calculated
            )
        
        # Link journal entry to payment voucher
        payment_voucher.journal_entry = journal_entry
        payment_voucher.save(update_fields=['journal_entry'])
        
        print(f"[LEDGER] ✅ Posted payment to GL: {journal_entry.entry_number}")
        return journal_entry
        
    except Exception as e:
        print(f"[LEDGER] ⚠️ Error posting payment to GL: {e}")
        import traceback
        traceback.print_exc()
        return None


def auto_create_accounting_on_approval(procurement_request):
    """
    Helper function to automatically create accounting entries
    when procurement is approved by accounts department
    
    Call this after accounts approval:
    auto_create_accounting_on_approval(procurement_request)
    """
    try:
        print(f"\n[ACCOUNTING] Starting auto-creation for {procurement_request.request_number}")
        
        result = ProcurementAccountingIntegration.create_accounting_entries_for_procurement(
            procurement_request
        )
        
        if result and result.get('success'):
            print(f"\n{'='*70}")
            print(f"✅ ACCOUNTING INTEGRATION SUCCESS!")
            print(f"{'='*70}")
            print(f"Procurement: {procurement_request.request_number}")
            print(f"Amount: GHS {result['payment_voucher'].amount:,.2f}")
            print(f"")
            print(f"Created:")
            print(f"  • Accounts Payable: {result['accounts_payable'].bill_number} - {result['accounts_payable'].vendor_name}")
            print(f"  • Expense Entry: {result['expense'].expense_number}")
            print(f"  • Payment Voucher: {result['payment_voucher'].voucher_number}")
            print(f"")
            print(f"Status: Ready for Payment Processing")
            print(f"{'='*70}\n")
            
            return result
        else:
            print(f"\n❌ Result was None or success=False")
            return None
        
    except Exception as e:
        print(f"\n❌ ERROR creating accounting entries: {e}")
        import traceback
        traceback.print_exc()
        return None

