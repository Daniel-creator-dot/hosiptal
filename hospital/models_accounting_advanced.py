"""
Advanced Accounting System - State of the Art
Complete double-entry accounting with journals, ledgers, and financial reporting
"""

import uuid
from django.db import models, transaction
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.validators import MinValueValidator
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timedelta, date
from .models import BaseModel, Patient, Invoice, Department, Staff, Payer
from .models_accounting import Account, CostCenter


# ==================== CHART OF ACCOUNTS & LEDGERS ====================

class AccountCategory(BaseModel):
    """Account Categories for better organization"""
    CATEGORY_TYPES = [
        ('asset', 'Asset'),
        ('current_asset', 'Current Asset'),
        ('fixed_asset', 'Fixed Asset'),
        ('liability', 'Liability'),
        ('current_liability', 'Current Liability'),
        ('long_term_liability', 'Long Term Liability'),
        ('equity', 'Equity'),
        ('revenue', 'Revenue'),
        ('expense', 'Expense'),
        ('cost_of_sales', 'Cost of Sales'),
    ]
    
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=200)
    category_type = models.CharField(max_length=30, choices=CATEGORY_TYPES)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['code']
        verbose_name_plural = 'Account Categories'
    
    def __str__(self):
        return f"{self.code} - {self.name}"


class FiscalYear(BaseModel):
    """Fiscal Year for accounting periods"""
    name = models.CharField(max_length=50)
    start_date = models.DateField()
    end_date = models.DateField()
    is_closed = models.BooleanField(default=False)
    closed_date = models.DateTimeField(null=True, blank=True)
    closed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        ordering = ['-start_date']
    
    def __str__(self):
        return f"{self.name} ({self.start_date} to {self.end_date})"
    
    @property
    def is_current(self):
        today = timezone.now().date()
        return self.start_date <= today <= self.end_date


class AccountingPeriod(BaseModel):
    """Monthly accounting periods"""
    fiscal_year = models.ForeignKey(FiscalYear, on_delete=models.CASCADE, related_name='periods')
    period_number = models.IntegerField()  # 1-12
    name = models.CharField(max_length=50)  # e.g., "January 2025"
    start_date = models.DateField()
    end_date = models.DateField()
    is_closed = models.BooleanField(default=False)
    closed_date = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-start_date']
        unique_together = ['fiscal_year', 'period_number']
    
    def __str__(self):
        return f"{self.name} (Period {self.period_number})"


# ==================== JOURNALS & TRANSACTIONS ====================

class Journal(BaseModel):
    """Journal Types for different transaction categories"""
    JOURNAL_TYPES = [
        ('general', 'General Journal'),
        ('sales', 'Sales Journal'),
        ('purchase', 'Purchase Journal'),
        ('payment', 'Payment Journal'),
        ('receipt', 'Receipt Journal'),
        ('cash', 'Cash Journal'),
        ('bank', 'Bank Journal'),
    ]
    
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=100)
    journal_type = models.CharField(max_length=20, choices=JOURNAL_TYPES)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    
    # Default accounts for this journal
    default_debit_account = models.ForeignKey(
        Account, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='journal_defaults_debit'
    )
    default_credit_account = models.ForeignKey(
        Account, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='journal_defaults_credit'
    )
    
    class Meta:
        ordering = ['code']
    
    def __str__(self):
        return f"{self.code} - {self.name}"


class AdvancedJournalEntry(BaseModel):
    """Advanced Journal Entry Header (Double-Entry Bookkeeping)"""
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('posted', 'Posted'),
        ('void', 'Void'),
        ('reversed', 'Reversed'),
    ]
    
    entry_number = models.CharField(max_length=50, unique=True)
    journal = models.ForeignKey(Journal, on_delete=models.PROTECT, related_name='entries')
    entry_date = models.DateField(default=timezone.now)
    posting_date = models.DateField(null=True, blank=True)
    
    fiscal_year = models.ForeignKey(FiscalYear, on_delete=models.PROTECT, null=True, blank=True)
    accounting_period = models.ForeignKey(AccountingPeriod, on_delete=models.PROTECT, null=True, blank=True)
    
    reference = models.CharField(max_length=100, blank=True, help_text="External reference (invoice, PO, etc.)")
    description = models.TextField()
    notes = models.TextField(blank=True)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    
    # Amounts
    total_debit = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_credit = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # User tracking
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='journal_entries_created')
    posted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='journal_entries_posted')
    
    # Links
    invoice = models.ForeignKey(Invoice, on_delete=models.SET_NULL, null=True, blank=True)
    reversed_entry = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='reversals')
    
    class Meta:
        ordering = ['-entry_date', '-entry_number']
        verbose_name_plural = 'Journal Entries'
    
    def __str__(self):
        return f"{self.entry_number} - {self.entry_date} - GHS {self.total_debit}"
    
    def save(self, *args, **kwargs):
        if not self.entry_number:
            self.entry_number = self.generate_entry_number()
        super().save(*args, **kwargs)
    
    @staticmethod
    def generate_entry_number():
        """Generate unique journal entry number"""
        today = timezone.now()
        prefix = f"JE{today.strftime('%Y%m')}"
        
        last_entry = AdvancedJournalEntry.objects.filter(
            entry_number__startswith=prefix
        ).order_by('-entry_number').first()
        
        if last_entry:
            last_num = int(last_entry.entry_number[-6:])
            new_num = last_num + 1
        else:
            new_num = 1
        
        return f"{prefix}{new_num:06d}"
    
    def post(self, user):
        """Post journal entry to general ledger"""
        if self.status == 'posted':
            raise ValueError("Entry already posted")
        
        if abs(self.total_debit - self.total_credit) > 0.01:
            raise ValueError("Debits and credits must balance")
        
        with transaction.atomic():
            # Update ledger for each line
            for line in self.lines.all():
                line.post_to_ledger()
            
            # Mark as posted
            self.status = 'posted'
            self.posting_date = timezone.now().date()
            self.posted_by = user
            self.save()
    
    def void(self):
        """Void the journal entry"""
        if self.status == 'void':
            raise ValueError("Entry already voided")
        
        with transaction.atomic():
            self.status = 'void'
            self.save()
            
            # Void all ledger entries
            AdvancedGeneralLedger.objects.filter(journal_entry=self).update(is_voided=True)
    
    @property
    def is_balanced(self):
        """Check if debits equal credits"""
        return abs(self.total_debit - self.total_credit) < 0.01


class AdvancedJournalEntryLine(BaseModel):
    """Advanced Journal Entry Lines (individual debit/credit entries)"""
    journal_entry = models.ForeignKey(AdvancedJournalEntry, on_delete=models.CASCADE, related_name='lines')
    line_number = models.IntegerField()
    
    account = models.ForeignKey(Account, on_delete=models.PROTECT)
    cost_center = models.ForeignKey(CostCenter, on_delete=models.SET_NULL, null=True, blank=True)
    
    description = models.CharField(max_length=500)
    
    debit_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    credit_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # Optional links
    patient = models.ForeignKey(Patient, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        ordering = ['journal_entry', 'line_number']
        unique_together = ['journal_entry', 'line_number']
    
    def __str__(self):
        return f"{self.journal_entry.entry_number}-{self.line_number}: {self.account.account_code}"
    
    def post_to_ledger(self):
        """Post this line to the general ledger"""
        AdvancedGeneralLedger.objects.create(
            journal_entry=self.journal_entry,
            journal_entry_line=self,
            account=self.account,
            cost_center=self.cost_center,
            transaction_date=self.journal_entry.entry_date,
            posting_date=self.journal_entry.posting_date or timezone.now().date(),
            description=self.description,
            debit_amount=self.debit_amount,
            credit_amount=self.credit_amount,
            balance=0,  # Will be calculated
            fiscal_year=self.journal_entry.fiscal_year,
            accounting_period=self.journal_entry.accounting_period,
        )


class AdvancedGeneralLedger(BaseModel):
    """Advanced General Ledger - All posted transactions"""
    journal_entry = models.ForeignKey(AdvancedJournalEntry, on_delete=models.PROTECT)
    journal_entry_line = models.ForeignKey(AdvancedJournalEntryLine, on_delete=models.PROTECT)
    
    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name='advanced_ledger_entries')
    cost_center = models.ForeignKey(CostCenter, on_delete=models.SET_NULL, null=True, blank=True)
    
    transaction_date = models.DateField()
    posting_date = models.DateField()
    
    description = models.CharField(max_length=500)
    
    debit_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    credit_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    balance = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    fiscal_year = models.ForeignKey(FiscalYear, on_delete=models.PROTECT, null=True, blank=True)
    accounting_period = models.ForeignKey(AccountingPeriod, on_delete=models.PROTECT, null=True, blank=True)
    
    is_voided = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['transaction_date', 'account']
        indexes = [
            models.Index(fields=['account', 'transaction_date']),
            models.Index(fields=['fiscal_year', 'accounting_period']),
        ]
    
    def __str__(self):
        return f"{self.account.account_code} - {self.transaction_date} - Dr:{self.debit_amount} Cr:{self.credit_amount}"
    
    def save(self, *args, **kwargs):
        """Calculate running balance before saving - but preserve Excel import balances"""
        from decimal import Decimal
        
        # If balance is already set and non-zero (from Excel import), preserve it
        # Only calculate if balance is 0 or not set
        update_fields = kwargs.get('update_fields', [])
        
        # For Excel imports: balance is set explicitly, don't recalculate
        # For new entries: calculate from previous balance
        if self.balance and self.balance != 0:
            # Balance already set (from Excel import) - preserve it
            pass
        elif 'balance' not in update_fields or self.balance == 0:
            # Calculate running balance for new entries
            # Get previous balance from last entry for this account (excluding this entry)
            previous_entry = AdvancedGeneralLedger.objects.filter(
                account=self.account,
                is_voided=False,
                is_deleted=False
            ).exclude(pk=self.pk if self.pk else None).order_by('transaction_date', 'created', 'id').last()
            
            previous_balance = previous_entry.balance if previous_entry else Decimal('0.00')
            
            # Calculate balance change based on account type
            if self.account.account_type in ['asset', 'expense']:
                # Assets and Expenses: Debit increases, Credit decreases
                # Balance = previous_balance + debit - credit
                balance_change = self.debit_amount - self.credit_amount
            else:
                # Liabilities, Equity, Revenue: Credit increases, Debit decreases
                # Balance = previous_balance + credit - debit
                balance_change = self.credit_amount - self.debit_amount
            
            # Update running balance
            self.balance = previous_balance + balance_change
        
        super().save(*args, **kwargs)


# ==================== PAYMENT VOUCHERS ====================

