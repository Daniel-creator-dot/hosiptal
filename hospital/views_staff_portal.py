"""
Staff Portal Views
Allows staff to view their information, apply for leave, and see notifications
"""
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.db.models import Q
from .models import Staff, Notification, Department
from .models_advanced import LeaveRequest
from .models_audit import ActivityLog, AuditLog
from .models_hr import PerformanceReview
import logging

logger = logging.getLogger(__name__)


@login_required
def staff_portal(request):
    """Main staff portal dashboard"""
    try:
        staff = Staff.objects.get(user=request.user, is_deleted=False)
    except Staff.DoesNotExist:
        # Auto-provision a minimal staff profile for superusers/admins so they can access the portal
        if request.user.is_superuser or request.user.is_staff:
            dept, _ = Department.objects.get_or_create(
                name="Administration",
                defaults={
                    "code": "ADMIN",
                    "description": "System Administration",
                },
            )
            staff = Staff.objects.create(
                user=request.user,
                profession='admin',
                department=dept,
                employee_id=f"ADM-{request.user.id}",
                phone_number=request.user.email or '',
            )
        else:
            messages.error(request, "Staff profile not found. Please contact HR.")
            return redirect('hospital:dashboard')
    
    # Get recent notifications
    recent_notifications = Notification.objects.filter(
        recipient=request.user,
        is_deleted=False
    ).order_by('-created')[:10]
    
    unread_notifications = Notification.objects.filter(
        recipient=request.user,
        is_read=False,
        is_deleted=False
    ).count()
    
    # Get recent activity logs for this staff
    recent_activities = ActivityLog.objects.filter(
        user=request.user
    ).order_by('-created')[:20]
    
    # Get pending leave requests
    pending_leaves = LeaveRequest.objects.filter(
        staff=staff,
        is_deleted=False
    ).order_by('-created')[:10]
    
    # Get approved leaves (upcoming)
    from datetime import timedelta
    upcoming_leaves = LeaveRequest.objects.filter(
        staff=staff,
        status='approved',
        start_date__gte=timezone.now().date(),
        is_deleted=False
    ).order_by('start_date')[:5]
    
    # Get pending medical chits
    from .models_hr import StaffMedicalChit
    pending_medical_chits = StaffMedicalChit.objects.filter(
        staff=staff,
        status='pending',
        is_deleted=False
    ).order_by('-created')[:5]
    
    # Get staff information
    staff_info = {
        'name': staff.user.get_full_name() or staff.user.username,
        'employee_id': staff.employee_id or 'N/A',
        'department': staff.department.name if staff.department else 'N/A',
        'profession': staff.profession or 'N/A',
        'phone': staff.phone_number or 'N/A',
        'email': staff.user.email or 'N/A',
    }
    
    context = {
        'title': 'Staff Portal',
        'staff': staff,
        'staff_info': staff_info,
        'recent_notifications': recent_notifications,
        'unread_notifications': unread_notifications,
        'recent_activities': recent_activities,
        'pending_leaves': pending_leaves,
        'upcoming_leaves': upcoming_leaves,
        'pending_medical_chits': pending_medical_chits,
    }
    
    return render(request, 'hospital/staff/portal.html', context)


