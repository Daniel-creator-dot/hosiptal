"""
Automatic Attendance Signals
Auto-track attendance when staff login via password or biometric
"""

from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver, Signal
from django.utils import timezone
from datetime import datetime, time
from .models_auto_attendance import StaffAttendance
from .models_hr import StaffShift


# Custom signal for biometric login
biometric_login_success = Signal()


def get_client_ip(request):
    """Get client IP address"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def determine_if_late(check_in_time, shift_start=None):
    """
    Determine if staff is late
    Returns (is_late, late_minutes)
    """
    # If shift assigned, use shift start time
    if shift_start:
        grace_period = 15  # 15 minutes grace period
        
        # Compare times
        check_in_dt = datetime.combine(datetime.today(), check_in_time)
        shift_start_dt = datetime.combine(datetime.today(), shift_start)
        
        if check_in_dt > shift_start_dt:
            late_seconds = (check_in_dt - shift_start_dt).total_seconds()
            late_minutes = int(late_seconds / 60)
            
            if late_minutes > grace_period:
                return True, late_minutes - grace_period
    
    # Default: Late if after 9 AM
    default_start = time(9, 0)  # 9:00 AM
    if check_in_time > default_start:
        check_in_dt = datetime.combine(datetime.today(), check_in_time)
        default_dt = datetime.combine(datetime.today(), default_start)
        late_minutes = int((check_in_dt - default_dt).total_seconds() / 60)
        
        if late_minutes > 15:  # 15 min grace
            return True, late_minutes - 15
    
    return False, 0


@receiver(user_logged_in)
def auto_create_attendance_on_login(sender, request, user, **kwargs):
    """
    Automatically create/update attendance when staff logs in with PASSWORD
    """
    # Check if user is staff
    if not hasattr(user, 'staff'):
        return
    
    staff = user.staff
    today = timezone.now().date()
    now_time = timezone.now().time()
    
    try:
        # Get or create attendance record for today
        attendance, created = StaffAttendance.objects.get_or_create(
            staff=staff,
            date=today,
            defaults={
                'login_method': 'password',
                'check_in_time': now_time,
                'status': 'present',
                'check_in_ip': get_client_ip(request) if request else None,
            }
        )
        
        if not created:
            # Update existing record
            attendance.last_login_time = timezone.now()
            attendance.login_count += 1
            
            # If first check-in time not set, set it now
            if not attendance.check_in_time:
                attendance.check_in_time = now_time
            
            attendance.save()
        
        # Find today's shift and check in
        try:
            shift = StaffShift.objects.filter(
                staff=staff,
                shift_date=today,
                is_deleted=False
            ).first()
            
            if shift and not shift.checked_in:
                # Auto check-in to shift
                shift.checked_in = True
                shift.check_in_time = timezone.now()
                shift.save()
                
                # Link shift to attendance
                attendance.assigned_shift = shift
                
                # Check if late
                is_late, late_mins = determine_if_late(now_time, shift.start_time)
                attendance.is_late = is_late
                attendance.late_minutes = late_mins
                
                if is_late:
                    attendance.status = 'late'
                
                attendance.save()
                
                print(f"[AUTO-ATTENDANCE] {staff} checked in to shift - {shift.get_shift_type_display()}")
        
        except Exception as e:
            print(f"[AUTO-ATTENDANCE] Shift check-in error: {e}")
        
        if created:
            print(f"[AUTO-ATTENDANCE] Created attendance for {staff} - Password login at {now_time.strftime('%H:%M')}")
        else:
            print(f"[AUTO-ATTENDANCE] Updated attendance for {staff} - Login #{attendance.login_count}")
    
    except Exception as e:
        print(f"[AUTO-ATTENDANCE ERROR] Failed to create attendance: {e}")


@receiver(biometric_login_success)
def auto_create_attendance_on_biometric(sender, user, method='biometric', **kwargs):
    """
    Automatically create/update attendance when staff logs in with BIOMETRIC
    """
    # Check if user is staff
    if not hasattr(user, 'staff'):
        return
    
    staff = user.staff
    today = timezone.now().date()
    now_time = timezone.now().time()
    
    try:
        # Determine biometric method
        login_method = 'biometric'
        if method == 'fingerprint':
            login_method = 'biometric_fingerprint'
        
        # Get or create attendance record for today
        attendance, created = StaffAttendance.objects.get_or_create(
            staff=staff,
            date=today,
            defaults={
                'login_method': login_method,
                'check_in_time': now_time,
                'status': 'present',
            }
        )
        
        if not created:
            # Update existing record (might have logged in with password earlier)
            attendance.last_login_time = timezone.now()
            attendance.login_count += 1
            
            # If first check-in time not set, set it now
            if not attendance.check_in_time:
                attendance.check_in_time = now_time
            
            # Update method if biometric (more secure)
            if attendance.login_method == 'password':
                attendance.login_method = login_method
            
            attendance.save()
        
        # Find today's shift and check in
        try:
            shift = StaffShift.objects.filter(
                staff=staff,
                shift_date=today,
                is_deleted=False
            ).first()
            
            if shift and not shift.checked_in:
                # Auto check-in to shift
                shift.checked_in = True
                shift.check_in_time = timezone.now()
                shift.save()
                
                # Link shift to attendance
                attendance.assigned_shift = shift
                
                # Check if late
                is_late, late_mins = determine_if_late(now_time, shift.start_time)
                attendance.is_late = is_late
                attendance.late_minutes = late_mins
                
                if is_late:
                    attendance.status = 'late'
                
                attendance.save()
                
                print(f"[BIOMETRIC-ATTENDANCE] {staff} checked in via {method} - {shift.get_shift_type_display()}")
        
        except Exception as e:
            print(f"[BIOMETRIC-ATTENDANCE] Shift check-in error: {e}")
        
        if created:
            print(f"[BIOMETRIC-ATTENDANCE] Created attendance for {staff} - {method} at {now_time.strftime('%H:%M')}")
        else:
            print(f"[BIOMETRIC-ATTENDANCE] Updated attendance for {staff} - Login #{attendance.login_count}")
    
    except Exception as e:
        print(f"[BIOMETRIC-ATTENDANCE ERROR] Failed to create attendance: {e}")


def mark_attendance_manually(staff, date, status='present', notes=''):
    """
    Manual attendance marking (for admin/HR)
    """
    attendance, created = StaffAttendance.objects.get_or_create(
        staff=staff,
        date=date,
        defaults={
            'login_method': 'manual',
            'status': status,
            'notes': notes,
        }
    )
    
    if not created:
        attendance.status = status
        attendance.notes = notes
        attendance.save()
    
    return attendance


def auto_checkout_staff(staff):
    """
    Auto check-out staff (can be called at end of day)
    """
    today = timezone.now().date()
    now_time = timezone.now().time()
    
    try:
        attendance = StaffAttendance.objects.get(
            staff=staff,
            date=today,
            is_deleted=False
        )
        
        if not attendance.check_out_time:
            attendance.check_out_time = now_time
            attendance.save()
            
            # Also checkout from shift
            if attendance.assigned_shift:
                attendance.assigned_shift.check_out_time = timezone.now()
                attendance.assigned_shift.save()
            
            print(f"[AUTO-CHECKOUT] {staff} checked out at {now_time.strftime('%H:%M')}")
            return True
    
    except StaffAttendance.DoesNotExist:
        print(f"[AUTO-CHECKOUT] No attendance record for {staff} today")
        return False


def get_staff_attendance_stats(staff, month=None, year=None):
    """
    Get attendance statistics for a staff member
    """
    if not month:
        month = timezone.now().month
    if not year:
        year = timezone.now().year
    
    records = StaffAttendance.objects.filter(
        staff=staff,
        date__month=month,
        date__year=year,
        is_deleted=False
    )
    
    stats = {
        'total_days': records.count(),
        'present_days': records.filter(status='present').count(),
        'absent_days': records.filter(status='absent').count(),
        'late_days': records.filter(is_late=True).count(),
        'leave_days': records.filter(status='on_leave').count(),
        'total_hours': sum(r.working_hours for r in records),
        'average_check_in': None,
        'attendance_rate': 0.0,
    }
    
    # Calculate attendance rate
    if stats['total_days'] > 0:
        stats['attendance_rate'] = (stats['present_days'] / stats['total_days']) * 100
    
    return stats