class PaymentVoucher(BaseModel):
    """Payment Vouchers for expense payments"""
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('pending_approval', 'Pending Approval'),
        ('approved', 'Approved'),
        ('paid', 'Paid'),
        ('rejected', 'Rejected'),
        ('void', 'Void'),
    ]
    
    PAYMENT_TYPES = [
        ('supplier', 'Supplier Payment'),
        ('expense', 'Expense Payment'),
        ('salary', 'Salary Payment'),
        ('utility', 'Utility Payment'),
        ('tax', 'Tax Payment'),
        ('other', 'Other Payment'),
    ]
    
    PAYMENT_METHODS = [
        ('cash', 'Cash'),
        ('bank_transfer', 'Bank Transfer'),
        ('cheque', 'Cheque'),
        ('mobile_money', 'Mobile Money'),
        ('card', 'Card'),
        ('other', 'Other'),
    ]
    
    voucher_number = models.CharField(max_length=50, unique=True)
    voucher_date = models.DateField(default=timezone.now)
    
    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPES)
    payee_name = models.CharField(max_length=200)
    payee_type = models.CharField(max_length=50, blank=True)  # Supplier, Staff, Vendor, etc.
    
    description = models.TextField()
    amount = models.DecimalField(max_digits=15, decimal_places=2, validators=[MinValueValidator(0)])
    
    payment_method = models.CharField(max_length=50, choices=PAYMENT_METHODS, default='bank_transfer')
    payment_reference = models.CharField(max_length=100, blank=True)
    payment_date = models.DateField(null=True, blank=True)
    
    # Bank details
    bank_account = models.ForeignKey('BankAccount', on_delete=models.SET_NULL, null=True, blank=True, related_name='payment_vouchers', help_text="Bank account used for payment")
    bank_name = models.CharField(max_length=200, blank=True, help_text="Legacy field - use bank_account instead")
    account_number = models.CharField(max_length=50, blank=True, help_text="Legacy field - use bank_account instead")
    cheque_number = models.CharField(max_length=50, blank=True)
    cheque = models.ForeignKey('Cheque', on_delete=models.SET_NULL, null=True, blank=True, related_name='payment_vouchers')
    
    # Payment details
    memo = models.TextField(blank=True, help_text="Memo/details for the payment")
    
    # Approval workflow
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    requested_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='vouchers_requested')
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='vouchers_approved')
    approved_date = models.DateTimeField(null=True, blank=True)
    paid_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='vouchers_paid')
    
    # Accounting links
    journal_entry = models.ForeignKey(AdvancedJournalEntry, on_delete=models.SET_NULL, null=True, blank=True)
    expense_account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name='payment_vouchers')
    payment_account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name='voucher_payments')
    
    # Supporting documents
    invoice_number = models.CharField(max_length=100, blank=True)
    po_number = models.CharField(max_length=100, blank=True)
    
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-voucher_date', '-voucher_number']
    
    def __str__(self):
        return f"{self.voucher_number} - {self.payee_name} - GHS {self.amount}"
    
    def save(self, *args, **kwargs):
        if not self.voucher_number:
            self.voucher_number = self.generate_voucher_number()
        super().save(*args, **kwargs)
    
    @staticmethod
    def generate_voucher_number():
        """Generate unique payment voucher number"""
        today = timezone.now()
        prefix = f"PV{today.strftime('%Y%m')}"
        
        last_voucher = PaymentVoucher.objects.filter(
            voucher_number__startswith=prefix
        ).order_by('-voucher_number').first()
        
        if last_voucher:
            last_num = int(last_voucher.voucher_number[-6:])
            new_num = last_num + 1
        else:
            new_num = 1
        
        return f"{prefix}{new_num:06d}"
    
    def approve(self, user):
        """Approve payment voucher"""
        if self.status != 'pending_approval':
            raise ValueError("Only pending vouchers can be approved")
        
        self.status = 'approved'
        self.approved_by = user
        self.approved_date = timezone.now()
        self.save()
    
    def mark_paid(self, user, payment_date=None, apply_withholding_tax=True):
        """
        Mark voucher as paid and create journal entry
        If AP has withholding tax, pays net amount (97% for 3% WHT) and creates WHT Payable
        
        Args:
            user: User processing the payment
            payment_date: Date of payment (defaults to today)
            apply_withholding_tax: Whether to apply withholding tax if AP has WHT
        """
        if self.status != 'approved':
            raise ValueError("Only approved vouchers can be marked as paid")
        
        with transaction.atomic():
            # Check if this is a supplier payment with AP
            ap = None
            withholding_tax = None
            net_payment_amount = self.amount
            
            if self.payment_type == 'supplier':
                # Find associated AP
                ap = AccountsPayable.objects.filter(
                    payment_voucher=self
                ).first()
                
                if ap and apply_withholding_tax and not ap.supplier_is_exempted:
                    # Get withholding tax for this AP
                    withholding_tax = WithholdingTaxPayable.objects.filter(
                        accounts_payable=ap
                    ).first()
                    
                    if withholding_tax:
                        # Pay net amount (gross - WHT)
                        net_payment_amount = withholding_tax.net_amount_paid
                        print(f"[PAYMENT] Applying WHT: Gross GHS {self.amount:,.2f}, WHT GHS {withholding_tax.withholding_amount:,.2f}, Net GHS {net_payment_amount:,.2f}")
            
            # Create journal entry
            je = AdvancedJournalEntry.objects.create(
                journal=Journal.objects.get(journal_type='payment'),
                entry_date=payment_date or timezone.now().date(),
                description=f"Payment: {self.description}",
                reference=self.voucher_number,
                created_by=user,
            )
            
            line_number = 1
            
            # If AP exists, debit AP (not expense account)
            if ap:
                # Debit Accounts Payable
                ap_account, _ = Account.objects.get_or_create(
                    account_code='2100',
                    defaults={'account_name': 'Accounts Payable', 'account_type': 'liability'}
                )
                
                AdvancedJournalEntryLine.objects.create(
                    journal_entry=je,
                    line_number=line_number,
                    account=ap_account,
                    description=f"Payment to {self.payee_name}",
                    debit_amount=net_payment_amount,
                    credit_amount=0,
                )
                line_number += 1
                
                # Update AP
                ap.amount_paid += net_payment_amount
                ap.balance_due = ap.amount - ap.amount_paid
                ap.save(update_fields=['amount_paid', 'balance_due'])
            else:
                # Debit expense account (for non-AP payments)
                AdvancedJournalEntryLine.objects.create(
                    journal_entry=je,
                    line_number=line_number,
                    account=self.expense_account,
                    description=self.description,
                    debit_amount=self.amount,
                    credit_amount=0,
                )
                line_number += 1
            
            # Credit payment account (cash/bank)
            AdvancedJournalEntryLine.objects.create(
                journal_entry=je,
                line_number=line_number,
                account=self.payment_account,
                description=self.description,
                debit_amount=0,
                credit_amount=net_payment_amount,
            )
            line_number += 1
            
            # Update totals
            je.total_debit = net_payment_amount
            je.total_credit = net_payment_amount
            je.save()
            
            # Post journal entry
            je.post(user)
            
            # Update voucher
            self.status = 'paid'
            self.payment_date = payment_date or timezone.now().date()
            self.paid_by = user
            self.journal_entry = je
            self.save()
            
            print(f"[PAYMENT] ✅ Payment processed: {self.voucher_number} - GHS {net_payment_amount:,.2f}")


class Cheque(BaseModel):
    """Cheque Management - Track cheques issued for payments"""
    STATUS_CHOICES = [
        ('issued', 'Issued'),
        ('cleared', 'Cleared'),
        ('bounced', 'Bounced'),
        ('void', 'Void'),
        ('cancelled', 'Cancelled'),
    ]
    
    cheque_number = models.CharField(max_length=50, unique=True, help_text="Cheque number from cheque book")
    bank_account = models.ForeignKey('BankAccount', on_delete=models.PROTECT, related_name='cheques')
    
    payee_name = models.CharField(max_length=200)
    amount = models.DecimalField(max_digits=15, decimal_places=2, validators=[MinValueValidator(0)])
    
    issue_date = models.DateField(default=timezone.now, help_text="Date cheque was issued")
    cheque_date = models.DateField(help_text="Date written on cheque (may be post-dated)")
    clear_date = models.DateField(null=True, blank=True, help_text="Date cheque cleared the bank")
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='issued')
    
    # Links
    payment_voucher = models.ForeignKey(PaymentVoucher, on_delete=models.SET_NULL, null=True, blank=True, related_name='cheques')
    journal_entry = models.ForeignKey(AdvancedJournalEntry, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Details
    description = models.TextField(blank=True)
    memo = models.CharField(max_length=200, blank=True, help_text="Memo line on cheque")
    
    # Tracking
    issued_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='cheques_issued')
    cleared_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='cheques_cleared')
    
    # Bank reconciliation
    bank_statement_reference = models.CharField(max_length=100, blank=True)
    reconciliation_date = models.DateField(null=True, blank=True)
    
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-issue_date', '-cheque_number']
        indexes = [
            models.Index(fields=['cheque_number']),
            models.Index(fields=['status', 'cheque_date']),
            models.Index(fields=['bank_account', 'status']),
        ]
    
    def __str__(self):
        return f"Cheque #{self.cheque_number} - {self.payee_name} - GHS {self.amount} ({self.get_status_display()})"
    
    def save(self, *args, **kwargs):
        if not self.cheque_number:
            raise ValueError("Cheque number is required")
        super().save(*args, **kwargs)
    
    def clear(self, user, clear_date=None, bank_reference=None):
        """Mark cheque as cleared"""
        if self.status not in ['issued', 'bounced']:
            raise ValueError(f"Cannot clear cheque with status: {self.status}")
        
        self.status = 'cleared'
        self.clear_date = clear_date or timezone.now().date()
        self.cleared_by = user
        if bank_reference:
            self.bank_statement_reference = bank_reference
        self.save()
    
    def bounce(self, user, notes=None):
        """Mark cheque as bounced"""
        if self.status != 'issued':
            raise ValueError(f"Cannot bounce cheque with status: {self.status}")
        
        self.status = 'bounced'
        if notes:
            self.notes = f"{self.notes}\nBounced: {notes}" if self.notes else f"Bounced: {notes}"
        self.save()
    
    def void_cheque(self, user, reason=None):
        """Void a cheque"""
        if self.status in ['cleared', 'void']:
            raise ValueError(f"Cannot void cheque with status: {self.status}")
        
        self.status = 'void'
        if reason:
            self.notes = f"{self.notes}\nVoided: {reason}" if self.notes else f"Voided: {reason}"
        self.save()
    
    @property
    def is_post_dated(self):
        """Check if cheque is post-dated"""
        return self.cheque_date > timezone.now().date()
    
    @property
    def days_outstanding(self):
        """Calculate days since cheque was issued"""
        if self.status == 'cleared' and self.clear_date:
            return (self.clear_date - self.issue_date).days
        return (timezone.now().date() - self.issue_date).days


class ReceiptVoucher(BaseModel):
    """Receipt Vouchers for revenue collection"""
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('issued', 'Issued'),
        ('void', 'Void'),
    ]
    
    receipt_number = models.CharField(max_length=50, unique=True)
    receipt_date = models.DateField(default=timezone.now)
    
    received_from = models.CharField(max_length=200)
    patient = models.ForeignKey(Patient, on_delete=models.SET_NULL, null=True, blank=True)
    
    amount = models.DecimalField(max_digits=15, decimal_places=2, validators=[MinValueValidator(0)])
    payment_method = models.CharField(max_length=50, default='cash')
    
    description = models.TextField()
    reference = models.CharField(max_length=100, blank=True)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    
    # Accounting
    journal_entry = models.ForeignKey(AdvancedJournalEntry, on_delete=models.SET_NULL, null=True, blank=True)
    revenue_account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name='receipt_vouchers')
    cash_account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name='receipt_payments')
    
    invoice = models.ForeignKey(Invoice, on_delete=models.SET_NULL, null=True, blank=True)
    
    received_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    class Meta:
        ordering = ['-receipt_date', '-receipt_number']
    
    def __str__(self):
        return f"{self.receipt_number} - {self.received_from} - GHS {self.amount}"
    
    def save(self, *args, **kwargs):
        if not self.receipt_number:
            self.receipt_number = self.generate_receipt_number()
        super().save(*args, **kwargs)
    
    @staticmethod
    def generate_receipt_number():
        """Generate unique receipt number"""
        today = timezone.now()
        prefix = f"RV{today.strftime('%Y%m')}"
        
        last_receipt = ReceiptVoucher.objects.filter(
            receipt_number__startswith=prefix
        ).order_by('-receipt_number').first()
        
        if last_receipt:
            last_num = int(last_receipt.receipt_number[-6:])
            new_num = last_num + 1
        else:
            new_num = 1
        
        return f"{prefix}{new_num:06d}"


# ==================== REVENUE MANAGEMENT ====================

class RevenueCategory(BaseModel):
    """Revenue Categories"""
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=200)
    account = models.ForeignKey(Account, on_delete=models.PROTECT)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['code']
        verbose_name_plural = 'Revenue Categories'
    
    def __str__(self):
        return f"{self.code} - {self.name}"


