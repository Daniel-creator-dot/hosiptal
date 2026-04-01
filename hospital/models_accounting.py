"""
Accounting and Financial Management Models
"""
import uuid
from django.db import models, IntegrityError
from django.contrib.auth.models import User
from django.utils import timezone
from model_utils.models import TimeStampedModel
from .models import BaseModel, Patient, Invoice, Payer


class CostCenter(BaseModel):
    """Cost Centers for departmental accounting"""
    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=128)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['code']
    
    def __str__(self):
        return f"{self.code} — {self.name}"


class Account(BaseModel):
    """Chart of Accounts"""
    ACCOUNT_TYPES = [
        ('asset', 'Asset'),
        ('liability', 'Liability'),
        ('equity', 'Equity'),
        ('revenue', 'Revenue'),
        ('expense', 'Expense'),
    ]
    
    account_code = models.CharField(max_length=20, unique=True)
    account_name = models.CharField(max_length=200)
    account_type = models.CharField(max_length=20, choices=ACCOUNT_TYPES)
    parent_account = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='sub_accounts')
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['account_code']
        verbose_name = 'Chart of Accounts (Account)'
        verbose_name_plural = 'Chart of Accounts'
    
    def __str__(self):
        return f"{self.account_code} - {self.account_name}"


class Transaction(BaseModel):
    """Financial Transactions"""
    TRANSACTION_TYPES = [
        ('payment_received', 'Payment Received'),
        ('refund_issued', 'Refund Issued'),
        ('adjustment', 'Adjustment'),
        ('write_off', 'Write Off'),
        ('transfer', 'Transfer'),
    ]
    
    PAYMENT_METHODS = [
        ('cash', 'Cash'),
        ('card', 'Card'),
        ('bank_transfer', 'Bank Transfer'),
        ('mobile_money', 'Mobile Money'),
        ('cheque', 'Cheque'),
        ('insurance', 'Insurance'),
        ('deposit', 'Deposit (from patient account)'),
    ]
    
    transaction_number = models.CharField(max_length=50, unique=True)
    transaction_type = models.CharField(max_length=30, choices=TRANSACTION_TYPES)
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='transactions', null=True, blank=True)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='financial_transactions', null=True, blank=True)
    
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS, default='cash')
    reference_number = models.CharField(max_length=100, blank=True)
    
    processed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='processed_transactions')
    transaction_date = models.DateTimeField(default=timezone.now)
    notes = models.TextField(blank=True)
    
    # Accounting fields
    debit_account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name='debit_transactions', null=True, blank=True)
    credit_account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name='credit_transactions', null=True, blank=True)
    
    class Meta:
        ordering = ['-transaction_date']
    
    def __str__(self):
        return f"{self.transaction_number} - {self.get_transaction_type_display()} - GHS {self.amount}"
    
    def save(self, *args, **kwargs):
        if not self.transaction_number:
            self.transaction_number = self.generate_transaction_number()
        super().save(*args, **kwargs)
    
    @staticmethod
    def generate_transaction_number():
        """Generate unique transaction number with microseconds and random component"""
        from datetime import datetime
        import random
        prefix = "TXN"
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S%f')  # Added %f for microseconds
        random_suffix = random.randint(10, 99)  # Add random 2-digit number for extra uniqueness
        return f"{prefix}{timestamp}{random_suffix}"


