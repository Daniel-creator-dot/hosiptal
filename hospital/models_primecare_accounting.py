"""
Primecare Medical Centre - Accounting System
Implements the accounting requirements from the technical guide
"""
from django.db import models, transaction
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.validators import MinValueValidator
from decimal import Decimal
from datetime import timedelta
from .models import BaseModel, Patient, Invoice, Payer
from .models_accounting import Account, GeneralLedger, JournalEntry, JournalEntryLine
from .models_accounting_advanced import AdvancedJournalEntry, AdvancedJournalEntryLine, BankAccount, Journal


class UndepositedFunds(BaseModel):
    """
    Undeposited Funds - Cash receipts held before bank deposit
    After 24 hours, cash receipts are matched to revenue accounts
    """
    STATUS_CHOICES = [
        ('pending', 'Pending (Not Deposited)'),
        ('deposited', 'Deposited to Bank'),
        ('matched', 'Matched to Revenue'),
    ]
    
    entry_number = models.CharField(max_length=50, unique=True)
    entry_date = models.DateField(default=timezone.now)
    
    # Amount details
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, validators=[MinValueValidator(0)])
    
    # Revenue breakdown
    registration_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    consultation_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    laboratory_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    pharmacy_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    surgeries_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    admissions_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    radiology_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    dental_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    physiotherapy_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    matched_at = models.DateTimeField(null=True, blank=True)
    matched_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='matched_undeposited_funds')
    
    # Links
    journal_entry = models.ForeignKey(AdvancedJournalEntry, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Deposit info
    bank_account = models.ForeignKey(BankAccount, on_delete=models.SET_NULL, null=True, blank=True, related_name='deposits')
    deposit_date = models.DateField(null=True, blank=True)
    deposit_reference = models.CharField(max_length=100, blank=True)
    
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-entry_date', '-created']
        verbose_name_plural = 'Undeposited Funds'
    
    def __str__(self):
        return f"Undeposited Funds {self.entry_number} - GHS {self.total_amount}"
    
    def save(self, *args, **kwargs):
        if not self.entry_number:
            self.entry_number = self.generate_entry_number()
        super().save(*args, **kwargs)
    
    @staticmethod
    def generate_entry_number():
        """Generate unique entry number"""
        from datetime import datetime
        prefix = "UF"
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S%f')
        return f"{prefix}{timestamp}"
    
    def match_to_revenue(self, user):
        """
        Match undeposited funds to revenue accounts after 24 hours
        Creates journal entries:
        Debit: Undeposited Funds
        Credit: Revenue accounts (Registration, Consultation, etc.)
        """
        if self.status != 'pending':
            raise ValueError("Only pending entries can be matched to revenue")
        
        with transaction.atomic():
            # Get or create accounts
            undeposited_account, _ = Account.objects.get_or_create(
                account_code='1015',
                defaults={
                    'account_name': 'Undeposited Funds',
                    'account_type': 'asset',
                }
            )
            
            # Get revenue accounts
            revenue_accounts = {
                'registration': Account.objects.filter(account_code='4100').first(),
                'consultation': Account.objects.filter(account_code='4110').first(),
                'laboratory': Account.objects.filter(account_code='4120').first(),
                'pharmacy': Account.objects.filter(account_code='4130').first(),
                'surgeries': Account.objects.filter(account_code='4140').first(),
                'admissions': Account.objects.filter(account_code='4150').first(),
                'radiology': Account.objects.filter(account_code='4160').first(),
                'dental': Account.objects.filter(account_code='4170').first(),
                'physiotherapy': Account.objects.filter(account_code='4180').first(),
            }
            
            # Create journal entry
            journal, _ = Journal.objects.get_or_create(
                code='CASH',
                defaults={'name': 'Cash Journal', 'journal_type': 'cash'}
            )
            
            je = AdvancedJournalEntry.objects.create(
                journal=journal,
                entry_date=self.entry_date,
                description=f"Cash revenue matching - {self.entry_number}",
                reference=self.entry_number,
                created_by=user,
                status='draft',
            )
            
            line_number = 1
            
            # Credit: Undeposited Funds (decrease asset)
            AdvancedJournalEntryLine.objects.create(
                journal_entry=je,
                line_number=line_number,
                account=undeposited_account,
                description=f"Undeposited funds matched to revenue",
                debit_amount=0,
                credit_amount=self.total_amount,
            )
            line_number += 1
            
            # Debit: Revenue accounts (increase revenue)
            revenue_amounts = {
                'registration': self.registration_amount,
                'consultation': self.consultation_amount,
                'laboratory': self.laboratory_amount,
                'pharmacy': self.pharmacy_amount,
                'surgeries': self.surgeries_amount,
                'admissions': self.admissions_amount,
                'radiology': self.radiology_amount,
                'dental': self.dental_amount,
                'physiotherapy': self.physiotherapy_amount,
            }
            
            for rev_type, amount in revenue_amounts.items():
                if amount > 0 and revenue_accounts[rev_type]:
                    AdvancedJournalEntryLine.objects.create(
                        journal_entry=je,
                        line_number=line_number,
                        account=revenue_accounts[rev_type],
                        description=f"{rev_type.title()} revenue",
                        debit_amount=amount,
                        credit_amount=0,
                    )
                    line_number += 1
            
            # Update totals
            je.total_debit = self.total_amount
            je.total_credit = self.total_amount
            je.save()
            
            # Post journal entry
            je.post(user)
            
            # Update status
            self.status = 'matched'
            self.matched_at = timezone.now()
            self.matched_by = user
            self.journal_entry = je
            self.save()
            
            return je


class InsuranceReceivableEntry(BaseModel):
    """
    Insurance Receivable - Credit revenue entries
    After 48 hours, credit sales are matched to revenue accounts
    """
    STATUS_CHOICES = [
        ('pending', 'Pending (Not Matched)'),
        ('matched', 'Matched to Revenue'),
        ('partially_paid', 'Partially Paid'),
        ('paid', 'Fully Paid'),
    ]
    
    entry_number = models.CharField(max_length=50, unique=True)
    entry_date = models.DateField(default=timezone.now)
    
    # Insurance company
    payer = models.ForeignKey(Payer, on_delete=models.PROTECT, related_name='receivable_entries')
    
    # Amount details
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, validators=[MinValueValidator(0)])
    
    # Revenue breakdown
    registration_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    consultation_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    laboratory_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    pharmacy_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    surgeries_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    admissions_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    radiology_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    dental_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    physiotherapy_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    matched_at = models.DateTimeField(null=True, blank=True)
    matched_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='matched_receivables')
    
    # Links
    journal_entry = models.ForeignKey(AdvancedJournalEntry, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Payment tracking
    amount_received = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    amount_rejected = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    withholding_tax = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    outstanding_amount = models.DecimalField(max_digits=15, decimal_places=2)
    
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-entry_date', '-created']
        verbose_name_plural = 'Insurance Receivable Entries'
    
    def __str__(self):
        return f"IRE {self.entry_number} - {self.payer.name} - GHS {self.total_amount}"
    
    def save(self, *args, **kwargs):
        if not self.entry_number or not str(self.entry_number).strip():
            self.entry_number = self.generate_entry_number()
        if not hasattr(self, 'outstanding_amount') or self.outstanding_amount is None:
            self.outstanding_amount = self.total_amount
        super().save(*args, **kwargs)
    
    @staticmethod
    def generate_entry_number():
        """Generate unique entry number for insurance receivable entries. Never returns empty."""
        from datetime import datetime
        import uuid
        prefix = "IRE"
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S%f')
        suffix = (uuid.uuid4().hex or "")[:8]
        if not suffix:
            suffix = str(uuid.uuid4())[:8]
        value = f"{prefix}{timestamp}{suffix}"
        return value if (value and value.strip()) else f"{prefix}{uuid.uuid4().hex[:12]}"


class CorporateReceivableEntry(InsuranceReceivableEntry):
    """Proxy model for Corporate Receivable Entries - separates corporate from insurance"""
    class Meta:
        proxy = True
        verbose_name = 'Corporate Receivable Entry'
        verbose_name_plural = 'Corporate Receivable Entries'
    
    def __str__(self):
        return f"AR {self.entry_number} - {self.payer.name} - GHS {self.total_amount}"
    
    def save(self, *args, **kwargs):
        if not self.entry_number:
            self.entry_number = self.generate_entry_number()
        if not hasattr(self, 'outstanding_amount') or self.outstanding_amount is None:
            self.outstanding_amount = self.total_amount
        super().save(*args, **kwargs)
    
    @staticmethod
    def generate_entry_number():
        """Generate unique entry number"""
        from datetime import datetime
        prefix = "AR"
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S%f')
        return f"{prefix}{timestamp}"
    
    def match_to_revenue(self, user):
        """
        Match insurance receivable to revenue accounts after 48 hours
        Creates journal entries:
        Debit: Accounts Receivable (Insurance Company)
        Credit: Revenue accounts
        """
        if self.status != 'pending':
            raise ValueError("Only pending entries can be matched to revenue")
        
        with transaction.atomic():
            # Get or create AR account for this payer
            ar_account, _ = Account.objects.get_or_create(
                account_code=f'1200-{self.payer.id}',
                defaults={
                    'account_name': f'Accounts Receivable - {self.payer.name}',
                    'account_type': 'asset',
                }
            )
            
            # Get revenue accounts
            revenue_accounts = {
                'registration': Account.objects.filter(account_code='4100').first(),
                'consultation': Account.objects.filter(account_code='4110').first(),
                'laboratory': Account.objects.filter(account_code='4120').first(),
                'pharmacy': Account.objects.filter(account_code='4130').first(),
                'surgeries': Account.objects.filter(account_code='4140').first(),
                'admissions': Account.objects.filter(account_code='4150').first(),
                'radiology': Account.objects.filter(account_code='4160').first(),
                'dental': Account.objects.filter(account_code='4170').first(),
                'physiotherapy': Account.objects.filter(account_code='4180').first(),
            }
            
            # Create journal entry
            journal, _ = Journal.objects.get_or_create(
                code='SALES',
                defaults={'name': 'Sales Journal', 'journal_type': 'sales'}
            )
            
            je = AdvancedJournalEntry.objects.create(
                journal=journal,
                entry_date=self.entry_date,
                description=f"Credit revenue matching - {self.payer.name} - {self.entry_number}",
                reference=self.entry_number,
                created_by=user,
                status='draft',
            )
            
            line_number = 1
            
            # Debit: Accounts Receivable (increase asset)
            AdvancedJournalEntryLine.objects.create(
                journal_entry=je,
                line_number=line_number,
                account=ar_account,
                description=f"Accounts Receivable - {self.payer.name}",
                debit_amount=self.total_amount,
                credit_amount=0,
            )
            line_number += 1
            
            # Credit: Revenue accounts (increase revenue)
            revenue_amounts = {
                'registration': self.registration_amount,
                'consultation': self.consultation_amount,
                'laboratory': self.laboratory_amount,
                'pharmacy': self.pharmacy_amount,
                'surgeries': self.surgeries_amount,
                'admissions': self.admissions_amount,
                'radiology': self.radiology_amount,
                'dental': self.dental_amount,
                'physiotherapy': self.physiotherapy_amount,
            }
            
            for rev_type, amount in revenue_amounts.items():
                if amount > 0 and revenue_accounts[rev_type]:
                    AdvancedJournalEntryLine.objects.create(
                        journal_entry=je,
                        line_number=line_number,
                        account=revenue_accounts[rev_type],
                        description=f"{rev_type.title()} revenue",
                        debit_amount=0,
                        credit_amount=amount,
                    )
                    line_number += 1
            
            # Update totals
            je.total_debit = self.total_amount
            je.total_credit = self.total_amount
            je.save()
            
            # Post journal entry
            je.post(user)
            
            # Update status
            self.status = 'matched'
            self.matched_at = timezone.now()
            self.matched_by = user
            self.journal_entry = je
            self.save()
            
            return je


class InsurancePaymentReceived(BaseModel):
    """
    Insurance Payment Received - Records payment from insurance with rejections and WHT
    """
    entry_number = models.CharField(max_length=50, unique=True)
    entry_date = models.DateField(default=timezone.now)
    
    # Insurance company
    payer = models.ForeignKey(Payer, on_delete=models.PROTECT, related_name='payments_received')
    receivable_entry = models.ForeignKey(InsuranceReceivableEntry, on_delete=models.CASCADE, related_name='payments', null=True, blank=True)
    
    # Amounts
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, validators=[MinValueValidator(0)])
    amount_received = models.DecimalField(max_digits=15, decimal_places=2, validators=[MinValueValidator(0)])
    amount_rejected = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    withholding_tax = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    withholding_tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0, help_text="WHT rate as percentage")
    
    # Bank details
    bank_account = models.ForeignKey(BankAccount, on_delete=models.PROTECT, related_name='insurance_payments')
    payment_reference = models.CharField(max_length=100, blank=True)
    
    # Links
    journal_entry = models.ForeignKey(AdvancedJournalEntry, on_delete=models.SET_NULL, null=True, blank=True)
    
    notes = models.TextField(blank=True)
    processed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='processed_insurance_payments')
    
    class Meta:
        ordering = ['-entry_date', '-created']
        verbose_name_plural = 'Insurance Payments Received'
    
    def __str__(self):
        return f"Payment {self.entry_number} - {self.payer.name} - GHS {self.amount_received}"
    
    def save(self, *args, **kwargs):
        if not self.entry_number:
            self.entry_number = self.generate_entry_number()
        super().save(*args, **kwargs)
    
    @staticmethod
    def generate_entry_number():
        """Generate unique entry number"""
        from datetime import datetime
        prefix = "IPR"
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S%f')
        return f"{prefix}{timestamp}"
    
    def create_accounting_entries(self, user):
        """
        Create accounting entries for insurance payment received:
        1. Debit: Bank Account (amount received)
        2. Debit: Rejection Account (amount rejected)
        3. Debit: Withholding Tax Receivable (WHT amount)
        4. Credit: Accounts Receivable (total amount)
        """
        with transaction.atomic():
            # Get or create accounts
            ar_account, _ = Account.objects.get_or_create(
                account_code=f'1200-{self.payer.id}',
                defaults={
                    'account_name': f'Accounts Receivable - {self.payer.name}',
                    'account_type': 'asset',
                }
            )
            
            rejection_account, _ = Account.objects.get_or_create(
                account_code='5200',
                defaults={
                    'account_name': 'Bills Rejections',
                    'account_type': 'expense',
                }
            )
            
            wht_account, _ = Account.objects.get_or_create(
                account_code='1300',
                defaults={
                    'account_name': 'Withholding Tax Receivable',
                    'account_type': 'asset',
                }
            )
            
            # Create journal entry
            journal, _ = Journal.objects.get_or_create(
                code='RECEIPT',
                defaults={'name': 'Receipt Journal', 'journal_type': 'receipt'}
            )
            
            je = AdvancedJournalEntry.objects.create(
                journal=journal,
                entry_date=self.entry_date,
                description=f"Insurance payment received - {self.payer.name} - {self.entry_number}",
                reference=self.entry_number,
                created_by=user,
                status='draft',
            )
            
            line_number = 1
            total_debit = Decimal('0.00')
            total_credit = Decimal('0.00')
            
            # 1. Debit: Bank Account (amount received)
            if self.amount_received > 0:
                AdvancedJournalEntryLine.objects.create(
                    journal_entry=je,
                    line_number=line_number,
                    account=self.bank_account.account,
                    description=f"Payment received from {self.payer.name}",
                    debit_amount=self.amount_received,
                    credit_amount=0,
                )
                total_debit += self.amount_received
                line_number += 1
            
            # 2. Debit: Rejection Account (amount rejected)
            if self.amount_rejected > 0:
                AdvancedJournalEntryLine.objects.create(
                    journal_entry=je,
                    line_number=line_number,
                    account=rejection_account,
                    description=f"Bills rejected by {self.payer.name}",
                    debit_amount=self.amount_rejected,
                    credit_amount=0,
                )
                total_debit += self.amount_rejected
                line_number += 1
            
            # 3. Debit: Withholding Tax Receivable (WHT amount)
            if self.withholding_tax > 0:
                AdvancedJournalEntryLine.objects.create(
                    journal_entry=je,
                    line_number=line_number,
                    account=wht_account,
                    description=f"Withholding tax from {self.payer.name}",
                    debit_amount=self.withholding_tax,
                    credit_amount=0,
                )
                total_debit += self.withholding_tax
                line_number += 1
            
            # 4. Credit: Accounts Receivable (total amount)
            AdvancedJournalEntryLine.objects.create(
                journal_entry=je,
                line_number=line_number,
                account=ar_account,
                description=f"Accounts Receivable - {self.payer.name}",
                debit_amount=0,
                credit_amount=self.total_amount,
            )
            total_credit = self.total_amount
            
            # Update totals
            je.total_debit = total_debit
            je.total_credit = total_credit
            je.save()
            
            # Post journal entry
            je.post(user)
            
            # Update receivable entry
            if self.receivable_entry:
                self.receivable_entry.amount_received += self.amount_received
                self.receivable_entry.amount_rejected += self.amount_rejected
                self.receivable_entry.withholding_tax += self.withholding_tax
                self.receivable_entry.outstanding_amount = (
                    self.receivable_entry.total_amount - 
                    self.receivable_entry.amount_received - 
                    self.receivable_entry.amount_rejected - 
                    self.receivable_entry.withholding_tax
                )
                
                if self.receivable_entry.outstanding_amount <= 0:
                    self.receivable_entry.status = 'paid'
                elif self.receivable_entry.amount_received > 0:
                    self.receivable_entry.status = 'partially_paid'
                
                self.receivable_entry.save()
            
            # Link journal entry
            self.journal_entry = je
            self.processed_by = user
            self.save()
            
            return je

