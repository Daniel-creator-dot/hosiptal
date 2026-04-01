"""
HR Activities Management Views
Allow HR and Admin to create and manage hospital activities
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q
from django.core.paginator import Paginator
from datetime import datetime, timedelta

from .models import Staff, Department, Notification
from .models_hr_activities import HospitalActivity, ActivityRSVP
from .decorators import role_required
import logging

logger = logging.getLogger(__name__)


def _get_activity_recipients(activity):
    """Get staff who should receive SMS for this activity."""
    if activity.all_staff:
        return Staff.objects.filter(
            is_active=True,
            is_deleted=False
        ).select_related('user').distinct()
    staff_ids = set()
    if activity.departments.exists():
        dept_staff = Staff.objects.filter(
            department__in=activity.departments.all(),
            is_active=True,
            is_deleted=False
        ).values_list('id', flat=True)
        staff_ids.update(dept_staff)
    if activity.specific_staff.exists():
        specific_ids = activity.specific_staff.filter(
            is_active=True,
            is_deleted=False
        ).values_list('id', flat=True)
        staff_ids.update(specific_ids)
    return Staff.objects.filter(
        id__in=staff_ids,
        is_active=True,
        is_deleted=False
    ).select_related('user').distinct()


def _send_activity_created_sms(activity):
    """Send SMS to staff when HR creates an activity. Returns (sent_count, skipped_no_phone, attempted)."""
    sent = 0
    skipped_no_phone = 0
    attempted = 0
    try:
        from .services.sms_service import sms_service
        recipients = list(_get_activity_recipients(activity))
        if not recipients:
            logger.info(f"No recipients for activity '{activity.title}' (all_staff={activity.all_staff})")
            return 0, 0, 0
        time_str = activity.start_time.strftime('%I:%M %p') if activity.start_time else 'All day'
        date_str = activity.start_date.strftime('%b %d, %Y')
        loc_str = f" at {activity.location}" if activity.location else ""
        mandatory_str = " [MANDATORY]" if activity.is_mandatory else ""
        message = (
            f"PrimeCare: New activity - {activity.title}{mandatory_str}. "
            f"{date_str} {time_str}{loc_str}. "
            f"Check Staff Dashboard for details."
        )
        for staff in recipients:
            phone = (staff.phone_number or '').strip()
            if not phone or len(phone) < 9:
                skipped_no_phone += 1
                continue
            attempted += 1
            name = staff.user.get_full_name() or (staff.user.username if staff.user else '')
            try:
                sms_log = sms_service.send_sms(
                    phone,
                    message,
                    message_type='activity_reminder',
                    recipient_name=name,
                    related_object_id=str(activity.id),
                    related_object_type='HospitalActivity'
                )
                if sms_log and getattr(sms_log, 'status', '') == 'sent':
                    sent += 1
                elif sms_log and getattr(sms_log, 'status', '') == 'failed':
                    logger.warning(f"Activity SMS failed for {staff}: {getattr(sms_log, 'error_message', 'Unknown')}")
            except Exception as e:
                logger.warning(f"Failed to send activity SMS to {staff}: {e}")
        if sent:
            logger.info(f"Sent activity SMS to {sent} staff for '{activity.title}'")
        elif attempted and not sent:
            logger.warning(f"SMS attempted for {attempted} staff but all failed - check SMS_API_KEY and balance")
        elif skipped_no_phone and not attempted:
            logger.info(f"No SMS sent for '{activity.title}': {skipped_no_phone} staff have no phone number")
    except ImportError as e:
        logger.warning(f"SMS service not available for activity notifications: {e}")
    except Exception as e:
        logger.exception(f"Error sending activity SMS: {e}")
    return sent, skipped_no_phone, attempted


def _build_activity_message(activity):
    """Build title and message for activity notification."""
    time_str = activity.start_time.strftime('%I:%M %p') if activity.start_time else 'All day'
    date_str = activity.start_date.strftime('%b %d, %Y')
    loc_str = f" at {activity.location}" if activity.location else ""
    mandatory_str = " [MANDATORY]" if activity.is_mandatory else ""
    title = f"Activity: {activity.title}{mandatory_str}"
    message = f"{date_str} {time_str}{loc_str}. Check Staff Dashboard for details."
    return title, message


def _create_activity_notifications(activity, created_by_user=None):
    """Create in-app Notification for each staff recipient so they see it in the bell."""
    try:
        recipients = list(_get_activity_recipients(activity))
        # Include organizer so creator sees the notification
        if activity.organizer_id and activity.organizer.user_id:
            organizer_staff = activity.organizer
            if organizer_staff not in recipients:
                recipients.append(organizer_staff)
        title, message = _build_activity_message(activity)
        seen_users = set()
        for staff in recipients:
            if staff and staff.user_id and staff.user_id not in seen_users:
                seen_users.add(staff.user_id)
                Notification.objects.update_or_create(
                    recipient_id=staff.user_id,
                    notification_type='activity',
                    related_object_id=activity.id,
                    related_object_type='HospitalActivity',
                    defaults={'title': title, 'message': message, 'is_deleted': False}
                )
        # Ensure creator sees it even if not in departments/specific_staff
        if created_by_user and created_by_user.id not in seen_users:
            Notification.objects.update_or_create(
                recipient_id=created_by_user.id,
                notification_type='activity',
                related_object_id=activity.id,
                related_object_type='HospitalActivity',
                defaults={'title': title, 'message': message, 'is_deleted': False}
            )
            seen_users.add(created_by_user.id)
        logger.info(f"Created activity notifications for {len(seen_users)} staff for '{activity.title}'")
    except Exception as e:
        logger.warning(f"Failed to create activity notifications: {e}")


def _update_activity_notifications(activity):
    """Update existing activity notifications when activity is edited so staff see the change."""
    try:
        title, message = _build_activity_message(activity)
        updated = Notification.objects.filter(
            related_object_id=activity.id,
            related_object_type='HospitalActivity',
            is_deleted=False
        ).update(title=title, message=message)
        if updated:
            logger.info(f"Updated {updated} activity notifications for '{activity.title}'")
    except Exception as e:
        logger.warning(f"Failed to update activity notifications: {e}")


def _send_activity_updated_sms(activity):
    """Send SMS to staff when HR updates an activity. Returns (sent_count, skipped_no_phone, attempted)."""
    sent = 0
    skipped_no_phone = 0
    attempted = 0
    try:
        from .services.sms_service import sms_service
        recipients = list(_get_activity_recipients(activity))
        if not recipients:
            return 0, 0, 0
        time_str = activity.start_time.strftime('%I:%M %p') if activity.start_time else 'All day'
        date_str = activity.start_date.strftime('%b %d, %Y')
        loc_str = f" at {activity.location}" if activity.location else ""
        mandatory_str = " [MANDATORY]" if activity.is_mandatory else ""
        message = (
            f"PrimeCare: Activity UPDATED - {activity.title}{mandatory_str}. "
            f"New: {date_str} {time_str}{loc_str}. "
            f"Check Staff Dashboard for details."
        )
        for staff in recipients:
            phone = (staff.phone_number or '').strip()
            if not phone or len(phone) < 9:
                skipped_no_phone += 1
                continue
            attempted += 1
            name = staff.user.get_full_name() or (staff.user.username if staff.user else '')
            try:
                sms_log = sms_service.send_sms(
                    phone,
                    message,
                    message_type='activity_reminder',
                    recipient_name=name,
                    related_object_id=str(activity.id),
                    related_object_type='HospitalActivity'
                )
                if sms_log and getattr(sms_log, 'status', '') == 'sent':
                    sent += 1
            except Exception as e:
                logger.warning(f"Failed to send activity-updated SMS to {staff}: {e}")
        if sent:
            logger.info(f"Sent activity-updated SMS to {sent} staff for '{activity.title}'")
    except ImportError:
        pass
    except Exception as e:
        logger.warning(f"Error sending activity-updated SMS: {e}")
    return sent, skipped_no_phone, attempted


def is_hr_or_admin(user):
    """Check if user is HR Manager or Admin"""
    if user.is_superuser:
        return True
    if user.is_staff:
        # Check if user is in HR Manager group or has HR permissions
        if user.groups.filter(name__in=['HR Manager', 'Admin']).exists():
            return True
        # Check if user has HR-related profession
        try:
            if hasattr(user, 'staff') and user.staff.profession in ['hr_manager', 'admin']:
                return True
        except:
            pass
    return False


@login_required
def activity_list(request):
    """
    List all hospital activities
    """
    activities = HospitalActivity.objects.filter(
        is_deleted=False
    ).select_related('organizer', 'organizer__user').prefetch_related('departments', 'specific_staff').order_by('-start_date', '-start_time')
    
    # Filter by date if provided
    date_filter = request.GET.get('date')
    if date_filter:
        try:
            filter_date = datetime.strptime(date_filter, '%Y-%m-%d').date()
            activities = activities.filter(
                Q(start_date__lte=filter_date) & Q(end_date__gte=filter_date)
            )
        except:
            pass
    
    # Filter by type if provided
    activity_type = request.GET.get('type')
    if activity_type:
        activities = activities.filter(activity_type=activity_type)
    
    # Pagination
    paginator = Paginator(activities, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'activities': page_obj,
        'activity_types': HospitalActivity.ACTIVITY_TYPES,
        'can_create': is_hr_or_admin(request.user),
    }
    
    return render(request, 'hospital/hr/activity_list.html', context)


@login_required
def activity_create(request):
    """
    Create a new hospital activity (HR/Admin only)
    """
    if not is_hr_or_admin(request.user):
        messages.warning(request, 'Access denied. Only HR Managers and Administrators can create activities.')
        return redirect('hospital:activity_list')
    
    # Get current user's staff record for organizer
    organizer = None
    try:
        organizer = request.user.staff
    except:
        pass
    
    if request.method == 'POST':
        try:
            # Create activity
            activity = HospitalActivity.objects.create(
                title=request.POST.get('title'),
                description=request.POST.get('description', ''),
                activity_type=request.POST.get('activity_type', 'announcement'),
                priority=request.POST.get('priority', 'normal'),
                start_date=request.POST.get('start_date'),
                end_date=request.POST.get('end_date', request.POST.get('start_date')),
                start_time=request.POST.get('start_time') or None,
                end_time=request.POST.get('end_time') or None,
                location=request.POST.get('location', ''),
                organizer=organizer,
                all_staff=request.POST.get('all_staff') == 'on',
                is_mandatory=request.POST.get('is_mandatory') == 'on',
                requires_rsvp=request.POST.get('requires_rsvp') == 'on',
                max_participants=request.POST.get('max_participants') or None,
                external_link=request.POST.get('external_link', ''),
                is_published=request.POST.get('is_published', 'on') == 'on',
            )
            
            # Handle file upload
            if 'attachment' in request.FILES:
                activity.attachment = request.FILES['attachment']
                activity.save()
            
            # Handle departments
            department_ids = request.POST.getlist('departments')
            if department_ids:
                departments = Department.objects.filter(id__in=department_ids)
                activity.departments.set(departments)
            
            # Handle specific staff
            staff_ids = request.POST.getlist('specific_staff')
            if staff_ids:
                staff_members = Staff.objects.filter(id__in=staff_ids)
                activity.specific_staff.set(staff_members)
            
            # Create in-app notifications so staff see activity in the bell
            _create_activity_notifications(activity, created_by_user=request.user)
            # Send SMS notification to all relevant staff
            sms_sent, sms_skipped, sms_attempted = _send_activity_created_sms(activity)
            if sms_sent:
                messages.success(request, f'Activity "{activity.title}" created successfully! SMS sent to {sms_sent} staff.')
            elif sms_attempted and not sms_sent:
                messages.warning(request, f'Activity "{activity.title}" created. SMS failed - check SMS_API_KEY and account balance in settings.')
            elif sms_skipped:
                messages.success(request, f'Activity "{activity.title}" created successfully! Add phone numbers to Staff profiles (Admin → Staff) to enable SMS notifications.')
            else:
                messages.success(request, f'Activity "{activity.title}" created successfully!')
            return redirect('hospital:activity_detail_manage', pk=activity.id)
        
        except Exception as e:
            messages.error(request, f'Error creating activity: {str(e)}')
    
    # Get all departments and staff for selection
    departments = Department.objects.filter(is_deleted=False).order_by('name')
    all_staff = Staff.objects.filter(
        is_active=True,
        is_deleted=False
    ).select_related('user').order_by('user__first_name', 'user__last_name')
    
    # Set default dates
    today = timezone.now().date()
    default_start = today
    default_end = today
    
    context = {
        'activity_types': HospitalActivity.ACTIVITY_TYPES,
        'priority_levels': HospitalActivity.PRIORITY_LEVELS,
        'departments': departments,
        'all_staff': all_staff,
        'default_start': default_start,
        'default_end': default_end,
        'organizer': organizer,
    }
    
    return render(request, 'hospital/hr/activity_create.html', context)


@login_required
def activity_detail(request, pk):
    """
    View activity details
    """
    activity = get_object_or_404(HospitalActivity, id=pk, is_deleted=False)
    
    # Get RSVPs if activity requires RSVP
    rsvps = []
    if activity.requires_rsvp:
        rsvps = ActivityRSVP.objects.filter(
            activity=activity,
            is_deleted=False
        ).select_related('staff', 'staff__user').order_by('-responded_at')
    
    # Check if current user has RSVP'd
    user_rsvp = None
    try:
        if hasattr(request.user, 'staff'):
            user_rsvp = ActivityRSVP.objects.filter(
                activity=activity,
                staff=request.user.staff,
                is_deleted=False
            ).first()
    except:
        pass
    
    can_edit = is_hr_or_admin(request.user)
    
    context = {
        'activity': activity,
        'rsvps': rsvps,
        'user_rsvp': user_rsvp,
        'can_edit': can_edit,
    }
    
    return render(request, 'hospital/hr/activity_detail_manage.html', context)


@login_required
def activity_edit(request, pk):
    """
    Edit an existing activity (HR/Admin only)
    """
    if not is_hr_or_admin(request.user):
        messages.warning(request, 'Access denied. Only HR Managers and Administrators can edit activities.')
        return redirect('hospital:activity_detail_manage', pk=pk)
    
    activity = get_object_or_404(HospitalActivity, id=pk, is_deleted=False)
    
    if request.method == 'POST':
        try:
            activity.title = request.POST.get('title')
            activity.description = request.POST.get('description', '')
            activity.activity_type = request.POST.get('activity_type', 'announcement')
            activity.priority = request.POST.get('priority', 'normal')
            activity.start_date = request.POST.get('start_date')
            activity.end_date = request.POST.get('end_date', request.POST.get('start_date'))
            activity.start_time = request.POST.get('start_time') or None
            activity.end_time = request.POST.get('end_time') or None
            activity.location = request.POST.get('location', '')
            activity.all_staff = request.POST.get('all_staff') == 'on'
            activity.is_mandatory = request.POST.get('is_mandatory') == 'on'
            activity.requires_rsvp = request.POST.get('requires_rsvp') == 'on'
            activity.max_participants = request.POST.get('max_participants') or None
            activity.external_link = request.POST.get('external_link', '')
            activity.is_published = request.POST.get('is_published', 'on') == 'on'
            
            # Handle file upload
            if 'attachment' in request.FILES:
                activity.attachment = request.FILES['attachment']
            
            activity.save()
            
            # Handle departments
            department_ids = request.POST.getlist('departments')
            if department_ids:
                departments = Department.objects.filter(id__in=department_ids)
                activity.departments.set(departments)
            else:
                activity.departments.clear()
            
            # Handle specific staff
            staff_ids = request.POST.getlist('specific_staff')
            if staff_ids:
                staff_members = Staff.objects.filter(id__in=staff_ids)
                activity.specific_staff.set(staff_members)
            else:
                activity.specific_staff.clear()
            
            # Update in-app notifications so staff see the change in the bell
            _update_activity_notifications(activity)
            # Create notifications for any new recipients (staff added after initial create)
            _create_activity_notifications(activity, created_by_user=request.user)
            # Send activity-updated SMS to staff
            sms_sent, _, _ = _send_activity_updated_sms(activity)
            if sms_sent:
                messages.success(request, f'Activity "{activity.title}" updated successfully! SMS sent to {sms_sent} staff.')
            else:
                messages.success(request, f'Activity "{activity.title}" updated successfully!')
            return redirect('hospital:activity_detail_manage', pk=activity.id)
        
        except Exception as e:
            messages.error(request, f'Error updating activity: {str(e)}')
    
    # Get all departments and staff for selection
    departments = Department.objects.filter(is_deleted=False).order_by('name')
    all_staff = Staff.objects.filter(
        is_active=True,
        is_deleted=False
    ).select_related('user').order_by('user__first_name', 'user__last_name')
    
    # Get selected departments and staff
    selected_departments = list(activity.departments.values_list('id', flat=True))
    selected_staff = list(activity.specific_staff.values_list('id', flat=True))
    
    context = {
        'activity': activity,
        'activity_types': HospitalActivity.ACTIVITY_TYPES,
        'priority_levels': HospitalActivity.PRIORITY_LEVELS,
        'departments': departments,
        'all_staff': all_staff,
        'selected_departments': selected_departments,
        'selected_staff': selected_staff,
    }
    
    return render(request, 'hospital/hr/activity_edit.html', context)


@login_required
def activity_delete(request, pk):
    """
    Delete an activity (HR/Admin only)
    """
    if not is_hr_or_admin(request.user):
        messages.warning(request, 'Access denied.')
        return redirect('hospital:activity_list')
    
    activity = get_object_or_404(HospitalActivity, id=pk, is_deleted=False)
    
    if request.method == 'POST':
        activity.is_deleted = True
        activity.save()
        messages.success(request, f'Activity "{activity.title}" deleted successfully!')
        return redirect('hospital:activity_list')
    
    context = {
        'activity': activity,
    }
    
    return render(request, 'hospital/hr/activity_delete.html', context)


@login_required
def activity_rsvp(request, pk):
    """
    RSVP to an activity
    """
    activity = get_object_or_404(HospitalActivity, id=pk, is_deleted=False)
    
    if not activity.requires_rsvp:
        messages.warning(request, 'This activity does not require RSVP.')
        return redirect('hospital:activity_detail_manage', pk=pk)
    
    try:
        staff = request.user.staff
    except:
        messages.error(request, 'Staff profile not found.')
        return redirect('hospital:activity_detail_manage', pk=pk)
    
    if request.method == 'POST':
        response = request.POST.get('response', 'yes')
        comments = request.POST.get('comments', '')
        
        # Update or create RSVP
        rsvp, created = ActivityRSVP.objects.update_or_create(
            activity=activity,
            staff=staff,
            defaults={
                'response': response,
                'comments': comments,
            }
        )
        
        if created:
            messages.success(request, 'RSVP submitted successfully!')
        else:
            messages.success(request, 'RSVP updated successfully!')
        
        return redirect('hospital:activity_detail_manage', pk=pk)
    
    # Get existing RSVP if any
    existing_rsvp = ActivityRSVP.objects.filter(
        activity=activity,
        staff=staff,
        is_deleted=False
    ).first()
    
    context = {
        'activity': activity,
        'existing_rsvp': existing_rsvp,
    }
    
    return render(request, 'hospital/hr/activity_rsvp.html', context)

