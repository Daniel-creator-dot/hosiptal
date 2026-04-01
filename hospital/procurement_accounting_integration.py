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
    AdvancedJournalEntry, AdvancedJournalEntryLine, Journal, AdvancedGeneralLedger,
    WithholdingTaxPayable
)


class ProcurementAccountingIntegration:
    """
    Integration layer between procurement and accounting
    Handles automatic creation of accounting entries
    """
    
    @staticmethod
    def create_accounting_entries_for_procurement(procurement_request, expense_account=None,
                                                  liability_account=None, payment_account=None):
        """
        Create complete accounting entries when procurement is approved.
        
        Optional accounts (for finance to choose debit/credit):
        - expense_account: Account to DEBIT (expense recognition). If None, uses default 5100.
        - liability_account: Account to CREDIT for AP (e.g. 2100 Accounts Payable). If None, uses default 2100.
        - payment_account: Bank/Cash account to CREDIT when payment is made (for voucher). If None, uses default 1010.
        
        This creates:
        1. Accounts Payable (AP) - Records liability to vendor
        2. Expense Entry - Recognizes the expense
        3. Payment Voucher - Authorizes payment
        All post to General Ledger and update finance reports.
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
                
                # 2. EXPENSE ACCOUNT (Debit) - use selected or default
                if expense_account is None:
                    expense_account, _ = Account.objects.get_or_create(
                        account_code='5100',
                        defaults={'account_name': 'Operating Expenses', 'account_type': 'expense'}
                    )
                else:
                    expense_account = Account.objects.get(pk=expense_account) if isinstance(expense_account, (int, str)) else expense_account
                
                expense_category, _ = ExpenseCategory.objects.get_or_create(
                    code='EXP-PROC',
                    defaults={
                        'name': 'Procurement Expenses',
                        'account': expense_account,
                        'requires_approval': True,
                    }
                )
                if expense_category.account_id != expense_account.pk:
                    expense_category.account = expense_account
                    expense_category.save(update_fields=['account'])
                
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
                
                # 3. PAYMENT ACCOUNT (Credit when paying) - use selected or default
                if payment_account is None:
                    payment_account, _ = Account.objects.get_or_create(
                        account_code='1010',
                        defaults={'account_name': 'Bank Account - Main', 'account_type': 'asset'}
                    )
                else:
                    payment_account = Account.objects.get(pk=payment_account) if isinstance(payment_account, (int, str)) else payment_account
                bank_account = payment_account
                
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
                
                # Post to General Ledger (using selected liability account for AP if provided)
                try:
                    journal_entry = create_procurement_journal_entry(
                        procurement_request=procurement_request,
                        expense=expense,
                        ap=ap,
                        voucher=voucher,
                        liability_account=liability_account,
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
    def create_ap_from_grn(grn, invoice_amount, invoice_number, supplier_name, supply_type='goods', supplier_is_exempted=False):
        """
        Create Accounts Payable from Goods Received Note (GRN)
        Implements 3-way matching: PO, Invoice, GRN
        
        According to guidelines:
        - GRN amount and Invoice amount MUST be equal
        - If not the same, system should not allow the transfer
        - If same, create AP with GRN amount
        - Automatically calculate withholding tax (3% for goods, 5% works, 7.5% local services, 20% foreign)
        - Create WithholdingTaxPayable entry
        
        Args:
            grn: GoodsReceiptNote object
            invoice_amount: Amount from supplier invoice
            invoice_number: Supplier invoice number
            supplier_name: Supplier/vendor name
            supply_type: 'goods', 'works', 'local_services', 'foreign_services'
            supplier_is_exempted: Whether supplier is exempted from WHT
        
        Returns:
            dict with 'success', 'accounts_payable', 'withholding_tax', 'error'
        """
        try:
            with db_transaction.atomic():
                # Get GRN amount (total from GRN lines)
                grn_amount = Decimal('0.00')
                if hasattr(grn, 'lines'):
                    grn_amount = sum(line.line_total for line in grn.lines.all())
                elif hasattr(grn, 'total_amount'):
                    grn_amount = grn.total_amount
                else:
                    return {
                        'success': False,
                        'error': 'GRN amount cannot be determined'
                    }
                
                # 3-WAY MATCHING VALIDATION
                if abs(invoice_amount - grn_amount) > Decimal('0.01'):  # Allow small rounding differences
                    return {
                        'success': False,
                        'error': f'3-way matching failed: Invoice amount (GHS {invoice_amount:,.2f}) does not match GRN amount (GHS {grn_amount:,.2f}). System cannot allow transfer.'
                    }
                
                # Get purchase order if available
                po_number = ''
                if hasattr(grn, 'purchase_order') and grn.purchase_order:
                    if hasattr(grn.purchase_order, 'po_number'):
                        po_number = grn.purchase_order.po_number
                    elif hasattr(grn.purchase_order, 'purchase_number'):
                        po_number = grn.purchase_order.purchase_number
                
                # Get or create purchase account based on supply type
                purchase_account_map = {
                    'goods': ('5200', 'Purchases - Drugs'),
                    'works': ('5300', 'Purchases - Works'),
                    'local_services': ('5400', 'Purchases - Local Services'),
                    'foreign_services': ('5500', 'Purchases - Foreign Services'),
                }
                account_code, account_name = purchase_account_map.get(supply_type, ('5200', 'Purchases'))
                
                purchase_account, _ = Account.objects.get_or_create(
                    account_code=account_code,
                    defaults={'account_name': account_name, 'account_type': 'expense'}
                )
                
                # Get or create AP account
                ap_account, _ = Account.objects.get_or_create(
                    account_code='2100',
                    defaults={'account_name': 'Accounts Payable', 'account_type': 'liability'}
                )
                
                # Create Accounts Payable
                from datetime import datetime
                bill_prefix = "AP"
                year_month = datetime.now().strftime('%Y%m')
                ap_count = AccountsPayable.objects.filter(
                    bill_number__startswith=f"{bill_prefix}{year_month}"
                ).count()
                bill_number = f"{bill_prefix}{year_month}{ap_count + 1:05d}"
                
                ap = AccountsPayable.objects.create(
                    bill_number=bill_number,
                    vendor_name=supplier_name,
                    vendor_invoice=invoice_number,
                    bill_date=timezone.now().date(),
                    due_date=timezone.now().date() + timezone.timedelta(days=30),
                    amount=grn_amount,  # Use GRN amount (not invoice amount per guidelines)
                    amount_paid=Decimal('0.00'),
                    balance_due=grn_amount,
                    description=f"Purchase from {supplier_name} - GRN: {grn.grn_number if hasattr(grn, 'grn_number') else 'N/A'}",
                    purchase_order_number=po_number,
                    invoice_amount=invoice_amount,
                    grn_amount=grn_amount,
                    grn_number=grn.grn_number if hasattr(grn, 'grn_number') else '',
                    is_matched=True,  # Already validated above
                    supply_type=supply_type,
                    supplier_is_exempted=supplier_is_exempted,
                )
                
                print(f"[ACCOUNTING] ✅ Created AP from GRN: {supplier_name} - GHS {grn_amount}")
                
                # Calculate and create Withholding Tax Payable (unless exempted)
                withholding_tax = None
                if not supplier_is_exempted:
                    wht_rate = WithholdingTaxPayable.get_rate_for_supply_type(supply_type)
                    wht_amount = (grn_amount * wht_rate / 100)
                    
                    # Get or create WHT Payable account
                    wht_account, _ = Account.objects.get_or_create(
                        account_code='2400',
                        defaults={'account_name': 'Withholding Tax Payable', 'account_type': 'liability'}
                    )
                    
                    withholding_tax = WithholdingTaxPayable.objects.create(
                        supplier_name=supplier_name,
                        gross_amount=grn_amount,
                        withholding_rate=wht_rate,
                        withholding_amount=wht_amount,
                        net_amount_paid=grn_amount - wht_amount,
                        supply_type=supply_type,
                        is_exempted=False,
                        accounts_payable=ap,
                        payable_account=wht_account,
                        description=f"WHT on purchase from {supplier_name}",
                    )
                    
                    print(f"[ACCOUNTING] ✅ Created WHT Payable: GHS {wht_amount:,.2f} ({wht_rate}%)")
                
                # Create Journal Entry: Debit Purchase Account, Credit Accounts Payable
                expense_journal, _ = Journal.objects.get_or_create(
                    journal_type='general',
                    defaults={'name': 'General Journal', 'code': 'GJ', 'description': 'General journal entries'}
                )
                
                journal_entry = AdvancedJournalEntry.objects.create(
                    journal=expense_journal,
                    entry_date=timezone.now().date(),
                    description=f"Purchase from {supplier_name} - GRN: {grn.grn_number if hasattr(grn, 'grn_number') else 'N/A'}",
                    reference=bill_number,
                    status='posted',
                )
                
                # Debit: Purchase Account
                AdvancedJournalEntryLine.objects.create(
                    journal_entry=journal_entry,
                    line_number=1,
                    account=purchase_account,
                    description=f"Purchase from {supplier_name}",
                    debit_amount=grn_amount,
                    credit_amount=Decimal('0.00'),
                )
                
                # Credit: Accounts Payable
                AdvancedJournalEntryLine.objects.create(
                    journal_entry=journal_entry,
                    line_number=2,
                    account=ap_account,
                    description=f"AP for {supplier_name}",
                    debit_amount=Decimal('0.00'),
                    credit_amount=grn_amount,
                )
                
                # If WHT, also create WHT Payable entry
                if withholding_tax:
                    AdvancedJournalEntryLine.objects.create(
                        journal_entry=journal_entry,
                        line_number=3,
                        account=wht_account,
                        description=f"WHT Payable for {supplier_name}",
                        debit_amount=Decimal('0.00'),
                        credit_amount=withholding_tax.withholding_amount,
                    )
                    
                    # Adjust AP credit to net amount (gross - WHT)
                    # Update line 2 to credit net amount
                    line_2 = journal_entry.lines.get(line_number=2)
                    line_2.credit_amount = withholding_tax.net_amount_paid
                    line_2.save()
                
                # Update totals
                journal_entry.total_debit = grn_amount
                journal_entry.total_credit = grn_amount
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
                        balance=Decimal('0.00'),
                    )
                
                ap.journal_entry = journal_entry
                ap.save(update_fields=['journal_entry'])
                
                if withholding_tax:
                    withholding_tax.journal_entry = journal_entry
                    withholding_tax.save(update_fields=['journal_entry'])
                
                print(f"[ACCOUNTING] ✅ Posted to General Ledger: {journal_entry.entry_number}")
                
                return {
                    'success': True,
                    'accounts_payable': ap,
                    'withholding_tax': withholding_tax,
                    'message': f'AP created from GRN: GHS {grn_amount:,.2f}'
                }
        
        except Exception as e:
            print(f"\n❌ ERROR in create_ap_from_grn: {e}")
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


def create_procurement_journal_entry(procurement_request, expense, ap, voucher, liability_account=None):
    """
    Create General Ledger entries for procurement (double-entry).
    Debit: Expense Account (increases expenses)
    Credit: Accounts Payable account (increases liability).
    """
    try:
        expense_journal, _ = Journal.objects.get_or_create(
            journal_type='general',
            defaults={
                'name': 'General Journal',
                'code': 'GJ',
                'description': 'General journal entries'
            }
        )
        
        journal_entry = AdvancedJournalEntry.objects.create(
            journal=expense_journal,
            entry_date=expense.expense_date,
            description=f"Procurement Expense - {procurement_request.request_number}",
            reference=procurement_request.request_number,
            status='posted',
        )
        
        # Debit: Expense Account
        AdvancedJournalEntryLine.objects.create(
            journal_entry=journal_entry,
            line_number=1,
            account=expense.category.account,
            debit_amount=expense.amount,
            credit_amount=Decimal('0.00'),
            description=f"Procurement expense - {expense.vendor_name}"
        )
        
        # Credit: Liability (AP) account - use selected or default
        if liability_account is not None:
            ap_account = Account.objects.get(pk=liability_account) if isinstance(liability_account, (int, str)) else liability_account
        else:
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


def auto_create_accounting_on_approval(procurement_request, expense_account=None,
                                        liability_account=None, payment_account=None):
    """
    Create accounting entries when procurement is approved by accounts.
    Optional: expense_account (debit), liability_account (credit for AP), payment_account (credit when paying).
    """
    try:
        print(f"\n[ACCOUNTING] Starting auto-creation for {procurement_request.request_number}")
        
        result = ProcurementAccountingIntegration.create_accounting_entries_for_procurement(
            procurement_request,
            expense_account=expense_account,
            liability_account=liability_account,
            payment_account=payment_account,
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