class Revenue(BaseModel):
    """Revenue Tracking and Recording - Enhanced with Service Type Tracking"""
    revenue_number = models.CharField(max_length=50, unique=True, blank=True)
    revenue_date = models.DateField(default=timezone.now)
    
    category = models.ForeignKey(RevenueCategory, on_delete=models.PROTECT)
    description = models.TextField()
    
    amount = models.DecimalField(max_digits=15, decimal_places=2, validators=[MinValueValidator(0)])
    
    # Source
    patient = models.ForeignKey(Patient, on_delete=models.SET_NULL, null=True, blank=True)
    invoice = models.ForeignKey(Invoice, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Payment details
    payment_method = models.CharField(max_length=50)
    reference = models.CharField(max_length=100, blank=True)
    
    # SERVICE TYPE TRACKING (for revenue analysis)
    SERVICE_TYPES = [
        ('consultation', 'Consultation'),
        ('laboratory', 'Laboratory'),
        ('pharmacy', 'Pharmacy'),
        ('imaging', 'Imaging/Radiology'),
        ('dental', 'Dental'),
        ('gynecology', 'Gynecology'),
        ('surgery', 'Surgery'),
        ('emergency', 'Emergency'),
        ('ambulance', 'Ambulance/EMS'),
        ('admission', 'Admission/Inpatient'),
        ('other', 'Other Services'),
    ]
    service_type = models.CharField(max_length=20, choices=SERVICE_TYPES, default='other', blank=True)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Reference tracking (for linking to source transaction)
    reference_type = models.CharField(max_length=50, blank=True)  # payment, lab_result, prescription, ambulance_billing, etc.
    reference_id = models.CharField(max_length=100, blank=True)  # UUID or ID of source record
    
    # Recurring revenue tracking
    is_recurring = models.BooleanField(default=False)
    recurrence_period = models.CharField(max_length=20, blank=True)  # monthly, quarterly, annual
    
    # Accounting
    journal_entry = models.ForeignKey(AdvancedJournalEntry, on_delete=models.SET_NULL, null=True, blank=True)
    receipt_voucher = models.ForeignKey(ReceiptVoucher, on_delete=models.SET_NULL, null=True, blank=True)
    
    recorded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    class Meta:
        ordering = ['-revenue_date']
        verbose_name_plural = 'Revenues'
    
    def save(self, *args, **kwargs):
        """Auto-generate revenue number"""
        if not self.revenue_number:
            self.revenue_number = self.generate_revenue_number()
        super().save(*args, **kwargs)
    
    def generate_revenue_number(self):
        """Generate unique revenue number: RVYYYYMM000001"""
        today = self.revenue_date if isinstance(self.revenue_date, timezone.datetime) else timezone.datetime.combine(self.revenue_date, timezone.datetime.min.time())
        prefix = f"RN{today.strftime('%Y%m')}"
        
        last_revenue = Revenue.objects.filter(
            revenue_number__startswith=prefix
        ).order_by('-revenue_number').first()
        
        if last_revenue and last_revenue.revenue_number:
            try:
                last_num = int(last_revenue.revenue_number[-6:])
                new_num = last_num + 1
            except (ValueError, IndexError):
                new_num = 1
        else:
            new_num = 1
        
        return f"{prefix}{new_num:06d}"
    
    def __str__(self):
        return f"{self.revenue_number} - {self.category.name} - GHS {self.amount}"


# ==================== EXPENSE MANAGEMENT ====================

class ExpenseCategory(BaseModel):
    """Expense Categories"""
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=200)
    account = models.ForeignKey(Account, on_delete=models.PROTECT)
    requires_approval = models.BooleanField(default=True)
    approval_limit = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['code']
        verbose_name_plural = 'Expense Categories'
    
    def __str__(self):
        return f"{self.code} - {self.name}"


class Expense(BaseModel):
    """Expense Recording and Tracking"""
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('paid', 'Paid'),
        ('rejected', 'Rejected'),
    ]
    
    expense_number = models.CharField(max_length=50, unique=True)
    expense_date = models.DateField(default=timezone.now)
    
    category = models.ForeignKey(ExpenseCategory, on_delete=models.PROTECT)
    description = models.TextField()
    
    amount = models.DecimalField(max_digits=15, decimal_places=2, validators=[MinValueValidator(0)])
    
    # Vendor/Supplier
    vendor_name = models.CharField(max_length=200)
    vendor_invoice_number = models.CharField(max_length=100, blank=True)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    
    # Links
    payment_voucher = models.ForeignKey(PaymentVoucher, on_delete=models.SET_NULL, null=True, blank=True)
    journal_entry = models.ForeignKey(AdvancedJournalEntry, on_delete=models.SET_NULL, null=True, blank=True)
    
    # User tracking
    recorded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='expenses_recorded')
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='expenses_approved')
    
    class Meta:
        ordering = ['-expense_date']
    
    def __str__(self):
        return f"{self.expense_number} - {self.vendor_name} - GHS {self.amount}"
    
    def save(self, *args, **kwargs):
        """Auto-generate expense number"""
        if not self.expense_number:
            self.expense_number = self.generate_expense_number()
        super().save(*args, **kwargs)
    
    @staticmethod
    def generate_expense_number():
        """Generate unique expense number: EXP202511000001"""
        today = timezone.now()
        prefix = f"EXP{today.strftime('%Y%m')}"
        
        last_expense = Expense.objects.filter(
            expense_number__startswith=prefix
        ).order_by('-expense_number').first()
        
        if last_expense:
            try:
                last_num = int(last_expense.expense_number[-6:])
                new_num = last_num + 1
            except ValueError:
                new_num = 1
        else:
            new_num = 1
        
        return f"{prefix}{new_num:06d}"


# ==================== PETTY CASH TRANSACTIONS ====================

class PettyCashTransaction(BaseModel):
    """Petty Cash Transactions with Account Personnel and Officer Approval Workflow"""
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('pending_approval', 'Pending Account Officer Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('paid', 'Paid'),
        ('void', 'Void'),
    ]
    
    transaction_number = models.CharField(max_length=50, unique=True)
    transaction_date = models.DateField(default=timezone.now)
    
    # Transaction details
    description = models.TextField(help_text="Purpose of the petty cash transaction")
    amount = models.DecimalField(max_digits=15, decimal_places=2, validators=[MinValueValidator(0)])
    
    # Payee details
    payee_name = models.CharField(max_length=200, help_text="Name of person receiving payment")
    payee_type = models.CharField(max_length=50, blank=True, help_text="e.g., Staff, Vendor, Supplier")
    
    # Expense categorization
    expense_account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name='petty_cash_transactions', 
                                       limit_choices_to={'account_type': 'expense'}, 
                                       help_text="Expense account to debit")
    cost_center = models.ForeignKey(CostCenter, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Approval workflow
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='petty_cash_created', 
                                  help_text="Account Personnel who created this transaction")
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, 
                                   related_name='petty_cash_approved',
                                   help_text="Account Officer who approved this transaction")
    approved_date = models.DateTimeField(null=True, blank=True)
    rejected_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, 
                                   related_name='petty_cash_rejected')
    rejected_date = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True, help_text="Reason for rejection if applicable")
    
    # Payment details
    payment_date = models.DateField(null=True, blank=True, help_text="Date payment was made")
    receipt_number = models.CharField(max_length=100, blank=True, help_text="Receipt number if available")
    
    # Accounting links
    journal_entry = models.ForeignKey(AdvancedJournalEntry, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Supporting documents
    invoice_number = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True, help_text="Additional notes or comments")
    
    class Meta:
        ordering = ['-transaction_date', '-created']
        verbose_name = 'Petty Cash Transaction'
        verbose_name_plural = 'Petty Cash Transactions'
    
    def __str__(self):
        return f"{self.transaction_number} - {self.payee_name} - GHS {self.amount}"
    
    def save(self, *args, **kwargs):
        if not self.transaction_number:
            self.transaction_number = self.generate_transaction_number()
        super().save(*args, **kwargs)
    
    @staticmethod
    def generate_transaction_number():
        """Generate unique petty cash transaction number: PC202511000001"""
        today = timezone.now()
        prefix = f"PC{today.strftime('%Y%m')}"
        
        last_transaction = PettyCashTransaction.objects.filter(
            transaction_number__startswith=prefix
        ).order_by('-transaction_number').first()
        
        if last_transaction:
            try:
                last_num = int(last_transaction.transaction_number[-6:])
                new_num = last_num + 1
            except ValueError:
                new_num = 1
        else:
            new_num = 1
        
        return f"{prefix}{new_num:06d}"
    
    def requires_approval(self):
        """Check if transaction requires account officer approval"""
        # All transactions require approval, but amounts > 500 GHC are mandatory
        return True
    
    def can_be_auto_approved(self):
        """Check if transaction can be auto-approved (amount <= 500 GHC)"""
        return self.amount <= Decimal('500.00')
    
    def submit_for_approval(self, user):
        """Submit transaction for account officer approval"""
        if self.status != 'draft':
            raise ValueError("Only draft transactions can be submitted for approval")
        
        self.status = 'pending_approval'
        self.created_by = user
        self.save()
    
    def approve(self, user):
        """Approve transaction by account officer"""
        if self.status != 'pending_approval':
            raise ValueError("Only pending transactions can be approved")
        
        with transaction.atomic():
            self.status = 'approved'
            self.approved_by = user
            self.approved_date = timezone.now()
            self.save()
            
            # Create journal entry: Debit Expense, Credit Petty Cash
            self._create_journal_entry(user)
    
    def _create_journal_entry(self, user):
        """Create journal entry for approved petty cash transaction"""
        from .models_accounting_advanced import Journal, AdvancedJournalEntryLine
        
        # Get petty cash account (account code 1030)
        petty_cash_account = Account.objects.filter(account_code='1030').first()
        if not petty_cash_account:
            # Create petty cash account if it doesn't exist
            petty_cash_account = Account.objects.create(
                account_code='1030',
                account_name='Petty Cash',
                account_type='asset',
                description='Petty cash account for small payments',
                is_active=True
            )
        
        # Get payment journal
        payment_journal = Journal.objects.filter(journal_type='payment').first()
        if not payment_journal:
            payment_journal = Journal.objects.create(
                journal_code='PAY',
                journal_name='Payment Journal',
                journal_type='payment',
                is_active=True
            )
        
        # Create journal entry
        je = AdvancedJournalEntry.objects.create(
            journal=payment_journal,
            entry_date=self.transaction_date,
            description=f"Petty Cash Payment: {self.description}",
            status='posted',
            entered_by=user,
            is_posted=True,
        )
        
        # Debit Expense Account
        AdvancedJournalEntryLine.objects.create(
            journal_entry=je,
            account=self.expense_account,
            cost_center=self.cost_center,
            debit_amount=self.amount,
            credit_amount=0,
            description=self.description,
        )
        
        # Credit Petty Cash Account
        AdvancedJournalEntryLine.objects.create(
            journal_entry=je,
            account=petty_cash_account,
            debit_amount=0,
            credit_amount=self.amount,
            description=f"Petty Cash Payment: {self.payee_name}",
        )
        
        # Update totals
        je.total_debit = self.amount
        je.total_credit = self.amount
        je.save()
        
        # Link journal entry
        self.journal_entry = je
        self.save()
    
    def reject(self, user, reason=''):
        """Reject transaction by account officer"""
        if self.status != 'pending_approval':
            raise ValueError("Only pending transactions can be rejected")
        
        self.status = 'rejected'
        self.rejected_by = user
        self.rejected_date = timezone.now()
        self.rejection_reason = reason
        self.save()
    
    def mark_paid(self, user, payment_date=None):
        """Mark transaction as paid"""
        if self.status != 'approved':
            raise ValueError("Only approved transactions can be marked as paid")
        
        self.status = 'paid'
        self.payment_date = payment_date or timezone.now().date()
        self.save()


# ==================== ACCOUNTS RECEIVABLE/PAYABLE ====================

class AdvancedAccountsReceivable(BaseModel):
    """Advanced Accounts Receivable Tracking"""
    invoice = models.OneToOneField(Invoice, on_delete=models.CASCADE, related_name='advanced_ar')
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='advanced_ar_accounts')
    
    invoice_amount = models.DecimalField(max_digits=15, decimal_places=2)
    amount_paid = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    balance_due = models.DecimalField(max_digits=15, decimal_places=2)
    
    due_date = models.DateField()
    last_payment_date = models.DateField(null=True, blank=True)
    
    is_overdue = models.BooleanField(default=False)
    days_overdue = models.IntegerField(default=0)
    aging_bucket = models.CharField(max_length=20, blank=True)  # 0-30, 31-60, 61-90, 90+
    
    class Meta:
        ordering = ['due_date']
        verbose_name_plural = 'Accounts Receivable'
    
    def save(self, *args, **kwargs):
        # Calculate balance
        self.balance_due = self.invoice_amount - self.amount_paid
        
        # Calculate overdue status
        if self.due_date < timezone.now().date() and self.balance_due > 0:
            self.is_overdue = True
            self.days_overdue = (timezone.now().date() - self.due_date).days
            
            # Aging bucket
            if self.days_overdue <= 30:
                self.aging_bucket = '0-30'
            elif self.days_overdue <= 60:
                self.aging_bucket = '31-60'
            elif self.days_overdue <= 90:
                self.aging_bucket = '61-90'
            else:
                self.aging_bucket = '90+'
        else:
            self.is_overdue = False
            self.days_overdue = 0
            self.aging_bucket = 'current'
        
        super().save(*args, **kwargs)


