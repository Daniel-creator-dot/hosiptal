"""
Simple HOD (Head of Department) Model
Uses existing shift/roster models
"""

from django.db import models
from django.utils import timezone
from .models import BaseModel, Staff, Department


class HeadOfDepartment(BaseModel):
    """
    Designate staff as Head of Department
    Gives them authority to manage schedules using existing models
    """
    staff = models.OneToOneField(Staff, on_delete=models.CASCADE, related_name='hod_designation')
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='department_head')
    
    # Authority levels
    can_manage_schedules = models.BooleanField(default=True)
    can_approve_procurement = models.BooleanField(default=True)
    can_approve_leave = models.BooleanField(default=True)
    
    # Term
    appointed_date = models.DateField(default=timezone.now)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = 'Head of Department'
        verbose_name_plural = 'Heads of Department'
    
    def __str__(self):
        return f"{self.staff.user.get_full_name()} - HOD of {self.department.name}"

