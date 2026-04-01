"""
Nurse Assignment Views
Allows nurses to assign patients to doctors after vitals are recorded
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q

from .decorators import role_required
from .models import Encounter, Staff, Patient
from .models_queue import QueueEntry
from .models_workflow import PatientFlowStage


@login_required
@role_required('nurse', 'midwife', 'admin', message='Access denied. Only nurses can assign patients to doctors.')
def nurse_patient_assignment(request):
    """View for nurses to see patients who need doctor assignment after vitals"""
    
    # Get current nurse
    try:
        nurse = Staff.objects.get(user=request.user, is_active=True, is_deleted=False)
        if nurse.profession not in ['nurse', 'midwife'] and not request.user.is_superuser:
            messages.error(request, 'Access denied. Only nurses can access this page.')
            return redirect('hospital:dashboard')
    except Staff.DoesNotExist:
        messages.error(request, 'You must be registered as staff to access this page.')
        return redirect('hospital:dashboard')
    
    # Get patients who have vitals recorded but no doctor assigned
    today = timezone.now().date()
    
    # Get encounters with vitals completed but consultation pending
    # First get base queryset
    encounters_base = Encounter.objects.filter(
        status='active',
        is_deleted=False,
        vitals__isnull=False  # Has vitals recorded
    ).exclude(
        # Exclude if already has assigned doctor in queue
        queue_entries__assigned_doctor__isnull=False,
        queue_entries__is_deleted=False
    ).select_related('patient', 'provider')
    
    # Deduplicate: keep only most recent per patient per day
    # Use DISTINCT ON approach since UUID fields don't support MAX()
    from django.db import connection
    
    # Get base filter conditions for SQL
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT DISTINCT ON (e.patient_id, e.started_at::date) e.id
            FROM hospital_encounter e
            WHERE e.is_deleted = false 
              AND e.status = 'active'
              AND EXISTS (
                  SELECT 1 FROM hospital_vitalsign v 
                  WHERE v.encounter_id = e.id
              )
              AND NOT EXISTS (
                  SELECT 1 FROM hospital_queueentry q 
                  WHERE q.encounter_id = e.id 
                    AND q.assigned_doctor_id IS NOT NULL 
                    AND q.is_deleted = false
              )
            ORDER BY e.patient_id, e.started_at::date, e.id DESC
            LIMIT 50
        """)
        latest_ids = [row[0] for row in cursor.fetchall()]
    
    encounters_needing_assignment = Encounter.objects.filter(
        id__in=latest_ids
    ).select_related('patient', 'provider').order_by('-started_at', '-id')
    
    # Get queue entries that need doctor assignment
    queue_entries_needing_assignment = QueueEntry.objects.filter(
        queue_date=today,
        is_deleted=False,
        status__in=['checked_in', 'vitals_completed'],
        assigned_doctor__isnull=True  # No doctor assigned yet
    ).select_related('patient', 'encounter', 'department').order_by('check_in_time')
    
    # Get all available doctors
    from django.contrib.auth.models import User, Group
    try:
        doctor_group = Group.objects.get(name='Doctor')
        available_doctors = User.objects.filter(
            groups=doctor_group,
            is_active=True,
            staff__is_active=True,
            staff__is_deleted=False,
            staff__profession='doctor'
        ).select_related('staff').order_by('staff__first_name', 'staff__last_name')
    except Group.DoesNotExist:
        available_doctors = User.objects.none()
    
    context = {
        'nurse': nurse,
        'encounters_needing_assignment': encounters_needing_assignment,
        'queue_entries_needing_assignment': queue_entries_needing_assignment,
        'available_doctors': available_doctors,
        'today': today,
    }
    
    return render(request, 'hospital/nurse_patient_assignment.html', context)


