"""
HR and Staff Management Models
"""
import uuid
from django.db import models
from django.db.models import Q
from django.contrib.auth.models import User
from django.utils import timezone
from model_utils.models import TimeStampedModel
from decimal import Decimal
from .models import BaseModel, Staff, Department


class PayGrade(BaseModel):
    """Staff pay grades/levels"""
    grade_name = models.CharField(max_length=50)
    level = models.PositiveIntegerField(default=1)
    base_salary = models.DecimalField(max_digits=12, decimal_places=2)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['level']
    
    def __str__(self):
        return f"{self.grade_name} (Level {self.level})"


class StaffContract(BaseModel):
    """Staff employment contracts"""
    CONTRACT_TYPES = [
        ('permanent', 'Permanent'),
        ('contract', 'Contract'),
        ('temporary', 'Temporary'),
        ('probation', 'Probation'),
        ('intern', 'Intern'),
    ]
    
    staff = models.OneToOneField(Staff, on_delete=models.CASCADE, related_name='contract')
    contract_type = models.CharField(max_length=20, choices=CONTRACT_TYPES)
    pay_grade = models.ForeignKey(PayGrade, on_delete=models.PROTECT, related_name='contracts')
    
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    
    basic_salary = models.DecimalField(max_digits=12, decimal_places=2)
    allowances = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    benefits = models.JSONField(default=dict, blank=True)
    
    job_title = models.CharField(max_length=200)
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name='contracts')
    
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-start_date']
    
    def __str__(self):
        return f"{self.staff.user.get_full_name()} - {self.job_title} ({self.get_contract_type_display()})"
    
    @property
    def total_monthly_salary(self):
        """Calculate total monthly salary"""
        return self.basic_salary + self.allowances


class PayrollPeriod(BaseModel):
    """Payroll periods"""
    period_name = models.CharField(max_length=50)
    start_date = models.DateField()
    end_date = models.DateField()
    pay_date = models.DateField()
    
    is_processed = models.BooleanField(default=False)
    processed_at = models.DateTimeField(null=True, blank=True)
    processed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        ordering = ['-start_date']
    
    def __str__(self):
        return f"{self.period_name} - {self.start_date} to {self.end_date}"


