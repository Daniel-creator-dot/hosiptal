"""
Department Budgeting System
Comprehensive budget management for hospital departments
"""

from django.db import models
from django.core.validators import MinValueValidator
from django.utils import timezone
from django.db.models import Sum, Q
from decimal import Decimal
from .models import BaseModel, Department, Staff
from django.contrib.auth.models import User


class BudgetPeriod(BaseModel):
    """
    Budget periods (fiscal years, quarters, months)
    """
    PERIOD_TYPES = [
        ('annual', 'Annual'),
        ('quarterly', 'Quarterly'),
        ('monthly', 'Monthly'),
    ]
    
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('approved', 'Approved'),
        ('active', 'Active'),
        ('closed', 'Closed'),
    ]
    
    name = models.CharField(max_length=100, help_text='e.g., FY 2025, Q1 2025, January 2025')
    period_type = models.CharField(max_length=20, choices=PERIOD_TYPES)
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    
    # Budget totals
    total_budget = models.DecimalField(max_digits=15, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    total_allocated = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # Approval workflow
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_budget_periods')
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_budget_periods')
    approved_at = models.DateTimeField(null=True, blank=True)
    
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-start_date']
        unique_together = ['period_type', 'start_date']
    
    def __str__(self):
        return f"{self.name} ({self.get_period_type_display})"
    
    def approve(self, user):
        """Approve budget period"""
        self.status = 'approved'
        self.approved_by = user
        self.approved_at = timezone.now()
        self.save()
    
    def activate(self):
        """Activate budget period"""
        self.status = 'active'
        self.save()
    
    def close(self):
        """Close budget period"""
        self.status = 'closed'
        self.save()
    
    def get_utilization_percentage(self):
        """Calculate overall budget utilization"""
        if self.total_budget > 0:
            return (self.total_allocated / self.total_budget) * 100
        return 0


class DepartmentBudget(BaseModel):
    """
    Budget allocated to each department for a specific period
    """
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('active', 'Active'),
    ]
    
    budget_period = models.ForeignKey(BudgetPeriod, on_delete=models.CASCADE, related_name='department_budgets')
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='budgets')
    
    # Budget amounts
    allocated_amount = models.DecimalField(max_digits=15, decimal_places=2, validators=[MinValueValidator(0)])
    
    # Category breakdown
    personnel_budget = models.DecimalField(max_digits=15, decimal_places=2, default=0, help_text='Salaries, benefits')
    operational_budget = models.DecimalField(max_digits=15, decimal_places=2, default=0, help_text='Day-to-day operations')
    supplies_budget = models.DecimalField(max_digits=15, decimal_places=2, default=0, help_text='Medical supplies, equipment')
    capital_budget = models.DecimalField(max_digits=15, decimal_places=2, default=0, help_text='Major purchases, infrastructure')
    
    # Tracking
    spent_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    committed_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0, help_text='Committed but not spent')
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    
    # Workflow
    submitted_by = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True, related_name='submitted_budgets')
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_dept_budgets')
    approved_at = models.DateTimeField(null=True, blank=True)
    
    justification = models.TextField(blank=True, help_text='Budget justification/rationale')
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-budget_period__start_date', 'department__name']
        unique_together = ['budget_period', 'department']
    
    def __str__(self):
        return f"{self.department.name} - {self.budget_period.name} - GHS {self.allocated_amount}"
    
    def save(self, *args, **kwargs):
        """Auto-calculate total allocated amount from categories"""
        self.allocated_amount = (
            self.personnel_budget + 
            self.operational_budget + 
            self.supplies_budget + 
            self.capital_budget
        )
        super().save(*args, **kwargs)
    
    def get_available_amount(self):
        """Calculate available budget"""
        return self.allocated_amount - self.spent_amount - self.committed_amount
    
    def get_utilization_percentage(self):
        """Calculate budget utilization percentage"""
        if self.allocated_amount > 0:
            return (self.spent_amount / self.allocated_amount) * 100
        return 0
    
    def get_commitment_percentage(self):
        """Calculate committed percentage"""
        if self.allocated_amount > 0:
            return ((self.spent_amount + self.committed_amount) / self.allocated_amount) * 100
        return 0
    
    def is_overbudget(self):
        """Check if over budget"""
        return self.spent_amount > self.allocated_amount
    
    def is_near_limit(self, threshold=90):
        """Check if approaching budget limit"""
        return self.get_utilization_percentage() >= threshold
    
    def submit_for_approval(self, staff):
        """Submit budget for approval"""
        self.status = 'submitted'
        self.submitted_by = staff
        self.submitted_at = timezone.now()
        self.save()
    
    def approve(self, user):
        """Approve department budget"""
        self.status = 'approved'
        self.approved_by = user
        self.approved_at = timezone.now()
        self.save()
    
    def reject(self):
        """Reject budget"""
        self.status = 'rejected'
        self.save()
    
    def activate(self):
        """Activate budget"""
        self.status = 'active'
        self.save()


