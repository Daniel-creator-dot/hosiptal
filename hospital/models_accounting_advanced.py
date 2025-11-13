"""
Advanced Accounting System - State of the Art
Complete double-entry accounting with journals, ledgers, and financial reporting
"""

import uuid
from django.db import models, transaction
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.validators import MinValueValidator
from decimal import Decimal
from datetime import datetime, timedelta
from .models import BaseModel, Patient, Invoice, Department
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
    
    voucher_number = models.CharField(max_length=50, unique=True)
    voucher_date = models.DateField(default=timezone.now)
    
    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPES)
    payee_name = models.CharField(max_length=200)
    payee_type = models.CharField(max_length=50, blank=True)  # Supplier, Staff, Vendor, etc.
    
    description = models.TextField()
    amount = models.DecimalField(max_digits=15, decimal_places=2, validators=[MinValueValidator(0)])
    
    payment_method = models.CharField(max_length=50, default='bank_transfer')
    payment_reference = models.CharField(max_length=100, blank=True)
    payment_date = models.DateField(null=True, blank=True)
    
    # Bank details
    bank_name = models.CharField(max_length=200, blank=True)
    account_number = models.CharField(max_length=50, blank=True)
    cheque_number = models.CharField(max_length=50, blank=True)
    
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
    
    def mark_paid(self, user, payment_date=None):
        """Mark voucher as paid and create journal entry"""
        if self.status != 'approved':
            raise ValueError("Only approved vouchers can be marked as paid")
        
        with transaction.atomic():
            # Create journal entry
            je = AdvancedJournalEntry.objects.create(
                journal=Journal.objects.get(journal_type='payment'),
                entry_date=payment_date or timezone.now().date(),
                description=f"Payment: {self.description}",
                reference=self.voucher_number,
                created_by=user,
            )
            
            # Debit expense account
            AdvancedJournalEntryLine.objects.create(
                journal_entry=je,
                line_number=1,
                account=self.expense_account,
                description=self.description,
                debit_amount=self.amount,
                credit_amount=0,
            )
            
            # Credit payment account (cash/bank)
            AdvancedJournalEntryLine.objects.create(
                journal_entry=je,
                line_number=2,
                account=self.payment_account,
                description=self.description,
                debit_amount=0,
                credit_amount=self.amount,
            )
            
            # Update totals
            je.total_debit = self.amount
            je.total_credit = self.amount
            je.save()
            
            # Post journal entry
            je.post(user)
            
            # Update voucher
            self.status = 'paid'
            self.payment_date = payment_date or timezone.now().date()
            self.paid_by = user
            self.journal_entry = je
            self.save()


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
    """Accounts Payable Tracking"""
    bill_number = models.CharField(max_length=50, unique=True)
    vendor_name = models.CharField(max_length=200)
    vendor_invoice = models.CharField(max_length=100)
    
    bill_date = models.DateField()
    due_date = models.DateField()
    
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    amount_paid = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    balance_due = models.DecimalField(max_digits=15, decimal_places=2)
    
    description = models.TextField()
    
    is_overdue = models.BooleanField(default=False)
    days_overdue = models.IntegerField(default=0)
    
    # Links
    payment_voucher = models.ForeignKey(PaymentVoucher, on_delete=models.SET_NULL, null=True, blank=True)
    journal_entry = models.ForeignKey(AdvancedJournalEntry, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        ordering = ['due_date']
        verbose_name_plural = 'Accounts Payable'
    
    def __str__(self):
        return f"{self.bill_number} - {self.vendor_name} - GHS {self.balance_due}"


# ==================== BANK & CASH MANAGEMENT ====================

class BankAccount(BaseModel):
    """Bank Accounts"""
    account_name = models.CharField(max_length=200)
    account_number = models.CharField(max_length=50, unique=True)
    bank_name = models.CharField(max_length=200)
    branch = models.CharField(max_length=200, blank=True)
    
    account_type = models.CharField(max_length=50, default='checking')  # checking, savings, credit
    currency = models.CharField(max_length=3, default='GHS')
    
    opening_balance = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    current_balance = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # Link to chart of accounts
    gl_account = models.ForeignKey(Account, on_delete=models.PROTECT)
    
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['bank_name', 'account_name']
    
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

