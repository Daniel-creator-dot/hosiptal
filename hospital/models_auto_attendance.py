"""
Automatic Attendance Tracking
Tracks staff attendance automatically upon login (password)
"""

from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
from .models import BaseModel, Staff
from datetime import datetime, time


class StaffAttendance(BaseModel):
    """
    Daily attendance record for staff
    Auto-created when staff logs in
    """
    ATTENDANCE_STATUS = [
        ('present', 'Present'),
        ('absent', 'Absent'),
        ('late', 'Late'),
        ('half_day', 'Half Day'),
        ('on_leave', 'On Leave'),
    ]
    
    LOGIN_METHOD = [
        ('password', 'Password Login'),
        ('manual', 'Manual Entry'),
    ]
    
    staff = models.ForeignKey(Staff, on_delete=models.CASCADE, related_name='attendance_records')
    date = models.DateField(default=timezone.now)
    
    # Login tracking
    login_method = models.CharField(max_length=30, choices=LOGIN_METHOD)
    first_login_time = models.DateTimeField(auto_now_add=True)
    last_login_time = models.DateTimeField(auto_now=True)
    login_count = models.IntegerField(default=1)  # Multiple logins same day
    
    # Check in/out
    check_in_time = models.TimeField(null=True, blank=True)
    check_out_time = models.TimeField(null=True, blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=ATTENDANCE_STATUS, default='present')
    is_late = models.BooleanField(default=False)
    late_minutes = models.IntegerField(default=0)
    
    # Location tracking
    check_in_location = models.CharField(max_length=200, blank=True)
    check_in_ip = models.GenericIPAddressField(null=True, blank=True)
    
    # Shift linkage
    assigned_shift = models.ForeignKey('hospital.StaffShift', on_delete=models.SET_NULL, 
                                      null=True, blank=True, related_name='attendance')
    
    # Notes
    notes = models.TextField(blank=True)
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='approved_attendance')
    
    class Meta:
        unique_together = ['staff', 'date']
        ordering = ['-date', 'staff']
        verbose_name = 'Staff Attendance'
        verbose_name_plural = 'Staff Attendance Records'
    
    def __str__(self):
        staff_name = f"{self.staff.first_name} {self.staff.last_name}" if hasattr(self.staff, 'first_name') else str(self.staff)
        return f"{staff_name} - {self.date} - {self.get_status_display()}"
    
    @property
    def working_hours(self):
        """Calculate total working hours"""
        if self.check_in_time and self.check_out_time:
            check_in = datetime.combine(self.date, self.check_in_time)
            check_out = datetime.combine(self.date, self.check_out_time)
            
            # Handle overnight shifts
            if check_out < check_in:
                check_out = check_out.replace(day=check_out.day + 1)
            
            duration = check_out - check_in
            return round(duration.total_seconds() / 3600, 2)
        return 0.0
    
    @property
    def is_checked_in(self):
        """Check if currently checked in"""
        return self.check_in_time and not self.check_out_time


class AttendanceSummary(BaseModel):
    """
    Monthly attendance summary for staff
    Auto-calculated for payroll and reporting
    """
    staff = models.ForeignKey(Staff, on_delete=models.CASCADE, related_name='monthly_attendance')
    month = models.IntegerField()
    year = models.IntegerField()
    
    # Counts
    days_present = models.IntegerField(default=0)
    days_absent = models.IntegerField(default=0)
    days_late = models.IntegerField(default=0)
    days_on_leave = models.IntegerField(default=0)
    
    # Hours
    total_hours_worked = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    overtime_hours = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Calculated
    attendance_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=100)
    
    class Meta:
        unique_together = ['staff', 'month', 'year']
        ordering = ['-year', '-month', 'staff']
        verbose_name = 'Attendance Summary'
        verbose_name_plural = 'Attendance Summaries'
    
    def __str__(self):
        staff_name = f"{self.staff.first_name} {self.staff.last_name}" if hasattr(self.staff, 'first_name') else str(self.staff)
        return f"{staff_name} - {self.month}/{self.year}"
    
    def calculate_summary(self):
        """Recalculate attendance summary"""
        from django.db.models import Sum, Count
        
        # Get all attendance for the month
        attendance_records = StaffAttendance.objects.filter(
            staff=self.staff,
            date__month=self.month,
            date__year=self.year,
            is_deleted=False
        )
        
        # Count by status
        self.days_present = attendance_records.filter(status='present').count()
        self.days_absent = attendance_records.filter(status='absent').count()
        self.days_late = attendance_records.filter(is_late=True).count()
        self.days_on_leave = attendance_records.filter(status='on_leave').count()
        
        # Calculate hours
        total_hours = 0
        for record in attendance_records:
            total_hours += record.working_hours
        
        self.total_hours_worked = total_hours
        
        # Calculate attendance percentage
        total_days = self.days_present + self.days_absent + self.days_late
        if total_days > 0:
            self.attendance_percentage = (self.days_present / total_days) * 100
        
        self.save()
        return self




