class Payroll(BaseModel):
    """Staff payroll records"""
    payroll_number = models.CharField(max_length=50, unique=True)
    staff = models.ForeignKey(Staff, on_delete=models.CASCADE, related_name='payrolls')
    period = models.ForeignKey(PayrollPeriod, on_delete=models.CASCADE, related_name='payrolls')
    contract = models.ForeignKey(StaffContract, on_delete=models.PROTECT, related_name='payrolls')
    
    # Earnings
    basic_salary = models.DecimalField(max_digits=12, decimal_places=2)
    allowances = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    overtime = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    bonuses = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_earnings = models.DecimalField(max_digits=12, decimal_places=2)
    
    # Deductions
    tax = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    social_security = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    pension = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    loan_repayment = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    other_deductions = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_deductions = models.DecimalField(max_digits=12, decimal_places=2)
    
    # Net Pay
    net_pay = models.DecimalField(max_digits=12, decimal_places=2)
    
    # Payment
    payment_method = models.CharField(max_length=20, choices=[
        ('bank_transfer', 'Bank Transfer'),
        ('cash', 'Cash'),
        ('cheque', 'Cheque'),
    ], default='bank_transfer')
    
    payment_status = models.CharField(max_length=20, choices=[
        ('pending', 'Pending'),
        ('processed', 'Processed'),
        ('paid', 'Paid'),
    ], default='pending')
    
    paid_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-period__start_date', 'staff']
    
    def __str__(self):
        return f"Payroll {self.payroll_number} - {self.staff.user.get_full_name()}"
    
    def save(self, *args, **kwargs):
        if not self.payroll_number:
            self.payroll_number = self.generate_payroll_number()
        
        # Calculate totals from allowance and deduction items if they exist
        # Otherwise use the legacy fields
        allowance_items = self.allowance_items.all() if hasattr(self, 'allowance_items') else []
        deduction_items = self.deduction_items.all() if hasattr(self, 'deduction_items') else []
        
        if allowance_items.exists():
            # Calculate from items
            allowances_total = sum(item.amount for item in allowance_items)
            self.allowances = allowances_total
        else:
            # Use legacy field
            allowances_total = self.allowances
        
        if deduction_items.exists():
            # Calculate from items
            deductions_total = sum(item.amount for item in deduction_items)
            self.total_deductions = deductions_total
        else:
            # Use legacy fields
            self.total_deductions = (
                self.tax + self.social_security + self.pension +
                self.loan_repayment + self.other_deductions
            )
        
        # Calculate totals
        self.total_earnings = (
            self.basic_salary + allowances_total + 
            self.overtime + self.bonuses
        )
        
        self.net_pay = self.total_earnings - self.total_deductions
        
        super().save(*args, **kwargs)
    
    def calculate_progressive_tax(self, taxable_income):
        """Calculate tax using progressive tax brackets"""
        config = PayrollConfiguration.get_active_config()
        if not config or config.tax_calculation_method != 'progressive':
            # Fall back to flat rate
            tax_rate = config.default_tax_rate if config else Decimal('15.00')
            return taxable_income * (tax_rate / Decimal('100'))
        
        from datetime import date
        today = date.today()
        
        # Get active tax brackets
        brackets = TaxBracket.objects.filter(
            is_active=True,
            is_deleted=False,
            effective_from__lte=today
        ).filter(
            Q(effective_to__isnull=True) | Q(effective_to__gte=today)
        ).order_by('min_income')
        
        if not brackets.exists():
            # No brackets, use flat rate
            return taxable_income * (config.default_tax_rate / Decimal('100'))
        
        tax_free = config.tax_free_allowance
        taxable_amount = max(Decimal('0'), taxable_income - tax_free)
        
        total_tax = Decimal('0')
        remaining_income = taxable_amount
        
        for bracket in brackets:
            if remaining_income <= 0:
                break
            
            bracket_min = bracket.min_income
            bracket_max = bracket.max_income if bracket.max_income else Decimal('999999999')
            
            if taxable_amount >= bracket_min:
                # Calculate income in this bracket
                income_in_bracket = min(remaining_income, bracket_max - bracket_min + Decimal('0.01'))
                
                # Calculate tax for this bracket
                bracket_tax = income_in_bracket * (bracket.tax_rate / Decimal('100'))
                bracket_tax += bracket.fixed_amount
                
                total_tax += bracket_tax
                remaining_income -= income_in_bracket
        
        return total_tax
    
    @staticmethod
    def generate_payroll_number():
        """Generate unique payroll number"""
        from datetime import datetime
        prefix = "PAY"
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        return f"{prefix}{timestamp}"


# ==================== PAYROLL CONFIGURATION MODELS ====================

class AllowanceType(BaseModel):
    """Types of allowances that can be configured"""
    CALCULATION_TYPES = [
        ('fixed', 'Fixed Amount'),
        ('percentage', 'Percentage of Basic Salary'),
        ('per_unit', 'Per Unit (e.g., per hour, per day)'),
    ]
    
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=20, unique=True, help_text="Short code for this allowance type")
    description = models.TextField(blank=True)
    
    calculation_type = models.CharField(max_length=20, choices=CALCULATION_TYPES, default='fixed')
    default_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Default amount or percentage")
    
    is_taxable = models.BooleanField(default=True, help_text="Whether this allowance is subject to tax")
    is_statutory = models.BooleanField(default=False, help_text="Whether this is a statutory/required allowance")
    
    display_order = models.PositiveIntegerField(default=0, help_text="Order for display in payroll")
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['display_order', 'name']
        verbose_name = "Allowance Type"
        verbose_name_plural = "Allowance Types"
    
    def __str__(self):
        return f"{self.name} ({self.code})"


