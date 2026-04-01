"""
Views for Lab Management: Equipment, Reagents, and Quality Control
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Count, Sum, Avg, F
from django.utils import timezone
from django.http import JsonResponse
from django.forms import ModelForm
from django import forms
from datetime import date, timedelta
from decimal import Decimal

from .models import Staff, Department
from .models_lab_management import (
    LabEquipment, EquipmentMaintenanceLog, LabReagent, ReagentTransaction,
    QualityControlTest, QCAlert
)


def _user_can_manage_lab_equipment(user):
    """Allow lab technician, admin role, or superuser to add/edit lab equipment."""
    if not user.is_authenticated:
        return False
    if user.is_superuser or user.is_staff:
        return True
    try:
        staff = user.staff
        role = (staff.profession or '').lower()
        if role in ('lab_technician', 'lab_tech') or 'lab' in role:
            return True
        if user.groups.filter(name__icontains='lab').exists():
            return True
        if user.groups.filter(name__in=['Admin', 'Administrator']).exists():
            return True
    except (Staff.DoesNotExist, AttributeError):
        pass
    return False


class LabEquipmentForm(ModelForm):
    """Form for lab technicians/admins to add lab equipment."""
    class Meta:
        model = LabEquipment
        fields = [
            'equipment_code', 'name', 'equipment_type', 'manufacturer', 'model',
            'serial_number', 'location', 'department', 'status',
            'purchase_date', 'warranty_expiry', 'purchase_cost',
            'next_maintenance_due', 'next_calibration_due', 'calibration_interval_days',
            'notes'
        ]
        widgets = {
            'equipment_code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. HEM-001'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'equipment_type': forms.Select(attrs={'class': 'form-select'}),
            'manufacturer': forms.TextInput(attrs={'class': 'form-control'}),
            'model': forms.TextInput(attrs={'class': 'form-control'}),
            'serial_number': forms.TextInput(attrs={'class': 'form-control'}),
            'location': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Lab section or room'}),
            'department': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'purchase_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'warranty_expiry': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'purchase_cost': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'next_maintenance_due': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'next_calibration_due': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'calibration_interval_days': forms.NumberInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def clean_serial_number(self):
        value = self.cleaned_data.get('serial_number')
        if value is not None and not value.strip():
            return None
        return value


@login_required
def lab_equipment_dashboard(request):
    """Lab equipment status dashboard"""
    today = timezone.now().date()
    
    # Get all equipment
    all_equipment = LabEquipment.objects.filter(is_deleted=False).select_related('department', 'assigned_to', 'assigned_to__user')
    
    # Statistics
    stats = {
        'total': all_equipment.count(),
        'operational': all_equipment.filter(status='operational').count(),
        'in_use': all_equipment.filter(status='in_use').count(),
        'maintenance': all_equipment.filter(status='maintenance').count(),
        'out_of_order': all_equipment.filter(status='out_of_order').count(),
        'needs_maintenance': sum(1 for eq in all_equipment if eq.needs_maintenance),
        'needs_calibration': sum(1 for eq in all_equipment if eq.needs_calibration),
    }
    
    # Equipment by type
    equipment_by_type = all_equipment.values('equipment_type').annotate(
        count=Count('id')
    ).order_by('-count')
    
    # Recent maintenance
    recent_maintenance = EquipmentMaintenanceLog.objects.filter(
        is_deleted=False
    ).select_related('equipment', 'technician', 'technician__user').order_by('-service_date')[:10]
    
    # Upcoming maintenance
    upcoming_maintenance = []
    for eq in all_equipment:
        if eq.next_maintenance_due and eq.next_maintenance_due <= today + timedelta(days=7):
            upcoming_maintenance.append(eq)
    
    # Upcoming calibrations
    upcoming_calibrations = []
    for eq in all_equipment:
        if eq.next_calibration_due and eq.next_calibration_due <= today + timedelta(days=7):
            upcoming_calibrations.append(eq)
    
    # Active alerts
    active_alerts = QCAlert.objects.filter(
        is_resolved=False,
        is_deleted=False
    ).select_related('equipment').order_by('-priority', '-created')[:10]
    
    context = {
        'equipment': all_equipment,
        'stats': stats,
        'equipment_by_type': equipment_by_type,
        'recent_maintenance': recent_maintenance,
        'upcoming_maintenance': upcoming_maintenance,
        'upcoming_calibrations': upcoming_calibrations,
        'active_alerts': active_alerts,
        'can_add_equipment': _user_can_manage_lab_equipment(request.user),
    }
    return render(request, 'hospital/lab_equipment_dashboard.html', context)


@login_required
def lab_equipment_add(request):
    """Add new lab equipment. Allowed for lab technicians, admin, and superuser."""
    if not _user_can_manage_lab_equipment(request.user):
        messages.error(request, 'You do not have permission to add lab equipment.')
        return redirect('hospital:lab_equipment_dashboard')
    form = LabEquipmentForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, f'Equipment "{form.instance.name}" has been added.')
        return redirect('hospital:lab_equipment_dashboard')
    context = {'form': form, 'is_edit': False}
    return render(request, 'hospital/lab_equipment_form.html', context)


@login_required
def lab_reagent_dashboard(request):
    """Lab reagent inventory dashboard"""
    today = timezone.now().date()
    
    # Get all reagents
    all_reagents = LabReagent.objects.filter(is_deleted=False)
    
    # Statistics
    stats = {
        'total': all_reagents.count(),
        'low_stock': sum(1 for r in all_reagents if r.is_low_stock),
        'expired': sum(1 for r in all_reagents if r.is_expired),
        'expiring_soon': sum(1 for r in all_reagents if r.is_expiring_soon),
        'total_value': sum(r.stock_value for r in all_reagents),
    }
    
    # Low stock items
    low_stock_items = [r for r in all_reagents if r.is_low_stock]
    
    # Expired items
    expired_items = [r for r in all_reagents if r.is_expired]
    
    # Expiring soon (next 30 days)
    expiring_soon_items = [r for r in all_reagents if r.is_expiring_soon]
    
    # Recent transactions
    recent_transactions = ReagentTransaction.objects.filter(
        is_deleted=False
    ).select_related('reagent', 'performed_by', 'performed_by__user').order_by('-created')[:20]
    
    # Reagents by category
    reagents_by_category = all_reagents.values('category').annotate(
        count=Count('id'),
        total_value=Sum(F('quantity_on_hand') * F('unit_cost'))
    ).order_by('-count')
    
    # Active alerts
    active_alerts = QCAlert.objects.filter(
        is_resolved=False,
        is_deleted=False,
        alert_type__in=['reagent_low', 'reagent_expired']
    ).select_related('reagent').order_by('-priority', '-created')[:10]
    
    context = {
        'reagents': all_reagents,
        'stats': stats,
        'low_stock_items': low_stock_items,
        'expired_items': expired_items,
        'expiring_soon_items': expiring_soon_items,
        'recent_transactions': recent_transactions,
        'reagents_by_category': reagents_by_category,
        'active_alerts': active_alerts,
    }
    return render(request, 'hospital/lab_reagent_dashboard.html', context)


@login_required
def quality_control_dashboard(request):
    """Quality control test dashboard"""
    today = timezone.now().date()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)
    
    # Get all QC tests
    all_qc_tests = QualityControlTest.objects.filter(is_deleted=False).select_related(
        'equipment', 'control_material', 'performed_by', 'performed_by__user',
        'reviewed_by', 'reviewed_by__user'
    )

    # Recent tests queryset (last 30 days) - keep as queryset, don't slice yet
    recent_tests_qs = all_qc_tests.filter(test_date__gte=month_ago).order_by('-test_date', '-test_time')
    
    # Recent tests for display (slice only when needed)
    recent_tests = recent_tests_qs[:50]

    # Statistics (use week_ago for stats)
    week_recent_tests_qs = all_qc_tests.filter(test_date__gte=week_ago)
    stats = {
        'total_tests': week_recent_tests_qs.count(),
        'passed': week_recent_tests_qs.filter(status='passed').count(),
        'failed': week_recent_tests_qs.filter(status='failed').count(),
        'warning': week_recent_tests_qs.filter(status='warning').count(),
        'pending': week_recent_tests_qs.filter(status='pending').count(),
        'with_violations': week_recent_tests_qs.filter(
            Q(rule_1_2s=True) | Q(rule_1_3s=True) | Q(rule_2_2s=True) |
            Q(rule_r_4s=True) | Q(rule_4_1s=True) | Q(rule_10x=True)
        ).count(),
    }

    # Tests by equipment
    tests_by_equipment = all_qc_tests.filter(test_date__gte=week_ago).values(
        'equipment__name'
    ).annotate(
        total=Count('id'),
        passed=Count('id', filter=Q(status='passed')),
        failed=Count('id', filter=Q(status='failed')),
    ).order_by('-total')

    # Failed tests - filter before slicing
    failed_tests = recent_tests_qs.filter(status='failed')[:10]

    # Tests with violations - filter before slicing
    tests_with_violations = recent_tests_qs.filter(
        Q(rule_1_2s=True) | Q(rule_1_3s=True) | Q(rule_2_2s=True) |
        Q(rule_r_4s=True) | Q(rule_4_1s=True) | Q(rule_10x=True)
    )[:10]
    
    # Active alerts
    active_alerts = QCAlert.objects.filter(
        is_resolved=False,
        is_deleted=False,
        alert_type='qc_failure'
    ).select_related('equipment', 'qc_test').order_by('-priority', '-created')[:10]
    
    # Equipment needing QC
    equipment_list = LabEquipment.objects.filter(is_deleted=False, status__in=['operational', 'in_use'])
    equipment_qc_status = []
    for eq in equipment_list:
        last_qc = all_qc_tests.filter(equipment=eq).order_by('-test_date').first()
        days_since_qc = None
        if last_qc:
            days_since_qc = (today - last_qc.test_date).days
        
        equipment_qc_status.append({
            'equipment': eq,
            'last_qc': last_qc,
            'days_since_qc': days_since_qc,
            'needs_qc': days_since_qc is None or days_since_qc > 1,  # Daily QC expected
        })
    
    context = {
        'recent_tests': recent_tests,
        'stats': stats,
        'tests_by_equipment': tests_by_equipment,
        'failed_tests': failed_tests,
        'tests_with_violations': tests_with_violations,
        'active_alerts': active_alerts,
        'equipment_qc_status': equipment_qc_status,
    }
    return render(request, 'hospital/quality_control_dashboard.html', context)


@login_required
def equipment_detail(request, equipment_id):
    """Equipment detail view with maintenance history"""
    equipment = get_object_or_404(LabEquipment, pk=equipment_id, is_deleted=False)
    
    # Maintenance history
    maintenance_logs = EquipmentMaintenanceLog.objects.filter(
        equipment=equipment,
        is_deleted=False
    ).select_related('technician', 'technician__user').order_by('-service_date')
    
    # QC tests for this equipment
    qc_tests = QualityControlTest.objects.filter(
        equipment=equipment,
        is_deleted=False
    ).select_related('performed_by', 'performed_by__user', 'reviewed_by', 'reviewed_by__user').order_by('-test_date', '-test_time')[:20]
    
    # Recent usage (tests run)
    recent_usage = equipment.total_tests_run
    
    context = {
        'equipment': equipment,
        'maintenance_logs': maintenance_logs,
        'qc_tests': qc_tests,
        'recent_usage': recent_usage,
    }
    return render(request, 'hospital/equipment_detail.html', context)


@login_required
def reagent_detail(request, reagent_id):
    """Reagent detail view with transaction history"""
    reagent = get_object_or_404(LabReagent, pk=reagent_id, is_deleted=False)
    
    # Transaction history
    transactions_qs = ReagentTransaction.objects.filter(
        reagent=reagent,
        is_deleted=False
    ).select_related('performed_by', 'performed_by__user').order_by('-created')
    
    # Transaction history for display
    transactions = transactions_qs[:50]
    
    # Usage statistics - use the queryset before slicing
    usage_stats = transactions_qs.filter(transaction_type='used').aggregate(
        total_used=Sum('quantity'),
        usage_count=Count('id')
    )
    
    context = {
        'reagent': reagent,
        'transactions': transactions,
        'usage_stats': usage_stats,
    }
    return render(request, 'hospital/reagent_detail.html', context)


@login_required
def qc_test_detail(request, qc_test_id):
    """QC test detail view"""
    qc_test = get_object_or_404(QualityControlTest, pk=qc_test_id, is_deleted=False)
    
    # Related alerts
    related_alerts = QCAlert.objects.filter(
        qc_test=qc_test,
        is_deleted=False
    ).select_related('resolved_by', 'resolved_by__user')
    
    context = {
        'qc_test': qc_test,
        'related_alerts': related_alerts,
    }
    return render(request, 'hospital/qc_test_detail.html', context)


@login_required
def create_qc_test(request):
    """Create a new QC test"""
    if request.method == 'POST':
        try:
            equipment = get_object_or_404(LabEquipment, pk=request.POST.get('equipment'), is_deleted=False)
            
            qc_test = QualityControlTest.objects.create(
                equipment=equipment,
                qc_type=request.POST.get('qc_type', 'daily'),
                test_date=request.POST.get('test_date') or timezone.now().date(),
                test_time=request.POST.get('test_time') or timezone.now().time(),
                control_material_id=request.POST.get('control_material') or None,
                batch_number=request.POST.get('batch_number', ''),
                test_name=request.POST.get('test_name', ''),
                expected_value=request.POST.get('expected_value', ''),
                observed_value=request.POST.get('observed_value', ''),
                units=request.POST.get('units', ''),
                within_range=request.POST.get('within_range') == 'on',
                performed_by=request.user.staff if hasattr(request.user, 'staff') else None,
                notes=request.POST.get('notes', ''),
            )
            
            # Check QC rules (simplified - can be enhanced)
            if qc_test.expected_value and qc_test.observed_value:
                try:
                    expected = float(qc_test.expected_value)
                    observed = float(qc_test.observed_value)
                    deviation = abs(observed - expected) / expected if expected != 0 else 0
                    
                    # Simple rule checks (can be enhanced with proper Westgard rules)
                    if deviation > 0.03:  # 3% deviation
                        qc_test.rule_1_2s = True
                    if deviation > 0.05:  # 5% deviation
                        qc_test.rule_1_3s = True
                except ValueError:
                    pass
            
            qc_test.save()
            
            # Create alert if failed
            if qc_test.status == 'failed':
                QCAlert.objects.create(
                    alert_type='qc_failure',
                    priority='critical',
                    title=f'QC Failed: {equipment.name} - {qc_test.test_name}',
                    message=f'QC test failed on {qc_test.test_date}. {qc_test.corrective_action or "No corrective action taken."}',
                    equipment=equipment,
                    qc_test=qc_test,
                )
            
            messages.success(request, 'QC test created successfully.')
            return redirect('hospital:quality_control_dashboard')
        except Exception as e:
            messages.error(request, f'Error creating QC test: {str(e)}')
    
    # GET request - show form
    equipment_list = LabEquipment.objects.filter(is_deleted=False, status__in=['operational', 'in_use'])
    control_materials = LabReagent.objects.filter(category='control', is_deleted=False)
    
    context = {
        'equipment_list': equipment_list,
        'control_materials': control_materials,
    }
    return render(request, 'hospital/create_qc_test.html', context)


@login_required
def record_reagent_transaction(request):
    """Record reagent usage or receipt with proper accountability"""
    # Get staff profile - use 'staff' as related_name (not 'staff_profile')
    try:
        staff = request.user.staff
    except Staff.DoesNotExist:
        staff = None
    
    # Check if user is lab technician - check both profession and user groups
    is_lab_tech = False
    if staff:
        profession_lower = (staff.profession or '').lower()
        is_lab_tech = (
            profession_lower == 'lab_technician' or 
            profession_lower == 'lab_tech' or
            'lab' in profession_lower or
            request.user.groups.filter(name__icontains='lab').exists()
        )
    
    if request.method == 'POST':
        try:
            reagent = get_object_or_404(LabReagent, pk=request.POST.get('reagent'), is_deleted=False)
            transaction_type = request.POST.get('transaction_type')
            quantity = Decimal(request.POST.get('quantity', '0'))
            
            # SECURITY: Lab techs can ONLY deduct (use) reagents, not add
            if is_lab_tech and transaction_type != 'used':
                messages.error(request, 'Lab technicians can only record reagent usage (deductions). Adding quantities requires inventory manager approval.')
                return redirect('hospital:record_reagent_transaction')
            
            # ACCOUNTABILITY: For "used" transactions, require patient and purpose
            patient_id = request.POST.get('patient_id')
            lab_result_id = request.POST.get('lab_result_id')
            purpose = request.POST.get('purpose', '').strip()
            test_name = request.POST.get('test_name', '').strip()
            
            if transaction_type == 'used':
                if not patient_id:
                    messages.error(request, 'Patient selection is required when recording reagent usage for accountability.')
                    return redirect('hospital:record_reagent_transaction')
                if not purpose:
                    messages.error(request, 'Purpose/clinical indication is required when recording reagent usage.')
                    return redirect('hospital:record_reagent_transaction')
                
                # Get patient
                from .models import Patient
                try:
                    patient = Patient.objects.get(pk=patient_id, is_deleted=False)
                except Patient.DoesNotExist:
                    messages.error(request, 'Selected patient not found.')
                    return redirect('hospital:record_reagent_transaction')
                
                # Get lab result if provided
                lab_result = None
                if lab_result_id:
                    from .models import LabResult
                    try:
                        lab_result = LabResult.objects.get(pk=lab_result_id, is_deleted=False)
                        if not test_name:
                            test_name = lab_result.test.name if lab_result.test else ''
                    except LabResult.DoesNotExist:
                        pass
            else:
                patient = None
                lab_result = None
            
            # Validate quantity for deductions
            if transaction_type in ['used', 'expired']:
                if quantity > reagent.quantity_on_hand:
                    messages.error(request, f'Insufficient stock. Available: {reagent.quantity_on_hand} {reagent.unit}, Requested: {quantity} {reagent.unit}')
                    return redirect('hospital:record_reagent_transaction')
            
            transaction = ReagentTransaction.objects.create(
                reagent=reagent,
                transaction_type=transaction_type,
                quantity=quantity,
                batch_number=request.POST.get('batch_number', ''),
                expiry_date=request.POST.get('expiry_date') or None,
                performed_by=staff,
                reference=request.POST.get('reference', ''),
                notes=request.POST.get('notes', ''),
                patient=patient if transaction_type == 'used' else None,
                lab_result=lab_result if transaction_type == 'used' else None,
                purpose=purpose if transaction_type == 'used' else '',
                test_name=test_name if transaction_type == 'used' else '',
            )
            
            # Update reagent quantity
            if transaction_type == 'received':
                reagent.quantity_on_hand += quantity
            elif transaction_type == 'used':
                reagent.quantity_on_hand -= quantity
                reagent.total_used += quantity
                reagent.last_used_at = timezone.now()
            elif transaction_type == 'expired':
                reagent.quantity_on_hand -= quantity
            
            reagent.save()
            
            # Create alert if low stock
            if reagent.is_low_stock and not QCAlert.objects.filter(
                reagent=reagent,
                alert_type='reagent_low',
                is_resolved=False,
                is_deleted=False
            ).exists():
                QCAlert.objects.create(
                    alert_type='reagent_low',
                    priority='high',
                    title=f'Low Stock: {reagent.name}',
                    message=f'{reagent.name} is below reorder level ({reagent.quantity_on_hand} {reagent.unit} remaining)',
                    reagent=reagent,
                )
            
            messages.success(request, 'Transaction recorded successfully.')
            return redirect('hospital:lab_reagent_dashboard')
        except Exception as e:
            messages.error(request, f'Error recording transaction: {str(e)}')
    
    # GET request - show form
    reagents = LabReagent.objects.filter(is_deleted=False).order_by('name')
    
    # Get recent patients and lab results for accountability
    recent_patients = []
    recent_lab_results = []
    if is_lab_tech:
        # For lab techs, show recent patients and pending lab results
        from .models import Patient, LabResult, Order
        recent_patients = Patient.objects.filter(
            encounters__orders__order_type='lab',
            encounters__orders__is_deleted=False
        ).distinct().order_by('-encounters__orders__requested_at')[:50]
        
        # Get pending/in-progress lab results
        recent_lab_results = LabResult.objects.filter(
            status__in=['pending', 'in_progress'],
            is_deleted=False
        ).select_related('test', 'order', 'order__encounter', 'order__encounter__patient').order_by('-created')[:50]
    
    context = {
        'reagents': reagents,
        'is_lab_tech': is_lab_tech,
        'recent_patients': recent_patients,
        'recent_lab_results': recent_lab_results,
    }
    return render(request, 'hospital/record_reagent_transaction.html', context)


@login_required
def resolve_alert(request, alert_id):
    """Resolve a QC alert"""
    if request.method == 'POST':
        alert = get_object_or_404(QCAlert, pk=alert_id, is_deleted=False)
        alert.is_resolved = True
        alert.resolved_at = timezone.now()
        alert.resolved_by = request.user.staff if hasattr(request.user, 'staff') else None
        alert.resolution_notes = request.POST.get('resolution_notes', '')
        alert.save()
        messages.success(request, 'Alert resolved successfully.')
        return redirect(request.META.get('HTTP_REFERER', 'hospital:quality_control_dashboard'))
    
    alert = get_object_or_404(QCAlert, pk=alert_id, is_deleted=False)
    context = {
        'alert': alert,
    }
    return render(request, 'hospital/resolve_alert.html', context)