@login_required
def staff_leave_request(request):
    """Staff leave request form"""
    try:
        staff = Staff.objects.get(user=request.user, is_deleted=False)
    except Staff.DoesNotExist:
        messages.error(request, "Staff profile not found. Please contact HR.")
        return redirect('hospital:staff_portal')
    
    if request.method == 'POST':
        try:
            start_date = request.POST.get('start_date')
            end_date = request.POST.get('end_date')
            leave_type = request.POST.get('leave_type', 'annual')
            reason = request.POST.get('reason', '')
            
            if not start_date or not end_date:
                messages.error(request, "Please provide both start and end dates.")
                return redirect('hospital:staff_leave_request')
            
            # Calculate days requested
            from datetime import datetime
            start = datetime.strptime(start_date, '%Y-%m-%d').date()
            end = datetime.strptime(end_date, '%Y-%m-%d').date()
            days_requested = LeaveRequest.calculate_working_days(start, end)
            
            # Create leave request
            leave_request = LeaveRequest.objects.create(
                staff=staff,
                start_date=start_date,
                end_date=end_date,
                leave_type=leave_type,
                reason=reason,
                days_requested=days_requested,
                status='pending',
                submitted_at=timezone.now(),
            )
            
            # Create notification for HR
            from django.contrib.auth.models import User
            hr_users = User.objects.filter(
                Q(is_staff=True) | Q(is_superuser=True)
            ).filter(
                Q(staff__department__name__icontains='hr') | Q(staff__profession__icontains='hr')
            )
            
            # If no HR users found, notify all admins
            if not hr_users.exists():
                hr_users = User.objects.filter(Q(is_staff=True) | Q(is_superuser=True))[:5]
            
            for hr_user in hr_users:
                Notification.objects.create(
                    recipient=hr_user,
                    notification_type='info',
                    title=f'New Leave Request from {staff.user.get_full_name()}',
                    message=f'{staff.user.get_full_name()} ({staff.employee_id or staff.user.username}) has requested {leave_type.replace("_", " ").title()} leave from {start_date} to {end_date} ({days_requested} days). Reason: {reason[:100] if reason else "No reason provided"}',
                    related_object_id=leave_request.id,
                    related_object_type='LeaveRequest',
                )
            
            # Also notify the staff member
            Notification.objects.create(
                recipient=request.user,
                notification_type='success',
                title='Leave Request Submitted',
                message=f'Your {leave_type.replace("_", " ").title()} leave request from {start_date} to {end_date} has been submitted and is pending HR approval.',
                related_object_id=leave_request.id,
                related_object_type='LeaveRequest',
            )
            
            messages.success(request, f"Leave request submitted successfully. HR will review it shortly. You will be notified once it's reviewed.")
            return redirect('hospital:staff_portal')
            
        except Exception as e:
            logger.error(f"Error creating leave request: {e}", exc_info=True)
            messages.error(request, f"Error submitting leave request: {str(e)}")
    
    # Get leave types from model
    LEAVE_TYPES = LeaveRequest.LEAVE_TYPES
    
    context = {
        'title': 'Apply for Leave',
        'staff': staff,
        'leave_types': LEAVE_TYPES,
    }
    
    return render(request, 'hospital/staff/leave_request.html', context)


@login_required
def staff_leave_history(request):
    """Staff leave history"""
    try:
        staff = Staff.objects.get(user=request.user, is_deleted=False)
    except Staff.DoesNotExist:
        messages.error(request, "Staff profile not found.")
        return redirect('hospital:staff_portal')
    
    leave_requests = LeaveRequest.objects.filter(
        staff=staff,
        is_deleted=False
    ).order_by('-created')
    
    context = {
        'title': 'My Leave History',
        'staff': staff,
        'leave_requests': leave_requests,
    }
    
    return render(request, 'hospital/staff/leave_history.html', context)


@login_required
def staff_activities(request):
    """Staff activity log"""
    try:
        staff = Staff.objects.get(user=request.user, is_deleted=False)
    except Staff.DoesNotExist:
        messages.error(request, "Staff profile not found.")
        return redirect('hospital:staff_portal')
    
    # Get all activities for this user
    activities = ActivityLog.objects.filter(
        user=request.user
    ).order_by('-created')
    
    # Get audit logs related to this staff
    audit_logs = AuditLog.objects.filter(
        user=request.user
    ).order_by('-created')
    
    context = {
        'title': 'My Activities',
        'staff': staff,
        'activities': activities[:50],  # Limit to 50 most recent
        'audit_logs': audit_logs[:50],
    }
    
    return render(request, 'hospital/staff/activities.html', context)


@login_required
def staff_notifications(request):
    """Staff notifications page"""
    try:
        staff = Staff.objects.get(user=request.user, is_deleted=False)
    except Staff.DoesNotExist:
        messages.error(request, "Staff profile not found.")
        return redirect('hospital:staff_portal')
    
    notifications = Notification.objects.filter(
        recipient=request.user,
        is_deleted=False
    ).order_by('-created')
    
    unread_count = notifications.filter(is_read=False).count()
    
    context = {
        'title': 'My Notifications',
        'staff': staff,
        'notifications': notifications,
        'unread_count': unread_count,
    }
    
    return render(request, 'hospital/staff/notifications.html', context)