class DeductionType(BaseModel):
    """Types of deductions that can be configured"""
    CALCULATION_TYPES = [
        ('fixed', 'Fixed Amount'),
        ('percentage', 'Percentage of Basic Salary'),
        ('percentage_of_gross', 'Percentage of Gross Pay'),
        ('tiered', 'Tiered Calculation (e.g., tax brackets)'),
    ]
    
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=20, unique=True, help_text="Short code for this deduction type")
    description = models.TextField(blank=True)
    
    calculation_type = models.CharField(max_length=20, choices=CALCULATION_TYPES, default='fixed')
    default_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Default amount or percentage")
    
    is_statutory = models.BooleanField(default=False, help_text="Whether this is a statutory/required deduction")
    is_loan = models.BooleanField(default=False, help_text="Whether this is a loan repayment")
    
    max_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, help_text="Maximum deduction amount (if applicable)")
    min_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, help_text="Minimum deduction amount (if applicable)")
    
    display_order = models.PositiveIntegerField(default=0, help_text="Order for display in payroll")
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['display_order', 'name']
        verbose_name = "Deduction Type"
        verbose_name_plural = "Deduction Types"
    
    def __str__(self):
        return f"{self.name} ({self.code})"


class TaxBracket(BaseModel):
    """Tax brackets for progressive tax calculation"""
    bracket_name = models.CharField(max_length=100)
    min_income = models.DecimalField(max_digits=12, decimal_places=2, help_text="Minimum income for this bracket")
    max_income = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, help_text="Maximum income for this bracket (null = no upper limit)")
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, help_text="Tax rate as percentage (e.g., 15.00 for 15%)")
    fixed_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Fixed tax amount for this bracket")
    
    effective_from = models.DateField(help_text="Date this bracket becomes effective")
    effective_to = models.DateField(null=True, blank=True, help_text="Date this bracket expires (null = current)")
    
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['min_income']
        verbose_name = "Tax Bracket"
        verbose_name_plural = "Tax Brackets"
    
    def __str__(self):
        return f"{self.bracket_name} ({self.min_income} - {self.max_income or '∞'}) @ {self.tax_rate}%"


class PayrollConfiguration(BaseModel):
    """System-wide payroll configuration settings"""
    name = models.CharField(max_length=100, default="Default Payroll Configuration")
    
    # Tax settings
    tax_calculation_method = models.CharField(max_length=20, choices=[
        ('flat', 'Flat Rate'),
        ('progressive', 'Progressive (Tax Brackets)'),
        ('custom', 'Custom Calculation'),
    ], default='progressive')
    
    default_tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=15.00, help_text="Default flat tax rate (%)")
    tax_free_allowance = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Tax-free allowance amount")
    
    # Social Security settings
    social_security_rate = models.DecimalField(max_digits=5, decimal_places=2, default=5.00, help_text="Social security contribution rate (%)")
    social_security_max_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, help_text="Maximum social security contribution")
    
    # Pension settings
    pension_rate = models.DecimalField(max_digits=5, decimal_places=2, default=10.00, help_text="Pension contribution rate (%)")
    pension_max_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, help_text="Maximum pension contribution")
    
    # Payroll period settings
    default_payroll_day = models.PositiveIntegerField(default=25, help_text="Default day of month for payroll processing")
    
    # Overtime settings
    regular_hours_per_day = models.DecimalField(max_digits=4, decimal_places=2, default=8.00)
    overtime_multiplier = models.DecimalField(max_digits=4, decimal_places=2, default=1.50, help_text="Overtime multiplier (e.g., 1.5 for time and a half)")
    
    # Currency
    currency_symbol = models.CharField(max_length=10, default="GHS")
    currency_code = models.CharField(max_length=10, default="GHS")
    
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=True, help_text="Use this as the default configuration")
    
    notes = models.TextField(blank=True)
    
    class Meta:
        verbose_name = "Payroll Configuration"
        verbose_name_plural = "Payroll Configurations"
    
    def __str__(self):
        return f"{self.name}"
    
    def save(self, *args, **kwargs):
        # Ensure only one default configuration
        if self.is_default:
            PayrollConfiguration.objects.filter(is_default=True, is_deleted=False).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)
    
    @classmethod
    def get_active_config(cls):
        """Get the active payroll configuration"""
        return cls.objects.filter(is_active=True, is_default=True, is_deleted=False).first()


