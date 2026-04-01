"""
Automatic Attendance Signals
Auto-track attendance when staff login via password
"""

from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver
from django.utils import timezone
from datetime import datetime, time
from .models_auto_attendance import StaffAttendance
from .models_hr import StaffShift


def get_client_ip(request):
    """Get client IP address"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


LATE_GRACE_MINUTES = 30


def get_department_default_start(staff, check_in_time):
    """
    Provide department-based shift start times when explicit StaffShift is missing.
    Currently supports cashier double-shift windows: 8am-2pm and 2pm-8pm.
    """
    if not staff or not getattr(staff, 'department', None):
        return None
    
    dept_name = (staff.department.name or '').lower()
    if 'cashier' in dept_name:
        afternoon_start = time(14, 0)
        if check_in_time >= afternoon_start:
            return afternoon_start
        return time(8, 0)
    
    return None


def determine_if_late(staff, check_in_time, shift_start=None):
    """
    Determine if staff is late
    Returns (is_late, late_minutes)
    """
    # If shift assigned, use shift start time
    effective_start = shift_start or get_department_default_start(staff, check_in_time)
    
    if effective_start:
        grace_period = LATE_GRACE_MINUTES
        
        check_in_dt = datetime.combine(datetime.today(), check_in_time)
        shift_start_dt = datetime.combine(datetime.today(), effective_start)
        
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
        
        if late_minutes > LATE_GRACE_MINUTES:
            return True, late_minutes - LATE_GRACE_MINUTES
    
    return False, 0


def sync_attendance_calendar_record(attendance):
    """
    Ensure AttendanceCalendar has an entry that mirrors StaffAttendance
    """
    try:
        from decimal import Decimal
        from .models_hr_enhanced import AttendanceCalendar
        
        check_in_time = attendance.check_in_time
        if not check_in_time and attendance.first_login_time:
            check_in_time = attendance.first_login_time.time()
        
        working_hours = attendance.working_hours or 0
        total_hours = Decimal(str(working_hours)) if working_hours else Decimal('0.00')
        
        defaults = {
            'status': 'late' if attendance.is_late else attendance.status,
            'check_in_time': check_in_time,
            'check_out_time': attendance.check_out_time,
            'is_late': attendance.is_late,
            'late_by_minutes': max(attendance.late_minutes or 0, 0),
            'total_hours': total_hours,
            'notes': attendance.notes or 'Auto-synced from login activity',
        }
        
        record, created = AttendanceCalendar.objects.get_or_create(
            staff=attendance.staff,
            attendance_date=attendance.date,
            defaults=defaults
        )
        
        if not created:
            updated_fields = []
            for field, value in defaults.items():
                if value is not None and getattr(record, field) != value:
                    setattr(record, field, value)
                    updated_fields.append(field)
            
            # Only persist if anything changed
            if updated_fields:
                record.save(update_fields=updated_fields)
        
        return record
    
    except Exception as e:
        print(f"[AUTO-ATTENDANCE] Attendance calendar sync failed: {e}")
        return None


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
                is_late, late_mins = determine_if_late(staff, now_time, shift.start_time)
                attendance.is_late = is_late
                attendance.late_minutes = late_mins
                
                if is_late:
                    attendance.status = 'late'
                
                attendance.save()
                
                print(f"[AUTO-ATTENDANCE] {staff} checked in to shift - {shift.get_shift_type_display()}")
        
        except Exception as e:
            print(f"[AUTO-ATTENDANCE] Shift check-in error: {e}")
        
        if not attendance.is_late:
            is_late, late_mins = determine_if_late(staff, now_time, None)
            if is_late:
                attendance.is_late = True
                attendance.late_minutes = late_mins
                attendance.status = 'late'
                attendance.save(update_fields=['is_late', 'late_minutes', 'status'])
        
        sync_attendance_calendar_record(attendance)
        
        if created:
            print(f"[AUTO-ATTENDANCE] Created attendance for {staff} - Password login at {now_time.strftime('%H:%M')}")
        else:
            print(f"[AUTO-ATTENDANCE] Updated attendance for {staff} - Login #{attendance.login_count}")
    
    except Exception as e:
        print(f"[AUTO-ATTENDANCE ERROR] Failed to create attendance: {e}")


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
    
    sync_attendance_calendar_record(attendance)
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
            
            sync_attendance_calendar_record(attendance)
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








