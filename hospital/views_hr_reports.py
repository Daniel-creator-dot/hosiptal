"""
HR Reports and Analytics Views
"""
from django.shortcuts import render
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import HttpResponse, JsonResponse
from django.db.models import Count, Q, Sum, Avg
from django.utils import timezone
from datetime import date, timedelta
from decimal import Decimal
import csv
from io import BytesIO

from .models import Staff, Department
from .models_hr import (
    PayrollPeriod, Payroll, LeaveBalance, PerformanceReview, 
    TrainingRecord, StaffContract, PayGrade
)
from .models_advanced import LeaveRequest, Attendance

try:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    EXCEL_AVAILABLE = True
except ImportError:
    EXCEL_AVAILABLE = False


def is_hr_or_admin(user):
    """Check if user is HR or Admin"""
    # Allow superusers, staff users, and users in Admin/HR groups
    if user.is_superuser or user.is_staff:
        return True
    return user.groups.filter(name__in=['Admin', 'HR']).exists()


@login_required
def hr_reports_dashboard(request):
    """Main HR Reports Dashboard"""
    today = date.today()
    current_month_start = date(today.year, today.month, 1)
    
    # Staff Statistics
    total_staff = Staff.objects.filter(is_deleted=False, is_active=True).count()
    staff_by_department = Staff.objects.filter(
        is_deleted=False, is_active=True
    ).values('department__name').annotate(count=Count('id')).order_by('-count')
    
    staff_by_profession = Staff.objects.filter(
        is_deleted=False, is_active=True
    ).values('profession').annotate(count=Count('id')).order_by('-count')
    
    # Leave Statistics
    pending_leaves = LeaveRequest.objects.filter(
        status='pending', is_deleted=False
    ).count()
    
    approved_leaves_this_month = LeaveRequest.objects.filter(
        status='approved',
        approved_at__gte=current_month_start,
        is_deleted=False
    ).count()
    
    staff_on_leave_today = LeaveRequest.objects.filter(
        status='approved',
        start_date__lte=today,
        end_date__gte=today,
        is_deleted=False
    ).count()
    
    # Contract Expiry
    contracts_expiring_soon = StaffContract.objects.filter(
        end_date__gte=today,
        end_date__lte=today + timedelta(days=90),
        is_deleted=False,
        is_active=True
    ).count()
    
    # Birthday Statistics
    staff_with_birthdays = Staff.objects.filter(
        is_deleted=False,
        is_active=True,
        date_of_birth__isnull=False
    ).count()
    
    # Training Statistics
    trainings_this_year = TrainingRecord.objects.filter(
        start_date__year=today.year,
        is_deleted=False
    ).count()
    
    # Performance Reviews
    reviews_this_year = PerformanceReview.objects.filter(
        review_date__year=today.year,
        is_deleted=False
    ).count()
    
    # Payroll Statistics
    try:
        latest_payroll = PayrollPeriod.objects.filter(
            is_deleted=False
        ).order_by('-end_date').first()
        
        if latest_payroll:
            total_payroll = Payroll.objects.filter(
                period=latest_payroll,
                is_deleted=False
            ).aggregate(
                total=Sum('net_pay')
            )['total'] or Decimal('0.00')
        else:
            total_payroll = Decimal('0.00')
    except:
        total_payroll = Decimal('0.00')
    
    # Leave breakdown by status
    all_leaves = LeaveRequest.objects.filter(is_deleted=False)
    rejected_leaves_count = all_leaves.filter(status='rejected').count()
    cancelled_leaves_count = all_leaves.filter(status='cancelled').count()
    
    # Gender distribution
    male_count = Staff.objects.filter(
        is_deleted=False, is_active=True, gender='male'
    ).count()
    female_count = Staff.objects.filter(
        is_deleted=False, is_active=True, gender='female'
    ).count()
    
    # Employment status
    permanent_count = Staff.objects.filter(
        is_deleted=False, is_active=True, employment_status='permanent'
    ).count()
    contract_count = Staff.objects.filter(
        is_deleted=False, is_active=True, employment_status='contract'
    ).count()
    probation_count = Staff.objects.filter(
        is_deleted=False, is_active=True, employment_status='probation'
    ).count()
    
    # Recent Activities
    recent_leaves = LeaveRequest.objects.filter(
        is_deleted=False
    ).select_related('staff__user', 'staff__department').order_by('-created')[:10]
    
    recent_reviews = PerformanceReview.objects.filter(
        is_deleted=False
    ).select_related('staff__user', 'reviewed_by__user').order_by('-review_date')[:10]
    
    context = {
        'total_staff': total_staff,
        'staff_by_department': staff_by_department,
        'staff_by_profession': staff_by_profession,
        'pending_leaves': pending_leaves,
        'approved_leaves_this_month': approved_leaves_this_month,
        'rejected_leaves_count': rejected_leaves_count,
        'cancelled_leaves_count': cancelled_leaves_count,
        'staff_on_leave_today': staff_on_leave_today,
        'contracts_expiring_soon': contracts_expiring_soon,
        'staff_with_birthdays': staff_with_birthdays,
        'trainings_this_year': trainings_this_year,
        'reviews_this_year': reviews_this_year,
        'total_payroll': total_payroll,
        'male_count': male_count,
        'female_count': female_count,
        'permanent_count': permanent_count,
        'contract_count': contract_count,
        'probation_count': probation_count,
        'recent_leaves': recent_leaves,
        'recent_reviews': recent_reviews,
        'excel_available': EXCEL_AVAILABLE,
    }
    
    return render(request, 'hospital/hr_reports_dashboard.html', context)