class PayrollAllowance(BaseModel):
    """Individual allowances for a payroll record"""
    payroll = models.ForeignKey(Payroll, on_delete=models.CASCADE, related_name='allowance_items')
    allowance_type = models.ForeignKey(AllowanceType, on_delete=models.PROTECT, related_name='payroll_allowances')
    
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    description = models.CharField(max_length=200, blank=True)
    
    is_taxable = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['allowance_type__display_order']
        verbose_name = "Payroll Allowance"
        verbose_name_plural = "Payroll Allowances"
    
    def __str__(self):
        return f"{self.allowance_type.name} - {self.amount}"


class PayrollDeduction(BaseModel):
    """Individual deductions for a payroll record"""
    payroll = models.ForeignKey(Payroll, on_delete=models.CASCADE, related_name='deduction_items')
    deduction_type = models.ForeignKey(DeductionType, on_delete=models.PROTECT, related_name='payroll_deductions')
    
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    description = models.CharField(max_length=200, blank=True)
    
    class Meta:
        ordering = ['deduction_type__display_order']
        verbose_name = "Payroll Deduction"
        verbose_name_plural = "Payroll Deductions"
    
    def __str__(self):
        return f"{self.deduction_type.name} - {self.amount}"


class LeaveBalance(BaseModel):
    """Staff leave balances"""
    staff = models.OneToOneField(Staff, on_delete=models.CASCADE, related_name='leave_balance')
    
    annual_leave = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    sick_leave = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    casual_leave = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    comp_off = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    last_updated = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Leave Balance - {self.staff.user.get_full_name()}"


class PerformanceKPI(BaseModel):
    """Key Performance Indicators for performance reviews"""
    kpi_code = models.CharField(max_length=50, unique=True)
    kpi_name = models.CharField(max_length=200)
    description = models.TextField()
    category = models.CharField(max_length=100, choices=[
        ('clinical', 'Clinical Excellence'),
        ('customer_service', 'Customer Service'),
        ('teamwork', 'Teamwork & Collaboration'),
        ('communication', 'Communication'),
        ('punctuality', 'Punctuality & Attendance'),
        ('leadership', 'Leadership'),
        ('technical', 'Technical Skills'),
        ('productivity', 'Productivity'),
    ])
    
    weight_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)  # Weight in overall score
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['category', 'kpi_name']
    
    def __str__(self):
        return f"{self.kpi_code} - {self.kpi_name}"


class PerformanceReview(BaseModel):
    """Staff performance reviews - enhanced with KPIs"""
    RATINGS = [
        ('outstanding', 'Outstanding (5)'),
        ('excellent', 'Excellent (4)'),
        ('good', 'Good (3)'),
        ('satisfactory', 'Satisfactory (2)'),
        ('needs_improvement', 'Needs Improvement (1)'),
    ]
    
    review_number = models.CharField(max_length=50, unique=True)
    staff = models.ForeignKey(Staff, on_delete=models.CASCADE, related_name='performance_reviews')
    reviewed_by = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, related_name='conducted_reviews')
    
    review_period_start = models.DateField()
    review_period_end = models.DateField()
    review_date = models.DateField(default=timezone.now)
    review_type = models.CharField(max_length=20, choices=[
        ('annual', 'Annual Review'),
        ('probation', 'Probation Review'),
        ('mid_year', 'Mid-Year Review'),
        ('special', 'Special Review'),
    ], default='annual')
    
    overall_rating = models.CharField(max_length=20, choices=RATINGS)
    overall_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)  # Calculated from KPIs
    
    # Detailed sections
    strengths = models.TextField(blank=True)
    weaknesses = models.TextField(blank=True)
    achievements = models.TextField(blank=True)
    improvement_areas = models.TextField(blank=True)
    
    # Goals and development
    goals = models.TextField(blank=True)
    development_plan = models.TextField(blank=True)
    training_needs = models.TextField(blank=True)
    
    # Recommendations
    promotion_recommended = models.BooleanField(default=False)
    salary_increase_recommended = models.BooleanField(default=False)
    recommended_increase_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    comments = models.TextField(blank=True)
    staff_comments = models.TextField(blank=True)  # Staff's self-assessment or response
    
    # Approval workflow
    status = models.CharField(max_length=20, choices=[
        ('draft', 'Draft'),
        ('pending', 'Pending Staff Acknowledgment'),
        ('acknowledged', 'Acknowledged by Staff'),
        ('approved', 'Approved by Management'),
    ], default='draft')
    
    staff_acknowledged_at = models.DateTimeField(null=True, blank=True)
    is_approved = models.BooleanField(default=False)
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-review_date']
    
    def __str__(self):
        return f"Performance Review {self.review_number} - {self.staff.user.get_full_name()}"
    
    def save(self, *args, **kwargs):
        if not self.review_number:
            self.review_number = self.generate_review_number()
        super().save(*args, **kwargs)
    
    @staticmethod
    def generate_review_number():
        """Generate unique review number"""
        from datetime import datetime
        prefix = "PERF"
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        return f"{prefix}{timestamp}"
    
    def calculate_overall_score(self):
        """Calculate overall score from KPI ratings"""
        kpi_ratings = self.kpi_ratings.all()
        if not kpi_ratings:
            return Decimal('0.00')
        
        total_score = Decimal('0.00')
        total_weight = Decimal('0.00')
        
        for rating in kpi_ratings:
            if rating.kpi.weight_percentage:
                total_score += rating.score * (rating.kpi.weight_percentage / Decimal('100'))
                total_weight += rating.kpi.weight_percentage
        
        if total_weight > 0:
            self.overall_score = total_score
            self.save(update_fields=['overall_score'])
        
        return self.overall_score


