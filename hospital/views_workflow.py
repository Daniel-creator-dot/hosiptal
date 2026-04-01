"""
Patient Workflow Views
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q
from datetime import timedelta
from .models import Patient, Encounter, VitalSign, Staff, Order
from .models_workflow import PatientFlowStage, WorkflowTemplate, Bill, PaymentRequest


def ensure_patient_flow_stages(encounter):
    """
    Ensure PatientFlowStage rows exist for an encounter (template or defaults).
    Used by patient_flow and record_vitals so vitals recording advances workflow
    even when the flow page was never opened first.
    """
    existing = PatientFlowStage.objects.filter(encounter=encounter, is_deleted=False)
    if existing.exists():
        return

    try:
        template = WorkflowTemplate.objects.get(
            encounter_type=encounter.encounter_type,
            is_active=True
        )
        for stage_type in template.stages:
            PatientFlowStage.objects.get_or_create(
                encounter=encounter,
                stage_type=stage_type,
                is_deleted=False,
                defaults={'status': 'pending'}
            )
    except WorkflowTemplate.DoesNotExist:
        if encounter.encounter_type == 'inpatient':
            default_stages = ['registration', 'triage', 'vitals', 'consultation', 'laboratory', 'admission', 'billing', 'payment']
        elif encounter.encounter_type == 'er':
            default_stages = ['registration', 'triage', 'vitals', 'consultation', 'treatment', 'billing', 'payment', 'discharge']
        else:
            default_stages = ['registration', 'vitals', 'consultation', 'billing', 'payment']

        for stage_type in default_stages:
            PatientFlowStage.objects.get_or_create(
                encounter=encounter,
                stage_type=stage_type,
                is_deleted=False,
                defaults={'status': 'pending'}
            )


@login_required
def patient_flow(request, encounter_id):
    """World-Class Patient Flow Interface with Real-time Tracking"""
    from datetime import timedelta
    encounter = get_object_or_404(Encounter, pk=encounter_id, is_deleted=False)

    ensure_patient_flow_stages(encounter)
    stages = PatientFlowStage.objects.filter(
        encounter=encounter,
        is_deleted=False
    ).select_related('completed_by__user').order_by('created')
    
    # Calculate progress statistics
    total_stages = stages.count()
    completed_count = stages.filter(status='completed').count()
    in_progress_count = stages.filter(status='in_progress').count()
    pending_count = stages.filter(status='pending').count()
    progress_percentage = round((completed_count / total_stages * 100) if total_stages > 0 else 0)
    
    # Calculate timing statistics
    completed_stages = stages.filter(status='completed', started_at__isnull=False, completed_at__isnull=False)
    total_duration = timedelta()
    for stage in completed_stages:
        if stage.started_at and stage.completed_at:
            total_duration += (stage.completed_at - stage.started_at)
    
    total_time = f"{int(total_duration.total_seconds() // 60)} min" if total_duration else "0 min"
    avg_time = f"{int(total_duration.total_seconds() // 60 // completed_count) if completed_count > 0 else 0} min"
    
    # Calculate current wait time
    current_wait = "0 min"
    in_progress_stage = stages.filter(status='in_progress').first()
    if in_progress_stage and in_progress_stage.started_at:
        wait_duration = timezone.now() - in_progress_stage.started_at
        current_wait = f"{int(wait_duration.total_seconds() // 60)} min"
    
    # Get unique staff count
    staff_count = stages.filter(completed_by__isnull=False).values('completed_by').distinct().count()
    
    # Get current stage
    current_stage = stages.filter(status__in=['pending', 'in_progress']).first()
    
    # Check if vitals exist
    has_vitals = encounter.vitals.filter(is_deleted=False).exists()
    
    # Add helper properties to stages
    stages_list = list(stages)
    for stage in stages_list:
        # Calculate duration for completed stages
        if stage.status == 'completed' and stage.started_at and stage.completed_at:
            duration = stage.completed_at - stage.started_at
            minutes = int(duration.total_seconds() // 60)
            seconds = int(duration.total_seconds() % 60)
            stage.duration = f"{minutes}m {seconds}s" if minutes > 0 else f"{seconds}s"
        else:
            stage.duration = "N/A"
        
        # Calculate elapsed time for in-progress stages
        if stage.status == 'in_progress' and stage.started_at:
            elapsed = timezone.now() - stage.started_at
            minutes = int(elapsed.total_seconds() // 60)
            stage.elapsed_time = f"{minutes} min" if minutes > 0 else "< 1 min"
        else:
            stage.elapsed_time = "N/A"
    
    context = {
        'encounter': encounter,
        'stages': stages_list,
        'current_stage': current_stage,
        'has_vitals': has_vitals,
        # Statistics
        'total_stages': total_stages,
        'completed_count': completed_count,
        'in_progress_count': in_progress_count,
        'pending_count': pending_count,
        'progress_percentage': progress_percentage,
        'total_time': total_time,
        'avg_time': avg_time,
        'current_wait': current_wait,
        'staff_count': staff_count,
    }
    return render(request, 'hospital/patient_flow_worldclass.html', context)


@login_required
def start_flow_stage(request, stage_id):
    """Start a workflow stage"""
    stage = get_object_or_404(PatientFlowStage, pk=stage_id, is_deleted=False)
    
    if hasattr(request.user, 'staff_profile'):
        staff = request.user.staff
        stage.start(staff)
        
        # Redirect to appropriate view based on stage type
        if stage.stage_type == 'registration':
            return redirect('hospital:patient_detail', pk=stage.encounter.patient.pk)
        elif stage.stage_type == 'vitals':
            return redirect('hospital:record_vitals', encounter_id=stage.encounter.pk)
        elif stage.stage_type == 'consultation':
            return redirect('hospital:consultation_view', encounter_id=stage.encounter.pk)
        elif stage.stage_type == 'billing':
            return redirect('hospital:create_bill', encounter_id=stage.encounter.pk)
        elif stage.stage_type == 'payment':
            return redirect('hospital:cashier_payments')
    
    messages.success(request, f'{stage.get_stage_type_display()} stage started')
    return redirect('hospital:patient_flow', encounter_id=stage.encounter.pk)


@login_required
def complete_flow_stage(request, stage_id):
    """Complete a workflow stage"""
    stage = get_object_or_404(PatientFlowStage, pk=stage_id, is_deleted=False)
    
    if hasattr(request.user, 'staff_profile'):
        staff = request.user.staff
        stage.complete(staff)
        
        # Auto-start next stage (if consultation, auto-start after vitals)
        if stage.stage_type == 'vitals':
            next_stage = PatientFlowStage.objects.filter(
                encounter=stage.encounter,
                stage_type='consultation',
                status='pending',
                is_deleted=False
            ).first()
            if next_stage:
                next_stage.start(staff)
        else:
            next_stage = PatientFlowStage.objects.filter(
                encounter=stage.encounter,
                status='pending',
                is_deleted=False
            ).first()
            
            if next_stage:
                next_stage.start(staff)
    
    messages.success(request, f'{stage.get_stage_type_display()} completed successfully')
    return redirect('hospital:patient_flow', encounter_id=stage.encounter.pk)


from .decorators import role_required

@login_required
@role_required('doctor', 'nurse', 'midwife', 'admin', message='Access denied. Front desk staff cannot record vital signs.')
def record_vitals(request, encounter_id):
    """Record vital signs with automated validation - Only medical staff (doctors, nurses, midwives)"""
    encounter = get_object_or_404(Encounter, pk=encounter_id, is_deleted=False)
    
    if request.method == 'POST':
        from .models import VitalSign
        from .services.vital_signs_validator import VitalSignsValidator
        from decimal import Decimal
        
        # Helper functions for safe type conversion
        def safe_int(value, default=None):
            """Safely convert string to int, returning None for empty strings"""
            if not value or value == '':
                return default
            try:
                return int(value)
            except (ValueError, TypeError):
                return default
        
        def safe_decimal(value, default=None):
            """Safely convert string to Decimal, returning None for empty strings"""
            if not value or value == '':
                return default
            try:
                return Decimal(str(value))
            except (ValueError, TypeError):
                return default
        
        vital_data = {
            'systolic_bp': safe_int(request.POST.get('systolic_bp')),
            'diastolic_bp': safe_int(request.POST.get('diastolic_bp')),
            'pulse': safe_int(request.POST.get('pulse')),
            'temperature': safe_decimal(request.POST.get('temperature')),
            'spo2': safe_int(request.POST.get('spo2')),
            'respiratory_rate': safe_int(request.POST.get('respiratory_rate')),
        }
        
        # Validate vital signs
        patient = encounter.patient
        try:
            validation_results = VitalSignsValidator.validate_all_vitals(
                vital_data,
                patient.age,
                patient.gender
            )
        except:
            validation_results = {'overall': {'is_ok': True}}
        
        # Get current staff
        current_staff = None
        if hasattr(request.user, 'staff_profile'):
            current_staff = request.user.staff
        elif hasattr(request.user, 'staff'):
            current_staff = request.user.staff
        
        # Create vital sign record with enhanced fields
        vital = VitalSign.objects.create(
            encounter=encounter,
            # Core vitals
            systolic_bp=vital_data['systolic_bp'],
            diastolic_bp=vital_data['diastolic_bp'],
            pulse=vital_data['pulse'],
            temperature=vital_data['temperature'],
            spo2=vital_data['spo2'],
            respiratory_rate=vital_data['respiratory_rate'],
            # Extended vitals
            weight=safe_decimal(request.POST.get('weight')),
            height=safe_decimal(request.POST.get('height')),
            blood_glucose=safe_decimal(request.POST.get('blood_glucose')),
            # Clinical assessment
            consciousness_level=request.POST.get('consciousness_level', 'alert'),
            pain_score=safe_int(request.POST.get('pain_score')),
            supplemental_oxygen=request.POST.get('supplemental_oxygen') == 'true',
            oxygen_flow_rate=safe_decimal(request.POST.get('oxygen_flow_rate')),
            # Additional context
            position=request.POST.get('position', ''),
            capillary_refill=safe_int(request.POST.get('capillary_refill')),
            notes=request.POST.get('notes', ''),
            recorded_by=current_staff,
        )
        # Scores are auto-calculated in model's save() method

        ensure_patient_flow_stages(encounter)

        # Complete vitals stage and move to consultation (doctor)
        vitals_stage = PatientFlowStage.objects.filter(
            encounter=encounter,
            stage_type='vitals',
            status__in=['pending', 'in_progress']
        ).first()
        
        if vitals_stage:
            # Get current staff (nurse) if available
            current_staff = None
            if hasattr(request.user, 'staff_profile'):
                current_staff = request.user.staff
            elif hasattr(request.user, 'staff'):
                current_staff = request.user.staff
            
            # Complete vitals stage
            vitals_stage.complete(current_staff)
            
            # Auto-create and auto-start consultation stage (doctor) if it doesn't exist
            consultation_stage = PatientFlowStage.objects.filter(
                encounter=encounter,
                stage_type='consultation',
                is_deleted=False
            ).first()
            
            if not consultation_stage:
                # Use get_or_create to prevent duplicates (race condition safe)
                consultation_stage, created = PatientFlowStage.objects.get_or_create(
                    encounter=encounter,
                    stage_type='consultation',
                    is_deleted=False,
                    defaults={
                        'status': 'pending',
                        'notes': 'Auto-created after vital signs recorded'
                    }
                )
            
            # Auto-start consultation stage (move to doctor)
            if consultation_stage and consultation_stage.status == 'pending':
                consultation_stage.start(None)  # Will be assigned when doctor starts
            
            # Update queue entry if exists - allow nurse to assign doctor
            from .models_queue import QueueEntry
            queue_entry = QueueEntry.objects.filter(
                encounter=encounter,
                is_deleted=False
            ).first()
            
            if queue_entry:
                # If doctor is already assigned by front desk, keep it
                # Otherwise, nurse can assign one (handled in separate view)
                pass
        
        # Show validation message
        overall = validation_results.get('overall', {})
        if overall.get('is_ok'):
            messages.success(request, overall.get('message', 'Vital signs recorded successfully. Patient moved to consultation.'))
        elif 'critical' in overall.get('status', ''):
            messages.error(request, overall.get('message', '⚠️ Critical vital signs recorded - Immediate attention required! Patient moved to consultation.'))
        else:
            messages.warning(request, overall.get('message', '⚠️ Abnormal vital signs recorded - Review required. Patient moved to consultation.'))
        
        # Redirect to patient flow
        return redirect('hospital:patient_flow', encounter_id=encounter.pk)
    
    # Get previous vitals for comparison
    previous_vitals = encounter.vitals.filter(is_deleted=False).order_by('-recorded_at')[:10]
    
    context = {
        'encounter': encounter,
        'previous_vitals': previous_vitals,
    }
    return render(request, 'hospital/record_vitals_worldclass.html', context)


@login_required
def create_bill(request, encounter_id):
    """Create/Issue bill for patient"""
    encounter = get_object_or_404(Encounter, pk=encounter_id, is_deleted=False)
    
    # Import models at function level
    from .models import Invoice, InvoiceLine, Payer
    from decimal import Decimal
    from datetime import timedelta
    
    if request.method == 'POST':
        # Get or determine payer - ensure payer is not None
        payer = encounter.patient.primary_insurance
        if not payer:
            # Try to get Cash payer
            payer = Payer.objects.filter(payer_type='cash', is_active=True, is_deleted=False).first()
            if not payer:
                # Try any active payer
                payer = Payer.objects.filter(is_active=True, is_deleted=False).first()
                if not payer:
                    # Create a default Cash payer if none exists
                    payer = Payer.objects.create(
                        name='Cash',
                        payer_type='cash',
                        is_active=True
                    )
        
        # Ensure we have a payer before creating invoice
        if not payer:
            messages.error(request, 'Cannot create invoice: No payer available. Please configure payers in the system.')
            return redirect('hospital:patient_flow', encounter_id=encounter_id)
        
        # Use all_objects so we find existing invoice even in write-off period (avoid duplicates)
        invoice, created = Invoice.all_objects.get_or_create(
            encounter=encounter,
            patient=encounter.patient,
            is_deleted=False,
            defaults={
                'payer': payer,
                'due_at': timezone.now() + timedelta(days=30),
                'status': 'draft',
            }
        )
        invoice.update_totals()
        if (invoice.total_amount or 0) <= 0:
            messages.error(
                request,
                'Cannot issue bill: invoice total is zero. Add services (e.g. lab, pharmacy) to the encounter first, then issue the bill.'
            )
            return redirect('hospital:create_bill', encounter_id=encounter_id)
        # Mark invoice as issued when we issue the bill
        invoice.status = 'issued'
        invoice.save(update_fields=['status'])
        # Create bill
        bill_type = 'insurance' if request.POST.get('has_insurance') == 'on' else 'cash'
        insurance_covered = Decimal(request.POST.get('insurance_covered', 0))
        bill = Bill.objects.create(
            invoice=invoice,
            encounter=encounter,
            patient=encounter.patient,
            bill_type=bill_type,
            total_amount=invoice.total_amount,
            insurance_covered=insurance_covered if bill_type == 'insurance' else 0,
            status='issued',
            issued_by=request.user,
            due_date=(timezone.now() + timedelta(days=30)).date(),
        )
        
        # Create payment request if patient portion > 0
        try:
            from .models_workflow import PaymentRequest
            if bill.patient_portion > 0:
                PaymentRequest.objects.create(
                    invoice=invoice,
                    patient=encounter.patient,
                    requested_amount=bill.patient_portion,
                    payment_type='full',
                    requested_by=request.user,
                    status='pending',
                )
        except Exception:
            pass  # PaymentRequest may not exist
        
        # Complete billing stage
        billing_stage = PatientFlowStage.objects.filter(
            encounter=encounter,
            stage_type='billing',
            is_deleted=False
        ).first()
        if billing_stage:
            if hasattr(request.user, 'staff_profile'):
                billing_stage.complete(request.user.staff)
        
        messages.success(request, f'Bill {bill.bill_number} issued successfully')
        return redirect('hospital:patient_flow', encounter_id=encounter_id)
    
    # Get or create invoice - ensure payer is not None
    payer = encounter.patient.primary_insurance
    if not payer:
        # Try to get Cash payer
        payer = Payer.objects.filter(payer_type='cash', is_active=True, is_deleted=False).first()
        if not payer:
            # Try any active payer
            payer = Payer.objects.filter(is_active=True, is_deleted=False).first()
            if not payer:
                # Create a default Cash payer if none exists
                payer = Payer.objects.create(
                    name='Cash',
                    payer_type='cash',
                    is_active=True
                )
    
    # Ensure we have a payer before creating invoice
    if not payer:
        messages.error(request, 'Cannot create invoice: No payer available. Please configure payers in the system.')
        return redirect('hospital:patient_flow', encounter_id=encounter_id)
    
    # Use all_objects so we find existing invoice even in write-off period (avoid duplicates)
    invoice, created = Invoice.all_objects.get_or_create(
        encounter=encounter,
        patient=encounter.patient,
        is_deleted=False,
        defaults={
            'payer': payer,
            'due_at': timezone.now() + timedelta(days=30),
            'status': 'draft',
        }
    )
    invoice.update_totals()
    try:
        from hospital.utils_invoice_line import heal_invoice_zero_line_prices
        heal_invoice_zero_line_prices(invoice)
    except Exception:
        pass
    # Exclude waived lines from display
    invoice_lines = invoice.lines.filter(is_deleted=False, waived_at__isnull=True).select_related('service_code')
    context = {
        'encounter': encounter,
        'invoice': invoice,
        'invoice_lines': invoice_lines,
        'has_bill': Bill.objects.filter(invoice=invoice, is_deleted=False).exists(),
    }
    return render(request, 'hospital/create_bill.html', context)


@login_required
def flow_dashboard(request):
    """
    World-Class Patient Flow Dashboard
    Real-time monitoring of all patients in the system
    
    Features:
    - Date filtering (defaults to today)
    - Auto-archives consultations older than 24 hours
    - Historical view for previous encounters
    """
    from collections import defaultdict
    from datetime import timedelta, datetime
    
    today = timezone.now().date()
    now = timezone.now()
    
    # Get selected date from request (default to today)
    selected_date_str = request.GET.get('date', None)
    if selected_date_str:
        try:
            selected_date = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            selected_date = today
    else:
        selected_date = today
    
    # CRITICAL FIX: Apply date filtering and auto-archive
    if selected_date == today:
        # Today: 24-hour auto-archive threshold
        archive_threshold = now - timedelta(hours=24)
        # Get encounters from last 24 hours only
        active_encounters = Encounter.objects.filter(
            status='active',
            is_deleted=False
        ).filter(
            Q(started_at__gte=archive_threshold) | 
            Q(started_at__isnull=True, created__gte=archive_threshold)
        ).select_related('patient', 'provider').order_by('-started_at')[:50]
    else:
        # Past date: show all encounters from that specific date
        date_start = timezone.make_aware(datetime.combine(selected_date, datetime.min.time()))
        date_end = timezone.make_aware(datetime.combine(selected_date, datetime.max.time()))
        active_encounters = Encounter.objects.filter(
            status='active',
            is_deleted=False
        ).filter(
            Q(started_at__gte=date_start, started_at__lte=date_end) |
            Q(started_at__isnull=True, created__gte=date_start, created__lte=date_end)
        ).select_related('patient', 'provider').order_by('-started_at')[:50]
    
    # Get all flow stages for active encounters
    flow_stages = PatientFlowStage.objects.filter(
        encounter__in=active_encounters,
        is_deleted=False
    ).select_related('encounter__patient', 'completed_by__user')
    
    # Apply additional date filtering to flow stages
    if selected_date == today:
        # For today: exclude stages older than 24 hours
        flow_stages = flow_stages.filter(
            Q(started_at__gte=archive_threshold) | Q(started_at__isnull=True, created__gte=archive_threshold)
        )
    else:
        # For past dates: filter stages by date
        flow_stages = flow_stages.filter(
            Q(started_at__date=selected_date) | Q(started_at__isnull=True, created__date=selected_date)
        )
    
    # Statistics
    total_patients = active_encounters.count()
    completed_today = Encounter.objects.filter(
        status='completed',
        is_deleted=False,
        ended_at__date=timezone.now().date()
    ).count()
    
    # Calculate average wait time
    in_progress_stages = flow_stages.filter(status='in_progress', started_at__isnull=False)
    total_wait = 0
    wait_count = 0
    for stage in in_progress_stages:
        if stage.started_at:
            wait_duration = timezone.now() - stage.started_at
            total_wait += wait_duration.total_seconds() / 60
            wait_count += 1
    avg_wait_time = int(total_wait / wait_count) if wait_count > 0 else 0
    
    # Count delayed patients (waiting > 60 minutes in any stage)
    delayed_count = 0
    for stage in in_progress_stages:
        if stage.started_at:
            wait_duration = timezone.now() - stage.started_at
            if wait_duration.total_seconds() / 60 > 60:
                delayed_count += 1
    
    # Organize by stage type
    queue_by_stage = {
        'vitals': {
            'name': 'Vital Signs',
            'icon': 'heart-pulse',
            'color': '#EF4444',
            'bg': 'rgba(239, 68, 68, 0.1)',
            'patients': []
        },
        'consultation': {
            'name': 'Consultation',
            'icon': 'clipboard2-pulse',
            'color': '#667eea',
            'bg': 'rgba(102, 126, 234, 0.1)',
            'patients': []
        },
        'laboratory': {
            'name': 'Laboratory',
            'icon': 'flask',
            'color': '#06B6D4',
            'bg': 'rgba(6, 182, 212, 0.1)',
            'patients': []
        },
        'imaging': {
            'name': 'Imaging',
            'icon': 'x-ray',
            'color': '#8B5CF6',
            'bg': 'rgba(139, 92, 246, 0.1)',
            'patients': []
        },
        'pharmacy': {
            'name': 'Pharmacy',
            'icon': 'capsule',
            'color': '#10B981',
            'bg': 'rgba(16, 185, 129, 0.1)',
            'patients': []
        },
        'billing': {
            'name': 'Billing',
            'icon': 'receipt',
            'color': '#F59E0B',
            'bg': 'rgba(245, 158, 11, 0.1)',
            'patients': []
        },
    }
    
    # Populate queue data - DEDUPLICATE by patient MRN per stage (show only most recent encounter per patient)
    seen_patients_by_stage = {}  # Track seen patients per stage: {stage_type: {mrn: latest_stage_data}}
    
    # First pass: collect all stages and group by patient MRN per stage
    for stage in flow_stages.filter(status__in=['pending', 'in_progress']).order_by('-started_at', '-created'):
        stage_type = stage.stage_type
        if stage_type not in queue_by_stage:
            continue
            
        patient_mrn = stage.encounter.patient.mrn
        encounter_id = str(stage.encounter.pk)
        
        # Initialize seen dict for this stage if not exists
        if stage_type not in seen_patients_by_stage:
            seen_patients_by_stage[stage_type] = {}
        
        wait_minutes = 0
        if stage.started_at:
            wait_duration = timezone.now() - stage.started_at
            wait_minutes = int(wait_duration.total_seconds() / 60)
        
        patient_data = {
            'encounter_id': stage.encounter.pk,
            'patient_name': stage.encounter.patient.full_name,
            'mrn': patient_mrn,
            'encounter_type': stage.encounter.get_encounter_type_display(),
            'wait_minutes': wait_minutes,
            'staff': stage.completed_by.user.get_full_name() if stage.completed_by else None,
            'stage_id': stage.pk,
            'stage_created': stage.created,
            'stage_started': stage.started_at or stage.created,
        }
        
        # If we haven't seen this patient in this stage, or this is a more recent stage, use it
        if patient_mrn not in seen_patients_by_stage[stage_type]:
            seen_patients_by_stage[stage_type][patient_mrn] = patient_data
        else:
            # Compare timestamps - keep the most recent one
            existing_data = seen_patients_by_stage[stage_type][patient_mrn]
            existing_time = existing_data.get('stage_started') or existing_data.get('stage_created')
            current_time = patient_data.get('stage_started') or patient_data.get('stage_created')
            
            if current_time and existing_time and current_time > existing_time:
                # Current stage is more recent, replace
                seen_patients_by_stage[stage_type][patient_mrn] = patient_data
            elif not existing_time and current_time:
                # Current has time, existing doesn't - use current
                seen_patients_by_stage[stage_type][patient_mrn] = patient_data
            # Otherwise keep existing (it's more recent or same)
    
    # Second pass: add unique patients to queue_by_stage
    for stage_type, patients_dict in seen_patients_by_stage.items():
        if stage_type in queue_by_stage:
            # Sort by most recent first, then add to queue
            sorted_patients = sorted(
                patients_dict.values(),
                key=lambda x: x.get('stage_started') or x.get('stage_created') or timezone.now(),
                reverse=True
            )
            queue_by_stage[stage_type]['patients'] = sorted_patients

    # Third pass: populate Laboratory and Imaging from Orders by ORDER DATE (not encounter list).
    # This ensures pending lab/imaging orders show even when no encounters are in the 24h window.
    if selected_date == today:
        lab_date_filter = Q(requested_at__gte=archive_threshold) | Q(requested_at__isnull=True, created__gte=archive_threshold)
        imaging_date_filter = Q(requested_at__gte=archive_threshold) | Q(requested_at__isnull=True, created__gte=archive_threshold)
    else:
        lab_date_filter = Q(requested_at__date=selected_date) | Q(requested_at__isnull=True, created__date=selected_date)
        imaging_date_filter = Q(requested_at__date=selected_date) | Q(requested_at__isnull=True, created__date=selected_date)

    lab_orders = Order.objects.filter(
        order_type='lab',
        status__in=['pending', 'in_progress'],
        is_deleted=False
    ).filter(lab_date_filter).select_related('encounter', 'encounter__patient').order_by('-requested_at')[:100]
    lab_mrns = {p['mrn'] for p in queue_by_stage['laboratory']['patients']}
    for order in lab_orders:
        if order.encounter and order.encounter.patient and order.encounter.patient.mrn not in lab_mrns:
            lab_mrns.add(order.encounter.patient.mrn)
            wait_min = 0
            if order.requested_at:
                wait_min = max(0, int((now - order.requested_at).total_seconds() / 60))
            queue_by_stage['laboratory']['patients'].append({
                'encounter_id': order.encounter.pk,
                'patient_name': order.encounter.patient.full_name,
                'mrn': order.encounter.patient.mrn,
                'encounter_type': order.encounter.get_encounter_type_display(),
                'wait_minutes': wait_min,
                'staff': None,
                'stage_id': None,
                'stage_created': order.requested_at or order.created,
                'stage_started': order.requested_at or order.created,
            })
    queue_by_stage['laboratory']['patients'].sort(
        key=lambda x: x.get('stage_started') or x.get('stage_created') or timezone.now(),
        reverse=True
    )

    imaging_orders = Order.objects.filter(
        order_type='imaging',
        status__in=['pending', 'in_progress'],
        is_deleted=False
    ).filter(imaging_date_filter).select_related('encounter', 'encounter__patient').order_by('-requested_at')[:100]
    imaging_mrns = {p['mrn'] for p in queue_by_stage['imaging']['patients']}
    for order in imaging_orders:
        if order.encounter and order.encounter.patient and order.encounter.patient.mrn not in imaging_mrns:
            imaging_mrns.add(order.encounter.patient.mrn)
            wait_min = 0
            if order.requested_at:
                wait_min = max(0, int((now - order.requested_at).total_seconds() / 60))
            queue_by_stage['imaging']['patients'].append({
                'encounter_id': order.encounter.pk,
                'patient_name': order.encounter.patient.full_name,
                'mrn': order.encounter.patient.mrn,
                'encounter_type': order.encounter.get_encounter_type_display(),
                'wait_minutes': wait_min,
                'staff': None,
                'stage_id': None,
                'stage_created': order.requested_at or order.created,
                'stage_started': order.requested_at or order.created,
            })
    try:
        from .models_advanced import ImagingStudy
        if selected_date == today:
            study_date_filter = Q(created__gte=archive_threshold)
        else:
            study_date_filter = Q(created__date=selected_date)
        imaging_studies = ImagingStudy.objects.filter(
            status__in=['pending', 'in_progress', 'scheduled'],
            is_deleted=False
        ).filter(study_date_filter).select_related('encounter', 'encounter__patient').order_by('-created')[:100]
        for study in imaging_studies:
            if study.encounter and study.encounter.patient and study.encounter.patient.mrn not in imaging_mrns:
                imaging_mrns.add(study.encounter.patient.mrn)
                wait_min = max(0, int((now - (study.created or now)).total_seconds() / 60)) if study.created else 0
                queue_by_stage['imaging']['patients'].append({
                    'encounter_id': study.encounter.pk,
                    'patient_name': study.encounter.patient.full_name,
                    'mrn': study.encounter.patient.mrn,
                    'encounter_type': study.encounter.get_encounter_type_display(),
                    'wait_minutes': wait_min,
                    'staff': None,
                    'stage_id': None,
                    'stage_created': study.created,
                    'stage_started': study.created,
                })
        queue_by_stage['imaging']['patients'].sort(
            key=lambda x: x.get('stage_started') or x.get('stage_created') or timezone.now(),
            reverse=True
        )
    except (ImportError, AttributeError):
        pass

    # Get available dates for calendar
    all_encounters = Encounter.objects.filter(is_deleted=False)
    available_dates = []
    for i in range(30):
        check_date = today - timedelta(days=i)
        has_encounters = all_encounters.filter(started_at__date=check_date).exists()
        if has_encounters or check_date == today:
            available_dates.append(check_date)
    
    context = {
        'total_patients': total_patients,
        'completed_today': completed_today,
        'avg_wait_time': avg_wait_time,
        'delayed_count': delayed_count,
        'queue_by_stage': queue_by_stage,
        'today': today,
        'selected_date': selected_date,
        'available_dates': available_dates,
        'is_today': selected_date == today,
    }
    return render(request, 'hospital/flow_dashboard_worldclass.html', context)