@login_required
def staff_list_report(request):
    """Staff List Report"""
    department_filter = request.GET.get('department', '')
    profession_filter = request.GET.get('profession', '')
    status_filter = request.GET.get('status', 'active')
    export_format = request.GET.get('export', '')
    
    staff = Staff.objects.filter(is_deleted=False).select_related('user', 'department')
    
    if status_filter == 'active':
        staff = staff.filter(is_active=True)
    elif status_filter == 'inactive':
        staff = staff.filter(is_active=False)
    
    if department_filter:
        staff = staff.filter(department_id=department_filter)
    
    if profession_filter:
        staff = staff.filter(profession=profession_filter)
    
    staff = staff.order_by('department__name', 'user__last_name')
    
    if export_format == 'csv':
        return export_staff_csv(staff)
    elif export_format == 'excel' and EXCEL_AVAILABLE:
        return export_staff_excel(staff)
    
    departments = Department.objects.filter(is_deleted=False).order_by('name')
    professions = Staff.PROFESSION_CHOICES
    
    context = {
        'staff_list': staff,
        'departments': departments,
        'professions': professions,
        'department_filter': department_filter,
        'profession_filter': profession_filter,
        'status_filter': status_filter,
        'excel_available': EXCEL_AVAILABLE,
    }
    
    return render(request, 'hospital/reports/staff_list_report.html', context)