class PerformanceKPIRating(BaseModel):
    """Individual KPI ratings within a performance review"""
    review = models.ForeignKey(PerformanceReview, on_delete=models.CASCADE, related_name='kpi_ratings')
    kpi = models.ForeignKey(PerformanceKPI, on_delete=models.PROTECT)
    
    score = models.DecimalField(max_digits=3, decimal_places=1)  # 1.0 to 5.0
    comments = models.TextField(blank=True)
    evidence = models.TextField(blank=True)  # Examples/evidence of performance
    
    class Meta:
        ordering = ['kpi__category', 'kpi__kpi_name']
        unique_together = ['review', 'kpi']
    
    def __str__(self):
        return f"{self.review.review_number} - {self.kpi.kpi_name}: {self.score}"


class StaffPerformanceSnapshot(BaseModel):
    """
    Aggregated operational analytics per staff member/role over a time window.
    Used to surface dashboard insights and feed HR performance reviews.
    """
    ROLE_CHOICES = Staff.PROFESSION_CHOICES
    
    staff = models.ForeignKey(Staff, on_delete=models.CASCADE, related_name='performance_snapshots')
    role = models.CharField(max_length=30, choices=ROLE_CHOICES)
    period_start = models.DateField()
    period_end = models.DateField()
    
    metrics = models.JSONField(default=dict, blank=True)
    productivity_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    quality_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    engagement_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    overall_index = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    data_points = models.PositiveIntegerField(default=0)
    sync_source = models.CharField(max_length=50, default='dashboard_sync')
    synced_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-period_end', '-created']
        unique_together = ['staff', 'role', 'period_start', 'period_end']
    
    def __str__(self):
        return f"{self.staff.user.get_full_name()} - {self.role} ({self.period_start} → {self.period_end})"
    
    @property
    def period_label(self):
        return f"{self.period_start.strftime('%d %b %Y')} — {self.period_end.strftime('%d %b %Y')}"