class PaymentReceipt(BaseModel):
    """Payment receipts for patients"""
    SERVICE_TYPES = [
        ('lab', 'Laboratory Test'),
        ('pharmacy', 'Pharmacy/Medication'),
        ('pharmacy_prescription', 'Pharmacy Prescription'),
        ('pharmacy_walkin', 'Walk-in Pharmacy Sale'),
        ('medication', 'Medication Sale'),
        ('imaging', 'Imaging/Radiology'),
        ('imaging_study', 'Imaging Study'),
        ('consultation', 'Consultation'),
        ('admission', 'Admission'),
        ('detainment', 'Detainment'),
        ('procedure', 'Procedure'),
        ('combined', 'Combined Services'),
        ('other', 'Other'),
    ]
    
    receipt_number = models.CharField(max_length=50, unique=True)
    transaction = models.OneToOneField(Transaction, on_delete=models.CASCADE, related_name='receipt')
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='receipts')
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='receipts')
    
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=Transaction.PAYMENT_METHODS)
    received_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='issued_receipts')
    receipt_date = models.DateTimeField(default=timezone.now)
    notes = models.TextField(blank=True)
    
    # Service tracking fields
    service_type = models.CharField(max_length=30, choices=SERVICE_TYPES, default='other', blank=True)
    service_details = models.JSONField(default=dict, blank=True, help_text="Additional service details")
    
    # Verification tracking
    is_verified = models.BooleanField(default=False, help_text='Receipt has been verified')
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey('Staff', on_delete=models.SET_NULL, null=True, blank=True, related_name='verified_receipts')
    
    class Meta:
        ordering = ['-receipt_date']
    
    def __str__(self):
        return f"Receipt {self.receipt_number} - GHS {self.amount_paid}"
    
    def save(self, *args, **kwargs):
        if not self.receipt_number:
            self.receipt_number = self.generate_receipt_number()
        super().save(*args, **kwargs)
    
    @staticmethod
    def generate_receipt_number():
        """Generate unique receipt number with microseconds and random component"""
        from datetime import datetime
        import random
        prefix = "RCP"
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S%f')  # Added %f for microseconds
        random_suffix = random.randint(10, 99)  # Add random 2-digit number for extra uniqueness
        return f"{prefix}{timestamp}{random_suffix}"


class PaymentAllocation(BaseModel):
    """Track how payments are allocated to invoices"""
    payment_transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE, related_name='allocations')
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='payment_allocations')
    allocated_amount = models.DecimalField(max_digits=12, decimal_places=2)
    allocation_date = models.DateTimeField(default=timezone.now)
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-allocation_date']
    
    def __str__(self):
        return f"Allocation GHS {self.allocated_amount} to Invoice {self.invoice.invoice_number}"
    
    @staticmethod
    def allocate_payment(transaction, invoices_with_amounts):
        """
        Allocate a payment transaction to one or more invoices
        
        Args:
            transaction: Transaction object (payment_received)
            invoices_with_amounts: List of tuples [(invoice, amount), ...]
        
        Returns:
            List of created PaymentAllocation objects
        """
        from decimal import Decimal
        from django.core.exceptions import ValidationError
        
        total_allocated = sum(amount for _, amount in invoices_with_amounts)
        
        if total_allocated > transaction.amount:
            raise ValidationError(
                f'Total allocated amount GHS {total_allocated} exceeds payment amount ${transaction.amount}'
            )
        
        allocations = []
        for invoice, amount in invoices_with_amounts:
            if amount > invoice.balance:
                raise ValidationError(
                    f'Allocation amount GHS {amount} exceeds invoice {invoice.invoice_number} balance ${invoice.balance}'
                )
            
            allocation = PaymentAllocation.objects.create(
                payment_transaction=transaction,
                invoice=invoice,
                allocated_amount=amount,
                notes=f'Payment allocation from transaction {transaction.transaction_number}'
            )
            # Single source of truth: invoice totals/balance from lines + receipts (caller must create per-invoice receipt for this allocation; see plan §3)
            invoice.update_totals()
            allocations.append(allocation)
        
        return allocations


class AccountsReceivable(BaseModel):
    """Accounts Receivable aging and tracking"""
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='ar_entries')
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='ar_accounts')
    
    outstanding_amount = models.DecimalField(max_digits=12, decimal_places=2)
    due_date = models.DateField()
    days_overdue = models.IntegerField(default=0)
    
    aging_bucket = models.CharField(max_length=10, choices=[
        ('current', 'Current (0-30 days)'),
        ('31-60', '31-60 days'),
        ('61-90', '61-90 days'),
        ('90+', 'Over 90 days'),
    ], default='current')
    
    last_payment_date = models.DateField(null=True, blank=True)
    last_reminder_sent = models.DateField(null=True, blank=True)
    
    class Meta:
        ordering = ['due_date']
    
    def __str__(self):
        return f"AR - {self.invoice.invoice_number} - GHS {self.outstanding_amount}"
    
    def update_aging(self):
        """Update aging bucket based on days overdue"""
        from datetime import date
        today = date.today()
        self.days_overdue = (today - self.due_date).days
        
        if self.days_overdue <= 30:
            self.aging_bucket = 'current'
        elif self.days_overdue <= 60:
            self.aging_bucket = '31-60'
        elif self.days_overdue <= 90:
            self.aging_bucket = '61-90'
        else:
            self.aging_bucket = '90+'
        self.save()


