"""
Staff Self-Service Portal Views
Staff can request leave, view performance, training, etc.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q, Sum
from decimal import Decimal
from datetime import date, timedelta
from .models import Staff
from .models_hr import (
    LeaveBalance, PerformanceReview, TrainingRecord, StaffContract,
    Payroll, StaffShift, StaffQualification, TrainingProgram
)
from .models_advanced import LeaveRequest, Attendance


@login_required
def staff_dashboard(request):
    """Staff self-service dashboard"""
    # Get staff record for current user
    try:
        staff = Staff.objects.get(user=request.user, is_deleted=False)
    except Staff.DoesNotExist:
        messages.error(request, 'Staff profile not found.')
        return redirect('hospital:dashboard')
    
    # Leave balance
    leave_balance, _ = LeaveBalance.objects.get_or_create(staff=staff)
    
    # Pending leave requests
    pending_leaves = LeaveRequest.objects.filter(
        staff=staff,
        status='pending',
        is_deleted=False
    ).count()
    
    # Upcoming leaves (approved)
    upcoming_leaves = LeaveRequest.objects.filter(
        staff=staff,
        status='approved',
        start_date__gte=date.today(),
        is_deleted=False
    ).order_by('start_date')[:5]
    
    # Recent trainings
    recent_trainings = TrainingRecord.objects.filter(
        staff=staff,
        is_deleted=False
    ).order_by('-start_date')[:5]
    
    # Upcoming shifts
    upcoming_shifts = StaffShift.objects.filter(
        staff=staff,
        shift_date__gte=date.today(),
        is_deleted=False
    ).order_by('shift_date', 'start_time')[:7]
    
    # Latest performance review
    latest_review = PerformanceReview.objects.filter(
        staff=staff,
        is_deleted=False
    ).order_by('-review_date').first()
    
    # This month attendance
    attendance_count = Attendance.objects.filter(
        staff=staff,
        date__month=date.today().month,
        date__year=date.today().year,
        status='present',
        is_deleted=False
    ).count()
    
    context = {
        'staff': staff,
        'leave_balance': leave_balance,
        'pending_leaves': pending_leaves,
        'upcoming_leaves': upcoming_leaves,
        'recent_trainings': recent_trainings,
        'upcoming_shifts': upcoming_shifts,
        'latest_review': latest_review,
        'attendance_count': attendance_count,
    }
    return render(request, 'hospital/staff_dashboard.html', context)


@login_required
def staff_leave_request_create(request):
    """Staff create leave request"""
    try:
        staff = Staff.objects.get(user=request.user, is_deleted=False)
    except Staff.DoesNotExist:
        messages.error(request, 'Staff profile not found.')
        return redirect('hospital:dashboard')
    
    if request.method == 'POST':
        leave_type = request.POST.get('leave_type')
        start_date_str = request.POST.get('start_date')
        end_date_str = request.POST.get('end_date')
        reason = request.POST.get('reason', '').strip()
        contact = request.POST.get('contact_during_leave', '').strip()
        covering_staff_id = request.POST.get('covering_staff')
        handover_notes = request.POST.get('handover_notes', '').strip()
        
        try:
            start_date = date.fromisoformat(start_date_str)
            end_date = date.fromisoformat(end_date_str)
            
            # Calculate working days (excluding weekends)
            days_requested = LeaveRequest.calculate_working_days(start_date, end_date)
            
            # Validation
            if start_date < date.today():
                messages.error(request, 'Start date cannot be in the past.')
                return redirect('hospital:staff_leave_request_create')
            
            if end_date < start_date:
                messages.error(request, 'End date must be after start date.')
                return redirect('hospital:staff_leave_request_create')
            
            if not reason:
                messages.error(request, 'Reason is required.')
                return redirect('hospital:staff_leave_request_create')
            
            # Check leave balance
            leave_balance, _ = LeaveBalance.objects.get_or_create(staff=staff)
            available_days = 0
            
            if leave_type == 'annual':
                available_days = leave_balance.annual_leave
            elif leave_type == 'sick':
                available_days = leave_balance.sick_leave
            elif leave_type == 'casual':
                available_days = leave_balance.casual_leave
            
            if leave_type in ['annual', 'sick', 'casual'] and days_requested > available_days:
                messages.warning(request, f'Insufficient leave balance. Available: {available_days} days, Requested: {days_requested} days.')
            
            # Get covering staff if specified
            covering_staff = None
            if covering_staff_id:
                try:
                    covering_staff = Staff.objects.get(pk=covering_staff_id, is_deleted=False)
                except Staff.DoesNotExist:
                    pass
            
            # Create leave request
            leave_request = LeaveRequest.objects.create(
                staff=staff,
                leave_type=leave_type,
                start_date=start_date,
                end_date=end_date,
                days_requested=days_requested,
                reason=reason,
                contact_during_leave=contact,
                covering_staff=covering_staff,
                handover_notes=handover_notes,
                status='draft'
            )
            
            # Handle attachment if provided
            if request.FILES.get('attachment'):
                leave_request.attachment = request.FILES['attachment']
                leave_request.save()
            
            messages.success(request, 'Leave request created! Click "Submit" to send for approval.')
            return redirect('hospital:staff_leave_detail', pk=leave_request.pk)
            
        except ValueError as e:
            messages.error(request, f'Invalid date format: {str(e)}')
            return redirect('hospital:staff_leave_request_create')
    
    # Get leave balance
    leave_balance, _ = LeaveBalance.objects.get_or_create(staff=staff)
    
    # Get other staff for covering options
    other_staff = Staff.objects.filter(
        is_active=True,
        is_deleted=False
    ).exclude(pk=staff.pk).select_related('user')
    
    context = {
        'staff': staff,
        'leave_balance': leave_balance,
        'other_staff': other_staff,
    }
    return render(request, 'hospital/staff_leave_request_create.html', context)


@login_required
def staff_leave_list(request):
    """List all staff's leave requests"""
    try:
        staff = Staff.objects.get(user=request.user, is_deleted=False)
    except Staff.DoesNotExist:
        messages.error(request, 'Staff profile not found.')
        return redirect('hospital:dashboard')
    
    status_filter = request.GET.get('status', '')
    
    leave_requests = LeaveRequest.objects.filter(
        staff=staff,
        is_deleted=False
    ).order_by('-created')
    
    if status_filter:
        leave_requests = leave_requests.filter(status=status_filter)
    
    # Get leave balance
    leave_balance, _ = LeaveBalance.objects.get_or_create(staff=staff)
    
    context = {
        'staff': staff,
        'leave_requests': leave_requests,
        'status_filter': status_filter,
        'leave_balance': leave_balance,
    }
    return render(request, 'hospital/staff_leave_list.html', context)