@login_required
@role_required('nurse', 'midwife', 'admin', message='Access denied. Only nurses can assign patients to doctors.')
def assign_patient_to_doctor(request, encounter_id):
    """Assign a patient to a doctor after vitals are recorded"""
    
    # Get current nurse
    try:
        nurse = Staff.objects.get(user=request.user, is_active=True, is_deleted=False)
        if nurse.profession not in ['nurse', 'midwife'] and not request.user.is_superuser:
            messages.error(request, 'Access denied. Only nurses can assign patients.')
            return redirect('hospital:dashboard')
    except Staff.DoesNotExist:
        messages.error(request, 'You must be registered as staff.')
        return redirect('hospital:dashboard')
    
    encounter = get_object_or_404(Encounter, pk=encounter_id, is_deleted=False)
    
    if request.method == 'POST':
        doctor_id = request.POST.get('doctor_id')
        notes = request.POST.get('notes', '')
        
        if not doctor_id:
            messages.error(request, 'Please select a doctor.')
            return redirect('hospital:nurse_patient_assignment')
        
        try:
            from django.contrib.auth.models import User
            doctor_user = User.objects.get(pk=doctor_id, is_active=True)
            
            # Verify doctor is actually a doctor
            if not doctor_user.groups.filter(name='Doctor').exists():
                messages.error(request, 'Selected user is not a doctor.')
                return redirect('hospital:nurse_patient_assignment')
            
            # Get or create queue entry
            queue_entry = QueueEntry.objects.filter(
                encounter=encounter,
                is_deleted=False
            ).first()
            
            if not queue_entry:
                # Reuse an existing active same-day ticket for this patient to avoid
                # creating multiple queue numbers for one person.
                active_same_day_entry = QueueEntry.objects.filter(
                    patient=encounter.patient,
                    queue_date=timezone.now().date(),
                    status__in=['checked_in', 'called', 'vitals_completed', 'in_progress'],
                    is_deleted=False,
                ).order_by('-check_in_time', '-created').first()
                if active_same_day_entry:
                    queue_entry = active_same_day_entry
                    queue_entry.encounter = encounter
                    queue_entry.assigned_doctor = doctor_user
                    queue_entry.status = 'vitals_completed'
                    if notes:
                        queue_entry.notes = (queue_entry.notes or '') + f'\n[Nurse Assignment] {notes}'
                    queue_entry.save()
                else:
                    # Create queue entry if it doesn't exist
                    from .models import Department
                    default_dept = Department.objects.filter(name__icontains='outpatient').first()
                    if not default_dept:
                        default_dept = Department.objects.first()
                    
                    # Generate queue number (returns string + sequence; do not use a tuple as queue_number)
                    from .services.queue_service import QueueService
                    queue_service = QueueService()
                    queue_number_str, sequence = queue_service.generate_queue_number(default_dept)
                    
                    queue_entry = QueueEntry.objects.create(
                        patient=encounter.patient,
                        encounter=encounter,
                        department=default_dept,
                        queue_number=queue_number_str,
                        queue_date=timezone.now().date(),
                        sequence_number=sequence,
                        status='vitals_completed',
                        assigned_doctor=doctor_user,
                    )
            else:
                # Update existing queue entry
                queue_entry.assigned_doctor = doctor_user
                queue_entry.status = 'vitals_completed'
                if notes:
                    queue_entry.notes = (queue_entry.notes or '') + f'\n[Nurse Assignment] {notes}'
                queue_entry.save()
            
            # Update encounter provider
            doctor_staff = Staff.objects.filter(user=doctor_user, is_active=True, is_deleted=False).first()
            if doctor_staff:
                encounter.provider = doctor_staff
                encounter.save()
            
            # Update workflow stage
            consultation_stage = PatientFlowStage.objects.filter(
                encounter=encounter,
                stage_type='consultation',
                is_deleted=False
            ).first()
            
            if consultation_stage:
                consultation_stage.assigned_to = doctor_user
                consultation_stage.notes = (consultation_stage.notes or '') + f'\nAssigned by {nurse.full_name} after vitals'
                consultation_stage.save()
            
            messages.success(
                request, 
                f'Patient {encounter.patient.full_name} assigned to Dr. {doctor_staff.full_name if doctor_staff else doctor_user.get_full_name() or doctor_user.username}'
            )
            
            return redirect('hospital:nurse_patient_assignment')
            
        except User.DoesNotExist:
            messages.error(request, 'Selected doctor not found.')
        except Exception as e:
            messages.error(request, f'Error assigning patient: {str(e)}')
    
    return redirect('hospital:nurse_patient_assignment')


@login_required
@role_required('nurse', 'midwife', 'admin', message='Access denied.')
def view_patient_assignments(request):
    """View for nurses to see all patient assignments (front desk and nurse assignments)"""
    
    # Get current nurse
    try:
        nurse = Staff.objects.get(user=request.user, is_active=True, is_deleted=False)
        if nurse.profession not in ['nurse', 'midwife'] and not request.user.is_superuser:
            messages.error(request, 'Access denied.')
            return redirect('hospital:dashboard')
    except Staff.DoesNotExist:
        messages.error(request, 'You must be registered as staff.')
        return redirect('hospital:dashboard')
    
    today = timezone.now().date()
    
    # Get all queue entries with assigned doctors (both front desk and nurse assignments)
    assigned_entries = QueueEntry.objects.filter(
        queue_date=today,
        is_deleted=False,
        assigned_doctor__isnull=False
    ).select_related('patient', 'encounter', 'department', 'assigned_doctor').order_by('-check_in_time')
    
    # Group by doctor
    assignments_by_doctor = {}
    for entry in assigned_entries:
        doctor = entry.assigned_doctor
        doctor_name = doctor.get_full_name() or doctor.username
        
        if doctor_name not in assignments_by_doctor:
            assignments_by_doctor[doctor_name] = {
                'doctor': doctor,
                'entries': []
            }
        assignments_by_doctor[doctor_name]['entries'].append(entry)
    
    context = {
        'nurse': nurse,
        'assigned_entries': assigned_entries,
        'assignments_by_doctor': assignments_by_doctor,
        'today': today,
    }
    
    return render(request, 'hospital/view_patient_assignments.html', context)