class AccountsPayable(BaseModel):
    """
    Accounts Payable Tracking
    According to accrual accounting: ALL purchases (cash or credit) must first create liabilities
    """
    bill_number = models.CharField(max_length=50, unique=True)
    vendor_name = models.CharField(max_length=200)
    vendor_invoice = models.CharField(max_length=100)
    
    bill_date = models.DateField()
    due_date = models.DateField()
    
    amount = models.DecimalField(max_digits=15, decimal_places=2, help_text="Gross amount from invoice")
    amount_paid = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    balance_due = models.DecimalField(max_digits=15, decimal_places=2)
    
    description = models.TextField()
    
    is_overdue = models.BooleanField(default=False)
    days_overdue = models.IntegerField(default=0)
    
    # 3-Way Matching Fields
    purchase_order_number = models.CharField(max_length=100, blank=True, help_text="Purchase Order number")
    invoice_amount = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, help_text="Amount from supplier invoice")
    grn_amount = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, help_text="Amount from Goods Received Note")
    grn_number = models.CharField(max_length=100, blank=True, help_text="Goods Received Note number")
    is_matched = models.BooleanField(default=False, help_text="Whether 3-way matching is complete (PO, Invoice, GRN)")
    
    # Purchase Classification (for WHT calculation)
    SUPPLY_TYPES = [
        ('goods', 'Goods (3% WHT)'),
        ('works', 'Works (5% WHT)'),
        ('local_services', 'Local Services (7.5% WHT)'),
        ('foreign_services', 'Foreign Services (20% WHT)'),
    ]
    supply_type = models.CharField(max_length=20, choices=SUPPLY_TYPES, default='goods', help_text="Type of supply for WHT calculation")
    supplier_is_exempted = models.BooleanField(default=False, help_text="Whether supplier is exempted from WHT")
    
    # Links
    payment_voucher = models.ForeignKey(PaymentVoucher, on_delete=models.SET_NULL, null=True, blank=True)
    journal_entry = models.ForeignKey(AdvancedJournalEntry, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        ordering = ['due_date']
        verbose_name_plural = 'Accounts Payable'
    
    def __str__(self):
        return f"{self.bill_number} - {self.vendor_name} - GHS {self.balance_due}"
    
    def clean(self):
        """Django's clean method - called before save()"""
        super().clean()
        # Convert dates to date objects if they're strings
        if isinstance(self.bill_date, str):
            try:
                self.bill_date = datetime.strptime(self.bill_date, '%Y-%m-%d').date()
            except (ValueError, TypeError):
                try:
                    self.bill_date = datetime.strptime(self.bill_date, '%Y/%m/%d').date()
                except (ValueError, TypeError):
                    self.bill_date = timezone.now().date()
        
        if isinstance(self.due_date, str):
            try:
                self.due_date = datetime.strptime(self.due_date, '%Y-%m-%d').date()
            except (ValueError, TypeError):
                try:
                    self.due_date = datetime.strptime(self.due_date, '%Y/%m/%d').date()
                except (ValueError, TypeError):
                    # Default to bill_date + 30 days
                    if isinstance(self.bill_date, date):
                        self.due_date = self.bill_date + timedelta(days=30)
                    else:
                        self.due_date = timezone.now().date() + timedelta(days=30)
    
    def _ensure_date_object(self, date_value, default_date=None):
        """Helper method to ensure a value is a date object"""
        if date_value is None:
            return default_date or timezone.now().date()
        
        if isinstance(date_value, date):
            return date_value
        
        if isinstance(date_value, (datetime, timezone.datetime)):
            return date_value.date() if hasattr(date_value, 'date') else date_value
        
        if isinstance(date_value, str):
            try:
                return datetime.strptime(date_value, '%Y-%m-%d').date()
            except (ValueError, TypeError):
                try:
                    return datetime.strptime(date_value, '%Y/%m/%d').date()
                except (ValueError, TypeError):
                    return default_date or timezone.now().date()
        
        # Last resort
        return default_date or timezone.now().date()
    
    def save(self, *args, **kwargs):
        """Auto-calculate balance_due and overdue status"""
        # CRITICAL: Call full_clean() first to ensure dates are converted via clean()
        try:
            self.full_clean()
        except:
            # If full_clean() fails, at least try clean()
            try:
                self.clean()
            except:
                pass  # If clean() also fails, we'll handle conversion below
        
        # CRITICAL: Convert dates FIRST, before any operations
        # Force conversion - don't trust anything
        if not isinstance(self.bill_date, date):
            self.bill_date = self._ensure_date_object(self.bill_date, timezone.now().date())
        
        if not isinstance(self.due_date, date):
            default_due = (self.bill_date + timedelta(days=30)) if isinstance(self.bill_date, date) else (timezone.now().date() + timedelta(days=30))
            self.due_date = self._ensure_date_object(self.due_date, default_due)
        
        # Triple-check: ensure both are date objects after conversion
        if not isinstance(self.bill_date, date):
            self.bill_date = timezone.now().date()
        if not isinstance(self.due_date, date):
            self.due_date = self.bill_date + timedelta(days=30) if isinstance(self.bill_date, date) else timezone.now().date() + timedelta(days=30)
        
        # Ensure amount and amount_paid are Decimal
        from decimal import Decimal
        if not isinstance(self.amount, Decimal):
            try:
                self.amount = Decimal(str(self.amount))
            except (ValueError, TypeError):
                self.amount = Decimal('0.00')
        
        if not isinstance(self.amount_paid, Decimal):
            try:
                self.amount_paid = Decimal(str(self.amount_paid))
            except (ValueError, TypeError):
                self.amount_paid = Decimal('0.00')
        
        # Calculate balance
        self.balance_due = self.amount - self.amount_paid
        
        # Calculate overdue status - dates are now guaranteed to be date objects
        today = timezone.now().date()
        
        # Final safety check: ensure both dates are date objects
        if not isinstance(self.due_date, date):
            default_due_date = (self.bill_date + timedelta(days=30)) if isinstance(self.bill_date, date) else (timezone.now().date() + timedelta(days=30))
            self.due_date = self._ensure_date_object(self.due_date, default_due_date)
        
        if not isinstance(self.bill_date, date):
            self.bill_date = self._ensure_date_object(self.bill_date, timezone.now().date())
        
        # Calculate overdue status using a completely safe comparison function
        def safe_date_compare(date1, date2):
            """Safely compare two dates, converting strings to dates if needed"""
            try:
                # Convert both to date objects
                d1 = self._ensure_date_object(date1, timezone.now().date())
                d2 = self._ensure_date_object(date2, timezone.now().date())
                
                # Final check
                if not isinstance(d1, date):
                    d1 = timezone.now().date()
                if not isinstance(d2, date):
                    d2 = timezone.now().date()
                
                # Now safe to compare
                return d1 < d2, d1, d2
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Safe date compare failed: {e}, date1: {repr(date1)}, date2: {repr(date2)}")
                # Return False and today's date for both
                today = timezone.now().date()
                return False, today, today
        
        # Use safe comparison
        try:
            is_past_due, due_date_obj, today_obj = safe_date_compare(self.due_date, timezone.now().date())
            
            # Update instance with converted date
            self.due_date = due_date_obj
            
            if is_past_due and self.balance_due > 0:
                self.is_overdue = True
                self.days_overdue = (today_obj - due_date_obj).days
            else:
                self.is_overdue = False
                self.days_overdue = 0
                
        except Exception as e:
            # Last resort - just set defaults
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Date comparison completely failed: {e}. due_date: {repr(self.due_date)}, type: {type(self.due_date)}")
            self.is_overdue = False
            self.days_overdue = 0
        
        super().save(*args, **kwargs)
    
    def add_amount(self, new_amount, description=''):
        """
        Add a new amount to existing AP (when goods are brought in)
        Auto-calculates the new balance
        
        Args:
            new_amount: Decimal - The new amount to add
            description: str - Optional description for the addition
        
        Returns:
            The updated AP instance
        """
        from decimal import Decimal
        
        if not isinstance(new_amount, Decimal):
            new_amount = Decimal(str(new_amount))
        
        # Add to existing amount
        self.amount += new_amount
        
        # Recalculate balance (balance = amount - amount_paid)
        self.balance_due = self.amount - self.amount_paid
        
        # Update description if provided
        if description:
            if self.description:
                self.description += f"\n[Added: {timezone.now().strftime('%Y-%m-%d')}] {description} - GHS {new_amount:,.2f}"
            else:
                self.description = f"[Added: {timezone.now().strftime('%Y-%m-%d')}] {description} - GHS {new_amount:,.2f}"
        
        # Save will auto-calculate overdue status
        self.save()
        
        return self
    
    def validate_3_way_match(self):
        """
        Validate 3-way matching: PO, Invoice, GRN amounts must match
        Returns (is_valid, error_message)
        """
        if not self.invoice_amount or not self.grn_amount:
            return False, "Invoice amount and GRN amount must be set for 3-way matching"
        
        if abs(self.invoice_amount - self.grn_amount) > Decimal('0.01'):  # Allow small rounding differences
            return False, f"Invoice amount (GHS {self.invoice_amount}) does not match GRN amount (GHS {self.grn_amount})"
        
        if abs(self.invoice_amount - self.amount) > Decimal('0.01'):
            return False, f"Invoice amount (GHS {self.invoice_amount}) does not match AP amount (GHS {self.amount})"
        
        self.is_matched = True
        self.save(update_fields=['is_matched'])
        return True, "3-way matching validated successfully"


# ==================== BANK & CASH MANAGEMENT ====================

class BankAccount(BaseModel):
    """Bank Accounts"""
    ACCOUNT_TYPE_CHOICES = [
        ('checking', 'Checking / Current'),
        ('savings', 'Savings'),
        ('credit', 'Credit'),
        ('operating', 'Operating'),
        ('other', 'Other'),
    ]
    account_name = models.CharField(max_length=200)
    account_number = models.CharField(max_length=50, unique=True)
    bank_name = models.CharField(max_length=200)
    branch = models.CharField(max_length=200, blank=True)
    
    account_type = models.CharField(
        max_length=50,
        choices=ACCOUNT_TYPE_CHOICES,
        default='checking',
    )
    currency = models.CharField(max_length=3, default='GHS')
    
    opening_balance = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    current_balance = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # Link to chart of accounts
    gl_account = models.ForeignKey(Account, on_delete=models.PROTECT)
    
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['bank_name', 'account_name']
    
    def get_account_type_display_safe(self):
        """Return display label for account_type; use 'Checking / Current' for invalid/unknown values."""
        valid_values = [c[0] for c in self.ACCOUNT_TYPE_CHOICES]
        if self.account_type and self.account_type.lower() in [v.lower() for v in valid_values]:
            return self.get_account_type_display()
        return 'Checking / Current'
    
    def __str__(self):
        return f"{self.bank_name} - {self.account_number}"


class BankTransaction(BaseModel):
    """Bank Transactions for reconciliation"""
    TRANSACTION_TYPES = [
        ('deposit', 'Deposit'),
        ('withdrawal', 'Withdrawal'),
        ('transfer', 'Transfer'),
        ('fee', 'Bank Fee'),
        ('interest', 'Interest'),
    ]
    
    bank_account = models.ForeignKey(BankAccount, on_delete=models.CASCADE, related_name='transactions')
    transaction_date = models.DateField()
    
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    
    description = models.CharField(max_length=500)
    reference = models.CharField(max_length=100, blank=True)
    
    # Reconciliation
    is_reconciled = models.BooleanField(default=False)
    reconciled_date = models.DateField(null=True, blank=True)
    journal_entry = models.ForeignKey(AdvancedJournalEntry, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        ordering = ['-transaction_date']
    
    def __str__(self):
        return f"{self.bank_account.account_name} - {self.transaction_date} - GHS {self.amount}"


# ==================== BUDGETING ====================

class Budget(BaseModel):
    """Annual/Monthly Budgets"""
    name = models.CharField(max_length=200)
    fiscal_year = models.ForeignKey(FiscalYear, on_delete=models.CASCADE)
    accounting_period = models.ForeignKey(AccountingPeriod, on_delete=models.CASCADE, null=True, blank=True)
    
    start_date = models.DateField()
    end_date = models.DateField()
    
    description = models.TextField(blank=True)
    
    total_revenue_budget = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_expense_budget = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    is_approved = models.BooleanField(default=False)
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        ordering = ['-start_date']
    
    def __str__(self):
        return f"{self.name} - {self.fiscal_year}"


class BudgetLine(BaseModel):
    """Budget Line Items"""
    budget = models.ForeignKey(Budget, on_delete=models.CASCADE, related_name='lines')
    account = models.ForeignKey(Account, on_delete=models.PROTECT)
    cost_center = models.ForeignKey(CostCenter, on_delete=models.SET_NULL, null=True, blank=True)
    
    budgeted_amount = models.DecimalField(max_digits=15, decimal_places=2)
    actual_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    variance = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    variance_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['budget', 'account']
    
    def __str__(self):
        return f"{self.budget.name} - {self.account.account_code}"
    
    def calculate_variance(self):
        """Calculate budget variance"""
        self.variance = self.actual_amount - self.budgeted_amount
        if self.budgeted_amount != 0:
            self.variance_percent = (self.variance / self.budgeted_amount) * 100
        else:
            self.variance_percent = 0
        self.save()


# ==================== TAX MANAGEMENT ====================

class TaxRate(BaseModel):
    """Tax Rates and Types"""
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=200)
    rate = models.DecimalField(max_digits=5, decimal_places=2, help_text="Tax rate as percentage (e.g., 12.5 for 12.5%)")
    
    account = models.ForeignKey(Account, on_delete=models.PROTECT, help_text="Tax liability account")
    
    is_active = models.BooleanField(default=True)
    effective_date = models.DateField(default=timezone.now)
    
    class Meta:
        ordering = ['code']
    
    def __str__(self):
        return f"{self.code} - {self.name} ({self.rate}%)"


# ==================== AUDIT TRAIL ====================

class AccountingAuditLog(BaseModel):
    """Audit trail for all accounting transactions"""
    ACTION_TYPES = [
        ('create', 'Created'),
        ('update', 'Updated'),
        ('delete', 'Deleted'),
        ('post', 'Posted'),
        ('void', 'Voided'),
        ('approve', 'Approved'),
        ('reject', 'Rejected'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=20, choices=ACTION_TYPES)
    timestamp = models.DateTimeField(default=timezone.now)
    
    # What was changed
    model_name = models.CharField(max_length=100)
    object_id = models.CharField(max_length=100)
    object_repr = models.CharField(max_length=500)
    
    # Change details
    changes = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['model_name', 'object_id']),
            models.Index(fields=['user', 'timestamp']),
        ]
    
    def __str__(self):
        return f"{self.user} - {self.action} - {self.model_name} - {self.timestamp}"


