"""
Front Desk Visit Creation with Payer Type Verification
Ensures proper payer type selection and pricing
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse
from django.db import transaction
from decimal import Decimal

from hospital.models import Patient, Encounter, Department, Payer, Staff
from hospital.models_insurance_companies import InsuranceCompany, InsurancePlan, PatientInsurance
from hospital.services.visit_payer_sync_service import visit_payer_sync_service
from hospital.services.pricing_engine_service import PricingEngineService
import logging

logger = logging.getLogger(__name__)


@login_required
def frontdesk_visit_create(request, patient_id):
    """
    Create visit/encounter with payer type verification
    Front desk can verify/update payer type during check-in
    """
    patient = get_object_or_404(Patient, pk=patient_id, is_deleted=False)
    
    if request.method == 'POST':
        payer_type = request.POST.get('payer_type', '').strip()
        encounter_type = request.POST.get('encounter_type', 'outpatient')
        chief_complaint = request.POST.get('chief_complaint', '').strip() or 'Visit'
        visit_reason = request.POST.get('visit_reason', 'new').strip().lower()  # 'new' or 'review'
        department_id = request.POST.get('department_id')
        assigned_doctor_id = request.POST.get('assigned_doctor', '').strip()
        insurance_company_id = request.POST.get('insurance_company', '').strip()
        insurance_plan_id = request.POST.get('insurance_plan', '').strip()
        corporate_payer_id = request.POST.get('corporate_company', '').strip()
        
        try:
            with transaction.atomic():
                # Get department
                department = None
                if department_id:
                    try:
                        department = Department.objects.get(pk=department_id, is_deleted=False)
                    except Department.DoesNotExist:
                        pass
                
                if not department:
                    department = Department.objects.filter(
                        name__icontains='outpatient',
                        is_deleted=False
                    ).first()
                
                if not department:
                    department = Department.objects.filter(is_deleted=False).first()
                
                if not department:
                    messages.error(request, 'No active departments found. Please configure departments first.')
                    return redirect('hospital:patient_detail', pk=patient_id)
                
                # Get assigned doctor if provided
                assigned_doctor_staff = None
                assigned_doctor_user = None
                if assigned_doctor_id:
                    try:
                        assigned_doctor_staff = Staff.objects.get(
                            pk=assigned_doctor_id,
                            profession='doctor',
                            is_deleted=False,
                            user__isnull=False,
                            user__is_active=True
                        )
                        assigned_doctor_user = assigned_doctor_staff.user if assigned_doctor_staff else None
                    except (Staff.DoesNotExist, ValueError) as e:
                        logger.warning(f"Front desk visit: Assigned doctor {assigned_doctor_id} not found: {e}")
                        messages.warning(request, 'Selected doctor not found. Visit will be created without doctor assignment.')
                
                # Do NOT use front desk staff as provider - only assigned doctor. Prevents front desk appearing as "Attending Physician".
                
                # Prepare notes - add review marker if review visit
                visit_notes = f'Visit created by front desk - {request.user.get_full_name() or request.user.username}'
                if visit_reason == 'review':
                    visit_notes = f'[REVIEW_VISIT] {visit_notes}'
                    # Also prepend to chief_complaint if not already there
                    if 'review' not in chief_complaint.lower() and 'follow-up' not in chief_complaint.lower():
                        chief_complaint = f'Review: {chief_complaint}'
                
                # Reuse same-day active encounter to avoid duplicate records (same patient, same day = one encounter)
                today = timezone.now().date()
                existing_today = Encounter.objects.filter(
                    patient=patient,
                    status='active',
                    is_deleted=False,
                    started_at__date=today,
                ).exclude(chief_complaint__iexact='New patient registration').order_by('-started_at').first()
                
                if existing_today:
                    encounter = existing_today
                    # Update with latest chief complaint and provider so visit info is current
                    encounter.chief_complaint = chief_complaint
                    encounter.provider = assigned_doctor_staff or encounter.provider
                    encounter.notes = visit_notes
                    # Must match current check-in (Special Consultation / Gynae / etc.) or billing and cashier show wrong tier
                    if encounter.encounter_type != encounter_type:
                        encounter.encounter_type = encounter_type
                    encounter.save(
                        update_fields=[
                            'chief_complaint', 'provider', 'notes', 'modified', 'encounter_type',
                        ]
                    )
                    logger.info(f"Front desk visit: Reusing same-day encounter {encounter.id} for patient {patient.mrn}")
                else:
                    # Create encounter (provider=assigned doctor only; None if no doctor assigned)
                    encounter = Encounter.objects.create(
                        patient=patient,
                        encounter_type=encounter_type,
                        status='active',
                        started_at=timezone.now(),
                        provider=assigned_doctor_staff,
                        chief_complaint=chief_complaint,
                        notes=visit_notes
                    )
                
                # Set payer (insurance/corporate/cash) before consultation charge so invoice line gets correct price
                # If insurance selected with company/plan, create or update PatientInsurance
                if payer_type in ('insurance', 'private', 'nhis') and insurance_company_id:
                    try:
                        company = InsuranceCompany.objects.get(
                            pk=insurance_company_id,
                            is_active=True,
                            is_deleted=False
                        )
                        plan = None
                        if insurance_plan_id:
                            plan = InsurancePlan.objects.filter(
                                pk=insurance_plan_id,
                                insurance_company=company,
                                is_active=True,
                                is_deleted=False
                            ).first()
                        pi = PatientInsurance.objects.filter(
                            patient=patient,
                            status='active',
                            is_deleted=False
                        ).select_related('insurance_company').first()
                        policy_num = patient.insurance_id or patient.insurance_policy_number or ('VISIT-' + str(encounter.id)[:8])
                        member_id = patient.insurance_member_id or patient.insurance_id or patient.mrn or 'N/A'
                        if pi:
                            pi.insurance_company = company
                            pi.insurance_plan = plan
                            pi.policy_number = pi.policy_number or policy_num
                            pi.member_id = pi.member_id or member_id
                            pi.is_primary = True
                            pi.save()
                        else:
                            PatientInsurance.objects.create(
                                patient=patient,
                                insurance_company=company,
                                insurance_plan=plan,
                                policy_number=policy_num,
                                member_id=member_id,
                                effective_date=timezone.now().date(),
                                status='active',
                                is_primary=True,
                            )
                        Payer.objects.get_or_create(
                            name=company.name,
                            defaults={'payer_type': 'insurance', 'is_active': True}
                        )
                    except InsuranceCompany.DoesNotExist:
                        pass
                    except Exception as e:
                        logger.warning(f"Front desk visit: Could not update insurance: {e}")

                # If corporate selected with company, set payer directly; else verify payer type
                if payer_type == 'corporate' and corporate_payer_id:
                    try:
                        corp_payer = Payer.objects.filter(
                            pk=corporate_payer_id,
                            payer_type='corporate',
                            is_active=True,
                            is_deleted=False
                        ).first()
                        if corp_payer:
                            sync_result = visit_payer_sync_service.verify_and_set_payer_type(
                                encounter=encounter,
                                payer_type='corporate',
                                payer=corp_payer
                            )
                        else:
                            sync_result = visit_payer_sync_service.verify_and_set_payer_type(
                                encounter=encounter,
                                payer_type=payer_type if payer_type else None
                            )
                    except Exception as e:
                        logger.warning(f"Front desk visit: Corporate payer error: {e}")
                        sync_result = visit_payer_sync_service.verify_and_set_payer_type(
                            encounter=encounter,
                            payer_type=payer_type if payer_type else None
                        )
                else:
                    sync_result = visit_payer_sync_service.verify_and_set_payer_type(
                        encounter=encounter,
                        payer_type=payer_type if payer_type else None
                    )

                if sync_result['success']:
                    messages.success(
                        request,
                        f"Visit created! {sync_result['message']}. "
                        f"Pricing will use {sync_result['payer_type']} rates."
                    )
                else:
                    messages.warning(
                        request,
                        f"Visit created, but payer type sync had issues: {sync_result['message']}"
                    )

                # Consultation charge after payer is set so price goes straight to cashier
                if visit_reason == 'new':
                    try:
                        from .utils_billing import CONSULTATION_LINE_SERVICE_CODES, add_consultation_charge
                        from .utils_doctor_pricing import DoctorPricingService

                        consultation_type = 'general'
                        if encounter_type == 'specialist' or encounter_type == 'gynae':
                            consultation_type = 'specialist'
                        elif encounter_type == 'antenatal':
                            # Antenatal: add_consultation_charge uses MAT-ANC and 235 GHC
                            consultation_type = 'general'
                        elif assigned_doctor_staff:
                            pricing_info = DoctorPricingService.get_doctor_pricing_info(assigned_doctor_staff)
                            if pricing_info['is_specialist']:
                                consultation_type = 'specialist'

                        invoice = add_consultation_charge(
                            encounter,
                            consultation_type=consultation_type,
                            doctor_staff=assigned_doctor_staff
                        )
                        # Apply manual price override so it goes to cashier (direct query so line is always found)
                        if invoice:
                            manual_price_raw = request.POST.get('manual_price', '').strip()
                            if manual_price_raw:
                                try:
                                    override_price = Decimal(manual_price_raw)
                                    if override_price > 0:
                                        from .models import InvoiceLine
                                        consultation_line = InvoiceLine.objects.filter(
                                            invoice_id=invoice.pk,
                                            service_code__code__in=CONSULTATION_LINE_SERVICE_CODES,
                                            is_deleted=False
                                        ).order_by('-modified', '-created').first()
                                        if consultation_line:
                                            consultation_line.unit_price = override_price
                                            consultation_line.line_total = override_price * (consultation_line.quantity or Decimal('1'))
                                            consultation_line.save()
                                            invoice.refresh_from_db()
                                            invoice.update_totals()
                                            logger.info(f"Front desk override price GHS {override_price} applied for {patient.full_name}, cashier will see it.")
                                            messages.success(
                                                request,
                                                f"Override price GHS {override_price} applied. Bill sent to cashier."
                                            )
                                        else:
                                            logger.warning(f"Front desk override: no consultation line found on invoice {invoice.pk}")
                                except (ValueError, TypeError) as e:
                                    logger.warning(f"Front desk manual_price invalid: {e}")
                    except Exception as bill_error:
                        logger.warning(f"Error creating consultation bill: {bill_error}")

                # Send notification to assigned doctor if doctor was assigned
                if assigned_doctor_staff and assigned_doctor_staff.user:
                    try:
                        from hospital.models import Notification
                        Notification.objects.create(
                            recipient=assigned_doctor_staff.user,
                            notification_type='order_urgent',
                            title='New Patient Assigned',
                            message=f'Patient {patient.full_name} (MRN: {patient.mrn}) has been assigned to you. Chief Complaint: {chief_complaint[:100]}',
                            related_object_id=encounter.id,
                            related_object_type='Encounter'
                        )
                        logger.info(f"Front desk visit: Notification sent to doctor {assigned_doctor_staff.user.username}")
                        
                        # Also send SMS notification if doctor has phone number
                        try:
                            from hospital.services.sms_service import sms_service
                            doctor_name = assigned_doctor_staff.user.get_full_name() or assigned_doctor_staff.user.username
                            message = (
                                f"New Patient Assignment\n\n"
                                f"Patient: {patient.full_name}\n"
                                f"MRN: {patient.mrn}\n"
                                f"Complaint: {chief_complaint[:100]}\n\n"
                                f"Please check your consultation dashboard."
                            )
                            phone = getattr(assigned_doctor_staff.user, 'phone_number', None) or getattr(assigned_doctor_staff, 'phone_number', None)
                            if phone:
                                sms_service.send_sms(
                                    phone_number=phone,
                                    message=message,
                                    message_type='doctor_assignment',
                                    recipient_name=doctor_name,
                                    related_object_id=encounter.id,
                                    related_object_type='Encounter'
                                )
                        except Exception as sms_error:
                            logger.warning(f"Front desk visit: Failed to send SMS to doctor: {sms_error}")
                    except Exception as notif_error:
                        logger.warning(f"Front desk visit: Failed to send notification to doctor: {notif_error}")

                # Create queue entry if needed
                try:
                    from hospital.models_queue import QueueEntry
                    from hospital.services.queue_service import queue_service
                    
                    # Determine priority based on encounter type
                    priority = 1 if encounter_type == 'emergency' else 3  # 1=Emergency, 3=Normal
                    
                    queue_entry = queue_service.create_queue_entry(
                        patient=patient,
                        encounter=encounter,
                        department=department,
                        assigned_doctor=assigned_doctor_user,
                        priority=priority,
                        notes=f'Front desk check-in: {chief_complaint}'
                    )
                    
                    if queue_entry:
                        messages.info(request, f"Added to queue. Ticket: {queue_entry.display_ticket_number}")
                except Exception as queue_error:
                    # Queue creation is optional
                    logger.warning(f"Front desk visit: Queue creation failed: {queue_error}")
                
                return redirect('hospital:encounter_detail', pk=encounter.id)
                
        except Exception as e:
            messages.error(request, f'Error creating visit: {str(e)}')
            return redirect('hospital:patient_detail', pk=patient_id)
    
    # GET request - show form
    # Get current payer info
    current_payer = patient.primary_insurance
    current_payer_type = current_payer.payer_type if current_payer else 'cash'
    
    # Get departments
    departments = Department.objects.filter(is_deleted=False).order_by('name')
    
    # Get available doctors for assignment - more inclusive query
    # Include all doctors with active users (regardless of staff.is_active status)
    available_doctors = Staff.objects.filter(
        profession='doctor',
        is_deleted=False,
        user__isnull=False,
        user__is_active=True
    ).select_related('user', 'department').order_by('is_active', 'user__first_name', 'user__last_name')
    
    # Get doctor pricing information for display
    from .utils_doctor_pricing import DoctorPricingService
    doctors_with_pricing = []
    for doctor in available_doctors:
        pricing_info = DoctorPricingService.get_doctor_pricing_info(doctor)
        display_info = DoctorPricingService.get_doctor_display_info(doctor)
        is_first_visit = DoctorPricingService.is_first_visit_to_doctor(patient, doctor)
        
        doctors_with_pricing.append({
            'doctor': doctor,
            'pricing_info': pricing_info,
            'display_info': display_info,
            'is_first_visit': is_first_visit,
        })
    
    # Get payer type options
    payer_types = [
        ('cash', 'Cash Payment'),
        ('insurance', 'Insurance'),
        ('corporate', 'Corporate'),
    ]
    
    # Insurance companies for visit (accredited plans)
    insurance_companies = InsuranceCompany.objects.filter(
        is_active=True,
        status='active',
        is_deleted=False
    ).order_by('name')
    
    # Corporate companies for visit (ECG, etc.)
    corporate_payers = Payer.objects.filter(
        payer_type='corporate',
        is_active=True,
        is_deleted=False
    ).order_by('name')
    
    context = {
        'patient': patient,
        'current_payer': current_payer,
        'current_payer_type': current_payer_type,
        'departments': departments,
        'payer_types': payer_types,
        'available_doctors': available_doctors,
        'doctors_with_pricing': doctors_with_pricing,
        'insurance_companies': insurance_companies,
        'corporate_payers': corporate_payers,
    }
    
    return render(request, 'hospital/frontdesk_visit_create.html', context)


@login_required
def frontdesk_visit_update_payer(request, encounter_id):
    """
    Update payer type for existing visit/encounter
    """
    encounter = get_object_or_404(Encounter, pk=encounter_id, is_deleted=False)
    
    if request.method == 'POST':
        payer_type = request.POST.get('payer_type', '').strip()
        payer_id = request.POST.get('payer_id')
        
        try:
            payer = None
            if payer_id:
                payer = Payer.objects.filter(pk=payer_id, is_deleted=False).first()
            
            # Sync payer type
            sync_result = visit_payer_sync_service.verify_and_set_payer_type(
                encounter=encounter,
                payer_type=payer_type if payer_type else None,
                payer=payer
            )
            
            if sync_result['success']:
                messages.success(request, f"Payer type updated! {sync_result['message']}")
            else:
                messages.error(request, f"Error updating payer type: {sync_result['message']}")
            
            return redirect('hospital:encounter_detail', pk=encounter_id)
            
        except Exception as e:
            messages.error(request, f'Error updating payer type: {str(e)}')
            return redirect('hospital:encounter_detail', pk=encounter_id)
    
    # GET request - show update form
    current_payer = encounter.patient.primary_insurance
    current_payer_type = current_payer.payer_type if current_payer else 'cash'
    
    payer_types = [
        ('cash', 'Cash Payment'),
        ('insurance', 'Insurance'),
        ('corporate', 'Corporate'),
    ]
    
    context = {
        'encounter': encounter,
        'patient': encounter.patient,
        'current_payer': current_payer,
        'current_payer_type': current_payer_type,
        'payer_types': payer_types,
    }
    
    return render(request, 'hospital/frontdesk_visit_update_payer.html', context)


@login_required
def frontdesk_visit_pricing_preview(request, encounter_id):
    """
    Preview pricing for services based on current payer type
    """
    encounter = get_object_or_404(Encounter, pk=encounter_id, is_deleted=False)
    
    service_code_id = request.GET.get('service_code_id')
    if not service_code_id:
        return JsonResponse({'error': 'service_code_id required'}, status=400)
    
    try:
        from hospital.models import ServiceCode
        from hospital.services.pricing_engine_service import PricingEngineService
        
        service_code = ServiceCode.objects.get(pk=service_code_id, is_deleted=False)
        pricing_engine = PricingEngineService()
        
        # Get price for this service
        price = pricing_engine.get_service_price(
            service_code=service_code,
            patient=encounter.patient,
            payer=encounter.patient.primary_insurance
        )
        
        # Get payer info
        payer = encounter.patient.primary_insurance
        payer_type = payer.payer_type if payer else 'cash'
        
        return JsonResponse({
            'success': True,
            'service_code': service_code.code,
            'service_description': service_code.description,
            'price': str(price),
            'payer_type': payer_type,
            'payer_name': payer.name if payer else 'Cash',
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
