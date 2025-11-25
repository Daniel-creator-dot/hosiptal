"""
Enterprise Billing & Accounts Receivable Models
World-class system for corporate and insurance billing with multi-tier pricing
"""
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal
from .models import BaseModel


# Billing Cycle Choices
BILLING_CYCLE_CHOICES = [
    ('monthly', 'Monthly - End of Month'),
    ('bi_weekly', 'Bi-Weekly'),
    ('weekly', 'Weekly'),
    ('custom', 'Custom Schedule'),
]

# Credit Status Choices
CREDIT_STATUS_CHOICES = [
    ('active', '✅ Active - Good Standing'),
    ('suspended', '⚠️ Suspended - Credit Limit Exceeded'),
    ('on_hold', '🔒 On Hold - Payment Issues'),
    ('collection', '⛔ In Collection'),
    ('closed', '❌ Account Closed'),
]

# Statement Status Choices
STATEMENT_STATUS_CHOICES = [
    ('draft', 'Draft'),
    ('sent', 'Sent'),
    ('partially_paid', 'Partially Paid'),
    ('paid', 'Paid'),
    ('overdue', 'Overdue'),
    ('written_off', 'Written Off'),
]


class CorporateAccount(BaseModel):
    """
    Corporate/Company client with monthly billing
    Manages company accounts that send consolidated monthly invoices
    """
    
    # Company Information
    company_name = models.CharField(
        max_length=200,
        unique=True,
        help_text="Official company name"
    )
    company_code = models.CharField(
        max_length=20,
        unique=True,
        help_text="Unique identifier code for the company"
    )
    registration_number = models.CharField(
        max_length=50,
        blank=True,
        help_text="Business registration number"
    )
    tax_id = models.CharField(
        max_length=50,
        blank=True,
        help_text="Tax identification number"
    )
    
    # Contact Details
    billing_contact_name = models.CharField(max_length=200)
    billing_email = models.EmailField(help_text="Primary email for invoices")
    billing_phone = models.CharField(max_length=20)
    billing_address = models.TextField()
    
    # Additional Contacts
    accounts_contact_email = models.EmailField(blank=True)
    hr_contact_email = models.EmailField(blank=True)
    
    # Financial Terms
    credit_limit = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Maximum outstanding balance allowed"
    )
    payment_terms_days = models.IntegerField(
        default=30,
        help_text="Payment due within X days (e.g., Net 30)"
    )
    current_balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Current outstanding balance"
    )
    credit_status = models.CharField(
        max_length=20,
        choices=CREDIT_STATUS_CHOICES,
        default='active'
    )
    
    # Billing Settings
    billing_cycle = models.CharField(
        max_length=20,
        choices=BILLING_CYCLE_CHOICES,
        default='monthly'
    )
    billing_day_of_month = models.IntegerField(
        default=1,
        help_text="Day of month to generate statement (1-31)"
    )
    next_billing_date = models.DateField()
    last_billing_date = models.DateField(null=True, blank=True)
    
    # Pricing
    price_book = models.ForeignKey(
        'PriceBook',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Custom price book for this company"
    )
    global_discount_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Discount applied to all services"
    )
    
    # Contract
    contract_start_date = models.DateField()
    contract_end_date = models.DateField(
        null=True,
        blank=True,
        help_text="Leave blank for ongoing contracts"
    )
    contract_document = models.FileField(
        upload_to='contracts/',
        blank=True
    )
    contract_notes = models.TextField(blank=True)
    
    # Management
    account_manager = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='managed_corporate_accounts'
    )
    
    # Notifications
    send_statement_email = models.BooleanField(
        default=True,
        help_text="Email monthly statements"
    )
    send_payment_reminders = models.BooleanField(
        default=True,
        help_text="Send automated payment reminders"
    )
    reminder_days_before_due = models.IntegerField(
        default=7,
        help_text="Days before due date to send reminder"
    )
    
    # Statistics
    total_employees_enrolled = models.IntegerField(default=0)
    lifetime_revenue = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00')
    )
    average_monthly_billing = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00')
    )
    
    # Flags
    is_active = models.BooleanField(default=True)
    require_pre_authorization = models.BooleanField(
        default=False,
        help_text="Require approval before services"
    )
    
    class Meta:
        ordering = ['company_name']
        verbose_name = 'Corporate Account'
        verbose_name_plural = 'Corporate Accounts'
        indexes = [
            models.Index(fields=['company_code']),
            models.Index(fields=['credit_status']),
            models.Index(fields=['next_billing_date']),
        ]
    
    def __str__(self):
        return f"{self.company_name} ({self.company_code})"
    
    @property
    def credit_available(self):
        """Calculate available credit"""
        return self.credit_limit - self.current_balance
    
    @property
    def credit_utilization_percentage(self):
        """Calculate credit utilization percentage"""
        if self.credit_limit > 0:
            return (self.current_balance / self.credit_limit) * 100
        return 0
    
    def is_credit_limit_exceeded(self):
        """Check if current balance exceeds credit limit"""
        return self.current_balance > self.credit_limit
    
    def update_balance(self, amount):
        """Update current balance"""
        self.current_balance += amount
        self.save(update_fields=['current_balance'])