class DisciplinaryAction(BaseModel):
    """Staff disciplinary actions"""
    ACTION_TYPES = [
        ('verbal_warning', 'Verbal Warning'),
        ('written_warning', 'Written Warning'),
        ('suspension', 'Suspension'),
        ('termination', 'Termination'),
        ('other', 'Other'),
    ]
    
    action_number = models.CharField(max_length=50, unique=True)
    staff = models.ForeignKey(Staff, on_delete=models.CASCADE, related_name='disciplinary_actions')
    action_type = models.CharField(max_length=20, choices=ACTION_TYPES)
    
    incident_date = models.DateField()
    action_date = models.DateField(default=timezone.now)
    reported_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    description = models.TextField()
    action_taken = models.TextField()
    duration_days = models.PositiveIntegerField(null=True, blank=True)  # For suspensions
    
    is_resolved = models.BooleanField(default=False)
    resolution_date = models.DateField(null=True, blank=True)
    resolution_notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-action_date']
    
    def __str__(self):
        return f"{self.get_action_type_display()} - {self.staff.user.get_full_name()}"
    
    def save(self, *args, **kwargs):
        if not self.action_number:
            self.action_number = self.generate_action_number()
        super().save(*args, **kwargs)
    
    @staticmethod
    def generate_action_number():
        """Generate unique action number"""
        from datetime import datetime
        prefix = "DISC"
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        return f"{prefix}{timestamp}"


class TrainingProgram(BaseModel):
    """Training programs/courses catalog"""
    PROGRAM_TYPES = [
        ('mandatory', 'Mandatory'),
        ('optional', 'Optional'),
        ('certification', 'Certification'),
        ('cme', 'Continuing Medical Education'),
    ]
    
    program_code = models.CharField(max_length=50, unique=True)
    program_name = models.CharField(max_length=200)
    program_type = models.CharField(max_length=20, choices=PROGRAM_TYPES)
    category = models.CharField(max_length=100)
    
    description = models.TextField()
    objectives = models.TextField()
    duration_hours = models.DecimalField(max_digits=6, decimal_places=2)
    validity_months = models.PositiveIntegerField(null=True, blank=True)  # For certifications
    
    provider = models.CharField(max_length=200)
    cost_per_person = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    max_participants = models.PositiveIntegerField(null=True, blank=True)
    
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['program_name']
    
    def __str__(self):
        return f"{self.program_code} - {self.program_name}"


class TrainingRecord(BaseModel):
    """Staff training records - enhanced"""
    record_number = models.CharField(max_length=50, unique=True)
    staff = models.ForeignKey(Staff, on_delete=models.CASCADE, related_name='training_records')
    program = models.ForeignKey(TrainingProgram, on_delete=models.PROTECT, null=True, blank=True, related_name='records')
    
    training_title = models.CharField(max_length=200)
    training_type = models.CharField(max_length=100)
    provider = models.CharField(max_length=200)
    location = models.CharField(max_length=200, blank=True)
    
    start_date = models.DateField()
    end_date = models.DateField()
    duration_hours = models.DecimalField(max_digits=6, decimal_places=2)
    
    # Assessment
    assessment_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    passed = models.BooleanField(default=True)
    
    # Certificate
    certificate_issued = models.BooleanField(default=False)
    certificate_number = models.CharField(max_length=100, blank=True)
    certificate_file = models.FileField(upload_to='training_certificates/', null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)  # For certifications
    
    cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    funded_by = models.CharField(max_length=100, choices=[
        ('hospital', 'Hospital'),
        ('self', 'Self-Funded'),
        ('sponsor', 'External Sponsor'),
    ], default='hospital')
    
    status = models.CharField(max_length=20, choices=[
        ('scheduled', 'Scheduled'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ], default='scheduled')
    
    trainer_name = models.CharField(max_length=200, blank=True)
    feedback = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-start_date']
    
    def __str__(self):
        return f"{self.training_title} - {self.staff.user.get_full_name()}"
    
    def save(self, *args, **kwargs):
        if not self.record_number:
            self.record_number = self.generate_record_number()
        super().save(*args, **kwargs)
    
    @staticmethod
    def generate_record_number():
        """Generate unique record number"""
        from datetime import datetime
        prefix = "TRN"
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        return f"{prefix}{timestamp}"


class StaffDocument(BaseModel):
    """Staff documents/files"""
    DOCUMENT_TYPES = [
        ('cv', 'CV/Resume'),
        ('certificate', 'Certificate'),
        ('qualification', 'Qualification'),
        ('contract', 'Contract'),
        ('id', 'ID Document'),
        ('license', 'License'),
        ('other', 'Other'),
    ]
    
    staff = models.ForeignKey(Staff, on_delete=models.CASCADE, related_name='documents')
    document_type = models.CharField(max_length=20, choices=DOCUMENT_TYPES)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    
    file = models.FileField(upload_to='staff_documents/')
    expiry_date = models.DateField(null=True, blank=True)
    
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-created']
    
    def __str__(self):
        return f"{self.title} - {self.staff.user.get_full_name()}"


class StaffNote(BaseModel):
    """General staff notes/remarks"""
    staff = models.ForeignKey(Staff, on_delete=models.CASCADE, related_name='notes')
    note_type = models.CharField(max_length=50, choices=[
        ('general', 'General'),
        ('warning', 'Warning'),
        ('commendation', 'Commendation'),
        ('medical', 'Medical'),
        ('other', 'Other'),
    ], default='general')
    
    title = models.CharField(max_length=200)
    content = models.TextField()
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    is_confidential = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-created']
    
    def __str__(self):
        return f"{self.title} - {self.staff.user.get_full_name()}"


class StaffShift(BaseModel):
    """Staff shift/schedule management"""
    SHIFT_TYPES = [
        ('day', 'Day Shift'),
        ('evening', 'Evening Shift'),
        ('night', 'Night Shift'),
        ('on_call', 'On-Call'),
        ('weekend', 'Weekend'),
    ]
    
    staff = models.ForeignKey(Staff, on_delete=models.CASCADE, related_name='shifts')
    shift_type = models.CharField(max_length=20, choices=SHIFT_TYPES)
    start_time = models.TimeField()
    end_time = models.TimeField()
    shift_date = models.DateField()
    
    location = models.ForeignKey('Ward', on_delete=models.SET_NULL, null=True, blank=True, related_name='shifts')
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='shifts')
    
    # Assignment details
    assigned_location = models.CharField(max_length=200, blank=True, help_text='Specific location/unit assignment')
    assigned_duties = models.TextField(blank=True, help_text='Specific duties for this shift')
    
    assigned_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='assigned_shifts')
    notes = models.TextField(blank=True)
    
    is_confirmed = models.BooleanField(default=False)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['shift_date', 'start_time']
    
    def __str__(self):
        return f"{self.staff.user.get_full_name()} - {self.shift_date} ({self.get_shift_type_display()})"