@login_required
def staff_leave_detail(request, pk):
    """View leave request details"""
    leave_request = get_object_or_404(LeaveRequest, pk=pk, is_deleted=False)
    
    # Verify ownership
    try:
        staff = Staff.objects.get(user=request.user, is_deleted=False)
        if leave_request.staff != staff and not request.user.is_staff:
            messages.error(request, 'Unauthorized access.')
            return redirect('hospital:staff_leave_list')
    except Staff.DoesNotExist:
        messages.error(request, 'Staff profile not found.')
        return redirect('hospital:dashboard')
    
    context = {
        'leave_request': leave_request,
        'staff': staff,
    }
    return render(request, 'hospital/staff_leave_detail.html', context)


@login_required
def staff_leave_submit(request, pk):
    """Submit leave request for approval"""
    leave_request = get_object_or_404(LeaveRequest, pk=pk, is_deleted=False)
    
    # Verify ownership
    try:
        staff = Staff.objects.get(user=request.user, is_deleted=False)
        if leave_request.staff != staff:
            messages.error(request, 'Unauthorized access.')
            return redirect('hospital:staff_leave_list')
    except Staff.DoesNotExist:
        messages.error(request, 'Staff profile not found.')
        return redirect('hospital:dashboard')
    
    if leave_request.submit():
        messages.success(request, 'Leave request submitted for approval!')
    else:
        messages.error(request, 'Leave request cannot be submitted.')
    
    return redirect('hospital:staff_leave_detail', pk=pk)


@login_required
def staff_leave_cancel(request, pk):
    """Cancel leave request"""
    leave_request = get_object_or_404(LeaveRequest, pk=pk, is_deleted=False)
    
    # Verify ownership
    try:
        staff = Staff.objects.get(user=request.user, is_deleted=False)
        if leave_request.staff != staff:
            messages.error(request, 'Unauthorized access.')
            return redirect('hospital:staff_leave_list')
    except Staff.DoesNotExist:
        messages.error(request, 'Staff profile not found.')
        return redirect('hospital:dashboard')
    
    if leave_request.status in ['draft', 'pending']:
        leave_request.status = 'cancelled'
        leave_request.save()
        messages.success(request, 'Leave request cancelled.')
    else:
        messages.error(request, 'Cannot cancel leave request.')
    
    return redirect('hospital:staff_leave_list')


@login_required
def staff_training_history(request):
    """View staff training history"""
    try:
        staff = Staff.objects.get(user=request.user, is_deleted=False)
    except Staff.DoesNotExist:
        messages.error(request, 'Staff profile not found.')
        return redirect('hospital:dashboard')
    
    trainings = TrainingRecord.objects.filter(
        staff=staff,
        is_deleted=False
    ).order_by('-start_date')
    
    # Statistics
    total_trainings = trainings.count()
    total_hours = trainings.aggregate(Sum('duration_hours'))['duration_hours__sum'] or Decimal('0.00')
    completed_trainings = trainings.filter(status='completed').count()
    
    # Upcoming trainings
    upcoming = trainings.filter(
        start_date__gte=date.today(),
        status='scheduled'
    )
    
    context = {
        'staff': staff,
        'trainings': trainings,
        'total_trainings': total_trainings,
        'total_hours': total_hours,
        'completed_trainings': completed_trainings,
        'upcoming': upcoming,
    }
    return render(request, 'hospital/staff_training_history.html', context)


@login_required
def staff_performance_reviews(request):
    """View staff performance reviews"""
    try:
        staff = Staff.objects.get(user=request.user, is_deleted=False)
    except Staff.DoesNotExist:
        messages.error(request, 'Staff profile not found.')
        return redirect('hospital:dashboard')
    
    reviews = PerformanceReview.objects.filter(
        staff=staff,
        is_deleted=False
    ).order_by('-review_date')
    
    context = {
        'staff': staff,
        'reviews': reviews,
    }
    return render(request, 'hospital/staff_performance_reviews.html', context)


@login_required
def staff_profile(request):
    """Staff profile with documents and qualifications"""
    try:
        staff = Staff.objects.get(user=request.user, is_deleted=False)
    except Staff.DoesNotExist:
        messages.error(request, 'Staff profile not found.')
        return redirect('hospital:dashboard')
    
    # Get related data
    contract = StaffContract.objects.filter(
        staff=staff,
        is_active=True,
        is_deleted=False
    ).first()
    
    qualifications = StaffQualification.objects.filter(
        staff=staff,
        is_deleted=False
    ).order_by('-issue_date')
    
    context = {
        'staff': staff,
        'contract': contract,
        'qualifications': qualifications,
    }
    return render(request, 'hospital/staff_profile.html', context)