class CorporateEmployee(BaseModel):
    """
    Link between company employees and their corporate account
    Tracks employee enrollment and coverage limits
    """
    
    corporate_account = models.ForeignKey(
        'CorporateAccount',
        on_delete=models.CASCADE,
        related_name='employees'
    )
    patient = models.ForeignKey(
        'Patient',
        on_delete=models.CASCADE,
        related_name='corporate_enrollments'
    )
    
    # Employee Details
    employee_id = models.CharField(
        max_length=50,
        help_text="Company employee ID number"
    )
    department = models.CharField(max_length=100, blank=True)
    designation = models.CharField(max_length=100, blank=True)
    employee_email = models.EmailField(blank=True)
    
    # Enrollment
    enrollment_date = models.DateField(auto_now_add=True)
    termination_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date when employee left company"
    )
    is_active = models.BooleanField(default=True)
    
    # Coverage Limits (if applicable)
    has_annual_limit = models.BooleanField(default=False)
    annual_limit = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Maximum coverage per year"
    )
    utilized_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Amount used this year"
    )
    limit_reset_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date when limit resets (usually Jan 1)"
    )
    
    # Dependents
    covers_dependents = models.BooleanField(default=False)
    number_of_dependents = models.IntegerField(default=0)
    dependent_limit = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )
    
    # Notes
    special_instructions = models.TextField(blank=True)
    
    class Meta:
        unique_together = ['corporate_account', 'patient']
        ordering = ['-enrollment_date']
        verbose_name = 'Corporate Employee'
        verbose_name_plural = 'Corporate Employees'
        indexes = [
            models.Index(fields=['employee_id']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return f"{self.patient.full_name} - {self.corporate_account.company_name}"
    
    @property
    def remaining_limit(self):
        """Calculate remaining annual limit"""
        if self.has_annual_limit and self.annual_limit:
            return self.annual_limit - self.utilized_amount
        return None
    
    def check_limit_exceeded(self, amount):
        """Check if proposed amount exceeds limit"""
        if not self.has_annual_limit:
            return False
        if not self.annual_limit:
            return False
        return (self.utilized_amount + amount) > self.annual_limit


class MonthlyStatement(BaseModel):
    """
    Consolidated monthly bill for corporate/insurance accounts
    Groups all services for the billing period
    """
    
    # Account Details
    payer = models.ForeignKey(
        'Payer',
        on_delete=models.CASCADE,
        related_name='monthly_statements'
    )
    corporate_account = models.ForeignKey(
        'CorporateAccount',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='statements'
    )
    
    # Statement Period
    statement_number = models.CharField(
        max_length=50,
        unique=True,
        help_text="Unique statement identifier"
    )
    statement_date = models.DateField(
        help_text="Date statement was generated"
    )
    period_start = models.DateField(help_text="Billing period start")
    period_end = models.DateField(help_text="Billing period end")
    
    # Financial Summary
    opening_balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Balance brought forward from previous statement"
    )
    total_charges = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Total new charges this period"
    )
    total_payments = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Payments received this period"
    )
    total_adjustments = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Adjustments/credits"
    )
    closing_balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Amount due"
    )
    
    # Taxes
    tax_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00')
    )
    
    # Line Items Count
    total_line_items = models.IntegerField(
        default=0,
        help_text="Number of service transactions"
    )
    total_patients_served = models.IntegerField(
        default=0,
        help_text="Number of unique patients"
    )
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=STATEMENT_STATUS_CHOICES,
        default='draft'
    )
    
    # Due Date
    due_date = models.DateField(help_text="Payment due by this date")
    payment_terms = models.CharField(
        max_length=100,
        default='Net 30 days'
    )
    
    # Distribution
    sent_date = models.DateTimeField(null=True, blank=True)
    sent_via = models.CharField(
        max_length=20,
        choices=[
            ('email', 'Email'),
            ('post', 'Post'),
            ('both', 'Email & Post'),
            ('portal', 'Online Portal')
        ],
        default='email'
    )
    sent_to_email = models.EmailField(blank=True)
    
    # Files
    pdf_file = models.FileField(
        upload_to='statements/%Y/%m/',
        blank=True,
        help_text="Generated PDF statement"
    )
    
    # Payment Tracking
    last_payment_date = models.DateField(null=True, blank=True)
    last_payment_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True
    )
    
    # Reminders
    reminder_count = models.IntegerField(
        default=0,
        help_text="Number of payment reminders sent"
    )
    last_reminder_sent = models.DateTimeField(null=True, blank=True)
    
    # Notes
    notes = models.TextField(blank=True)
    internal_notes = models.TextField(
        blank=True,
        help_text="Notes not visible to client"
    )
    
    class Meta:
        ordering = ['-statement_date']
        verbose_name = 'Monthly Statement'
        verbose_name_plural = 'Monthly Statements'
        indexes = [
            models.Index(fields=['statement_number']),
            models.Index(fields=['status']),
            models.Index(fields=['due_date']),
            models.Index(fields=['statement_date']),
        ]
    
    def __str__(self):
        company = self.corporate_account.company_name if self.corporate_account else self.payer.name
        return f"{self.statement_number} - {company}"
    
    @property
    def is_overdue(self):
        """Check if statement is past due date"""
        if self.status in ['paid', 'written_off']:
            return False
        return timezone.now().date() > self.due_date
    
    @property
    def days_overdue(self):
        """Calculate days overdue"""
        if not self.is_overdue:
            return 0
        return (timezone.now().date() - self.due_date).days
    
    @property
    def amount_outstanding(self):
        """Calculate amount still owed"""
        return self.closing_balance - (self.last_payment_amount or Decimal('0.00'))
    
    @staticmethod
    def generate_statement_number(period_end):
        """Generate unique statement number"""
        from datetime import datetime
        prefix = "STMT"
        date_str = period_end.strftime('%Y%m')
        
        # Get last statement for this period
        last_stmt = MonthlyStatement.objects.filter(
            statement_number__startswith=f"{prefix}-{date_str}"
        ).order_by('-statement_number').first()
        
        if last_stmt:
            # Extract sequence number and increment
            try:
                seq = int(last_stmt.statement_number.split('-')[-1])
                seq += 1
            except:
                seq = 1
        else:
            seq = 1
        
        return f"{prefix}-{date_str}-{seq:04d}"