class BudgetLineItem(BaseModel):
    """
    Detailed line items within department budget
    """
    CATEGORY_CHOICES = [
        ('personnel', 'Personnel'),
        ('operational', 'Operational'),
        ('supplies', 'Supplies & Equipment'),
        ('capital', 'Capital Expenditure'),
        ('utilities', 'Utilities'),
        ('maintenance', 'Maintenance'),
        ('training', 'Training & Development'),
        ('other', 'Other'),
    ]
    
    department_budget = models.ForeignKey(DepartmentBudget, on_delete=models.CASCADE, related_name='line_items')
    
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    item_name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    
    budgeted_amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    spent_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Account code linkage
    account_code = models.CharField(max_length=50, blank=True, help_text='GL account code')
    
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['category', 'item_name']
    
    def __str__(self):
        return f"{self.item_name} - GHS {self.budgeted_amount}"
    
    def get_remaining(self):
        """Get remaining budget for this line item"""
        return self.budgeted_amount - self.spent_amount
    
    def get_utilization_percentage(self):
        """Calculate utilization percentage"""
        if self.budgeted_amount > 0:
            return (self.spent_amount / self.budgeted_amount) * 100
        return 0


class BudgetExpense(BaseModel):
    """
    Track expenses against department budgets
    """
    department_budget = models.ForeignKey(DepartmentBudget, on_delete=models.PROTECT, related_name='expenses')
    line_item = models.ForeignKey(BudgetLineItem, on_delete=models.SET_NULL, null=True, blank=True, related_name='expenses')
    
    expense_date = models.DateField(default=timezone.now)
    description = models.CharField(max_length=500)
    amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    
    # Reference to actual expense record
    payment_voucher = models.ForeignKey('hospital.PaymentVoucher', on_delete=models.SET_NULL, null=True, blank=True, related_name='budget_expenses')
    
    # Categorization
    expense_category = models.CharField(max_length=50)
    vendor = models.CharField(max_length=200, blank=True)
    reference_number = models.CharField(max_length=100, blank=True)
    
    # Approval
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-expense_date']
    
    def __str__(self):
        return f"{self.description} - GHS {self.amount} ({self.expense_date})"
    
    def save(self, *args, **kwargs):
        """Update budget spent amount when expense is saved"""
        is_new = self.pk is None
        super().save(*args, **kwargs)
        
        if is_new:
            # Update department budget spent amount
            self.department_budget.spent_amount += self.amount
            self.department_budget.save(update_fields=['spent_amount'])
            
            # Update line item spent amount if linked
            if self.line_item:
                self.line_item.spent_amount += self.amount
                self.line_item.save(update_fields=['spent_amount'])


class BudgetTransfer(BaseModel):
    """
    Transfer budget between departments or categories
    """
    STATUS_CHOICES = [
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('completed', 'Completed'),
    ]
    
    transfer_date = models.DateField(default=timezone.now)
    
    # Source
    from_department_budget = models.ForeignKey(DepartmentBudget, on_delete=models.CASCADE, related_name='transfers_out')
    from_line_item = models.ForeignKey(BudgetLineItem, on_delete=models.SET_NULL, null=True, blank=True, related_name='transfers_out')
    
    # Destination
    to_department_budget = models.ForeignKey(DepartmentBudget, on_delete=models.CASCADE, related_name='transfers_in')
    to_line_item = models.ForeignKey(BudgetLineItem, on_delete=models.SET_NULL, null=True, blank=True, related_name='transfers_in')
    
    amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Workflow
    requested_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='budget_transfer_requests')
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_budget_transfers')
    approved_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-transfer_date']
    
    def __str__(self):
        return f"Transfer GHS {self.amount} from {self.from_department_budget.department} to {self.to_department_budget.department}"
    
    def approve(self, user):
        """Approve and execute budget transfer"""
        if self.status == 'pending':
            # Deduct from source
            if self.from_line_item:
                self.from_line_item.budgeted_amount -= self.amount
                self.from_line_item.save()
            self.from_department_budget.allocated_amount -= self.amount
            self.from_department_budget.save()
            
            # Add to destination
            if self.to_line_item:
                self.to_line_item.budgeted_amount += self.amount
                self.to_line_item.save()
            self.to_department_budget.allocated_amount += self.amount
            self.to_department_budget.save()
            
            # Mark as approved
            self.status = 'completed'
            self.approved_by = user
            self.approved_at = timezone.now()
            self.save()
    
    def reject(self):
        """Reject transfer"""
        self.status = 'rejected'
        self.save()