@login_required
@require_http_methods(["POST"])
def mark_notification_read_staff(request, notification_id):
    """Mark notification as read (staff portal)"""
    try:
        notification = Notification.objects.get(
            id=notification_id,
            recipient=request.user,
            is_deleted=False
        )
        notification.mark_as_read()
        return JsonResponse({'success': True})
    except Notification.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Notification not found'}, status=404)


@login_required
@require_http_methods(["POST"])
def mark_all_notifications_read_staff(request):
    """Mark all notifications as read (staff portal)"""
    Notification.objects.filter(
        recipient=request.user,
        is_read=False,
        is_deleted=False
    ).update(is_read=True, read_at=timezone.now())
    
    messages.success(request, "All notifications marked as read.")
    return redirect('hospital:staff_notifications')


@login_required
def staff_performance_reviews(request):
    """Staff performance reviews list"""
    try:
        staff = Staff.objects.get(user=request.user, is_deleted=False)
    except Staff.DoesNotExist:
        messages.error(request, "Staff profile not found.")
        return redirect('hospital:staff_portal')
    
    reviews = PerformanceReview.objects.filter(
        staff=staff,
        is_deleted=False
    ).select_related('reviewed_by', 'reviewed_by__user').order_by('-review_date')
    
    context = {
        'title': 'My Performance Reviews',
        'staff': staff,
        'reviews': reviews,
    }
    
    return render(request, 'hospital/staff_performance_reviews.html', context)


@login_required
def my_profile(request):
    """Allow users to view their own profile"""
    try:
        staff = Staff.objects.select_related('user', 'department').get(
            user=request.user, 
            is_deleted=False
        )
    except Staff.DoesNotExist:
        messages.error(request, "Staff profile not found. Please contact HR.")
        return redirect('hospital:dashboard')
    
    # Get related data (similar to HR staff_detail but for own profile)
    from .models_hr import StaffContract, LeaveBalance, Payroll, PerformanceReview, TrainingRecord, StaffDocument
    
    try:
        contract = StaffContract.objects.get(staff=staff, is_active=True, is_deleted=False)
    except StaffContract.DoesNotExist:
        contract = None
    
    leave_balance = LeaveBalance.objects.filter(staff=staff, is_deleted=False).first()
    
    # Get recent payrolls (last 6 months)
    from datetime import timedelta
    six_months_ago = timezone.now() - timedelta(days=180)
    payrolls = Payroll.objects.filter(
        staff=staff,
        is_deleted=False,
        created__gte=six_months_ago
    ).select_related('period').order_by('-period__start_date')[:6]
    
    # Get recent performance reviews
    performance_reviews = PerformanceReview.objects.filter(
        staff=staff,
        is_deleted=False
    ).select_related('reviewed_by', 'reviewed_by__user').order_by('-review_date')[:5]
    
    # Get recent training records
    training_records = TrainingRecord.objects.filter(
        staff=staff,
        is_deleted=False
    ).order_by('-start_date')[:10]
    
    # Get active documents (only non-sensitive ones)
    documents = StaffDocument.objects.filter(
        staff=staff,
        is_active=True,
        is_deleted=False,
        document_type__in=['certificate', 'qualification', 'id_card', 'other']  # Exclude sensitive docs
    ).order_by('-created')[:10]
    
    # Get recent leave requests
    recent_leaves = LeaveRequest.objects.filter(
        staff=staff,
        is_deleted=False
    ).order_by('-created')[:10]
    
    # Calculate years of service
    years_of_service = None
    if staff.date_of_joining:
        delta = timezone.now().date() - staff.date_of_joining
        years_of_service = delta.days / 365.25
    
    context = {
        'title': 'My Profile',
        'staff': staff,
        'contract': contract,
        'leave_balance': leave_balance,
        'payrolls': payrolls,
        'performance_reviews': performance_reviews,
        'training_records': training_records,
        'documents': documents,
        'recent_leaves': recent_leaves,
        'years_of_service': years_of_service,
        'is_own_profile': True,  # Flag to show this is user's own profile
    }
    
    return render(request, 'hospital/staff/my_profile.html', context)