class StatementLine(BaseModel):
    """
    Individual service line item on monthly statement
    Detailed breakdown of charges
    """
    
    statement = models.ForeignKey(
        'MonthlyStatement',
        on_delete=models.CASCADE,
        related_name='lines'
    )
    
    # Service Details
    service_date = models.DateField(help_text="Date service was provided")
    patient = models.ForeignKey(
        'Patient',
        on_delete=models.CASCADE
    )
    employee_id = models.CharField(
        max_length=50,
        blank=True,
        help_text="Company employee ID"
    )
    
    # Service
    service_code = models.ForeignKey(
        'ServiceCode',
        on_delete=models.SET_NULL,
        null=True
    )
    description = models.CharField(max_length=500)
    category = models.CharField(
        max_length=50,
        blank=True,
        help_text="Service category (Consultation, Lab, Pharmacy, etc.)"
    )
    quantity = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('1.00')
    )
    
    # Pricing
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    discount_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00')
    )
    discount_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00')
    )
    tax_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00')
    )
    line_total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Final amount for this line"
    )
    
    # References
    invoice = models.ForeignKey(
        'Invoice',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    encounter = models.ForeignKey(
        'Encounter',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    
    # Provider
    provider_name = models.CharField(max_length=200, blank=True)
    
    class Meta:
        ordering = ['service_date', 'patient__last_name']
        verbose_name = 'Statement Line'
        verbose_name_plural = 'Statement Lines'
        indexes = [
            models.Index(fields=['statement', 'service_date']),
            models.Index(fields=['patient']),
        ]
    
    def __str__(self):
        return f"{self.service_date} - {self.patient.full_name} - {self.description}"


class ServicePricing(BaseModel):
    """
    Multi-tier pricing for services
    Supports Cash, Corporate, and Insurance pricing
    """
    
    service_code = models.ForeignKey(
        'ServiceCode',
        on_delete=models.CASCADE,
        related_name='pricing_tiers'
    )
    
    # Price Tiers
    cash_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Walk-in/Cash patient price"
    )
    corporate_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Standard corporate contracted price"
    )
    insurance_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Standard insurance negotiated price"
    )
    
    # Effective Dates
    effective_from = models.DateField(help_text="Price effective from this date")
    effective_to = models.DateField(
        null=True,
        blank=True,
        help_text="Leave blank for ongoing"
    )
    is_active = models.BooleanField(default=True)
    
    # Payer-Specific Overrides
    payer = models.ForeignKey(
        'Payer',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="Specific payer (corporate/insurance) for custom pricing"
    )
    custom_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Custom negotiated price for this payer"
    )
    
    # Notes
    pricing_notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-effective_from']
        verbose_name = 'Service Pricing'
        verbose_name_plural = 'Service Pricing'
        indexes = [
            models.Index(fields=['service_code', 'is_active']),
            models.Index(fields=['payer', 'is_active']),
            models.Index(fields=['effective_from', 'effective_to']),
        ]
    
    def __str__(self):
        if self.payer:
            return f"{self.service_code.name} - {self.payer.name} - GHS {self.custom_price}"
        return f"{self.service_code.name} - Multi-tier Pricing"
    
    def is_currently_effective(self):
        """Check if pricing is currently effective"""
        today = timezone.now().date()
        if not self.is_active:
            return False
        if today < self.effective_from:
            return False
        if self.effective_to and today > self.effective_to:
            return False
        return True