@login_required
def leave_report(request):
    """Leave Report"""
    status_filter = request.GET.get('status', '')
    leave_type_filter = request.GET.get('leave_type', '')
    department_filter = request.GET.get('department', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    export_format = request.GET.get('export', '')
    
    leaves = LeaveRequest.objects.filter(
        is_deleted=False
    ).select_related('staff__user', 'staff__department', 'approved_by__user')
    
    if status_filter:
        leaves = leaves.filter(status=status_filter)
    
    if leave_type_filter:
        leaves = leaves.filter(leave_type=leave_type_filter)
    
    if department_filter:
        leaves = leaves.filter(staff__department_id=department_filter)
    
    if date_from:
        leaves = leaves.filter(start_date__gte=date_from)
    
    if date_to:
        leaves = leaves.filter(end_date__lte=date_to)
    
    leaves = leaves.order_by('-start_date')
    
    # Statistics
    total_days = leaves.aggregate(total=Sum('days_requested'))['total'] or 0
    approved_count = leaves.filter(status='approved').count()
    pending_count = leaves.filter(status='pending').count()
    rejected_count = leaves.filter(status='rejected').count()
    
    if export_format == 'csv':
        return export_leave_csv(leaves)
    elif export_format == 'excel' and EXCEL_AVAILABLE:
        return export_leave_excel(leaves)
    
    departments = Department.objects.filter(is_deleted=False).order_by('name')
    
    context = {
        'leaves': leaves,
        'departments': departments,
        'status_filter': status_filter,
        'leave_type_filter': leave_type_filter,
        'department_filter': department_filter,
        'date_from': date_from,
        'date_to': date_to,
        'total_days': total_days,
        'approved_count': approved_count,
        'pending_count': pending_count,
        'rejected_count': rejected_count,
        'leave_types': LeaveRequest.LEAVE_TYPES,
        'excel_available': EXCEL_AVAILABLE,
    }
    
    return render(request, 'hospital/reports/leave_report.html', context)


@login_required
def attendance_report(request):
    """Attendance Report"""
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    department_filter = request.GET.get('department', '')
    export_format = request.GET.get('export', '')
    
    attendance = Attendance.objects.filter(
        is_deleted=False
    ).select_related('staff__user', 'staff__department')
    
    if date_from:
        attendance = attendance.filter(date__gte=date_from)
    
    if date_to:
        attendance = attendance.filter(date__lte=date_to)
    
    if department_filter:
        attendance = attendance.filter(staff__department_id=department_filter)
    
    attendance = attendance.order_by('-date', 'staff__user__last_name')
    
    # Statistics
    present_count = attendance.filter(status='present').count()
    absent_count = attendance.filter(status='absent').count()
    late_count = attendance.filter(status='late').count()
    
    if export_format == 'csv':
        return export_attendance_csv(attendance)
    
    departments = Department.objects.filter(is_deleted=False).order_by('name')
    
    context = {
        'attendance': attendance,
        'departments': departments,
        'date_from': date_from,
        'date_to': date_to,
        'department_filter': department_filter,
        'present_count': present_count,
        'absent_count': absent_count,
        'late_count': late_count,
        'excel_available': EXCEL_AVAILABLE,
    }
    
    return render(request, 'hospital/reports/attendance_report.html', context)


@login_required
def payroll_report(request):
    """Payroll Report"""
    period_id = request.GET.get('period', '')
    department_filter = request.GET.get('department', '')
    export_format = request.GET.get('export', '')
    
    periods = PayrollPeriod.objects.filter(is_deleted=False).order_by('-end_date')
    
    if period_id:
        selected_period = PayrollPeriod.objects.filter(pk=period_id, is_deleted=False).first()
    else:
        selected_period = periods.first()
    
    payrolls = []
    total_gross = Decimal('0.00')
    total_deductions = Decimal('0.00')
    total_net = Decimal('0.00')
    
    if selected_period:
        payrolls = Payroll.objects.filter(
            period=selected_period,
            is_deleted=False
        ).select_related('staff__user', 'staff__department')
        
        if department_filter:
            payrolls = payrolls.filter(staff__department_id=department_filter)
        
        payrolls = payrolls.order_by('staff__user__last_name')
        
        # Calculate totals
        totals = payrolls.aggregate(
            total_gross=Sum('gross_pay'),
            total_deductions=Sum('total_deductions'),
            total_net=Sum('net_pay')
        )
        
        total_gross = totals['total_gross'] or Decimal('0.00')
        total_deductions = totals['total_deductions'] or Decimal('0.00')
        total_net = totals['total_net'] or Decimal('0.00')
    
    if export_format == 'csv':
        return export_payroll_csv(payrolls, selected_period)
    
    departments = Department.objects.filter(is_deleted=False).order_by('name')
    
    context = {
        'periods': periods,
        'selected_period': selected_period,
        'payrolls': payrolls,
        'departments': departments,
        'period_id': period_id,
        'department_filter': department_filter,
        'total_gross': total_gross,
        'total_deductions': total_deductions,
        'total_net': total_net,
        'excel_available': EXCEL_AVAILABLE,
    }
    
    return render(request, 'hospital/reports/payroll_report.html', context)


@login_required
def training_report(request):
    """Training Report"""
    year_filter = request.GET.get('year', str(date.today().year))
    department_filter = request.GET.get('department', '')
    export_format = request.GET.get('export', '')
    
    trainings = TrainingRecord.objects.filter(
        is_deleted=False
    ).select_related('staff__user', 'staff__department')
    
    if year_filter:
        trainings = trainings.filter(start_date__year=year_filter)
    
    if department_filter:
        trainings = trainings.filter(staff__department_id=department_filter)
    
    trainings = trainings.order_by('-start_date')
    
    # Statistics
    total_trainings = trainings.count()
    completed = trainings.filter(status='completed').count()
    
    if export_format == 'csv':
        return export_training_csv(trainings)
    
    departments = Department.objects.filter(is_deleted=False).order_by('name')
    years = range(date.today().year, date.today().year - 5, -1)
    
    context = {
        'trainings': trainings,
        'departments': departments,
        'years': years,
        'year_filter': year_filter,
        'department_filter': department_filter,
        'total_trainings': total_trainings,
        'completed': completed,
        'excel_available': EXCEL_AVAILABLE,
    }
    
    return render(request, 'hospital/reports/training_report.html', context)


@login_required
def performance_report(request):
    """Performance Review Report"""
    year_filter = request.GET.get('year', str(date.today().year))
    department_filter = request.GET.get('department', '')
    export_format = request.GET.get('export', '')
    
    reviews = PerformanceReview.objects.filter(
        is_deleted=False
    ).select_related('staff__user', 'staff__department', 'reviewed_by__user')
    
    if year_filter:
        reviews = reviews.filter(review_date__year=year_filter)
    
    if department_filter:
        reviews = reviews.filter(staff__department_id=department_filter)
    
    reviews = reviews.order_by('-review_date')
    
    # Statistics
    total_reviews = reviews.count()
    avg_score = reviews.aggregate(avg=Avg('overall_rating'))['avg'] or 0
    
    if export_format == 'csv':
        return export_performance_csv(reviews)
    
    departments = Department.objects.filter(is_deleted=False).order_by('name')
    years = range(date.today().year, date.today().year - 5, -1)
    
    context = {
        'reviews': reviews,
        'departments': departments,
        'years': years,
        'year_filter': year_filter,
        'department_filter': department_filter,
        'total_reviews': total_reviews,
        'avg_score': round(avg_score, 2),
        'excel_available': EXCEL_AVAILABLE,
    }
    
    return render(request, 'hospital/reports/performance_report.html', context)


# Export Functions
def export_staff_csv(staff_queryset):
    """Export staff list to CSV"""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="staff_list_{date.today()}.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Employee ID', 'Name', 'Department', 'Profession', 'Email', 'Phone', 'Date Joined', 'Status'])
    
    for staff in staff_queryset:
        writer.writerow([
            staff.employee_id or '-',
            staff.user.get_full_name(),
            staff.department.name if staff.department else '-',
            staff.get_profession_display(),
            staff.user.email,
            getattr(staff, 'phone_number', '-'),
            staff.date_of_joining.strftime('%Y-%m-%d') if staff.date_of_joining else '-',
            'Active' if staff.is_active else 'Inactive'
        ])
    
    return response


def export_staff_excel(staff_queryset):
    """Export staff list to Excel"""
    wb = Workbook()
    ws = wb.active
    ws.title = "Staff List"
    
    # Headers
    headers = ['Employee ID', 'Name', 'Department', 'Profession', 'Email', 'Phone', 'Date Joined', 'Status']
    ws.append(headers)
    
    # Style headers
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
        cell.alignment = Alignment(horizontal="center")
    
    # Data
    for staff in staff_queryset:
        ws.append([
            staff.employee_id or '-',
            staff.user.get_full_name(),
            staff.department.name if staff.department else '-',
            staff.get_profession_display(),
            staff.user.email,
            getattr(staff, 'phone_number', '-'),
            staff.date_of_joining.strftime('%Y-%m-%d') if staff.date_of_joining else '-',
            'Active' if staff.is_active else 'Inactive'
        ])
    
    # Adjust column widths
    for column in ws.columns:
        max_length = 0
        column_letter = column[0].column_letter
        for cell in column:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except:
                pass
        adjusted_width = min(max_length + 2, 50)
        ws.column_dimensions[column_letter].width = adjusted_width
    
    # Save to BytesIO
    output = BytesIO()
    wb.save(output)
    output.seek(0)
    
    response = HttpResponse(
        output.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="staff_list_{date.today()}.xlsx"'
    
    return response


def export_leave_csv(leave_queryset):
    """Export leave report to CSV"""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="leave_report_{date.today()}.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Request #', 'Staff Name', 'Department', 'Leave Type', 'Start Date', 'End Date', 'Days', 'Status', 'Approved By', 'Approved At'])
    
    for leave in leave_queryset:
        writer.writerow([
            leave.request_number or '-',
            leave.staff.user.get_full_name(),
            leave.staff.department.name if leave.staff.department else '-',
            leave.get_leave_type_display(),
            leave.start_date.strftime('%Y-%m-%d'),
            leave.end_date.strftime('%Y-%m-%d'),
            leave.days_requested,
            leave.get_status_display(),
            leave.approved_by.user.get_full_name() if leave.approved_by else '-',
            leave.approved_at.strftime('%Y-%m-%d %H:%M') if leave.approved_at else '-'
        ])
    
    return response


def export_leave_excel(leave_queryset):
    """Export leave report to Excel"""
    wb = Workbook()
    ws = wb.active
    ws.title = "Leave Report"
    
    # Headers
    headers = ['Request #', 'Staff Name', 'Department', 'Leave Type', 'Start Date', 'End Date', 'Days', 'Status', 'Approved By', 'Approved At']
    ws.append(headers)
    
    # Style headers
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
        cell.alignment = Alignment(horizontal="center")
    
    # Data
    for leave in leave_queryset:
        ws.append([
            leave.request_number or '-',
            leave.staff.user.get_full_name(),
            leave.staff.department.name if leave.staff.department else '-',
            leave.get_leave_type_display(),
            leave.start_date.strftime('%Y-%m-%d'),
            leave.end_date.strftime('%Y-%m-%d'),
            leave.days_requested,
            leave.get_status_display(),
            leave.approved_by.user.get_full_name() if leave.approved_by else '-',
            leave.approved_at.strftime('%Y-%m-%d %H:%M') if leave.approved_at else '-'
        ])
    
    # Adjust column widths
    for column in ws.columns:
        max_length = 0
        column_letter = column[0].column_letter
        for cell in column:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except:
                pass
        adjusted_width = min(max_length + 2, 50)
        ws.column_dimensions[column_letter].width = adjusted_width
    
    output = BytesIO()
    wb.save(output)
    output.seek(0)
    
    response = HttpResponse(
        output.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="leave_report_{date.today()}.xlsx"'
    
    return response


def export_attendance_csv(attendance_queryset):
    """Export attendance report to CSV"""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="attendance_report_{date.today()}.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Date', 'Staff Name', 'Department', 'Check In', 'Check Out', 'Status', 'Notes'])
    
    for att in attendance_queryset:
        writer.writerow([
            att.date.strftime('%Y-%m-%d'),
            att.staff.user.get_full_name(),
            att.staff.department.name if att.staff.department else '-',
            att.check_in_time.strftime('%H:%M') if att.check_in_time else '-',
            att.check_out_time.strftime('%H:%M') if att.check_out_time else '-',
            att.get_status_display(),
            att.notes or '-'
        ])
    
    return response


def export_payroll_csv(payroll_queryset, period):
    """Export payroll report to CSV"""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="payroll_report_{date.today()}.csv"'
    
    writer = csv.writer(response)
    if period:
        writer.writerow([f'Payroll Report - {period.period_name}'])
        writer.writerow([])
    
    writer.writerow(['Employee ID', 'Staff Name', 'Department', 'Gross Pay', 'Total Deductions', 'Net Pay', 'Payment Status'])
    
    for payroll in payroll_queryset:
        writer.writerow([
            payroll.staff.employee_id or '-',
            payroll.staff.user.get_full_name(),
            payroll.staff.department.name if payroll.staff.department else '-',
            f'{payroll.gross_pay:.2f}',
            f'{payroll.total_deductions:.2f}',
            f'{payroll.net_pay:.2f}',
            payroll.get_payment_status_display()
        ])
    
    return response


def export_training_csv(training_queryset):
    """Export training report to CSV"""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="training_report_{date.today()}.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Staff Name', 'Department', 'Training Title', 'Training Type', 'Start Date', 'End Date', 'Duration (Hours)', 'Provider', 'Status'])
    
    for training in training_queryset:
        writer.writerow([
            training.staff.user.get_full_name(),
            training.staff.department.name if training.staff.department else '-',
            training.training_title,
            training.get_training_type_display(),
            training.start_date.strftime('%Y-%m-%d') if training.start_date else '-',
            training.end_date.strftime('%Y-%m-%d') if training.end_date else '-',
            training.duration_hours or '-',
            training.provider or '-',
            training.get_status_display()
        ])
    
    return response


def export_performance_csv(review_queryset):
    """Export performance review report to CSV"""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="performance_report_{date.today()}.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Staff Name', 'Department', 'Review Date', 'Period', 'Overall Rating', 'Reviewer', 'Recommendation'])
    
    for review in review_queryset:
        writer.writerow([
            review.staff.user.get_full_name(),
            review.staff.department.name if review.staff.department else '-',
            review.review_date.strftime('%Y-%m-%d'),
            review.get_review_period_display(),
            review.overall_rating,
            review.reviewed_by.user.get_full_name() if review.reviewed_by else '-',
            review.recommendation or '-'
        ])
    
    return response