# ==================== CASHBOOK ====================

class Cashbook(BaseModel):
    """Cashbook - Receipts and Payments held until next day before revenue classification"""
    ENTRY_TYPES = [
        ('receipt', 'Receipt'),
        ('payment', 'Payment'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending (Held)'),
        ('classified', 'Classified to Revenue'),
        ('void', 'Void'),
    ]
    
    entry_number = models.CharField(max_length=50, unique=True)
    entry_type = models.CharField(max_length=20, choices=ENTRY_TYPES)
    entry_date = models.DateField(default=timezone.now)
    
    # Amounts
    amount = models.DecimalField(max_digits=15, decimal_places=2, validators=[MinValueValidator(0)])
    
    # Payment/Receipt details
    payee_or_payer = models.CharField(max_length=200, help_text="Name of person/entity receiving or making payment")
    description = models.TextField()
    reference = models.CharField(max_length=100, blank=True)
    
    # Payment method
    payment_method = models.CharField(max_length=50, choices=PaymentVoucher.PAYMENT_METHODS, default='cash')
    cheque = models.ForeignKey(Cheque, on_delete=models.SET_NULL, null=True, blank=True, related_name='cashbook_entries')
    
    # Links
    patient = models.ForeignKey(Patient, on_delete=models.SET_NULL, null=True, blank=True)
    invoice = models.ForeignKey(Invoice, on_delete=models.SET_NULL, null=True, blank=True)
    journal_entry = models.ForeignKey(AdvancedJournalEntry, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Account classification (set after next day)
    revenue_account = models.ForeignKey(Account, on_delete=models.SET_NULL, null=True, blank=True, related_name='cashbook_revenues')
    expense_account = models.ForeignKey(Account, on_delete=models.SET_NULL, null=True, blank=True, related_name='cashbook_expenses')
    cash_account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name='cashbook_entries')
    
    # Status and timing
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    held_until = models.DateField(null=True, blank=True, help_text="Date when entry can be classified to revenue (next day after entry date)")
    classified_at = models.DateTimeField(null=True, blank=True)
    classified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='cashbook_classified')
    
    # User tracking
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='cashbook_entries_created')
    
    class Meta:
        ordering = ['-entry_date', '-entry_number']
        indexes = [
            models.Index(fields=['entry_date', 'status']),
            models.Index(fields=['held_until', 'status']),
        ]
    
    def __str__(self):
        return f"{self.entry_number} - {self.get_entry_type_display()} - GHS {self.amount}"
    
    def save(self, *args, **kwargs):
        if not self.entry_number:
            self.entry_number = self.generate_entry_number()
        
        # Set held_until to next calendar day if not set
        if not self.held_until and self.status == 'pending':
            from datetime import timedelta
            # Set to next day (entry_date + 1 day)
            if self.entry_date:
                self.held_until = self.entry_date + timedelta(days=1)
            else:
                # If entry_date not set, use today + 1 day
                self.held_until = timezone.now().date() + timedelta(days=1)
        
        super().save(*args, **kwargs)
    
    @staticmethod
    def generate_entry_number():
        """Generate unique cashbook entry number"""
        today = timezone.now()
        prefix = f"CB{today.strftime('%Y%m')}"
        
        last_entry = Cashbook.objects.filter(
            entry_number__startswith=prefix
        ).order_by('-entry_number').first()
        
        if last_entry:
            try:
                last_num = int(last_entry.entry_number[-6:])
                new_num = last_num + 1
            except ValueError:
                new_num = 1
        else:
            new_num = 1
        
        return f"{prefix}{new_num:06d}"
    
    def can_classify(self):
        """Check if entry can be classified to revenue (next day has arrived)"""
        if not self.held_until:
            return False
        today = timezone.now().date()
        return today >= self.held_until and self.status == 'pending'
    
    def classify_to_revenue(self, user, revenue_account=None, expense_account=None):
        """Classify cashbook entry to revenue/expense accounts after next day"""
        if not self.can_classify():
            today = timezone.now().date()
            raise ValueError(f"Entry cannot be classified yet. Can be classified from {self.held_until}. Today is {today}.")
        
        if self.status != 'pending':
            raise ValueError("Only pending entries can be classified")
        
        with transaction.atomic():
            # Create journal entry
            je = AdvancedJournalEntry.objects.create(
                journal=Journal.objects.get_or_create(journal_type='cash', defaults={'code': 'CASH', 'name': 'Cash Journal'})[0],
                entry_date=timezone.now().date(),
                description=f"Cashbook classification: {self.description}",
                reference=self.entry_number,
                created_by=user,
            )
            
            if self.entry_type == 'receipt':
                # Receipt: Debit Cash, Credit Revenue
                account_to_credit = revenue_account or self.revenue_account
                if not account_to_credit:
                    raise ValueError("Revenue account must be specified for receipts")
                
                AdvancedJournalEntryLine.objects.create(
                    journal_entry=je,
                    line_number=1,
                    account=self.cash_account,
                    description=f"Cash receipt: {self.description}",
                    debit_amount=self.amount,
                    credit_amount=0,
                )
                
                AdvancedJournalEntryLine.objects.create(
                    journal_entry=je,
                    line_number=2,
                    account=account_to_credit,
                    description=f"Revenue: {self.description}",
                    debit_amount=0,
                    credit_amount=self.amount,
                )
                
                self.revenue_account = account_to_credit
                
            else:  # payment
                # Payment: Debit Expense, Credit Cash
                account_to_debit = expense_account or self.expense_account
                if not account_to_debit:
                    raise ValueError("Expense account must be specified for payments")
                
                AdvancedJournalEntryLine.objects.create(
                    journal_entry=je,
                    line_number=1,
                    account=account_to_debit,
                    description=f"Expense: {self.description}",
                    debit_amount=self.amount,
                    credit_amount=0,
                )
                
                AdvancedJournalEntryLine.objects.create(
                    journal_entry=je,
                    line_number=2,
                    account=self.cash_account,
                    description=f"Cash payment: {self.description}",
                    debit_amount=0,
                    credit_amount=self.amount,
                )
                
                self.expense_account = account_to_debit
            
            # Update totals and post
            je.total_debit = self.amount
            je.total_credit = self.amount
            je.save()
            je.post(user)
            
            # Update cashbook entry
            self.status = 'classified'
            self.classified_at = timezone.now()
            self.classified_by = user
            self.journal_entry = je
            self.save()


# ==================== BANK RECONCILIATION ====================

class BankReconciliation(BaseModel):
    """Bank Reconciliation - Match bank statements with accounting records"""
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('reconciled', 'Fully Reconciled'),
    ]
    
    reconciliation_number = models.CharField(max_length=50, unique=True)
    bank_account = models.ForeignKey(BankAccount, on_delete=models.PROTECT, related_name='reconciliations')
    
    statement_date = models.DateField(help_text="Date of bank statement")
    statement_balance = models.DecimalField(max_digits=15, decimal_places=2, help_text="Ending balance per bank statement")
    
    book_balance = models.DecimalField(max_digits=15, decimal_places=2, help_text="Ending balance per books")
    
    # Reconciliation items
    deposits_in_transit = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    outstanding_cheques = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    bank_charges = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    interest_earned = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    other_adjustments = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    adjusted_balance = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    difference = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    
    reconciled_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    reconciled_at = models.DateTimeField(null=True, blank=True)
    
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-statement_date', '-reconciliation_number']
    
    def __str__(self):
        return f"{self.reconciliation_number} - {self.bank_account.account_name} - {self.statement_date}"
    
    def save(self, *args, **kwargs):
        if not self.reconciliation_number:
            self.reconciliation_number = self.generate_reconciliation_number()
        
        # Calculate adjusted balance
        self.adjusted_balance = (
            self.book_balance
            + self.deposits_in_transit
            - self.outstanding_cheques
            - self.bank_charges
            + self.interest_earned
            + self.other_adjustments
        )
        
        # Calculate difference
        self.difference = self.statement_balance - self.adjusted_balance
        
        super().save(*args, **kwargs)
    
    @staticmethod
    def generate_reconciliation_number():
        """Generate unique reconciliation number"""
        today = timezone.now()
        prefix = f"BR{today.strftime('%Y%m')}"
        
        last_recon = BankReconciliation.objects.filter(
            reconciliation_number__startswith=prefix
        ).order_by('-reconciliation_number').first()
        
        if last_recon:
            try:
                last_num = int(last_recon.reconciliation_number[-6:])
                new_num = last_num + 1
            except ValueError:
                new_num = 1
        else:
            new_num = 1
        
        return f"{prefix}{new_num:06d}"
    
    def reconcile(self, user):
        """Mark reconciliation as completed"""
        if abs(self.difference) > 0.01:
            raise ValueError(f"Reconciliation is not balanced. Difference: GHS {self.difference}")
        
        self.status = 'reconciled'
        self.reconciled_by = user
        self.reconciled_at = timezone.now()
        self.save()
        
        # Mark all matched transactions as reconciled
        BankTransaction.objects.filter(
            bank_account=self.bank_account,
            transaction_date__lte=self.statement_date,
            is_reconciled=False
        ).update(
            is_reconciled=True,
            reconciled_date=self.statement_date
        )