class GeneralLedger(BaseModel):
    """General Ledger entries for double-entry bookkeeping"""
    entry_number = models.CharField(max_length=50, unique=True)
    transaction_date = models.DateField()
    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name='ledger_entries')
    
    debit_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    credit_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)  # Running balance
    
    reference_type = models.CharField(max_length=50, blank=True)  # e.g., 'invoice', 'payment', 'adjustment'
    reference_id = models.CharField(max_length=50, blank=True)
    reference_number = models.CharField(max_length=100, blank=True)  # Receipt number, invoice number, etc.
    
    description = models.TextField()
    entered_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    class Meta:
        ordering = ['-transaction_date', '-created']
    
    def __str__(self):
        return f"{self.entry_number} - {self.account.account_name}"
    
    def save(self, *args, **kwargs):
        if not self.entry_number:
            self.entry_number = self.generate_entry_number()
        
        # Calculate running balance if not explicitly set or if balance is 0
        update_fields = kwargs.get('update_fields', [])
        if 'balance' not in update_fields or self.balance == 0:
            # Get previous balance from last entry for this account (excluding this entry)
            previous_entry = GeneralLedger.objects.filter(
                account=self.account,
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
        
        # Retry logic to handle race conditions
        max_retries = 5
        for attempt in range(max_retries):
            try:
                super().save(*args, **kwargs)
                break
            except IntegrityError as e:
                if 'entry_number' in str(e) and attempt < max_retries - 1:
                    # Regenerate entry number and retry
                    self.entry_number = self.generate_entry_number()
                    continue
                else:
                    raise
    
    @staticmethod
    def generate_entry_number():
        """Generate unique ledger entry number with collision handling"""
        from datetime import datetime
        
        prefix = "GL"
        
        # Use timestamp with microseconds for better precision
        now = datetime.now()
        base_timestamp = now.strftime('%Y%m%d%H%M%S')
        microseconds = now.microsecond
        
        # Try the base entry number first
        entry_number = f"{prefix}{base_timestamp}{microseconds:06d}"
        
        # Check if entry number already exists and increment if needed
        max_attempts = 100
        attempt = 0
        
        while GeneralLedger.objects.filter(entry_number=entry_number).exists() and attempt < max_attempts:
            attempt += 1
            # Add a sequence number to ensure uniqueness
            entry_number = f"{prefix}{base_timestamp}{microseconds:06d}{attempt:03d}"
        
        if attempt >= max_attempts:
            # Fallback: use UUID component if too many collisions
            import uuid
            unique_id = str(uuid.uuid4())[:8]
            entry_number = f"{prefix}{base_timestamp}{unique_id}"
        
        return entry_number


class JournalEntry(BaseModel):
    """Journal entries for manual accounting adjustments"""
    entry_number = models.CharField(max_length=50, unique=True)
    entry_date = models.DateField()
    ref = models.CharField(max_length=64, blank=True, null=True)  # reference/voucher number
    reference_number = models.CharField(max_length=100, blank=True)  # alias for ref for compatibility
    entry_type = models.CharField(max_length=50, blank=True, default='manual')  # payment, adjustment, manual
    status = models.CharField(max_length=20, default='posted', choices=[
        ('draft', 'Draft'),
        ('posted', 'Posted'),
        ('void', 'Void'),
    ])
    description = models.TextField()
    source = models.CharField(max_length=64, blank=True, null=True)  # e.g., "Excel GL 2025"
    entered_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    posted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='posted_journal_entries')  # alias for backward compatibility
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_journals')
    approved_at = models.DateTimeField(null=True, blank=True)
    is_posted = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-entry_date']
    
    def __str__(self):
        return f"{self.entry_number} - {self.description[:50]}"
    
    def validate_balanced(self):
        """Validate that debits equal credits"""
        from decimal import Decimal
        from django.core.exceptions import ValidationError
        
        total_debits = Decimal('0.00')
        total_credits = Decimal('0.00')
        
        for line in self.lines.all():
            total_debits += line.debit_amount
            total_credits += line.credit_amount
        
        if total_debits != total_credits:
            raise ValidationError(
                f'Journal Entry is not balanced. Debits: GHS {total_debits}, Credits: ${total_credits}. '
                f'Difference: GHS {abs(total_debits - total_credits)}'
            )
        
        return True
    
    def post(self, user=None):
        """Post journal entry to general ledger after validation"""
        from django.core.exceptions import ValidationError
        
        if self.is_posted:
            raise ValidationError('This journal entry has already been posted.')
        
        # Validate that entry is balanced
        self.validate_balanced()
        
        # Create GL entries for each line
        for line in self.lines.all():
            GeneralLedger.objects.create(
                account=line.account,
                transaction_date=self.entry_date,
                debit_amount=line.debit_amount,
                credit_amount=line.credit_amount,
                reference_type='journal_entry',
                reference_id=str(self.pk),
                description=f'{self.description} - {line.description}' if line.description else self.description,
                entered_by=user or self.entered_by,
            )
        
        # Mark as posted
        self.is_posted = True
        self.approved_by = user
        self.approved_at = timezone.now()
        self.save()
        
        return True
    
    def save(self, *args, **kwargs):
        if not self.entry_number:
            self.entry_number = self.generate_entry_number()
        
        # Retry logic to handle race conditions
        max_retries = 5
        for attempt in range(max_retries):
            try:
                super().save(*args, **kwargs)
                break
            except IntegrityError as e:
                if 'entry_number' in str(e) and attempt < max_retries - 1:
                    # Regenerate entry number and retry
                    self.entry_number = self.generate_entry_number()
                    continue
                else:
                    raise
    
    @staticmethod
    def generate_entry_number():
        """Generate unique journal entry number with collision handling"""
        from datetime import datetime
        import uuid
        
        prefix = "JE"
        
        # Use timestamp with microseconds for better precision
        now = datetime.now()
        base_timestamp = now.strftime('%Y%m%d%H%M%S')
        microseconds = now.microsecond
        
        # Try the base entry number first
        entry_number = f"{prefix}{base_timestamp}{microseconds:06d}"
        
        # Check if entry number already exists and increment if needed
        max_attempts = 100
        attempt = 0
        
        while JournalEntry.objects.filter(entry_number=entry_number).exists() and attempt < max_attempts:
            attempt += 1
            # Add a sequence number to ensure uniqueness
            entry_number = f"{prefix}{base_timestamp}{microseconds:06d}{attempt:03d}"
        
        if attempt >= max_attempts:
            # Fallback: use UUID component if too many collisions
            unique_id = str(uuid.uuid4())[:8]
            entry_number = f"{prefix}{base_timestamp}{unique_id}"
        
        return entry_number


class JournalEntryLine(BaseModel):
    """Line items for journal entries"""
    journal_entry = models.ForeignKey(JournalEntry, on_delete=models.CASCADE, related_name='lines')
    account = models.ForeignKey(Account, on_delete=models.PROTECT)
    cost_center = models.ForeignKey(CostCenter, on_delete=models.SET_NULL, null=True, blank=True)
    debit_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    credit_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    description = models.TextField(blank=True)
    ext_ref = models.CharField(max_length=64, blank=True, null=True)  # external reference (invoice/patient/claim id)
    
    class Meta:
        ordering = ['created']
        indexes = [
            models.Index(fields=["account"]),
            models.Index(fields=["ext_ref"]),
        ]