class ARAgingSnapshot(BaseModel):
    """
    Accounts Receivable aging analysis snapshot
    Daily snapshot of outstanding balances by age
    """
    
    snapshot_date = models.DateField(
        unique=True,
        help_text="Date of this AR snapshot"
    )
    
    # Totals by Age Bucket
    current_0_30 = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Outstanding 0-30 days"
    )
    days_31_60 = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Outstanding 31-60 days"
    )
    days_61_90 = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Outstanding 61-90 days"
    )
    days_91_120 = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Outstanding 91-120 days"
    )
    days_over_120 = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Outstanding over 120 days"
    )
    total_outstanding = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Total AR balance"
    )
    
    # By Payer Type
    cash_outstanding = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00')
    )
    corporate_outstanding = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00')
    )
    insurance_outstanding = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00')
    )
    
    # Counts
    total_accounts = models.IntegerField(default=0)
    overdue_accounts = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['-snapshot_date']
        verbose_name = 'AR Aging Snapshot'
        verbose_name_plural = 'AR Aging Snapshots'
    
    def __str__(self):
        return f"AR Aging - {self.snapshot_date}"
    
    @property
    def overdue_percentage(self):
        """Calculate percentage of overdue AR"""
        if self.total_outstanding > 0:
            overdue = self.days_31_60 + self.days_61_90 + self.days_91_120 + self.days_over_120
            return (overdue / self.total_outstanding) * 100
        return 0
