class BankReconciliationItem(BaseModel):
    """Individual items in bank reconciliation"""
    reconciliation = models.ForeignKey(BankReconciliation, on_delete=models.CASCADE, related_name='items')
    
    transaction = models.ForeignKey(BankTransaction, on_delete=models.CASCADE, null=True, blank=True)
    journal_entry = models.ForeignKey(AdvancedJournalEntry, on_delete=models.CASCADE, null=True, blank=True)
    cheque = models.ForeignKey(Cheque, on_delete=models.CASCADE, null=True, blank=True)
    
    description = models.CharField(max_length=500)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    is_matched = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['reconciliation', 'created']


# ==================== INSURANCE RECEIVABLE ====================

class InsuranceReceivable(BaseModel):
    """Insurance Receivable - Track amounts due from insurance companies"""
    STATUS_CHOICES = [
        ('pending', 'Pending Submission'),
        ('submitted', 'Submitted to Insurance'),
        ('approved', 'Approved by Insurance'),
        ('paid', 'Paid'),
        ('rejected', 'Rejected'),
        ('partial', 'Partially Paid'),
    ]
    
    receivable_number = models.CharField(max_length=50, unique=True)
    insurance_company = models.ForeignKey('Payer', on_delete=models.PROTECT, related_name='receivables', limit_choices_to={'payer_type': 'insurance'})
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='insurance_receivables')
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='insurance_receivables')
    
    claim_number = models.CharField(max_length=100, blank=True, help_text="Insurance claim number")
    claim_date = models.DateField(default=timezone.now)
    
    total_amount = models.DecimalField(max_digits=15, decimal_places=2)
    amount_paid = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    balance_due = models.DecimalField(max_digits=15, decimal_places=2)
    
    due_date = models.DateField()
    payment_date = models.DateField(null=True, blank=True)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Tracking
    submitted_date = models.DateField(null=True, blank=True)
    approved_date = models.DateField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    
    # Accounting
    receivable_account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name='insurance_receivables')
    journal_entry = models.ForeignKey(AdvancedJournalEntry, on_delete=models.SET_NULL, null=True, blank=True)
    
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-claim_date', '-receivable_number']
        indexes = [
            models.Index(fields=['insurance_company', 'status']),
            models.Index(fields=['due_date', 'status']),
        ]
    
    def __str__(self):
        return f"{self.receivable_number} - {self.insurance_company.name} - GHS {self.balance_due}"
    
    def save(self, *args, **kwargs):
        if not self.receivable_number:
            self.receivable_number = self.generate_receivable_number()
        
        # Calculate balance
        self.balance_due = self.total_amount - self.amount_paid
        
        # Update status based on payment
        if self.amount_paid >= self.total_amount:
            self.status = 'paid'
        elif self.amount_paid > 0:
            self.status = 'partial'
        
        super().save(*args, **kwargs)
    
    @staticmethod
    def generate_receivable_number():
        """Generate unique insurance receivable number"""
        today = timezone.now()
        prefix = f"IR{today.strftime('%Y%m')}"
        
        last_rec = InsuranceReceivable.objects.filter(
            receivable_number__startswith=prefix
        ).order_by('-receivable_number').first()
        
        if last_rec:
            try:
                last_num = int(last_rec.receivable_number[-6:])
                new_num = last_num + 1
            except ValueError:
                new_num = 1
        else:
            new_num = 1
        
        return f"{prefix}{new_num:06d}"


# ==================== PROCUREMENT ACCOUNTING ====================

class ProcurementPurchase(BaseModel):
    """Procurement Purchases - Cash and Credit with Accounts Payable integration"""
    PURCHASE_TYPES = [
        ('cash', 'Cash Purchase'),
        ('credit', 'Credit Purchase'),
    ]
    
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('approved', 'Approved'),
        ('received', 'Goods Received'),
        ('paid', 'Paid'),
        ('cancelled', 'Cancelled'),
    ]
    
    purchase_number = models.CharField(max_length=50, unique=True)
    purchase_type = models.CharField(max_length=20, choices=PURCHASE_TYPES)
    purchase_date = models.DateField(default=timezone.now)
    
    supplier_name = models.CharField(max_length=200)
    supplier_invoice = models.CharField(max_length=100, blank=True)
    
    total_amount = models.DecimalField(max_digits=15, decimal_places=2)
    tax_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    net_amount = models.DecimalField(max_digits=15, decimal_places=2)
    
    description = models.TextField()
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    
    # For credit purchases - link to Accounts Payable
    accounts_payable = models.ForeignKey(AccountsPayable, on_delete=models.SET_NULL, null=True, blank=True, related_name='procurement_purchases')
    
    # Accounting
    expense_account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name='procurement_purchases')
    liability_account = models.ForeignKey(Account, on_delete=models.PROTECT, null=True, blank=True, related_name='procurement_liabilities', help_text="Accounts Payable account for credit purchases")
    payment_account = models.ForeignKey(Account, on_delete=models.PROTECT, null=True, blank=True, related_name='procurement_payments', help_text="Cash/Bank account for cash purchases")
    journal_entry = models.ForeignKey(AdvancedJournalEntry, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Classification
    classification = models.CharField(max_length=100, blank=True, help_text="Purchase classification/category")
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='procurement_approved')
    
    class Meta:
        ordering = ['-purchase_date', '-purchase_number']
    
    def __str__(self):
        return f"{self.purchase_number} - {self.supplier_name} - GHS {self.total_amount}"
    
    def save(self, *args, **kwargs):
        if not self.purchase_number:
            self.purchase_number = self.generate_purchase_number()
        
        # Calculate net amount
        self.net_amount = self.total_amount - self.tax_amount
        
        super().save(*args, **kwargs)
    
    @staticmethod
    def generate_purchase_number():
        """Generate unique purchase number"""
        today = timezone.now()
        prefix = f"PR{today.strftime('%Y%m')}"
        
        last_purchase = ProcurementPurchase.objects.filter(
            purchase_number__startswith=prefix
        ).order_by('-purchase_number').first()
        
        if last_purchase:
            try:
                last_num = int(last_purchase.purchase_number[-6:])
                new_num = last_num + 1
            except ValueError:
                new_num = 1
        else:
            new_num = 1
        
        return f"{prefix}{new_num:06d}"
    
    def process_purchase(self, user):
        """Process purchase and create accounting entries"""
        if self.status != 'approved':
            raise ValueError("Only approved purchases can be processed")
        
        with transaction.atomic():
            # Create journal entry
            je = AdvancedJournalEntry.objects.create(
                journal=Journal.objects.get_or_create(journal_type='purchase', defaults={'code': 'PUR', 'name': 'Purchase Journal'})[0],
                entry_date=self.purchase_date,
                description=f"Procurement: {self.description}",
                reference=self.purchase_number,
                created_by=user,
            )
            
            if self.purchase_type == 'cash':
                # Cash Purchase: Debit Expense, Credit Cash/Bank
                AdvancedJournalEntryLine.objects.create(
                    journal_entry=je,
                    line_number=1,
                    account=self.expense_account,
                    description=self.description,
                    debit_amount=self.net_amount,
                    credit_amount=0,
                )
                
                AdvancedJournalEntryLine.objects.create(
                    journal_entry=je,
                    line_number=2,
                    account=self.payment_account,
                    description=f"Payment: {self.description}",
                    debit_amount=0,
                    credit_amount=self.net_amount,
                )
                
            else:  # credit
                # Credit Purchase: Debit Expense, Credit Accounts Payable (Liability)
                if not self.liability_account:
                    raise ValueError("Liability account must be set for credit purchases")
                
                AdvancedJournalEntryLine.objects.create(
                    journal_entry=je,
                    line_number=1,
                    account=self.expense_account,
                    description=self.description,
                    debit_amount=self.net_amount,
                    credit_amount=0,
                )
                
                AdvancedJournalEntryLine.objects.create(
                    journal_entry=je,
                    line_number=2,
                    account=self.liability_account,
                    description=f"Accounts Payable: {self.description}",
                    debit_amount=0,
                    credit_amount=self.net_amount,
                )
                
                # Create Accounts Payable entry
                ap = AccountsPayable.objects.create(
                    bill_number=f"AP{self.purchase_number}",
                    vendor_name=self.supplier_name,
                    vendor_invoice=self.supplier_invoice,
                    bill_date=self.purchase_date,
                    due_date=self.purchase_date + timedelta(days=30),  # Default 30 days
                    amount=self.net_amount,
                    amount_paid=0,
                    balance_due=self.net_amount,
                    description=self.description,
                    journal_entry=je,
                )
                
                self.accounts_payable = ap
            
            # Update totals and post
            je.total_debit = self.net_amount
            je.total_credit = self.net_amount
            je.save()
            je.post(user)
            
            self.journal_entry = je
            self.status = 'paid' if self.purchase_type == 'cash' else 'received'
            self.save()


# ==================== PAYROLL & COMMISSIONS ====================

class AccountingPayroll(BaseModel):
    """Accounting Payroll Management"""
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('calculated', 'Calculated'),
        ('pending_approval', 'Pending administrator approval'),
        ('approved', 'Approved'),
        ('paid', 'Paid'),
    ]
    
    payroll_number = models.CharField(max_length=50, unique=True)
    payroll_period_start = models.DateField()
    payroll_period_end = models.DateField()
    pay_date = models.DateField()
    period_label = models.CharField(
        max_length=120, blank=True,
        help_text='Optional label shown in UI (e.g. January 2026 — Salary RMC)'
    )
    import_source_filename = models.CharField(max_length=255, blank=True)
    
    deduction_apply_percentages = models.BooleanField(
        default=False,
        help_text=(
            'When on, each staff line SSF (employee), PF (employee), PAYE, and optional other deduction '
            'are computed from the rates below whenever a line is saved or Excel is imported.'
        ),
    )
    deduction_ssnit_employee_pct = models.DecimalField(
        max_digits=6, decimal_places=2, default=Decimal('5.5'),
        help_text='SSF employee: % of basic salary (falls back to gross earnings if basic is zero).',
    )
    deduction_pension_employee_pct = models.DecimalField(
        max_digits=6, decimal_places=2, default=Decimal('5.0'),
        help_text='Provident fund (employee): % of basic salary (falls back to gross earnings if basic is zero).',
    )
    deduction_paye_pct = models.DecimalField(
        max_digits=6, decimal_places=2, default=Decimal('0'),
        help_text=(
            'Flat % for PAYE when Taxable income is set; if that is zero, estimated on '
            '(gross earnings - personal relief). Set 0 to enter PAYE manually.'
        ),
    )
    deduction_other_deduction_pct = models.DecimalField(
        max_digits=6, decimal_places=2, default=Decimal('0'),
        help_text='Optional extra deduction as % of gross earnings (maps to other deductions).',
    )
    
    total_gross_pay = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_deductions = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_net_pay = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='accounting_payrolls_created')
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='accounting_payrolls_approved')
    
    class Meta:
        ordering = ['-payroll_period_end', '-payroll_number']
    
    def __str__(self):
        return f"{self.payroll_number} - {self.payroll_period_start} to {self.payroll_period_end}"
    
    def save(self, *args, **kwargs):
        if not self.payroll_number:
            self.payroll_number = self.generate_payroll_number()
        
        self.total_net_pay = self.total_gross_pay - self.total_deductions
        super().save(*args, **kwargs)
    
    def recalculate_totals_from_entries(self):
        """Roll up line totals from active payroll entries."""
        from django.db.models import Sum
        agg = self.entries.filter(is_deleted=False).aggregate(
            g=Sum('gross_pay'),
            d=Sum('deductions'),
            n=Sum('net_pay'),
        )
        self.total_gross_pay = agg['g'] or Decimal('0')
        self.total_deductions = agg['d'] or Decimal('0')
        self.total_net_pay = agg['n'] or Decimal('0')
        self.save(update_fields=['total_gross_pay', 'total_deductions', 'total_net_pay', 'modified'])
    
    def apply_percentage_deductions_to_all_entries(self):
        """Recompute SSF/PF/PAYE/other on every line from this run’s percentage settings."""
        if not self.deduction_apply_percentages:
            return
        for entry in self.entries.filter(is_deleted=False):
            entry.save()
        self.recalculate_totals_from_entries()
    
    @staticmethod
    def generate_payroll_number():
        """Generate unique payroll number"""
        today = timezone.now()
        prefix = f"PY{today.strftime('%Y%m')}"
        
        last_payroll = AccountingPayroll.objects.filter(
            payroll_number__startswith=prefix
        ).order_by('-payroll_number').first()
        
        if last_payroll:
            try:
                last_num = int(last_payroll.payroll_number[-6:])
                new_num = last_num + 1
            except ValueError:
                new_num = 1
        else:
            new_num = 1
        
        return f"{prefix}{new_num:06d}"


