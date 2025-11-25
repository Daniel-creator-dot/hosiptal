"""
World-Class HR System Enhancements
Enhanced contract management, calendars, and advanced HR features
"""
from django.db import models
from django.utils import timezone
from decimal import Decimal
from .models import BaseModel, Staff
from .models_contracts import Contract


class StaffEmploymentContract(BaseModel):
    """
    Link staff contracts to main contract management system
    Enables expiry tracking and alerts for employment contracts
    """
    staff = models.ForeignKey(Staff, on_delete=models.CASCADE, 
                             related_name='employment_contracts')
    contract = models.ForeignKey(Contract, on_delete=models.PROTECT,
                                related_name='staff_employments',
                                help_text="Main contract record with expiry tracking")
    
    # Employment specific details
    is_current = models.BooleanField(default=True, 
                                     help_text="Is this the current active contract?")
    probation_end_date = models.DateField(null=True, blank=True,
                                         help_text="End of probation period")
    
    # Salary details (can be different from general contract value)
    monthly_salary = models.DecimalField(max_digits=12, decimal_places=2)
    annual_salary = models.DecimalField(max_digits=12, decimal_places=2)
    
    # Benefits
    health_insurance = models.BooleanField(default=True)
    pension_included = models.BooleanField(default=True)
    housing_allowance = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    transport_allowance = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    
    # Leave entitlements
    annual_leave_days = models.PositiveIntegerField(default=21)
    sick_leave_days = models.PositiveIntegerField(default=10)
    
    # Notice period
    notice_period_days = models.PositiveIntegerField(default=30,
                                                     help_text="Notice period in days")
    
    class Meta:
        ordering = ['-is_current', '-created']
        verbose_name = 'Staff Employment Contract'
        verbose_name_plural = 'Staff Employment Contracts'
    
    def __str__(self):
        return f"{self.staff.user.get_full_name()} - {self.contract.contract_name}"
    
    @property
    def days_until_expiry(self):
        """Get days until contract expires from linked contract"""
        return self.contract.days_until_expiry
    
    @property
    def is_expiring_soon(self):
        """Check if contract is expiring soon"""
        return self.contract.is_expiring_soon


class AttendanceCalendar(BaseModel):
    """
    Daily attendance tracking with calendar view
    """
    ATTENDANCE_STATUS = [
        ('present', 'Present'),
        ('absent', 'Absent'),
        ('late', 'Late'),
        ('half_day', 'Half Day'),
        ('on_leave', 'On Leave'),
        ('off_duty', 'Off Duty'),
        ('public_holiday', 'Public Holiday'),
    ]
    
    staff = models.ForeignKey(Staff, on_delete=models.CASCADE, 
                             related_name='attendance_calendar')
    attendance_date = models.DateField()
    
    status = models.CharField(max_length=20, choices=ATTENDANCE_STATUS, default='present')
    
    # Time tracking
    check_in_time = models.TimeField(null=True, blank=True)
    check_out_time = models.TimeField(null=True, blank=True)
    
    # Late/Early
    is_late = models.BooleanField(default=False)
    late_by_minutes = models.PositiveIntegerField(default=0)
    
    is_early_departure = models.BooleanField(default=False)
    early_by_minutes = models.PositiveIntegerField(default=0)
    
    # Total hours
    total_hours = models.DecimalField(max_digits=4, decimal_places=2, default=Decimal('0.00'))
    overtime_hours = models.DecimalField(max_digits=4, decimal_places=2, default=Decimal('0.00'))
    
    # Notes
    notes = models.TextField(blank=True)
    marked_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, 
                                  null=True, related_name='marked_attendances')
    
    class Meta:
        ordering = ['-attendance_date', 'staff']
        unique_together = ['staff', 'attendance_date']
        verbose_name = 'Attendance Record'
        verbose_name_plural = 'Attendance Calendar'
        indexes = [
            models.Index(fields=['staff', 'attendance_date']),
            models.Index(fields=['attendance_date', 'status']),
        ]
    
    def __str__(self):
        return f"{self.staff.user.get_full_name()} - {self.attendance_date} ({self.get_status_display()})"
    
    def calculate_hours(self):
        """Calculate total hours worked"""
        if self.check_in_time and self.check_out_time:
            from datetime import datetime, timedelta
            
            check_in = datetime.combine(self.attendance_date, self.check_in_time)
            check_out = datetime.combine(self.attendance_date, self.check_out_time)
            
            if check_out < check_in:
                # Crossed midnight
                check_out += timedelta(days=1)
            
            duration = check_out - check_in
            total_hours = Decimal(str(duration.total_seconds() / 3600))
            
            self.total_hours = round(total_hours, 2)
            
            # Calculate overtime (more than 8 hours)
            if total_hours > 8:
                self.overtime_hours = round(total_hours - Decimal('8.00'), 2)
            else:
                self.overtime_hours = Decimal('0.00')
            
            self.save(update_fields=['total_hours', 'overtime_hours'])


class PublicHoliday(BaseModel):
    """
    Public holidays calendar
    """
    holiday_name = models.CharField(max_length=200)
    holiday_date = models.DateField(unique=True)
    description = models.TextField(blank=True)
    
    is_recurring = models.BooleanField(default=False,
                                       help_text="Does this holiday occur every year?")
    
    class Meta:
        ordering = ['-holiday_date']
        verbose_name = 'Public Holiday'
        verbose_name_plural = 'Public Holidays'
    
    def __str__(self):
        return f"{self.holiday_name} - {self.holiday_date}"


class StaffPerformanceGoal(BaseModel):
    """
    Individual performance goals for staff
    """
    STATUS_CHOICES = [
        ('not_started', 'Not Started'),
        ('in_progress', 'In Progress'),
        ('achieved', 'Achieved'),
        ('partially_achieved', 'Partially Achieved'),
        ('not_achieved', 'Not Achieved'),
    ]
    
    staff = models.ForeignKey(Staff, on_delete=models.CASCADE, related_name='performance_goals')
    goal_title = models.CharField(max_length=300)
    description = models.TextField()
    
    # Timeline
    set_date = models.DateField(default=timezone.now)
    target_date = models.DateField()
    completed_date = models.DateField(null=True, blank=True)
    
    # Progress tracking
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='not_started')
    progress_percentage = models.PositiveIntegerField(default=0,
                                                      help_text="0-100%")
    
    # Measurement
    target_value = models.CharField(max_length=200, blank=True,
                                   help_text="Target to achieve (e.g., '95% patient satisfaction')")
    achieved_value = models.CharField(max_length=200, blank=True)
    
    # Review
    set_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL,
                               null=True, related_name='goals_set')
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-target_date', '-set_date']
        verbose_name = 'Performance Goal'
        verbose_name_plural = 'Performance Goals'
    
    def __str__(self):
        return f"{self.staff.user.get_full_name()} - {self.goal_title}"
    
    @property
    def is_overdue(self):
        """Check if goal is overdue"""
        return self.target_date < timezone.now().date() and self.status not in ['achieved', 'partially_achieved']
    
    @property
    def days_remaining(self):
        """Calculate days until target date"""
        delta = self.target_date - timezone.now().date()
        return delta.days























