"""
Advanced HR Views - Skills Matrix, Overtime, Staff Reports
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q, Count, Sum, Avg, F, ExpressionWrapper, DurationField
from django.http import JsonResponse
from datetime import date, timedelta, datetime
import json

from .models import Staff, Department
from .models_hr import (
    StaffShift, LeaveBalance, Payroll, StaffContract, 
    PerformanceReview, TrainingRecord, StaffQualification
)
from .models_advanced import LeaveRequest, Attendance


@login_required
def staff_skills_matrix(request):
    """Display staff skills and qualifications matrix"""
    
    # Get all active staff with their qualifications
    staff_list = Staff.objects.filter(
        is_active=True,
        is_deleted=False
    ).select_related('user', 'department').prefetch_related('qualifications')
    
    # Group by department
    departments = Department.objects.filter(
        is_deleted=False
    ).prefetch_related('staff')
    
    # Collect all unique qualification types
    qualification_types = StaffQualification.objects.filter(
        is_deleted=False,
        is_active=True
    ).values_list('qualification_type', flat=True).distinct()
    
    # Build skills matrix
    matrix_data = []
    for staff in staff_list:
        qualifications = staff.qualifications.filter(is_active=True, is_deleted=False)
        staff_data = {
            'staff': staff,
            'qualification_count': qualifications.count(),
            'qualifications': qualifications,
            'has_expired': qualifications.filter(
                expiry_date__isnull=False,
                expiry_date__lt=timezone.now().date()
            ).exists()
        }
        matrix_data.append(staff_data)
    
    # Statistics
    total_qualifications = StaffQualification.objects.filter(
        is_deleted=False,
        is_active=True
    ).count()
    
    avg_qualifications = matrix_data and sum(d['qualification_count'] for d in matrix_data) / len(matrix_data) or 0
    
    expiring_soon = StaffQualification.objects.filter(
        is_deleted=False,
        is_active=True,
        expiry_date__gte=timezone.now().date(),
        expiry_date__lte=timezone.now().date() + timedelta(days=90)
    ).count()
    
    context = {
        'title': 'Staff Skills Matrix',
        'matrix_data': matrix_data,
        'departments': departments,
        'qualification_types': qualification_types,
        'total_qualifications': total_qualifications,
        'avg_qualifications': round(avg_qualifications, 1),
        'expiring_soon': expiring_soon,
    }
    
    return render(request, 'hospital/hr/skills_matrix.html', context)


@login_required
def overtime_tracking(request):
    """Track and display staff overtime hours"""
    today = timezone.now().date()
    
    # Get date range from request or default to current month
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    if not start_date:
        start_date = date(today.year, today.month, 1)
    else:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    
    if not end_date:
        # Last day of current month
        if today.month == 12:
            end_date = date(today.year, 12, 31)
        else:
            end_date = date(today.year, today.month + 1, 1) - timedelta(days=1)
    else:
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    
    # Get all shifts in date range
    shifts = StaffShift.objects.filter(
        shift_date__gte=start_date,
        shift_date__lte=end_date,
        is_deleted=False
    ).select_related('staff__user', 'department')
    
    # Calculate overtime by staff
    staff_overtime = {}
    for shift in shifts:
        # Calculate shift duration
        start_datetime = datetime.combine(shift.shift_date, shift.start_time)
        end_datetime = datetime.combine(shift.shift_date, shift.end_time)
        
        # Handle overnight shifts
        if end_datetime < start_datetime:
            end_datetime += timedelta(days=1)
        
        duration = (end_datetime - start_datetime).total_seconds() / 3600  # hours
        
        # Standard work day is 8 hours
        overtime_hours = max(0, duration - 8)
        
        if shift.staff.id not in staff_overtime:
            staff_overtime[shift.staff.id] = {
                'staff': shift.staff,
                'total_hours': 0,
                'overtime_hours': 0,
                'shift_count': 0,
                'night_shifts': 0,
                'weekend_shifts': 0,
            }
        
        staff_overtime[shift.staff.id]['total_hours'] += duration
        staff_overtime[shift.staff.id]['overtime_hours'] += overtime_hours
        staff_overtime[shift.staff.id]['shift_count'] += 1
        
        # Count night shifts
        if shift.shift_type == 'night':
            staff_overtime[shift.staff.id]['night_shifts'] += 1
        
        # Count weekend shifts
        if shift.shift_date.weekday() >= 5:  # Saturday or Sunday
            staff_overtime[shift.staff.id]['weekend_shifts'] += 1
    
    # Sort by overtime hours
    overtime_list = sorted(
        staff_overtime.values(),
        key=lambda x: x['overtime_hours'],
        reverse=True
    )
    
    # Statistics
    total_overtime = sum(d['overtime_hours'] for d in overtime_list)
    total_staff_working = len(overtime_list)
    avg_overtime = total_overtime / total_staff_working if total_staff_working > 0 else 0
    
    # Top overtime workers
    top_overtime = overtime_list[:10]
    
    context = {
        'title': 'Overtime Tracking',
        'overtime_list': overtime_list,
        'top_overtime': top_overtime,
        'total_overtime': round(total_overtime, 1),
        'avg_overtime': round(avg_overtime, 1),
        'total_staff_working': total_staff_working,
        'start_date': start_date,
        'end_date': end_date,
        'date_range': f"{start_date.strftime('%b %d, %Y')} - {end_date.strftime('%b %d, %Y')}",
    }
    
    return render(request, 'hospital/hr/overtime_tracking.html', context)


@login_required
def staff_availability_dashboard(request):
    """Show real-time staff availability across departments"""
    today = timezone.now().date()
    
    # Get all active staff
    all_staff = Staff.objects.filter(
        is_active=True,
        is_deleted=False
    ).select_related('user', 'department')
    
    # Staff currently on leave
    staff_on_leave = LeaveRequest.objects.filter(
        status='approved',
        start_date__lte=today,
        end_date__gte=today,
        is_deleted=False
    ).values_list('staff_id', flat=True)
    
    # Staff on shift today
    staff_on_shift = StaffShift.objects.filter(
        shift_date=today,
        is_deleted=False
    ).values_list('staff_id', flat=True)
    
    # Build availability data by department
    departments = Department.objects.filter(is_deleted=False)
    availability_data = []
    
    for dept in departments:
        dept_staff = all_staff.filter(department=dept)
        total = dept_staff.count()
        
        on_leave = dept_staff.filter(id__in=staff_on_leave).count()
        on_shift = dept_staff.filter(id__in=staff_on_shift).count()
        available = total - on_leave
        
        availability_data.append({
            'department': dept,
            'total': total,
            'available': available,
            'on_leave': on_leave,
            'on_shift': on_shift,
            'availability_percentage': round((available / total * 100) if total > 0 else 0, 1)
        })
    
    # Overall statistics
    total_staff = all_staff.count()
    total_on_leave = len(staff_on_leave)
    total_available = total_staff - total_on_leave
    
    context = {
        'title': 'Staff Availability Dashboard',
        'availability_data': availability_data,
        'total_staff': total_staff,
        'total_available': total_available,
        'total_on_leave': total_on_leave,
        'availability_percentage': round((total_available / total_staff * 100) if total_staff > 0 else 0, 1),
        'today': today,
    }
    
    return render(request, 'hospital/hr/staff_availability.html', context)























