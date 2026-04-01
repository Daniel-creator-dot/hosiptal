"""
HR and Staff Management Views
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q, Sum, Count, Avg
from django.db import models
from django.http import JsonResponse
from datetime import date, timedelta
from decimal import Decimal
from .models import Staff, Department
from .models_hr import (
    PayGrade, StaffContract, PayrollPeriod, Payroll, LeaveBalance,
    PerformanceReview, DisciplinaryAction, TrainingRecord, StaffDocument, StaffNote,
    StaffShift, ShiftTemplate, StaffQualification, StaffMedicalChit,
    AllowanceType, DeductionType, TaxBracket, PayrollConfiguration
)
from .models_advanced import LeaveRequest, Attendance, DutyRoster
from .views_hod_shift_monitoring import is_hod
from .forms_hr import (
    StaffForm, StaffContractForm, LeaveRequestForm, StaffDocumentForm,
    PerformanceReviewForm, TrainingRecordForm,
    AllowanceTypeForm, DeductionTypeForm, TaxBracketForm, PayrollConfigurationForm
)
from .services.performance_analytics import performance_analytics_service


def is_hr_or_admin(user):
    """Check if user is HR or Admin"""
    return user.groups.filter(name__in=['Admin', 'HR']).exists() or user.is_staff


def is_hr_admin_or_hod(user):
    """
    Check if user is HR/Admin or a Head of Department.
    HODs (like Evans as Head of Laboratory) can manage timetables/shifts for their department.
    """
    return is_hr_or_admin(user) or is_hod(user)


def is_manager_or_admin(user):
    """Check if user is Manager or Admin"""
    return user.groups.filter(name__in=['Admin', 'HR', 'Manager']).exists() or user.is_staff


def _suggest_rating_from_score(score: float) -> str:
    """Map numeric performance index to HR rating choices."""
    if score >= 4.5:
        return 'outstanding'
    if score >= 3.5:
        return 'excellent'
    if score >= 2.5:
        return 'good'
    if score >= 1.5:
        return 'satisfactory'
    return 'needs_improvement'


@login_required
@user_passes_test(is_hr_or_admin, login_url='/admin/login/')
def hr_dashboard(request):
    """HR main dashboard"""
    from django.db.models import OuterRef, Subquery
    
    # Statistics - count distinct users to avoid duplicates
    # Get the most recent staff record per user (by created date)
    latest_staff = Staff.objects.filter(
        is_active=True,
        is_deleted=False,
        user=OuterRef('user')
    ).order_by('-created')[:1]
    
    latest_staff_ids = Staff.objects.filter(
        is_active=True,
        is_deleted=False
    ).annotate(
        latest_id=Subquery(latest_staff.values('id'))
    ).values_list('latest_id', flat=True).distinct()
    
    total_staff = Staff.objects.filter(
        id__in=latest_staff_ids,
        is_active=True,
        is_deleted=False
    ).count()
    total_contracts = StaffContract.objects.filter(is_active=True, is_deleted=False).count()
    
    # Payroll stats
    current_period = PayrollPeriod.objects.filter(is_processed=False).first()
    total_payroll = Payroll.objects.filter(
        period=current_period,
        is_deleted=False
    ).aggregate(Sum('net_pay'))['net_pay__sum'] or Decimal('0.00') if current_period else Decimal('0.00')
    
    # Leave stats
    pending_leaves = LeaveRequest.objects.filter(
        status='pending',
        is_deleted=False
    ).count()
    
    # Recent activities
    recent_payrolls = Payroll.objects.filter(
        is_deleted=False
    ).select_related('staff', 'period').order_by('-created')[:10]
    
    recent_leaves = LeaveRequest.objects.filter(
        is_deleted=False
    ).select_related('staff').order_by('-created')[:10]
    
    context = {
        'total_staff': total_staff,
        'total_contracts': total_contracts,
        'current_period': current_period,
        'total_payroll': total_payroll,
        'pending_leaves': pending_leaves,
        'recent_payrolls': recent_payrolls,
        'recent_leaves': recent_leaves,
    }
    return render(request, 'hospital/hr_dashboard.html', context)


@login_required
@user_passes_test(is_hr_or_admin, login_url='/admin/login/')
def staff_list(request):
    """List all staff"""
    from .utils_roles import get_deduplicated_staff_queryset
    
    department_filter = request.GET.get('department')
    status_filter = request.GET.get('status', 'active')
    query = request.GET.get('q', '')
    
    # Get deduplicated staff queryset
    base_filter = {}
    if status_filter == 'active':
        base_filter['is_active'] = True
    elif status_filter == 'inactive':
        base_filter['is_active'] = False
    
    staff_list = get_deduplicated_staff_queryset(base_filter=base_filter)
    
    if department_filter:
        staff_list = staff_list.filter(department_id=department_filter)
    
    if query:
        staff_list = staff_list.filter(
            Q(user__first_name__icontains=query) |
            Q(user__last_name__icontains=query) |
            Q(user__email__icontains=query) |
            Q(employee_id__icontains=query) |
            Q(phone_number__icontains=query)
        )
    
    departments = Department.objects.filter(is_active=True, is_deleted=False)
    
    from datetime import date
    today = date.today()
    
    context = {
        'staff_list': staff_list.order_by('user__last_name', 'user__first_name')[:100],
        'departments': departments,
        'department_filter': department_filter,
        'status_filter': status_filter,
        'query': query,
        'today': today,
    }
    return render(request, 'hospital/staff_list.html', context)


@login_required
@user_passes_test(is_hr_or_admin, login_url='/admin/login/')
def staff_detail(request, pk):
    """Comprehensive Staff Profile View - Complete Staff Folder"""
    staff = get_object_or_404(
        Staff.objects.select_related('user', 'department', 'department__head_of_department'),
        pk=pk, 
        is_deleted=False
    )
    
    # Get related data
    try:
        contract = StaffContract.objects.get(staff=staff, is_active=True, is_deleted=False)
    except StaffContract.DoesNotExist:
        contract = None
    
    leave_balance = LeaveBalance.objects.filter(staff=staff, is_deleted=False).first()
    
    # ========== LEAVE HISTORY - All leaves spent ==========
    
    all_leaves = LeaveRequest.objects.filter(
        staff=staff,
        is_deleted=False
    ).select_related('approved_by').order_by('-start_date')
    
    # Calculate leave count
    all_leaves_count = all_leaves.count()
    
    # Calculate leave statistics
    approved_leaves = all_leaves.filter(status='approved')
    
    # Total leave days - ensure it's a number
    total_leave_days_result = approved_leaves.aggregate(
        total=Sum('days_requested')
    )['total']
    if total_leave_days_result is None:
        total_leave_days = 0
    else:
        total_leave_days = float(total_leave_days_result)
    
    # Leave by type
    leave_by_type = {}
    for leave_type_code, leave_type_name in LeaveRequest.LEAVE_TYPES:
        days_result = approved_leaves.filter(leave_type=leave_type_code).aggregate(
            total=Sum('days_requested')
        )['total']
        days = float(days_result) if days_result is not None else 0
        if days > 0:
            leave_by_type[leave_type_name] = days
    
    # Current year leaves
    current_year = date.today().year
    current_year_leaves = approved_leaves.filter(
        start_date__year=current_year
    )
    current_year_days_result = current_year_leaves.aggregate(
        total=Sum('days_requested')
    )['total']
    if current_year_days_result is None:
        current_year_days = 0
    else:
        current_year_days = float(current_year_days_result)
    
    # Check if staff is currently on leave
    today = date.today()
    current_leave = approved_leaves.filter(
        start_date__lte=today,
        end_date__gte=today
    ).first()
    
    is_currently_on_leave = current_leave is not None
    
    # ========== PERFORMANCE REVIEWS - Complete with KPIs ==========
    performance_reviews = PerformanceReview.objects.filter(
        staff=staff,
        is_deleted=False
    ).prefetch_related('kpi_ratings__kpi').order_by('-review_date')
    
    # Performance count
    performance_reviews_count = performance_reviews.count()
    
    # Performance statistics
    if performance_reviews.exists():
        latest_review = performance_reviews.first()
        avg_score = performance_reviews.aggregate(
            avg=Avg('overall_score')
        )['avg'] or 0
    else:
        latest_review = None
        avg_score = 0
    
    # ========== REAL-TIME PERFORMANCE SNAPSHOT ==========
    # Get or generate latest performance snapshot (auto-updated as staff work)
    latest_performance_snapshot = None
    performance_snapshot_history = []
    try:
        latest_performance_snapshot = performance_analytics_service.ensure_recent_snapshot(staff)
        performance_snapshot_history = performance_analytics_service.get_recent_snapshots(staff, limit=4)
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Could not generate performance snapshot: {e}")
    
    # ========== MEDICAL HISTORY - Medical Chits ==========
    medical_chits = StaffMedicalChit.objects.filter(
        staff=staff,
        is_deleted=False
    ).select_related('hr_approved_by', 'encounter').order_by('-application_date')
    
    # Medical chit statistics
    total_chits = medical_chits.count() or 0
    approved_chits = medical_chits.filter(status='approved').count() or 0
    used_chits = medical_chits.filter(status='used').count() or 0
    
    # ========== TRAINING RECORDS ==========
    training_records = TrainingRecord.objects.filter(
        staff=staff,
        is_deleted=False
    ).select_related('program').order_by('-start_date')
    
    # Training count
    training_records_count = training_records.count()
    
    # ========== DOCUMENTS ==========
    documents = StaffDocument.objects.filter(
        staff=staff,
        is_active=True,
        is_deleted=False
    ).order_by('-created')
    
    # Documents count
    documents_count = documents.count()
    
    # ========== NOTES ==========
    notes = StaffNote.objects.filter(
        staff=staff,
        is_deleted=False
    ).select_related('created_by').order_by('-created')
    
    # ========== DISCIPLINARY ACTIONS ==========
    disciplinary_actions = DisciplinaryAction.objects.filter(
        staff=staff,
        is_deleted=False
    ).select_related('reported_by').order_by('-action_date')
    
    # ========== PAYROLL HISTORY ==========
    payrolls = Payroll.objects.filter(
        staff=staff,
        is_deleted=False
    ).select_related('period').order_by('-period__start_date')[:24]
    
    # ========== QUALIFICATIONS ==========
    qualifications = StaffQualification.objects.filter(
        staff=staff,
        is_deleted=False,
        is_active=True
    ).order_by('-issue_date')
    
    # ========== ATTENDANCE (if available) ==========
    attendance_records = []
    try:
        from .models_auto_attendance import StaffAttendance
        attendance_records = StaffAttendance.objects.filter(
            staff=staff,
            is_deleted=False
        ).order_by('-date')[:30]
    except:
        pass
    
    # Calculate attendance statistics
    attendance_stats = {}
    if attendance_records:
        total_days = len(attendance_records)
        present_days = sum(1 for a in attendance_records if a.status == 'present')
        attendance_stats = {
            'total_days': total_days,
            'present_days': present_days,
            'attendance_rate': (present_days / total_days * 100) if total_days > 0 else 0
        }
    
    context = {
        'staff': staff,
        'contract': contract,
        'leave_balance': leave_balance,
        
        # Leave data
        'all_leaves': all_leaves,
        'all_leaves_count': all_leaves_count,
        'total_leave_days': total_leave_days,
        'leave_by_type': leave_by_type,
        'current_year_leaves': current_year_leaves,
        'current_year_days': current_year_days,
        'is_currently_on_leave': is_currently_on_leave,
        'current_leave': current_leave,
        
        # Performance data
        'performance_reviews': performance_reviews,
        'performance_reviews_count': performance_reviews_count,
        'latest_review': latest_review,
        'avg_performance_score': float(avg_score) if avg_score else 0,
        'latest_performance_snapshot': latest_performance_snapshot,
        'performance_snapshot_history': performance_snapshot_history,
        
        # Medical history
        'medical_chits': medical_chits,
        'total_chits': int(total_chits),
        'approved_chits': int(approved_chits),
        'used_chits': int(used_chits),
        
        # Other data
        'training_records': training_records,
        'training_records_count': training_records_count,
        'documents': documents,
        'documents_count': documents_count,
        'notes': notes,
        'disciplinary_actions': disciplinary_actions,
        'payrolls': payrolls,
        'qualifications': qualifications,
        'attendance_records': attendance_records,
        'attendance_stats': attendance_stats,
    }
    return render(request, 'hospital/staff_detail.html', context)


@login_required
@user_passes_test(is_hr_or_admin, login_url='/admin/login/')
def payroll_list(request):
    """List payrolls"""
    period_filter = request.GET.get('period')
    status_filter = request.GET.get('status')
    
    payrolls = Payroll.objects.filter(is_deleted=False).select_related(
        'staff', 'period', 'contract'
    ).order_by('-period__start_date', 'staff')
    
    if period_filter:
        payrolls = payrolls.filter(period_id=period_filter)
    
    if status_filter:
        payrolls = payrolls.filter(payment_status=status_filter)
    
    periods = PayrollPeriod.objects.filter(is_deleted=False).order_by('-start_date')[:12]
    
    context = {
        'payrolls': payrolls[:200],
        'periods': periods,
        'period_filter': period_filter,
        'status_filter': status_filter,
    }
    return render(request, 'hospital/payroll_list.html', context)


@login_required
@user_passes_test(is_hr_or_admin, login_url='/admin/login/')
def payroll_detail(request, pk):
    """Payroll detail view"""
    payroll = get_object_or_404(Payroll, pk=pk, is_deleted=False)
    
    context = {
        'payroll': payroll,
    }
    return render(request, 'hospital/payroll_detail.html', context)


@login_required
@user_passes_test(is_hr_or_admin, login_url='/admin/login/')
def process_payroll(request, period_id):
    """Process payroll for a period using configured settings"""
    period = get_object_or_404(PayrollPeriod, pk=period_id, is_deleted=False)
    
    # Get payroll configuration
    config = PayrollConfiguration.get_active_config()
    if not config:
        messages.warning(request, 'No payroll configuration found. Please configure payroll settings first.')
        return redirect('hospital:payroll_settings')
    
    if request.method == 'POST':
        # Get all active contracts
        contracts = StaffContract.objects.filter(
            is_active=True,
            is_deleted=False,
            start_date__lte=period.end_date,
        ).filter(
            Q(end_date__isnull=True) | Q(end_date__gte=period.start_date)
        )
        
        # Get active allowance and deduction types
        active_allowance_types = AllowanceType.objects.filter(is_active=True, is_deleted=False)
        active_deduction_types = DeductionType.objects.filter(is_active=True, is_deleted=False)
        
        created_count = 0
        for contract in contracts:
            # Check if payroll already exists
            existing = Payroll.objects.filter(
                staff=contract.staff,
                period=period,
                is_deleted=False
            ).exists()
            
            if not existing:
                # Calculate earnings
                basic_salary = contract.basic_salary
                
                # Calculate allowances from configured types
                allowances_total = contract.allowances  # Legacy contract allowance
                
                # Create payroll record
                payroll = Payroll.objects.create(
                    staff=contract.staff,
                    period=period,
                    contract=contract,
                    basic_salary=basic_salary,
                    allowances=allowances_total,
                    overtime=0,
                    bonuses=0,
                    tax=0,
                    social_security=0,
                    pension=0,
                    loan_repayment=0,
                    other_deductions=0,
                    payment_status='pending',
                )
                
                # Add configured allowances (statutory allowances are applied automatically)
                from .models_hr import PayrollAllowance
                for allowance_type in active_allowance_types:
                    if allowance_type.is_statutory:
                        amount = Decimal('0')
                        if allowance_type.calculation_type == 'fixed':
                            amount = allowance_type.default_amount
                        elif allowance_type.calculation_type == 'percentage':
                            amount = basic_salary * (allowance_type.default_amount / Decimal('100'))
                        
                        if amount > 0:
                            PayrollAllowance.objects.create(
                                payroll=payroll,
                                allowance_type=allowance_type,
                                amount=amount,
                                is_taxable=allowance_type.is_taxable,
                                description=f"{allowance_type.name} - {period.period_name}"
                            )
                
                # Add contract-level allowances if any
                if contract.allowances > 0:
                    # Create a generic allowance entry for contract allowances
                    generic_allowance_type = active_allowance_types.filter(name__icontains='other').first() or active_allowance_types.first()
                    if generic_allowance_type:
                        PayrollAllowance.objects.create(
                            payroll=payroll,
                            allowance_type=generic_allowance_type,
                            amount=contract.allowances,
                            is_taxable=True,
                            description=f"Contract Allowance - {period.period_name}"
                        )
                    # If no allowance types exist, the legacy allowances field will be used
                
                # Calculate taxable income
                taxable_allowances = sum(
                    item.amount for item in payroll.allowance_items.all() 
                    if item.is_taxable
                )
                taxable_income = basic_salary + taxable_allowances
                
                # Calculate tax using progressive brackets if configured
                if config.tax_calculation_method == 'progressive':
                    tax = payroll.calculate_progressive_tax(taxable_income)
                else:
                    # Flat rate
                    tax_free = config.tax_free_allowance
                    taxable_amount = max(Decimal('0'), taxable_income - tax_free)
                    tax = taxable_amount * (config.default_tax_rate / Decimal('100'))
                
                # Calculate social security
                social_security = basic_salary * (config.social_security_rate / Decimal('100'))
                if config.social_security_max_amount:
                    social_security = min(social_security, config.social_security_max_amount)
                
                # Calculate pension
                pension = basic_salary * (config.pension_rate / Decimal('100'))
                if config.pension_max_amount:
                    pension = min(pension, config.pension_max_amount)
                
                # Add configured deductions (statutory deductions are applied automatically)
                from .models_hr import PayrollDeduction
                
                # Add tax deduction
                if tax > 0:
                    tax_deduction_type = active_deduction_types.filter(code='TAX').first() or active_deduction_types.filter(name__icontains='tax').first()
                    if tax_deduction_type:
                        PayrollDeduction.objects.create(
                            payroll=payroll,
                            deduction_type=tax_deduction_type,
                            amount=tax,
                            description=f"Tax - {period.period_name}"
                        )
                
                # Add social security deduction
                if social_security > 0:
                    ss_deduction_type = active_deduction_types.filter(code='SS').first() or active_deduction_types.filter(name__icontains='social security').first()
                    if ss_deduction_type:
                        PayrollDeduction.objects.create(
                            payroll=payroll,
                            deduction_type=ss_deduction_type,
                            amount=social_security,
                            description=f"Social Security - {period.period_name}"
                        )
                
                # Add pension deduction
                if pension > 0:
                    pension_deduction_type = active_deduction_types.filter(code='PENSION').first() or active_deduction_types.filter(name__icontains='pension').first()
                    if pension_deduction_type:
                        PayrollDeduction.objects.create(
                            payroll=payroll,
                            deduction_type=pension_deduction_type,
                            amount=pension,
                            description=f"Pension - {period.period_name}"
                        )
                
                # Add other statutory deductions
                for deduction_type in active_deduction_types:
                    if deduction_type.is_statutory and deduction_type.code not in ['TAX', 'SS', 'PENSION']:
                        amount = Decimal('0')
                        if deduction_type.calculation_type == 'fixed':
                            amount = deduction_type.default_amount
                        elif deduction_type.calculation_type == 'percentage':
                            amount = basic_salary * (deduction_type.default_amount / Decimal('100'))
                        elif deduction_type.calculation_type == 'percentage_of_gross':
                            gross = payroll.total_earnings
                            amount = gross * (deduction_type.default_amount / Decimal('100'))
                        
                        # Apply min/max limits
                        if deduction_type.min_amount:
                            amount = max(amount, deduction_type.min_amount)
                        if deduction_type.max_amount:
                            amount = min(amount, deduction_type.max_amount)
                        
                        if amount > 0:
                            PayrollDeduction.objects.create(
                                payroll=payroll,
                                deduction_type=deduction_type,
                                amount=amount,
                                description=f"{deduction_type.name} - {period.period_name}"
                            )
                
                # Update payroll with calculated values
                payroll.tax = tax
                payroll.social_security = social_security
                payroll.pension = pension
                payroll.save()  # This will recalculate totals from items
                
                created_count += 1
        
        period.is_processed = True
        period.processed_at = timezone.now()
        period.processed_by = request.user
        period.save()
        
        messages.success(request, f'Payroll processed for {created_count} staff members using configured settings')
        return redirect('hospital:payroll_list')
    
    context = {
        'period': period,
        'config': config,
        'contracts_count': StaffContract.objects.filter(
            is_active=True,
            is_deleted=False
        ).count(),
    }
    return render(request, 'hospital/process_payroll.html', context)


@login_required
@user_passes_test(is_hr_or_admin, login_url='/admin/login/')
def staff_create(request):
    """Create new staff"""
    if request.method == 'POST':
        form = StaffForm(request.POST)
        if form.is_valid():
            staff = form.save()
            messages.success(request, f'Staff {staff.user.get_full_name()} created successfully')
            return redirect('hospital:staff_detail', pk=staff.pk)
    else:
        form = StaffForm()
    
    context = {
        'form': form,
        'title': 'Add New Staff',
    }
    return render(request, 'hospital/staff_form.html', context)


@login_required
@user_passes_test(is_hr_or_admin, login_url='/admin/login/')
def staff_edit(request, pk):
    """Edit staff"""
    staff = get_object_or_404(Staff, pk=pk, is_deleted=False)
    
    if request.method == 'POST':
        form = StaffForm(request.POST, instance=staff)
        if form.is_valid():
            staff = form.save()
            messages.success(request, f'Staff {staff.user.get_full_name()} updated successfully')
            return redirect('hospital:staff_detail', pk=staff.pk)
    else:
        form = StaffForm(instance=staff)
    
    context = {
        'form': form,
        'staff': staff,
        'title': 'Edit Staff',
    }
    return render(request, 'hospital/staff_form.html', context)


@login_required
@user_passes_test(is_hr_or_admin, login_url='/admin/login/')
def staff_contract_create(request, staff_id):
    """Create staff contract"""
    staff = get_object_or_404(Staff, pk=staff_id, is_deleted=False)
    
    if request.method == 'POST':
        form = StaffContractForm(request.POST)
        if form.is_valid():
            contract = form.save(commit=False)
            contract.staff = staff
            contract.save()
            messages.success(request, 'Contract created successfully')
            return redirect('hospital:staff_detail', pk=staff.pk)
    else:
        form = StaffContractForm(initial={'department': staff.department})
    
    context = {
        'form': form,
        'staff': staff,
        'title': 'Create Contract',
    }
    return render(request, 'hospital/staff_contract_form.html', context)


@login_required
def leave_request_create(request):
    """Create leave request (available to all staff)"""
    if request.method == 'POST':
        form = LeaveRequestForm(request.POST)
        if form.is_valid():
            leave_request = form.save(commit=False)
            if hasattr(request.user, 'staff_profile'):
                leave_request.staff = request.user.staff
                # Calculate days if not provided
                if not leave_request.days_requested and leave_request.start_date and leave_request.end_date:
                    delta = leave_request.end_date - leave_request.start_date
                    leave_request.days_requested = delta.days + 1
                leave_request.save()
                messages.success(request, 'Leave request submitted successfully')
                return redirect('hospital:leave_request_list')
            else:
                messages.error(request, 'You must be a staff member to request leave')
    else:
        form = LeaveRequestForm()
    
    context = {
        'form': form,
        'title': 'Request Leave',
    }
    return render(request, 'hospital/leave_request_form.html', context)


@login_required
def leave_request_list(request):
    """List leave requests (staff can see their own, HR can see all)"""
    if request.user.groups.filter(name__in=['Admin', 'HR']).exists() or request.user.is_staff:
        leave_requests = LeaveRequest.objects.filter(is_deleted=False).select_related('staff').order_by('-created')
    else:
        if hasattr(request.user, 'staff_profile'):
            leave_requests = LeaveRequest.objects.filter(
                staff=request.user.staff,
                is_deleted=False
            ).order_by('-created')
        else:
            leave_requests = LeaveRequest.objects.none()
    
    context = {
        'leave_requests': leave_requests,
    }
    return render(request, 'hospital/leave_request_list.html', context)


@login_required
@user_passes_test(is_hr_or_admin, login_url='/admin/login/')
def leave_request_approve(request, pk):
    """Approve/reject leave request"""
    leave_request = get_object_or_404(LeaveRequest, pk=pk, is_deleted=False)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        comments = request.POST.get('comments', '')
        
        if action == 'approve':
            leave_request.status = 'approved'
            if hasattr(request.user, 'staff_profile'):
                leave_request.approved_by = request.user.staff
            leave_request.approved_at = timezone.now()
            messages.success(request, 'Leave request approved')
        elif action == 'reject':
            leave_request.status = 'rejected'
            if hasattr(request.user, 'staff_profile'):
                leave_request.approved_by = request.user.staff
        
        leave_request.save()
        return redirect('hospital:leave_request_list')
    
    context = {
        'leave_request': leave_request,
    }
    return render(request, 'hospital/leave_request_approve.html', context)


@login_required
@user_passes_test(is_hr_or_admin, login_url='/admin/login/')
def staff_document_upload(request, staff_id):
    """Upload staff document"""
    staff = get_object_or_404(Staff, pk=staff_id, is_deleted=False)
    
    if request.method == 'POST':
        form = StaffDocumentForm(request.POST, request.FILES)
        if form.is_valid():
            document = form.save(commit=False)
            document.staff = staff
            document.save()
            messages.success(request, 'Document uploaded successfully')
            return redirect('hospital:staff_detail', pk=staff.pk)
    else:
        form = StaffDocumentForm()
    
    context = {
        'form': form,
        'staff': staff,
        'title': 'Upload Document',
    }
    return render(request, 'hospital/staff_document_form.html', context)


@login_required
@user_passes_test(is_hr_admin_or_hod, login_url='/admin/login/')
def staff_shift_list(request):
    """List staff shifts"""
    date_filter = request.GET.get('date')
    staff_filter = request.GET.get('staff')
    department_filter = request.GET.get('department')

    # Determine current user's scope: HR/Admin (all departments) vs HOD (own department only)
    user_is_hod = is_hod(request.user)
    user_is_hr_admin = is_hr_or_admin(request.user)
    hod_department = None
    if user_is_hod:
        try:
            hod_department = request.user.staff.hod_designation.department
        except Exception:
            hod_department = None

    shifts = StaffShift.objects.filter(is_deleted=False).select_related(
        'staff', 'department', 'location'
    )

    # HODs should only ever see shifts for their own department, even if filters request otherwise.
    if user_is_hod and hod_department and not user_is_hr_admin:
        shifts = shifts.filter(department=hod_department)
    
    if date_filter:
        try:
            shifts = shifts.filter(shift_date=date_filter)
        except ValueError:
            pass
    else:
        # Default to current week
        from datetime import date, timedelta
        today = date.today()
        week_start = today - timedelta(days=today.weekday())
        shifts = shifts.filter(shift_date__gte=week_start)
    
    if staff_filter:
        shifts = shifts.filter(staff_id=staff_filter)
    
    if department_filter:
        shifts = shifts.filter(department_id=department_filter)
    
    # Group by date
    shifts_by_date = {}
    for shift in shifts.order_by('shift_date', 'start_time'):
        date_key = shift.shift_date.strftime('%Y-%m-%d')
        if date_key not in shifts_by_date:
            shifts_by_date[date_key] = []
        shifts_by_date[date_key].append(shift)
    
    from datetime import date, timedelta
    from django.db.models import OuterRef, Subquery
    
    # Get the most recent staff record ID for each user to avoid duplicates
    latest_staff = Staff.objects.filter(
        is_active=True,
        is_deleted=False,
        user=OuterRef('user')
    ).order_by('-created')[:1]
    latest_staff_ids = Staff.objects.filter(
        is_active=True,
        is_deleted=False
    ).annotate(
        latest_id=Subquery(latest_staff.values('id'))
    ).values_list('latest_id', flat=True).distinct()
    
    staff_qs = Staff.objects.filter(
        id__in=latest_staff_ids,
        is_active=True,
        is_deleted=False
    )
    departments_qs = Department.objects.filter(is_active=True, is_deleted=False)

    # Restrict staff/department filters for HODs to their department only
    if user_is_hod and hod_department and not user_is_hr_admin:
        staff_qs = staff_qs.filter(department=hod_department)
        departments_qs = departments_qs.filter(pk=hod_department.pk)

    staff_list = staff_qs.order_by('user__last_name')
    departments = departments_qs
    
    if not date_filter:
        today = date.today()
        week_start = today - timedelta(days=today.weekday())
        date_filter = week_start.strftime('%Y-%m-%d')
    
    context = {
        'shifts_by_date': shifts_by_date,
        'staff_list': staff_list,
        'departments': departments,
        'date_filter': date_filter,
        'staff_filter': staff_filter,
        'department_filter': department_filter,
    }
    return render(request, 'hospital/staff_shift_list.html', context)


@login_required
@user_passes_test(is_hr_admin_or_hod, login_url='/admin/login/')
def staff_shift_create(request):
    """Create staff shift"""
    # Determine if current user is acting as HOD (department-scoped) or HR/Admin (global)
    user_is_hod = is_hod(request.user)
    user_is_hr_admin = is_hr_or_admin(request.user)
    hod_department = None
    if user_is_hod:
        try:
            hod_department = request.user.staff.hod_designation.department
        except Exception:
            hod_department = None

    if request.method == 'POST':
        staff_id = request.POST.get('staff')
        shift_date = request.POST.get('shift_date')
        shift_type = request.POST.get('shift_type')
        start_time = request.POST.get('start_time')
        end_time = request.POST.get('end_time')
        department_id = request.POST.get('department')
        location_id = request.POST.get('location', '')
        notes = request.POST.get('notes', '')

        # HODs must only assign shifts within their own department;
        # ignore/override any posted department that does not match.
        if user_is_hod and hod_department:
            department_id = str(hod_department.id)

        try:
            if not all([staff_id, shift_date, shift_type, start_time, end_time, department_id]):
                raise ValueError('Please fill all required fields.')
            from django.utils.dateparse import parse_date, parse_time
            parsed_date = parse_date(shift_date)
            st = parse_time(start_time)
            et = parse_time(end_time)
            if not parsed_date or not st or not et:
                raise ValueError('Invalid date or time.')

            # If HOD, enforce that selected staff belongs to their department
            if user_is_hod and hod_department:
                staff_obj = Staff.objects.filter(
                    pk=int(staff_id),
                    department=hod_department,
                    is_deleted=False
                ).first()
                if not staff_obj:
                    raise ValueError('You can only assign shifts to staff in your department.')

            shift = StaffShift.objects.create(
                staff_id=int(staff_id),
                shift_date=parsed_date,
                shift_type=shift_type,
                start_time=st,
                end_time=et,
                department_id=int(department_id),
                location_id=int(location_id) if str(location_id).strip().isdigit() else None,
                notes=notes,
                assigned_by=request.user,
            )
            messages.success(request, 'Shift created successfully')
            return redirect('hospital:staff_shift_list')
        except Exception as e:
            messages.error(request, f'Error creating shift: {str(e)}')
    
    from .models import Ward
    from django.db.models import OuterRef, Subquery
    
    # Get the most recent staff record ID for each user to avoid duplicates
    latest_staff = Staff.objects.filter(
        is_active=True,
        is_deleted=False,
        user=OuterRef('user')
    ).order_by('-created')[:1]
    latest_staff_ids = Staff.objects.filter(
        is_active=True,
        is_deleted=False
    ).annotate(
        latest_id=Subquery(latest_staff.values('id'))
    ).values_list('latest_id', flat=True).distinct()
    
    staff_qs = Staff.objects.filter(
        id__in=latest_staff_ids,
        is_active=True,
        is_deleted=False
    )

    departments_qs = Department.objects.filter(is_active=True, is_deleted=False)

    # HOD view: restrict staff and departments to their department only
    if user_is_hod and hod_department and not user_is_hr_admin:
        staff_qs = staff_qs.filter(department=hod_department)
        departments_qs = departments_qs.filter(pk=hod_department.pk)

    staff_list = staff_qs.order_by('user__last_name')
    departments = departments_qs
    wards = Ward.objects.filter(is_active=True, is_deleted=False)
    
    context = {
        'staff_list': staff_list,
        'departments': departments,
        'wards': wards,
        'shift_templates': ShiftTemplate.objects.filter(is_active=True),
    }
    return render(request, 'hospital/staff_shift_form.html', context)


@login_required
@user_passes_test(is_hr_or_admin, login_url='/admin/login/')
def performance_review_create(request, staff_id):
    """Create performance review"""
    staff = get_object_or_404(Staff, pk=staff_id, is_deleted=False)
    latest_snapshot = performance_analytics_service.ensure_recent_snapshot(staff)
    snapshot_history = performance_analytics_service.get_recent_snapshots(staff, limit=4)
    
    if request.method == 'POST':
        form = PerformanceReviewForm(request.POST)
        if form.is_valid():
            review = form.save(commit=False)
            review.staff = staff
            if hasattr(request.user, 'staff_profile'):
                review.reviewed_by = request.user.staff
            review.save()
            messages.success(request, 'Performance review created successfully')
            return redirect('hospital:staff_detail', pk=staff.pk)
    else:
        initial = {
            'review_date': timezone.now().date(),
        }
        if latest_snapshot:
            initial['overall_rating'] = _suggest_rating_from_score(float(latest_snapshot.overall_index))
        form = PerformanceReviewForm(initial=initial)
    
    context = {
        'form': form,
        'staff': staff,
        'title': 'Create Performance Review',
        'performance_snapshot': latest_snapshot,
        'performance_snapshot_history': snapshot_history,
    }
    return render(request, 'hospital/performance_review_form.html', context)


@login_required
@user_passes_test(is_hr_or_admin, login_url='/admin/login/')
def training_record_create(request, staff_id):
    """Create training record"""
    staff = get_object_or_404(Staff, pk=staff_id, is_deleted=False)
    
    if request.method == 'POST':
        form = TrainingRecordForm(request.POST)
        if form.is_valid():
            training = form.save(commit=False)
            training.staff = staff
            training.save()
            messages.success(request, 'Training record created successfully')
            return redirect('hospital:staff_detail', pk=staff.pk)
    else:
        form = TrainingRecordForm()
    
    context = {
        'form': form,
        'staff': staff,
        'title': 'Add Training Record',
    }
    return render(request, 'hospital/training_record_form.html', context)


# ==================== PAYROLL SETTINGS VIEWS ====================

@login_required
@user_passes_test(is_hr_or_admin, login_url='/admin/login/')
def payroll_settings(request):
    """Payroll settings dashboard"""
    config = PayrollConfiguration.get_active_config()
    allowance_types = AllowanceType.objects.filter(is_deleted=False).order_by('display_order', 'name')
    deduction_types = DeductionType.objects.filter(is_deleted=False).order_by('display_order', 'name')
    tax_brackets = TaxBracket.objects.filter(is_deleted=False, is_active=True).order_by('min_income')
    
    context = {
        'config': config,
        'allowance_types': allowance_types,
        'deduction_types': deduction_types,
        'tax_brackets': tax_brackets,
    }
    return render(request, 'hospital/payroll_settings.html', context)


@login_required
@user_passes_test(is_hr_or_admin, login_url='/admin/login/')
def allowance_type_list(request):
    """List allowance types"""
    allowance_types = AllowanceType.objects.filter(is_deleted=False).order_by('display_order', 'name')
    
    context = {
        'allowance_types': allowance_types,
    }
    return render(request, 'hospital/allowance_type_list.html', context)


@login_required
@user_passes_test(is_hr_or_admin, login_url='/admin/login/')
def allowance_type_create(request):
    """Create allowance type"""
    if request.method == 'POST':
        form = AllowanceTypeForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Allowance type created successfully')
            return redirect('hospital:allowance_type_list')
    else:
        form = AllowanceTypeForm()
    
    context = {
        'form': form,
        'title': 'Add Allowance Type',
    }
    return render(request, 'hospital/allowance_type_form.html', context)


@login_required
@user_passes_test(is_hr_or_admin, login_url='/admin/login/')
def allowance_type_edit(request, pk):
    """Edit allowance type"""
    allowance_type = get_object_or_404(AllowanceType, pk=pk, is_deleted=False)
    
    if request.method == 'POST':
        form = AllowanceTypeForm(request.POST, instance=allowance_type)
        if form.is_valid():
            form.save()
            messages.success(request, 'Allowance type updated successfully')
            return redirect('hospital:allowance_type_list')
    else:
        form = AllowanceTypeForm(instance=allowance_type)
    
    context = {
        'form': form,
        'allowance_type': allowance_type,
        'title': 'Edit Allowance Type',
    }
    return render(request, 'hospital/allowance_type_form.html', context)


@login_required
@user_passes_test(is_hr_or_admin, login_url='/admin/login/')
def deduction_type_list(request):
    """List deduction types"""
    deduction_types = DeductionType.objects.filter(is_deleted=False).order_by('display_order', 'name')
    
    context = {
        'deduction_types': deduction_types,
    }
    return render(request, 'hospital/deduction_type_list.html', context)


@login_required
@user_passes_test(is_hr_or_admin, login_url='/admin/login/')
def deduction_type_create(request):
    """Create deduction type"""
    if request.method == 'POST':
        form = DeductionTypeForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Deduction type created successfully')
            return redirect('hospital:deduction_type_list')
    else:
        form = DeductionTypeForm()
    
    context = {
        'form': form,
        'title': 'Add Deduction Type',
    }
    return render(request, 'hospital/deduction_type_form.html', context)


@login_required
@user_passes_test(is_hr_or_admin, login_url='/admin/login/')
def deduction_type_edit(request, pk):
    """Edit deduction type"""
    deduction_type = get_object_or_404(DeductionType, pk=pk, is_deleted=False)
    
    if request.method == 'POST':
        form = DeductionTypeForm(request.POST, instance=deduction_type)
        if form.is_valid():
            form.save()
            messages.success(request, 'Deduction type updated successfully')
            return redirect('hospital:deduction_type_list')
    else:
        form = DeductionTypeForm(instance=deduction_type)
    
    context = {
        'form': form,
        'deduction_type': deduction_type,
        'title': 'Edit Deduction Type',
    }
    return render(request, 'hospital/deduction_type_form.html', context)


@login_required
@user_passes_test(is_hr_or_admin, login_url='/admin/login/')
def tax_bracket_list(request):
    """List tax brackets"""
    tax_brackets = TaxBracket.objects.filter(is_deleted=False).order_by('min_income')
    config = PayrollConfiguration.get_active_config()
    
    context = {
        'tax_brackets': tax_brackets,
        'config': config,
    }
    return render(request, 'hospital/tax_bracket_list.html', context)


@login_required
@user_passes_test(is_hr_or_admin, login_url='/admin/login/')
def tax_bracket_create(request):
    """Create tax bracket"""
    if request.method == 'POST':
        form = TaxBracketForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Tax bracket created successfully')
            return redirect('hospital:tax_bracket_list')
    else:
        form = TaxBracketForm()
    
    context = {
        'form': form,
        'title': 'Add Tax Bracket',
    }
    return render(request, 'hospital/tax_bracket_form.html', context)


@login_required
@user_passes_test(is_hr_or_admin, login_url='/admin/login/')
def tax_bracket_edit(request, pk):
    """Edit tax bracket"""
    tax_bracket = get_object_or_404(TaxBracket, pk=pk, is_deleted=False)
    
    if request.method == 'POST':
        form = TaxBracketForm(request.POST, instance=tax_bracket)
        if form.is_valid():
            form.save()
            messages.success(request, 'Tax bracket updated successfully')
            return redirect('hospital:tax_bracket_list')
    else:
        form = TaxBracketForm(instance=tax_bracket)
    
    context = {
        'form': form,
        'tax_bracket': tax_bracket,
        'title': 'Edit Tax Bracket',
    }
    return render(request, 'hospital/tax_bracket_form.html', context)


@login_required
@user_passes_test(is_hr_or_admin, login_url='/admin/login/')
def payroll_config_create(request):
    """Create payroll configuration"""
    if request.method == 'POST':
        form = PayrollConfigurationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Payroll configuration created successfully')
            return redirect('hospital:payroll_settings')
    else:
        form = PayrollConfigurationForm()
    
    context = {
        'form': form,
        'title': 'Add Payroll Configuration',
    }
    return render(request, 'hospital/payroll_config_form.html', context)


@login_required
@user_passes_test(is_hr_or_admin, login_url='/admin/login/')
def payroll_config_edit(request, pk):
    """Edit payroll configuration"""
    config = get_object_or_404(PayrollConfiguration, pk=pk, is_deleted=False)
    
    if request.method == 'POST':
        form = PayrollConfigurationForm(request.POST, instance=config)
        if form.is_valid():
            form.save()
            messages.success(request, 'Payroll configuration updated successfully')
            return redirect('hospital:payroll_settings')
    else:
        form = PayrollConfigurationForm(instance=config)
    
    context = {
        'form': form,
        'config': config,
        'title': 'Edit Payroll Configuration',
    }
    return render(request, 'hospital/payroll_config_form.html', context)


@login_required
@user_passes_test(is_manager_or_admin, login_url='/admin/login/')
def leave_approval_list(request):
    """Manager view of leave requests"""
    # Get staff record for current user
    try:
        manager_staff = Staff.objects.get(user=request.user, is_deleted=False)
        manager_department = manager_staff.department
    except Staff.DoesNotExist:
        manager_staff = None
        manager_department = None
    
    # Apply status filter (default to pending)
    status_filter = request.GET.get('status', 'pending')
    
    # Build base query
    if status_filter and status_filter != 'all':
        leave_requests = LeaveRequest.objects.filter(
            status=status_filter,
            is_deleted=False
        ).select_related('staff__user', 'staff__department').order_by('-submitted_at')
    else:
        # Show all leave requests
        leave_requests = LeaveRequest.objects.filter(
            is_deleted=False
        ).select_related('staff__user', 'staff__department').order_by('-submitted_at')
    
    # Department filtering: Only apply to pending requests
    # For approved/rejected/cancelled, show all if user is manager/admin
    # This allows managers to see leaves they approved even from other departments
    if not request.user.is_superuser and manager_department:
        # Only filter pending requests by department
        # Approved/rejected/cancelled should show all (you should see what you approved)
        if status_filter == 'pending':
            leave_requests = leave_requests.filter(staff__department=manager_department)
        # For other statuses, show leaves from your department OR leaves you approved
        elif manager_staff:
            leave_requests = leave_requests.filter(
                Q(staff__department=manager_department) | 
                Q(approved_by=manager_staff)
            )
    
    # Get counts for each status (with same filtering logic)
    all_leaves = LeaveRequest.objects.filter(is_deleted=False)
    
    if not request.user.is_superuser and manager_department and manager_staff:
        # Pending: only your department
        pending_count = all_leaves.filter(
            status='pending',
            staff__department=manager_department
        ).count()
        
        # Other statuses: your department OR you approved them
        approved_count = all_leaves.filter(
            status='approved'
        ).filter(
            Q(staff__department=manager_department) | Q(approved_by=manager_staff)
        ).count()
        
        rejected_count = all_leaves.filter(
            status='rejected'
        ).filter(
            Q(staff__department=manager_department) | Q(approved_by=manager_staff)
        ).count()
        
        cancelled_count = all_leaves.filter(
            status='cancelled'
        ).filter(
            Q(staff__department=manager_department) | Q(approved_by=manager_staff)
        ).count()
        
        all_count = all_leaves.filter(
            Q(staff__department=manager_department) | Q(approved_by=manager_staff)
        ).distinct().count()
    else:
        # Superuser sees all
        pending_count = all_leaves.filter(status='pending').count()
        approved_count = all_leaves.filter(status='approved').count()
        rejected_count = all_leaves.filter(status='rejected').count()
        cancelled_count = all_leaves.filter(status='cancelled').count()
        all_count = all_leaves.count()
    
    status_counts = {
        'pending': pending_count,
        'approved': approved_count,
        'rejected': rejected_count,
        'cancelled': cancelled_count,
        'all': all_count,
    }
    
    context = {
        'leave_requests': leave_requests,
        'status_filter': status_filter,
        'status_counts': status_counts,
        'manager_staff': manager_staff,
    }
    return render(request, 'hospital/leave_approval_list.html', context)


@login_required
@user_passes_test(is_manager_or_admin, login_url='/admin/login/')
def leave_approve(request, pk):
    """Approve a leave request"""
    leave_request = get_object_or_404(LeaveRequest, pk=pk, is_deleted=False)
    
    try:
        manager_staff = Staff.objects.get(user=request.user, is_deleted=False)
    except Staff.DoesNotExist:
        manager_staff = None
    
    if leave_request.approve(manager_staff):
        messages.success(request, f'Leave request approved for {leave_request.staff.user.get_full_name()}')
    else:
        messages.error(request, 'Could not approve leave request')
    
    return redirect('hospital:leave_approval_list')


@login_required
@user_passes_test(is_manager_or_admin, login_url='/admin/login/')
def leave_reject(request, pk):
    """Reject a leave request"""
    leave_request = get_object_or_404(LeaveRequest, pk=pk, is_deleted=False)
    
    if request.method == 'POST':
        reason = request.POST.get('reason', '').strip()
        
        if not reason:
            messages.error(request, 'Rejection reason is required')
            return redirect('hospital:leave_approval_list')
        
        try:
            manager_staff = Staff.objects.get(user=request.user, is_deleted=False)
        except Staff.DoesNotExist:
            manager_staff = None
        
        if leave_request.reject(manager_staff, reason):
            messages.success(request, f'Leave request rejected for {leave_request.staff.user.get_full_name()}')
        else:
            messages.error(request, 'Could not reject leave request')
    
    return redirect('hospital:leave_approval_list')


@login_required
@user_passes_test(is_hr_or_admin, login_url='/admin/login/')
def leave_print(request, pk):
    """Print approved leave document - HR/Admin only"""
    leave_request = get_object_or_404(LeaveRequest, pk=pk, is_deleted=False)
    
    # Only allow printing approved leaves
    if leave_request.status != 'approved':
        messages.error(request, 'Only approved leave requests can be printed.')
        return redirect('hospital:leave_approval_list')
    
    # Get hospital settings
    try:
        from .models_settings import HospitalSettings
        settings = HospitalSettings.objects.first()
        if not settings:
            # Create default settings if none exist
            settings = HospitalSettings.objects.create(
                hospital_name="Hospital Management System",
                report_header_color="#2196F3"
            )
    except Exception:
        settings = None
    
    context = {
        'leave_request': leave_request,
        'settings': settings,
    }
    return render(request, 'hospital/leave_print.html', context)


@login_required
@user_passes_test(is_hr_or_admin, login_url='/admin/login/')
def create_leave_for_staff(request):
    """Admin creates leave request on behalf of staff"""
    if request.method == 'POST':
        staff_id = request.POST.get('staff')
        leave_type = request.POST.get('leave_type')
        start_date_str = request.POST.get('start_date')
        end_date_str = request.POST.get('end_date')
        reason = request.POST.get('reason', '').strip()
        auto_approve = request.POST.get('auto_approve') == 'on'
        
        try:
            staff = Staff.objects.get(pk=staff_id, is_deleted=False)
            start_date = date.fromisoformat(start_date_str)
            end_date = date.fromisoformat(end_date_str)
            
            # Calculate working days (excluding weekends)
            days_requested = LeaveRequest.calculate_working_days(start_date, end_date)
            
            # Create leave request - always start as pending
            leave_request = LeaveRequest.objects.create(
                staff=staff,
                leave_type=leave_type,
                start_date=start_date,
                end_date=end_date,
                days_requested=days_requested,
                reason=reason,
                status='pending',
                submitted_at=timezone.now()
            )
            
            # Auto-approve if checked
            if auto_approve:
                admin_staff = Staff.objects.filter(user=request.user).first()
                if leave_request.approve(admin_staff):
                    messages.success(request, f'Leave request created and approved for {staff.user.get_full_name()}')
                    return redirect('hospital:leave_approval_list')
            
            messages.success(request, f'Leave request created for {staff.user.get_full_name()}')
            return redirect('hospital:leave_approval_list')
            
        except (Staff.DoesNotExist, ValueError) as e:
            messages.error(request, f'Error creating leave request: {str(e)}')
    
    # Get all staff for dropdown with their leave balances
    from django.db.models import OuterRef, Subquery
    
    # Get the most recent staff record ID for each user to avoid duplicates
    latest_staff = Staff.objects.filter(
        is_active=True,
        is_deleted=False,
        user=OuterRef('user')
    ).order_by('-created')[:1]
    latest_staff_ids = Staff.objects.filter(
        is_active=True,
        is_deleted=False
    ).annotate(
        latest_id=Subquery(latest_staff.values('id'))
    ).values_list('latest_id', flat=True).distinct()
    
    all_staff = Staff.objects.filter(
        id__in=latest_staff_ids,
        is_active=True,
        is_deleted=False
    ).select_related('user', 'department')
    
    # Attach leave balance to each staff
    for staff_member in all_staff:
        try:
            staff_member.leave_balance = LeaveBalance.objects.get(staff=staff_member)
        except LeaveBalance.DoesNotExist:
            # Create default leave balance if doesn't exist
            staff_member.leave_balance = LeaveBalance.objects.create(
                staff=staff_member,
                annual_leave=21,
                sick_leave=10,
                casual_leave=7
            )
    
    context = {
        'all_staff': all_staff,
    }
    return render(request, 'hospital/create_leave_for_staff.html', context)

