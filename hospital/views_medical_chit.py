"""
Staff Medical Chit System Views
Allows staff to apply for medical chits, HR to approve, and medical staff to access them
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods, require_POST
from django.utils import timezone
from django.db.models import Q
from django.core.paginator import Paginator
import logging

from .models import Staff, Notification, Department, Encounter, Patient
from .models_hr import StaffMedicalChit
from .services.sms_service import sms_service

logger = logging.getLogger(__name__)


# ==================== STAFF PORTAL VIEWS ====================

@login_required
def staff_medical_chit_apply(request):
    """Staff apply for medical chit through portal"""
    try:
        staff = Staff.objects.get(user=request.user, is_deleted=False)
    except Staff.DoesNotExist:
        messages.error(request, "Staff profile not found. Please contact HR.")
        return redirect('hospital:staff_portal')
    
    if request.method == 'POST':
        reason = request.POST.get('reason', '').strip()
        symptoms = request.POST.get('symptoms', '').strip()
        
        if not reason:
            messages.error(request, "Please provide a reason for requiring medical attention.")
            return redirect('hospital:staff_medical_chit_apply')
        
        try:
            # Create medical chit
            chit = StaffMedicalChit.objects.create(
                staff=staff,
                application_date=timezone.now().date(),
                reason=reason,
                symptoms=symptoms,
                status='pending'
            )
            
            # Notify HR
            from django.contrib.auth.models import User
            hr_users = User.objects.filter(
                Q(is_staff=True) | Q(is_superuser=True)
            ).filter(
                Q(staff__department__name__icontains='hr') | 
                Q(staff__profession__icontains='hr') |
                Q(staff__profession='hr_manager')
            )
            
            # If no HR users found, notify all admins
            if not hr_users.exists():
                hr_users = User.objects.filter(Q(is_staff=True) | Q(is_superuser=True))[:5]
            
            for hr_user in hr_users:
                Notification.objects.create(
                    recipient=hr_user,
                    notification_type='info',
                    title=f'New Medical Chit Request from {staff.user.get_full_name()}',
                    message=f'{staff.user.get_full_name()} ({staff.employee_id or staff.user.username}) has requested a medical chit. Reason: {reason[:100]}',
                    related_object_id=chit.id,
                    related_object_type='StaffMedicalChit',
                )
            
            # Notify staff member
            Notification.objects.create(
                recipient=request.user,
                notification_type='success',
                title='Medical Chit Application Submitted',
                message=f'Your medical chit application (Chit #: {chit.chit_number}) has been submitted and is pending HR approval.',
                related_object_id=chit.id,
                related_object_type='StaffMedicalChit',
            )
            
            messages.success(request, f"Medical chit application submitted successfully! Your chit number is {chit.chit_number}. HR will review it shortly.")
            return redirect('hospital:staff_medical_chit_history')
            
        except Exception as e:
            logger.error(f"Error creating medical chit: {e}", exc_info=True)
            messages.error(request, f"Error submitting medical chit application: {str(e)}")
    
    context = {
        'title': 'Apply for Medical Chit',
        'staff': staff,
    }
    
    return render(request, 'hospital/staff/medical_chit_apply.html', context)


@login_required
def staff_medical_chit_history(request):
    """Staff view their medical chit history"""
    try:
        staff = Staff.objects.get(user=request.user, is_deleted=False)
    except Staff.DoesNotExist:
        messages.error(request, "Staff profile not found.")
        return redirect('hospital:staff_portal')
    
    chits = StaffMedicalChit.objects.filter(
        staff=staff,
        is_deleted=False
    ).order_by('-application_date', '-created')
    
    # Pagination
    paginator = Paginator(chits, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'title': 'My Medical Chits',
        'staff': staff,
        'chits': page_obj,
    }
    
    return render(request, 'hospital/staff/medical_chit_history.html', context)


@login_required
def staff_medical_chit_detail(request, chit_id):
    """Staff view medical chit details"""
    try:
        staff = Staff.objects.get(user=request.user, is_deleted=False)
    except Staff.DoesNotExist:
        messages.error(request, "Staff profile not found.")
        return redirect('hospital:staff_portal')
    
    chit = get_object_or_404(
        StaffMedicalChit,
        id=chit_id,
        staff=staff,
        is_deleted=False
    )
    
    context = {
        'title': f'Medical Chit {chit.chit_number}',
        'staff': staff,
        'chit': chit,
    }
    
    return render(request, 'hospital/staff/medical_chit_detail.html', context)


@login_required
def staff_medical_chit_print(request, chit_id):
    """Print medical chit"""
    try:
        staff = Staff.objects.get(user=request.user, is_deleted=False)
    except Staff.DoesNotExist:
        messages.error(request, "Staff profile not found.")
        return redirect('hospital:staff_portal')
    
    chit = get_object_or_404(
        StaffMedicalChit,
        id=chit_id,
        staff=staff,
        is_deleted=False
    )
    
    context = {
        'title': f'Medical Chit {chit.chit_number}',
        'chit': chit,
        'staff': staff,
    }
    
    return render(request, 'hospital/staff/medical_chit_print.html', context)


# ==================== HR VIEWS ====================

@login_required
def hr_medical_chit_list(request):
    """HR view all medical chit requests"""
    # Check if user is HR
    try:
        staff = Staff.objects.get(user=request.user, is_deleted=False)
        is_hr = (staff.profession == 'hr_manager' or 
                 'hr' in staff.department.name.lower() if staff.department else False or
                 request.user.is_superuser or request.user.is_staff)
    except Staff.DoesNotExist:
        is_hr = request.user.is_superuser or request.user.is_staff
    
    if not is_hr:
        messages.error(request, "You don't have permission to access this page.")
        return redirect('hospital:dashboard')
    
    status_filter = request.GET.get('status', 'all')
    search_query = request.GET.get('search', '').strip()
    
    chits = StaffMedicalChit.objects.filter(is_deleted=False).select_related(
        'staff', 'staff__user', 'staff__department', 'hr_approved_by', 'encounter'
    )
    
    if status_filter != 'all':
        chits = chits.filter(status=status_filter)
    
    if search_query:
        chits = chits.filter(
            Q(chit_number__icontains=search_query) |
            Q(staff__user__first_name__icontains=search_query) |
            Q(staff__user__last_name__icontains=search_query) |
            Q(staff__employee_id__icontains=search_query) |
            Q(reason__icontains=search_query)
        )
    
    chits = chits.order_by('-application_date', '-created')
    
    # Pagination
    paginator = Paginator(chits, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Statistics
    stats = {
        'pending': StaffMedicalChit.objects.filter(status='pending', is_deleted=False).count(),
        'approved': StaffMedicalChit.objects.filter(status='approved', is_deleted=False).count(),
        'rejected': StaffMedicalChit.objects.filter(status='rejected', is_deleted=False).count(),
        'used': StaffMedicalChit.objects.filter(status='used', is_deleted=False).count(),
    }
    
    context = {
        'title': 'Medical Chit Management',
        'chits': page_obj,
        'status_filter': status_filter,
        'search_query': search_query,
        'stats': stats,
    }
    
    return render(request, 'hospital/hr/medical_chit_list.html', context)


@login_required
def hr_medical_chit_approve(request, chit_id):
    """HR approve medical chit"""
    # Check if user is HR
    try:
        staff = Staff.objects.get(user=request.user, is_deleted=False)
        is_hr = (staff.profession == 'hr_manager' or 
                 'hr' in staff.department.name.lower() if staff.department else False or
                 request.user.is_superuser or request.user.is_staff)
    except Staff.DoesNotExist:
        is_hr = request.user.is_superuser or request.user.is_staff
    
    if not is_hr:
        messages.error(request, "You don't have permission to approve medical chits.")
        return redirect('hospital:dashboard')
    
    chit = get_object_or_404(StaffMedicalChit, id=chit_id, is_deleted=False)
    
    if request.method == 'POST':
        approval_notes = request.POST.get('approval_notes', '').strip()
        authorized_name = request.POST.get('authorized_name', '').strip()
        authorized_signature = request.POST.get('authorized_signature', '').strip()
        
        try:
            chit.status = 'approved'
            chit.hr_approved_by = request.user
            chit.hr_approval_date = timezone.now()
            chit.hr_approval_notes = approval_notes
            chit.authorized_by_name = authorized_name or request.user.get_full_name()
            chit.authorized_by_signature = authorized_signature or request.user.get_full_name()
            
            # Set validity (7 days from approval)
            from datetime import timedelta
            chit.valid_until = timezone.now().date() + timedelta(days=7)
            
            chit.save()
            
            # Send SMS to staff
            if chit.staff.phone_number:
                try:
                    message = (
                        f"Dear {chit.staff.user.get_full_name()}, "
                        f"Your medical chit {chit.chit_number} has been APPROVED. "
                        f"Valid until {chit.valid_until.strftime('%d/%m/%Y')}. "
                        f"Please present this chit at the front desk to create your visit. "
                        f"PrimeCare Medical Center"
                    )
                    sms_result = sms_service.send_sms(
                        phone_number=chit.staff.phone_number,
                        message=message,
                        message_type='medical_chit_approval',
                        recipient_name=chit.staff.user.get_full_name(),
                        related_object_id=chit.id,
                        related_object_type='StaffMedicalChit'
                    )
                    if sms_result.status == 'sent':
                        chit.sms_sent_approval = True
                        chit.save(update_fields=['sms_sent_approval'])
                except Exception as sms_error:
                    logger.error(f"Failed to send SMS for chit approval: {sms_error}", exc_info=True)
            
            # Notify staff
            Notification.objects.create(
                recipient=chit.staff.user,
                notification_type='success',
                title=f'Medical Chit {chit.chit_number} Approved',
                message=f'Your medical chit {chit.chit_number} has been approved. Valid until {chit.valid_until.strftime("%d/%m/%Y")}. Please present it at the front desk.',
                related_object_id=chit.id,
                related_object_type='StaffMedicalChit',
            )
            
            messages.success(request, f"Medical chit {chit.chit_number} approved successfully. Staff has been notified.")
            return redirect('hospital:hr_medical_chit_list')
            
        except Exception as e:
            logger.error(f"Error approving medical chit: {e}", exc_info=True)
            messages.error(request, f"Error approving medical chit: {str(e)}")
    
    context = {
        'title': f'Approve Medical Chit {chit.chit_number}',
        'chit': chit,
    }
    
    return render(request, 'hospital/hr/medical_chit_approve.html', context)


@login_required
def hr_medical_chit_reject(request, chit_id):
    """HR reject medical chit"""
    # Check if user is HR
    try:
        staff = Staff.objects.get(user=request.user, is_deleted=False)
        is_hr = (staff.profession == 'hr_manager' or 
                 'hr' in staff.department.name.lower() if staff.department else False or
                 request.user.is_superuser or request.user.is_staff)
    except Staff.DoesNotExist:
        is_hr = request.user.is_superuser or request.user.is_staff
    
    if not is_hr:
        messages.error(request, "You don't have permission to reject medical chits.")
        return redirect('hospital:dashboard')
    
    chit = get_object_or_404(StaffMedicalChit, id=chit_id, is_deleted=False)
    
    if request.method == 'POST':
        rejection_reason = request.POST.get('rejection_reason', '').strip()
        
        if not rejection_reason:
            messages.error(request, "Please provide a reason for rejection.")
            return redirect('hospital:hr_medical_chit_reject', chit_id=chit_id)
        
        try:
            chit.status = 'rejected'
            chit.hr_approved_by = request.user
            chit.hr_approval_date = timezone.now()
            chit.hr_rejection_reason = rejection_reason
            chit.save()
            
            # Send SMS to staff
            if chit.staff.phone_number:
                try:
                    message = (
                        f"Dear {chit.staff.user.get_full_name()}, "
                        f"Your medical chit {chit.chit_number} has been REJECTED. "
                        f"Reason: {rejection_reason[:100]}. "
                        f"Please contact HR for more information. "
                        f"PrimeCare Medical Center"
                    )
                    sms_service.send_sms(
                        phone_number=chit.staff.phone_number,
                        message=message,
                        message_type='medical_chit_rejection',
                        recipient_name=chit.staff.user.get_full_name(),
                        related_object_id=chit.id,
                        related_object_type='StaffMedicalChit'
                    )
                except Exception as sms_error:
                    logger.error(f"Failed to send SMS for chit rejection: {sms_error}", exc_info=True)
            
            # Notify staff
            Notification.objects.create(
                recipient=chit.staff.user,
                notification_type='warning',
                title=f'Medical Chit {chit.chit_number} Rejected',
                message=f'Your medical chit {chit.chit_number} has been rejected. Reason: {rejection_reason}',
                related_object_id=chit.id,
                related_object_type='StaffMedicalChit',
            )
            
            messages.success(request, f"Medical chit {chit.chit_number} rejected. Staff has been notified.")
            return redirect('hospital:hr_medical_chit_list')
            
        except Exception as e:
            logger.error(f"Error rejecting medical chit: {e}", exc_info=True)
            messages.error(request, f"Error rejecting medical chit: {str(e)}")
    
    context = {
        'title': f'Reject Medical Chit {chit.chit_number}',
        'chit': chit,
    }
    
    return render(request, 'hospital/hr/medical_chit_reject.html', context)


# ==================== MEDICAL STAFF VIEWS ====================

@login_required
def medical_chit_view_approved(request):
    """Doctors/medical staff view approved medical chits"""
    try:
        current_staff = Staff.objects.get(user=request.user, is_deleted=False)
        is_medical = current_staff.profession in ['doctor', 'nurse', 'midwife', 'lab_technician', 'radiologist']
    except Staff.DoesNotExist:
        is_medical = False
    
    if not is_medical and not (request.user.is_superuser or request.user.is_staff):
        messages.error(request, "You don't have permission to access this page.")
        return redirect('hospital:dashboard')
    
    search_query = request.GET.get('search', '').strip()
    
    chits = StaffMedicalChit.objects.filter(
        status='approved',
        is_deleted=False
    ).select_related('staff', 'staff__user', 'staff__department', 'encounter')
    
    # Filter out expired chits
    from datetime import date
    today = date.today()
    chits = chits.filter(
        Q(valid_until__gte=today) | Q(valid_until__isnull=True)
    )
    
    if search_query:
        chits = chits.filter(
            Q(chit_number__icontains=search_query) |
            Q(staff__user__first_name__icontains=search_query) |
            Q(staff__user__last_name__icontains=search_query) |
            Q(staff__employee_id__icontains=search_query)
        )
    
    chits = chits.order_by('-application_date')
    
    # Pagination
    paginator = Paginator(chits, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'title': 'Approved Medical Chits',
        'chits': page_obj,
        'search_query': search_query,
    }
    
    return render(request, 'hospital/medical/medical_chit_approved.html', context)


# ==================== FRONT DESK VIEWS ====================

@login_required
def frontdesk_medical_chit_create_visit(request, chit_id):
    """Front desk create visit from medical chit"""
    chit = get_object_or_404(
        StaffMedicalChit,
        id=chit_id,
        is_deleted=False
    )
    
    if not chit.can_create_visit():
        messages.error(request, f"This medical chit ({chit.chit_number}) cannot be used to create a visit. It may be expired, already used, or not approved.")
        return redirect('hospital:dashboard')
    
    # Get or create patient for staff member
    try:
        # Try to find existing patient for this staff
        patient = Patient.objects.filter(
            phone_number=chit.staff.phone_number,
            is_deleted=False
        ).first()
        
        if not patient:
            # Create patient record for staff
            patient = Patient.objects.create(
                first_name=chit.staff.user.first_name or '',
                last_name=chit.staff.user.last_name or '',
                phone_number=chit.staff.phone_number or '',
                email=chit.staff.user.email or '',
                date_of_birth=chit.staff.date_of_birth,
                gender=chit.staff.gender or 'other',
                address=chit.staff.address or '',
                notes=f'Staff member - Employee ID: {chit.staff.employee_id}',
            )
        
        # Get default department
        from .models import Department
        department = Department.objects.filter(
            name__icontains='outpatient'
        ).first() or Department.objects.filter(is_deleted=False).first()
        
        if not department:
            messages.error(request, "No department found. Please contact administrator.")
            return redirect('hospital:dashboard')
        
        # Create encounter
        encounter = Encounter.objects.create(
            patient=patient,
            department=department,
            encounter_type='outpatient',
            status='active',
            started_at=timezone.now(),
            provider=chit.staff,  # Staff member is the "patient" here
            chief_complaint=chit.reason,
            notes=f'Medical chit visit - Chit #: {chit.chit_number}. {chit.symptoms}',
        )
        
        # Update chit
        chit.encounter = encounter
        chit.status = 'used'
        chit.visit_created_at = timezone.now()
        chit.visit_created_by = request.user
        chit.save()
        
        # Send SMS to staff
        if chit.staff.phone_number:
            try:
                message = (
                    f"Dear {chit.staff.user.get_full_name()}, "
                    f"Your visit has been created using medical chit {chit.chit_number}. "
                    f"Visit ID: {encounter.id}. "
                    f"Please proceed to the consultation area. "
                    f"PrimeCare Medical Center"
                )
                sms_service.send_sms(
                    phone_number=chit.staff.phone_number,
                    message=message,
                    message_type='medical_chit_visit_created',
                    recipient_name=chit.staff.user.get_full_name(),
                    related_object_id=chit.id,
                    related_object_type='StaffMedicalChit'
                )
            except Exception as sms_error:
                logger.error(f"Failed to send SMS for visit creation: {sms_error}", exc_info=True)
        
        # Notify staff
        Notification.objects.create(
            recipient=chit.staff.user,
            notification_type='info',
            title=f'Visit Created - Medical Chit {chit.chit_number}',
            message=f'Your visit has been created using medical chit {chit.chit_number}. Please proceed to consultation.',
            related_object_id=encounter.id,
            related_object_type='Encounter',
        )
        
        messages.success(request, f"Visit created successfully for {chit.staff.user.get_full_name()} using medical chit {chit.chit_number}.")
        return redirect('hospital:encounter_detail', encounter_id=encounter.id)
        
    except Exception as e:
        logger.error(f"Error creating visit from medical chit: {e}", exc_info=True)
        messages.error(request, f"Error creating visit: {str(e)}")
        return redirect('hospital:dashboard')


@login_required
def frontdesk_medical_chit_lookup(request):
    """Front desk lookup medical chit by number"""
    chit_number = request.GET.get('chit_number', '').strip()
    chit = None
    
    if chit_number:
        try:
            chit = StaffMedicalChit.objects.select_related(
                'staff', 'staff__user', 'staff__department', 'encounter'
            ).get(
                chit_number=chit_number.upper(),
                is_deleted=False
            )
        except StaffMedicalChit.DoesNotExist:
            messages.error(request, f"Medical chit {chit_number} not found.")
    
    from datetime import date
    today = date.today()
    
    context = {
        'title': 'Lookup Medical Chit',
        'chit': chit,
        'chit_number': chit_number,
        'today': today,
    }
    
    return render(request, 'hospital/frontdesk/medical_chit_lookup.html', context)