class AccountingPayrollEntry(BaseModel):
    """Individual accounting payroll entries for staff"""
    payroll = models.ForeignKey(AccountingPayroll, on_delete=models.CASCADE, related_name='entries')
    staff = models.ForeignKey('Staff', on_delete=models.CASCADE, related_name='payroll_entries')
    
    # RMC-style salary sheet breakdown (matches Sample Salary-RMC.xlsx — Raphal Medical Centre)
    basic_salary = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    housing_allowance = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    transport_allowance = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    other_allowances = models.DecimalField(
        max_digits=15, decimal_places=2, default=0,
        help_text='Other allowance / overtime (RMC column)',
    )
    overtime_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    bonus_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    medical_allowance = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    risk_emergency_allowance = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    paye_tax = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    ssnit_employee = models.DecimalField(
        max_digits=15, decimal_places=2, default=0,
        help_text='5.5% SSF employee contribution',
    )
    pension_employee = models.DecimalField(
        max_digits=15, decimal_places=2, default=0,
        help_text='5.0% PF employee',
    )
    pf_employer_contribution = models.DecimalField(
        max_digits=15, decimal_places=2, default=0,
        help_text='5.0% PF employer (informational)',
    )
    ssf_employer_contribution = models.DecimalField(
        max_digits=15, decimal_places=2, default=0,
        help_text='13% SSF employer (informational)',
    )
    personal_relief = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_relief = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    taxable_income = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    loan_deduction = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    other_deductions_detail = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    sheet_serial = models.PositiveIntegerField(null=True, blank=True)
    department_snapshot = models.CharField(max_length=200, blank=True)
    rank_snapshot = models.CharField(max_length=120, blank=True)
    service_length_snapshot = models.CharField(max_length=80, blank=True)
    
    gross_pay = models.DecimalField(max_digits=15, decimal_places=2)
    deductions = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    net_pay = models.DecimalField(max_digits=15, decimal_places=2)
    
    # Commission splits (for doctors)
    consultation_commission = models.DecimalField(max_digits=15, decimal_places=2, default=0, help_text="30% of consultation fees")
    surgery_commission = models.DecimalField(max_digits=15, decimal_places=2, default=0, help_text="30% of surgery fees")
    operational_share = models.DecimalField(max_digits=15, decimal_places=2, default=0, help_text="10% for operational items")
    hospital_share = models.DecimalField(max_digits=15, decimal_places=2, default=0, help_text="Remaining share to hospital")
    
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['payroll', 'staff']
        unique_together = ['payroll', 'staff']
    
    def __str__(self):
        return f"{self.payroll.payroll_number} - {self.staff.user.get_full_name()} - GHS {self.net_pay}"
    
    def save(self, *args, **kwargs):
        """Derive gross/deductions/net from RMC breakdown when any breakdown field is used."""
        D = Decimal
        earn = (
            self.basic_salary + self.housing_allowance + self.transport_allowance
            + self.other_allowances + self.overtime_amount + self.bonus_amount
            + self.medical_allowance + self.risk_emergency_allowance
        )
        payroll = None
        if self.payroll_id:
            payroll = self.payroll
        if (
            payroll
            and getattr(payroll, 'deduction_apply_percentages', False)
            and earn > D('0')
        ):
            base_staff = self.basic_salary if self.basic_salary > D('0') else earn
            q = lambda x: (x).quantize(D('0.01'), rounding=ROUND_HALF_UP)
            if payroll.deduction_ssnit_employee_pct > D('0'):
                self.ssnit_employee = q(base_staff * payroll.deduction_ssnit_employee_pct / D('100'))
            if payroll.deduction_pension_employee_pct > D('0'):
                self.pension_employee = q(base_staff * payroll.deduction_pension_employee_pct / D('100'))
            if payroll.deduction_paye_pct > D('0'):
                if self.taxable_income > D('0'):
                    self.paye_tax = q(self.taxable_income * payroll.deduction_paye_pct / D('100'))
                else:
                    taxable_est = earn - self.personal_relief
                    if taxable_est > D('0'):
                        self.paye_tax = q(taxable_est * payroll.deduction_paye_pct / D('100'))
                    else:
                        self.paye_tax = D('0')
            if payroll.deduction_other_deduction_pct > D('0'):
                self.other_deductions_detail = q(earn * payroll.deduction_other_deduction_pct / D('100'))
        ded = (
            self.paye_tax + self.ssnit_employee + self.pension_employee
            + self.loan_deduction + self.other_deductions_detail
        )
        if earn > D('0') or ded > D('0'):
            self.gross_pay = earn
            self.deductions = ded
        self.net_pay = self.gross_pay - self.deductions
        super().save(*args, **kwargs)


class DoctorCommission(BaseModel):
    """Doctor Commission Tracking - 30% to doctor, rest to hospital"""
    commission_number = models.CharField(max_length=50, unique=True)
    doctor = models.ForeignKey('Staff', on_delete=models.CASCADE, related_name='commissions', limit_choices_to={'profession': 'doctor'})
    
    service_type = models.CharField(max_length=50, choices=[
        ('consultation', 'Consultation'),
        ('surgery', 'Surgery'),
        ('procedure', 'Procedure'),
    ])
    
    service_date = models.DateField()
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='doctor_commissions')
    
    total_fee = models.DecimalField(max_digits=15, decimal_places=2)
    doctor_share = models.DecimalField(max_digits=15, decimal_places=2, help_text="30% of total fee")
    operational_share = models.DecimalField(max_digits=15, decimal_places=2, default=0, help_text="10% for operational items")
    hospital_share = models.DecimalField(max_digits=15, decimal_places=2, help_text="Remaining amount to hospital")
    
    is_paid = models.BooleanField(default=False)
    paid_date = models.DateField(null=True, blank=True)
    
    # Accounting
    doctor_receivable_account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name='doctor_commissions')
    hospital_revenue_account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name='hospital_commissions')
    operational_account = models.ForeignKey(Account, on_delete=models.PROTECT, null=True, blank=True, related_name='operational_commissions')
    journal_entry = models.ForeignKey(AdvancedJournalEntry, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        ordering = ['-service_date', '-commission_number']
    
    def __str__(self):
        return f"{self.commission_number} - {self.doctor.user.get_full_name()} - GHS {self.doctor_share}"
    
    def save(self, *args, **kwargs):
        if not self.commission_number:
            self.commission_number = self.generate_commission_number()
        
        # Calculate splits
        if self.service_type == 'surgery':
            # Surgery: 30% doctor, 10% operational, 60% hospital
            self.doctor_share = self.total_fee * Decimal('0.30')
            self.operational_share = self.total_fee * Decimal('0.10')
            self.hospital_share = self.total_fee - self.doctor_share - self.operational_share
        else:
            # Consultation/Procedure: 30% doctor, 10% operational, 60% hospital
            self.doctor_share = self.total_fee * Decimal('0.30')
            self.operational_share = self.total_fee * Decimal('0.10')
            self.hospital_share = self.total_fee - self.doctor_share - self.operational_share
        
        super().save(*args, **kwargs)
    
    @staticmethod
    def generate_commission_number():
        """Generate unique commission number"""
        today = timezone.now()
        prefix = f"DC{today.strftime('%Y%m')}"
        
        last_comm = DoctorCommission.objects.filter(
            commission_number__startswith=prefix
        ).order_by('-commission_number').first()
        
        if last_comm:
            try:
                last_num = int(last_comm.commission_number[-6:])
                new_num = last_num + 1
            except ValueError:
                new_num = 1
        else:
            new_num = 1
        
        return f"{prefix}{new_num:06d}"


# ==================== REVENUE GROUPING & PROFIT ANALYSIS ====================

class IncomeGroup(BaseModel):
    """Income Grouping for revenue classification"""
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name='income_groups')
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['code']
    
    def __str__(self):
        return f"{self.code} - {self.name}"


class ProfitLossReport(BaseModel):
    """Profit and Loss Reports with quarterly/yearly filtering"""
    REPORT_PERIODS = [
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('yearly', 'Yearly'),
    ]
    
    report_number = models.CharField(max_length=50, unique=True)
    report_period = models.CharField(max_length=20, choices=REPORT_PERIODS)
    period_start = models.DateField()
    period_end = models.DateField()
    fiscal_year = models.ForeignKey(FiscalYear, on_delete=models.PROTECT)
    
    # Revenue
    total_revenue = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    revenue_by_category = models.JSONField(default=dict, blank=True)
    
    # Expenses
    total_expenses = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    expenses_by_category = models.JSONField(default=dict, blank=True)
    
    # Profit/Loss
    gross_profit = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    net_profit = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    profit_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0, help_text="Net profit as percentage of revenue")
    
    # Generated
    generated_at = models.DateTimeField(default=timezone.now)
    generated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    class Meta:
        ordering = ['-period_end', '-report_number']
    
    def __str__(self):
        return f"{self.report_number} - {self.period_start} to {self.period_end}"
    
    def save(self, *args, **kwargs):
        if not self.report_number:
            self.report_number = self.generate_report_number()
        
        # Calculate profit
        self.gross_profit = self.total_revenue - self.total_expenses
        self.net_profit = self.gross_profit  # Can be adjusted for taxes
        
        # Calculate profit percentage
        if self.total_revenue > 0:
            self.profit_percentage = (self.net_profit / self.total_revenue) * 100
        else:
            self.profit_percentage = 0
        
        super().save(*args, **kwargs)
    
    @staticmethod
    def generate_report_number():
        """Generate unique report number"""
        today = timezone.now()
        prefix = f"PL{today.strftime('%Y%m')}"
        
        last_report = ProfitLossReport.objects.filter(
            report_number__startswith=prefix
        ).order_by('-report_number').first()
        
        if last_report:
            try:
                last_num = int(last_report.report_number[-6:])
                new_num = last_num + 1
            except ValueError:
                new_num = 1
        else:
            new_num = 1
        
        return f"{prefix}{new_num:06d}"


# ==================== REGISTRATION FEE ====================

class RegistrationFee(BaseModel):
    """Registration Fee Tracking"""
    fee_number = models.CharField(max_length=50, unique=True)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='registration_fees')
    registration_date = models.DateField(default=timezone.now)
    
    fee_amount = models.DecimalField(max_digits=15, decimal_places=2)
    payment_method = models.CharField(max_length=50, choices=PaymentVoucher.PAYMENT_METHODS, default='cash')
    
    # Accounting
    revenue_account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name='registration_fees')
    journal_entry = models.ForeignKey(AdvancedJournalEntry, on_delete=models.SET_NULL, null=True, blank=True)
    
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-registration_date', '-fee_number']
    
    def __str__(self):
        return f"{self.fee_number} - {self.patient.full_name} - GHS {self.fee_amount}"
    
    def save(self, *args, **kwargs):
        if not self.fee_number:
            self.fee_number = self.generate_fee_number()
        super().save(*args, **kwargs)
    
    @staticmethod
    def generate_fee_number():
        """Generate unique registration fee number"""
        today = timezone.now()
        prefix = f"RF{today.strftime('%Y%m')}"
        
        last_fee = RegistrationFee.objects.filter(
            fee_number__startswith=prefix
        ).order_by('-fee_number').first()
        
        if last_fee:
            try:
                last_num = int(last_fee.fee_number[-6:])
                new_num = last_num + 1
            except ValueError:
                new_num = 1
        else:
            new_num = 1
        
        return f"{prefix}{new_num:06d}"


# ==================== CASH SALES & CORPORATE ====================