class ShiftTemplate(BaseModel):
    """Reusable shift templates"""
    name = models.CharField(max_length=100)
    shift_type = models.CharField(max_length=20, choices=StaffShift.SHIFT_TYPES)
    start_time = models.TimeField()
    end_time = models.TimeField()
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='shift_templates')
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} - {self.get_shift_type_display()}"


class LeaveRequestApproval(BaseModel):
    """Leave request approval workflow"""
    leave_request = models.ForeignKey('LeaveRequest', on_delete=models.CASCADE, related_name='approvals')
    approver = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    approval_level = models.PositiveIntegerField(default=1)  # 1=Supervisor, 2=HR, 3=Manager
    
    status = models.CharField(max_length=20, choices=[
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], default='pending')
    
    comments = models.TextField(blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['approval_level', '-created']
    
    def __str__(self):
        return f"Approval {self.approval_level} - {self.leave_request}"


class StaffQualification(BaseModel):
    """Staff qualifications and certifications"""
    staff = models.ForeignKey(Staff, on_delete=models.CASCADE, related_name='qualifications')
    qualification_type = models.CharField(max_length=100, choices=[
        ('degree', 'Degree'),
        ('diploma', 'Diploma'),
        ('certification', 'Certification'),
        ('license', 'License'),
        ('specialization', 'Specialization'),
    ])
    
    title = models.CharField(max_length=200)
    institution = models.CharField(max_length=200)
    issue_date = models.DateField()
    expiry_date = models.DateField(null=True, blank=True)
    
    certificate_number = models.CharField(max_length=100, blank=True)
    document = models.FileField(upload_to='qualifications/', blank=True, null=True)
    
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-issue_date']
    
    def __str__(self):
        return f"{self.title} - {self.staff.user.get_full_name()}"


class StaffMedicalChit(BaseModel):
    """
    Staff Medical Chit System
    Allows staff to apply for medical attention through their portal.
    HR approves, and medical staff can access approved chits.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending HR Approval'),
        ('approved', 'Approved - Ready for Medical Attention'),
        ('rejected', 'Rejected'),
        ('used', 'Used - Visit Created'),
        ('expired', 'Expired'),
    ]
    
    # Chit Information
    chit_number = models.CharField(
        max_length=50,
        unique=True,
        help_text="Unique chit identifier (e.g., CHIT-2024-001)"
    )
    staff = models.ForeignKey(
        Staff,
        on_delete=models.CASCADE,
        related_name='medical_chits'
    )
    
    # Application Details
    application_date = models.DateField(
        default=timezone.now,
        help_text="Date staff applied for medical chit"
    )
    reason = models.TextField(
        help_text="Reason for requiring medical attention"
    )
    symptoms = models.TextField(
        blank=True,
        help_text="Symptoms or medical condition description"
    )
    
    # Status and Approval
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    
    # HR Approval
    hr_approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_medical_chits',
        help_text="HR staff who approved this chit"
    )
    hr_approval_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date and time HR approved this chit"
    )
    hr_approval_notes = models.TextField(
        blank=True,
        help_text="HR approval notes or comments"
    )
    hr_rejection_reason = models.TextField(
        blank=True,
        help_text="Reason for rejection if rejected"
    )
    
    # Medical Visit
    encounter = models.ForeignKey(
        'Encounter',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='medical_chit',
        help_text="Visit/encounter created from this chit"
    )
    visit_created_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the visit was created at front desk"
    )
    visit_created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_visits_from_chits',
        help_text="Front desk staff who created the visit"
    )
    
    # Validity
    valid_until = models.DateField(
        null=True,
        blank=True,
        help_text="Chit validity expiration date (default: 7 days from approval)"
    )
    
    # SMS Tracking
    sms_sent_approval = models.BooleanField(
        default=False,
        help_text="SMS sent to staff when approved"
    )
    sms_sent_visit_ready = models.BooleanField(
        default=False,
        help_text="SMS sent when chit is ready for visit"
    )
    
    # Additional Information
    authorized_by_name = models.CharField(
        max_length=200,
        blank=True,
        help_text="Name of HR/Admin who authorized (for printing)"
    )
    authorized_by_signature = models.CharField(
        max_length=200,
        blank=True,
        help_text="Signature of authorizing person (for printing)"
    )
    
    class Meta:
        ordering = ['-application_date', '-created']
        verbose_name = 'Staff Medical Chit'
        verbose_name_plural = 'Staff Medical Chits'
        indexes = [
            models.Index(fields=['chit_number']),
            models.Index(fields=['status']),
            models.Index(fields=['staff', 'status']),
            models.Index(fields=['application_date']),
        ]
    
    def __str__(self):
        return f"{self.chit_number} - {self.staff.user.get_full_name()} ({self.get_status_display()})"
    
    def save(self, *args, **kwargs):
        if not self.chit_number:
            self.chit_number = self.generate_chit_number()
        if not self.valid_until and self.status == 'approved':
            from datetime import timedelta
            self.valid_until = (timezone.now().date() + timedelta(days=7))
        super().save(*args, **kwargs)
    
    @staticmethod
    def generate_chit_number():
        """Generate unique chit number: CHIT-YYYY-NNNN"""
        from datetime import datetime
        year = datetime.now().year
        prefix = f"CHIT-{year}-"
        
        # Get last chit for this year
        last_chit = StaffMedicalChit.objects.filter(
            chit_number__startswith=prefix
        ).order_by('-chit_number').first()
        
        if last_chit:
            try:
                seq = int(last_chit.chit_number.split('-')[-1])
                seq += 1
            except:
                seq = 1
        else:
            seq = 1
        
        return f"{prefix}{seq:04d}"
    
    def is_valid(self):
        """Check if chit is still valid"""
        if self.status != 'approved':
            return False
        if self.valid_until and timezone.now().date() > self.valid_until:
            return False
        if self.status == 'used':
            return False
        return True
    
    def can_create_visit(self):
        """Check if visit can be created from this chit"""
        return self.status == 'approved' and self.is_valid() and not self.encounter