class BudgetVariance(BaseModel):
    """
    Track and explain budget variances
    """
    VARIANCE_TYPES = [
        ('favorable', 'Favorable'),
        ('unfavorable', 'Unfavorable'),
    ]
    
    department_budget = models.ForeignKey(DepartmentBudget, on_delete=models.CASCADE, related_name='variances')
    line_item = models.ForeignKey(BudgetLineItem, on_delete=models.SET_NULL, null=True, blank=True)
    
    variance_date = models.DateField(default=timezone.now)
    variance_amount = models.DecimalField(max_digits=12, decimal_places=2)
    variance_percentage = models.DecimalField(max_digits=5, decimal_places=2)
    variance_type = models.CharField(max_length=20, choices=VARIANCE_TYPES)
    
    explanation = models.TextField(help_text='Explain reason for variance')
    corrective_action = models.TextField(blank=True, help_text='Actions to address variance')
    
    identified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    class Meta:
        ordering = ['-variance_date']
    
    def __str__(self):
        return f"{self.department_budget.department} - {self.variance_type} variance: GHS {self.variance_amount}"


class BudgetAlert(BaseModel):
    """
    Automated alerts for budget thresholds
    """
    ALERT_TYPES = [
        ('threshold', 'Threshold Reached'),
        ('overbudget', 'Over Budget'),
        ('underutilized', 'Under-Utilized'),
        ('variance', 'Significant Variance'),
    ]
    
    SEVERITY_LEVELS = [
        ('info', 'Information'),
        ('warning', 'Warning'),
        ('critical', 'Critical'),
    ]
    
    department_budget = models.ForeignKey(DepartmentBudget, on_delete=models.CASCADE, related_name='alerts')
    
    alert_type = models.CharField(max_length=20, choices=ALERT_TYPES)
    severity = models.CharField(max_length=20, choices=SEVERITY_LEVELS)
    message = models.TextField()
    threshold_percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    
    current_utilization = models.DecimalField(max_digits=5, decimal_places=2)
    
    # Status
    is_acknowledged = models.BooleanField(default=False)
    acknowledged_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    
    action_taken = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-created']
    
    def __str__(self):
        return f"{self.get_severity_display()} - {self.department_budget.department}: {self.get_alert_type_display()}"
    
    def acknowledge(self, user, action_taken=''):
        """Acknowledge alert"""
        self.is_acknowledged = True
        self.acknowledged_by = user
        self.acknowledged_at = timezone.now()
        self.action_taken = action_taken
        self.save()


class BudgetRevision(BaseModel):
    """
    Track budget revisions and amendments
    """
    department_budget = models.ForeignKey(DepartmentBudget, on_delete=models.CASCADE, related_name='revisions')
    
    revision_date = models.DateField(default=timezone.now)
    revision_number = models.IntegerField()
    
    # Changes
    old_allocated_amount = models.DecimalField(max_digits=15, decimal_places=2)
    new_allocated_amount = models.DecimalField(max_digits=15, decimal_places=2)
    change_amount = models.DecimalField(max_digits=15, decimal_places=2)
    
    reason = models.TextField()
    justification = models.TextField()
    
    # Approval
    requested_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='budget_revision_requests')
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_budget_revisions')
    approved_at = models.DateTimeField(null=True, blank=True)
    is_approved = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-revision_date', '-revision_number']
    
    def __str__(self):
        return f"Revision #{self.revision_number} - {self.department_budget.department} - GHS {self.change_amount}"
    
    @staticmethod
    def create_revision(department_budget, new_amount, reason, justification, user):
        """Create a new budget revision"""
        # Get next revision number
        last_revision = BudgetRevision.objects.filter(
            department_budget=department_budget
        ).order_by('-revision_number').first()
        
        next_number = (last_revision.revision_number + 1) if last_revision else 1
        
        revision = BudgetRevision.objects.create(
            department_budget=department_budget,
            revision_number=next_number,
            old_allocated_amount=department_budget.allocated_amount,
            new_allocated_amount=new_amount,
            change_amount=new_amount - department_budget.allocated_amount,
            reason=reason,
            justification=justification,
            requested_by=user
        )
        
        return revision


class BudgetReport(BaseModel):
    """
    Generated budget reports for analysis
    """
    REPORT_TYPES = [
        ('monthly', 'Monthly Budget Report'),
        ('quarterly', 'Quarterly Budget Report'),
        ('annual', 'Annual Budget Report'),
        ('variance', 'Variance Analysis'),
        ('department', 'Department Budget Summary'),
        ('comparative', 'Comparative Analysis'),
    ]
    
    report_type = models.CharField(max_length=50, choices=REPORT_TYPES)
    report_period = models.ForeignKey(BudgetPeriod, on_delete=models.CASCADE, related_name='reports')
    department = models.ForeignKey(Department, on_delete=models.CASCADE, null=True, blank=True, related_name='budget_reports')
    
    report_date = models.DateField(default=timezone.now)
    generated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    # Report data (stored as JSON)
    report_data = models.JSONField(default=dict)
    
    # Summary statistics
    total_budget = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_spent = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_variance = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    utilization_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-report_date']
    
    def __str__(self):
        return f"{self.get_report_type_display()} - {self.report_period.name}"