class CashSale(BaseModel):
    """Cash Sales - Direct cash transactions"""
    sale_number = models.CharField(max_length=50, unique=True)
    sale_date = models.DateField(default=timezone.now)
    
    customer_name = models.CharField(max_length=200)
    description = models.TextField()
    
    total_amount = models.DecimalField(max_digits=15, decimal_places=2)
    payment_method = models.CharField(max_length=50, choices=PaymentVoucher.PAYMENT_METHODS, default='cash')
    
    # Accounting
    revenue_account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name='cash_sales')
    cash_account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name='cash_sale_payments')
    journal_entry = models.ForeignKey(AdvancedJournalEntry, on_delete=models.SET_NULL, null=True, blank=True)
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    class Meta:
        ordering = ['-sale_date', '-sale_number']
    
    def __str__(self):
        return f"{self.sale_number} - {self.customer_name} - GHS {self.total_amount}"
    
    def save(self, *args, **kwargs):
        if not self.sale_number:
            self.sale_number = self.generate_sale_number()
        super().save(*args, **kwargs)
    
    @staticmethod
    def generate_sale_number():
        """Generate unique sale number"""
        today = timezone.now()
        prefix = f"CS{today.strftime('%Y%m')}"
        
        last_sale = CashSale.objects.filter(
            sale_number__startswith=prefix
        ).order_by('-sale_number').first()
        
        if last_sale:
            try:
                last_num = int(last_sale.sale_number[-6:])
                new_num = last_num + 1
            except ValueError:
                new_num = 1
        else:
            new_num = 1
        
        return f"{prefix}{new_num:06d}"


class AccountingCorporateAccount(BaseModel):
    """Accounting Corporate Account Management"""
    account_number = models.CharField(max_length=50, unique=True, db_index=True)
    company_name = models.CharField(max_length=200)
    contact_person = models.CharField(max_length=200, blank=True)
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=20, blank=True)
    
    credit_limit = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    current_balance = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # Accounting
    receivable_account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name='corporate_accounts')
    
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['company_name']
    
    def __str__(self):
        return f"{self.account_number} - {self.company_name}"


# ==================== WITHHOLDING RECEIVABLE ====================

class WithholdingReceivable(BaseModel):
    """Withholding Receivable - Amounts withheld from payments"""
    withholding_number = models.CharField(max_length=50, unique=True)
    withholding_date = models.DateField(default=timezone.now)
    
    payer = models.CharField(max_length=200, help_text="Entity that withheld the amount")
    description = models.TextField()
    
    amount_withheld = models.DecimalField(max_digits=15, decimal_places=2)
    amount_recovered = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    balance = models.DecimalField(max_digits=15, decimal_places=2)
    
    # Accounting
    receivable_account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name='withholding_receivables')
    
    expected_recovery_date = models.DateField(null=True, blank=True)
    recovered_date = models.DateField(null=True, blank=True)
    
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-withholding_date', '-withholding_number']
    
    def __str__(self):
        return f"{self.withholding_number} - {self.payer} - GHS {self.balance}"
    
    def save(self, *args, **kwargs):
        if not self.withholding_number:
            self.withholding_number = self.generate_withholding_number()
        
        self.balance = self.amount_withheld - self.amount_recovered
        super().save(*args, **kwargs)
    
    @staticmethod
    def generate_withholding_number():
        """Generate unique withholding number"""
        today = timezone.now()
        prefix = f"WR{today.strftime('%Y%m')}"
        
        last_with = WithholdingReceivable.objects.filter(
            withholding_number__startswith=prefix
        ).order_by('-withholding_number').first()
        
        if last_with:
            try:
                last_num = int(last_with.withholding_number[-6:])
                new_num = last_num + 1
            except ValueError:
                new_num = 1
        else:
            new_num = 1
        
        return f"{prefix}{new_num:06d}"


# ==================== WITHHOLDING TAX PAYABLE ====================

class WithholdingTaxPayable(BaseModel):
    """
    Withholding Tax Payable - Tax withheld from supplier payments
    According to Ghana tax laws:
    - Goods: 3%
    - Works: 5%
    - Local Services: 7.5%
    - Foreign Services: 20%
    """
    withholding_number = models.CharField(max_length=50, unique=True)
    withholding_date = models.DateField(default=timezone.now)
    
    supplier_name = models.CharField(max_length=200, help_text="Supplier/vendor name")
    supplier_tin = models.CharField(max_length=50, blank=True, help_text="Supplier TIN number")
    is_exempted = models.BooleanField(default=False, help_text="Whether supplier is exempted from WHT")
    
    # Source transaction
    accounts_payable = models.ForeignKey(AccountsPayable, on_delete=models.CASCADE, related_name='withholding_taxes', null=True, blank=True)
    payment_voucher = models.ForeignKey(PaymentVoucher, on_delete=models.SET_NULL, null=True, blank=True, related_name='withholding_taxes')
    
    # Amounts
    gross_amount = models.DecimalField(max_digits=15, decimal_places=2, help_text="Gross amount before WHT")
    withholding_rate = models.DecimalField(max_digits=5, decimal_places=2, help_text="WHT rate as percentage (3, 5, 7.5, or 20)")
    withholding_amount = models.DecimalField(max_digits=15, decimal_places=2, help_text="Amount withheld")
    net_amount_paid = models.DecimalField(max_digits=15, decimal_places=2, help_text="Net amount paid to supplier (gross - WHT)")
    
    # Classification
    SUPPLY_TYPES = [
        ('goods', 'Goods (3%)'),
        ('works', 'Works (5%)'),
        ('local_services', 'Local Services (7.5%)'),
        ('foreign_services', 'Foreign Services (20%)'),
    ]
    supply_type = models.CharField(max_length=20, choices=SUPPLY_TYPES, default='goods')
    
    # Payment status
    amount_paid = models.DecimalField(max_digits=15, decimal_places=2, default=0, help_text="Amount of WHT paid to GRA")
    balance_due = models.DecimalField(max_digits=15, decimal_places=2, help_text="Balance due to GRA")
    
    # Dates
    due_date = models.DateField(null=True, blank=True, help_text="Due date for WHT payment to GRA")
    paid_date = models.DateField(null=True, blank=True)
    
    # Accounting
    payable_account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name='withholding_tax_payables', help_text="WHT Payable account (Current Liability)")
    journal_entry = models.ForeignKey(AdvancedJournalEntry, on_delete=models.SET_NULL, null=True, blank=True)
    
    description = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-withholding_date', '-withholding_number']
        verbose_name_plural = 'Withholding Tax Payable'
    
    def __str__(self):
        return f"{self.withholding_number} - {self.supplier_name} - GHS {self.withholding_amount}"
    
    def save(self, *args, **kwargs):
        if not self.withholding_number:
            self.withholding_number = self.generate_withholding_number()
        
        # Auto-calculate if not set
        if self.gross_amount and self.withholding_rate and not self.withholding_amount:
            if not self.is_exempted:
                self.withholding_amount = (self.gross_amount * self.withholding_rate / 100)
            else:
                self.withholding_amount = Decimal('0.00')
        
        if self.gross_amount and self.withholding_amount and not self.net_amount_paid:
            self.net_amount_paid = self.gross_amount - self.withholding_amount
        
        # Calculate balance
        self.balance_due = self.withholding_amount - self.amount_paid
        
        super().save(*args, **kwargs)
    
    @staticmethod
    def generate_withholding_number():
        """Generate unique withholding tax payable number"""
        today = timezone.now()
        prefix = f"WTP{today.strftime('%Y%m')}"
        
        last_wtp = WithholdingTaxPayable.objects.filter(
            withholding_number__startswith=prefix
        ).order_by('-withholding_number').first()
        
        if last_wtp:
            try:
                last_num = int(last_wtp.withholding_number[-6:])
                new_num = last_num + 1
            except ValueError:
                new_num = 1
        else:
            new_num = 1
        
        return f"{prefix}{new_num:06d}"
    
    @staticmethod
    def get_rate_for_supply_type(supply_type):
        """Get WHT rate based on supply type"""
        rates = {
            'goods': Decimal('3.00'),
            'works': Decimal('5.00'),
            'local_services': Decimal('7.5'),
            'foreign_services': Decimal('20.00'),
        }
        return rates.get(supply_type, Decimal('3.00'))


# ==================== DEPOSITS ====================

class Deposit(BaseModel):
    """Deposit Recording - From and To tracking"""
    DEPOSIT_TYPES = [
        ('from', 'Deposit From'),
        ('to', 'Deposit To'),
    ]
    
    deposit_number = models.CharField(max_length=50, unique=True)
    deposit_type = models.CharField(max_length=10, choices=DEPOSIT_TYPES)
    deposit_date = models.DateField(default=timezone.now)
    
    from_account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name='deposits_from', null=True, blank=True)
    to_account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name='deposits_to', null=True, blank=True)
    from_bank_account = models.ForeignKey(BankAccount, on_delete=models.PROTECT, related_name='deposits_from', null=True, blank=True)
    to_bank_account = models.ForeignKey(BankAccount, on_delete=models.PROTECT, related_name='deposits_to', null=True, blank=True)
    
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    description = models.TextField()
    reference = models.CharField(max_length=100, blank=True)
    
    # Accounting
    journal_entry = models.ForeignKey(AdvancedJournalEntry, on_delete=models.SET_NULL, null=True, blank=True)
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    class Meta:
        ordering = ['-deposit_date', '-deposit_number']
    
    def __str__(self):
        return f"{self.deposit_number} - {self.get_deposit_type_display()} - GHS {self.amount}"
    
    def save(self, *args, **kwargs):
        if not self.deposit_number:
            self.deposit_number = self.generate_deposit_number()
        super().save(*args, **kwargs)
    
    @staticmethod
    def generate_deposit_number():
        """Generate unique deposit number"""
        today = timezone.now()
        prefix = f"DP{today.strftime('%Y%m')}"
        
        last_deposit = Deposit.objects.filter(
            deposit_number__startswith=prefix
        ).order_by('-deposit_number').first()
        
        if last_deposit:
            try:
                last_num = int(last_deposit.deposit_number[-6:])
                new_num = last_num + 1
            except ValueError:
                new_num = 1
        else:
            new_num = 1
        
        return f"{prefix}{new_num:06d}"


# ==================== INITIAL REVALUATIONS ====================

class InitialRevaluation(BaseModel):
    """Initial Revaluations - Asset revaluations at period start"""
    revaluation_number = models.CharField(max_length=50, unique=True)
    revaluation_date = models.DateField(default=timezone.now)
    effective_date = models.DateField(help_text="Date when revaluation takes effect")
    
    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name='revaluations')
    asset_description = models.CharField(max_length=500)
    
    previous_value = models.DecimalField(max_digits=15, decimal_places=2)
    new_value = models.DecimalField(max_digits=15, decimal_places=2)
    revaluation_amount = models.DecimalField(max_digits=15, decimal_places=2, help_text="Difference (new - previous)")
    
    revaluation_type = models.CharField(max_length=20, choices=[
        ('appreciation', 'Appreciation'),
        ('depreciation', 'Depreciation'),
        ('write_up', 'Write Up'),
        ('write_down', 'Write Down'),
    ])
    
    reason = models.TextField()
    
    # Accounting
    journal_entry = models.ForeignKey(AdvancedJournalEntry, on_delete=models.SET_NULL, null=True, blank=True)
    
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-revaluation_date', '-revaluation_number']
    
    def __str__(self):
        return f"{self.revaluation_number} - {self.account.account_name} - GHS {self.revaluation_amount}"
    
    def save(self, *args, **kwargs):
        if not self.revaluation_number:
            self.revaluation_number = self.generate_revaluation_number()
        
        # Calculate revaluation amount
        self.revaluation_amount = self.new_value - self.previous_value
        
        # Determine revaluation type
        if self.revaluation_amount > 0:
            self.revaluation_type = 'appreciation'
        else:
            self.revaluation_type = 'depreciation'
        
        super().save(*args, **kwargs)
    
    @staticmethod
    def generate_revaluation_number():
        """Generate unique revaluation number"""
        today = timezone.now()
        prefix = f"RV{today.strftime('%Y%m')}"
        
        last_reval = InitialRevaluation.objects.filter(
            revaluation_number__startswith=prefix
        ).order_by('-revaluation_number').first()
        
        if last_reval:
            try:
                last_num = int(last_reval.revaluation_number[-6:])
                new_num = last_num + 1
            except ValueError:
                new_num = 1
        else:
            new_num = 1
        
        return f"{prefix}{new_num:06d}"

