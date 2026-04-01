"""
Imaging/Radiology Report Print Views
"""
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils import timezone

from .models_advanced import ImagingStudy
from .models_settings import HospitalSettings


@login_required
def print_imaging_report(request, study_id):
    """Print-friendly imaging/radiology report with professional letterhead"""
    study = get_object_or_404(ImagingStudy, pk=study_id, is_deleted=False)
    
    # Check payment status for cash patients - enforce payment before printing results
    from hospital.services.auto_billing_service import AutoBillingService
    from hospital.models_payment_verification import ImagingRelease
    from hospital.utils_roles import get_user_role
    from django.contrib import messages
    
    # Check if user is staff/admin (they can always print)
    user_role = get_user_role(request.user)
    is_staff = (user_role == 'admin' or request.user.is_staff or request.user.is_superuser)
    
    # For cash patients, check payment status
    patient = study.patient
    payer = patient.primary_insurance if hasattr(patient, 'primary_insurance') else None
    is_cash_patient = not payer or (payer and payer.payer_type == 'cash')
    
    if is_cash_patient and not is_staff:
        # Check payment status
        payment_status = AutoBillingService.check_payment_status('imaging', str(study_id))
        
        # Ensure release record exists
        try:
            release_record = study.release_record
        except:
            # Create release record if it doesn't exist
            release_record = ImagingRelease.objects.create(
                imaging_study=study,
                patient=patient,
                release_status='pending_payment'
            )
            # Try to create bill if not exists
            AutoBillingService.create_imaging_bill(study)
            payment_status = AutoBillingService.check_payment_status('imaging', str(study_id))
        
        # Only allow printing if payment is verified
        if not payment_status['paid']:
            messages.error(
                request,
                f"❌ PAYMENT REQUIRED! This imaging report requires payment before it can be printed. "
                f"Please proceed to the cashier to make payment. Status: {payment_status['message']}"
            )
            from django.urls import reverse
            try:
                from django.shortcuts import redirect
                return redirect(reverse('hospital:cashier_process_service_payment', args=['imaging', str(study_id)]))
            except:
                from django.http import HttpResponseForbidden
                return HttpResponseForbidden(
                    f"<h1>Payment Required</h1><p>This imaging report requires payment before it can be printed. "
                    f"Please proceed to the cashier to make payment.</p>"
                )
    
    settings = HospitalSettings.get_settings()
    
    context = {
        'study': study,
        'settings': settings,
        'now': timezone.now(),
    }
    
    return render(request, 'hospital/imaging_report_print.html', context)










