"""
Pharmacy Label Printing for Brother QL-820NWB Label Printer
Creates medication labels for dispensed prescriptions
"""

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils import timezone
from decimal import Decimal

from .models import Prescription, Patient, Staff
from .models_payment_verification import PharmacyDispensing
from .models_pharmacy_walkin import WalkInPharmacySale


@login_required
def pharmacy_label_print(request, prescription_id):
    """
    Print medication label for a prescription
    Optimized for Brother QL-820NWB (62mm label width)
    """
    prescription = get_object_or_404(Prescription, id=prescription_id, is_deleted=False)
    patient = prescription.order.encounter.patient
    
    # Get dispensing record if exists
    dispensing_record = None
    try:
        dispensing_record = prescription.dispensing_record
    except:
        pass
    
    # Get hospital settings
    from .models_settings import HospitalSettings
    hospital_settings = HospitalSettings.get_settings()
    
    context = {
        'title': f'Medication Label - {prescription.drug.name}',
        'prescription': prescription,
        'patient': patient,
        'dispensing_record': dispensing_record,
        'hospital_settings': hospital_settings,
    }
    
    return render(request, 'hospital/pharmacy/label_print.html', context)


@login_required
def pharmacy_walkin_label_print(request, sale_id):
    """
    Print label for walk-in pharmacy sale
    """
    sale = get_object_or_404(WalkInPharmacySale, id=sale_id, is_deleted=False)
    
    # Get hospital settings
    from .models_settings import HospitalSettings
    hospital_settings = HospitalSettings.get_settings()
    
    context = {
        'title': f'Pharmacy Label - {sale.customer_name or "Prescribe Sale"}',
        'sale': sale,
        'hospital_settings': hospital_settings,
    }
    
    return render(request, 'hospital/pharmacy/walkin_label_print.html', context)


@login_required
def pharmacy_batch_label_print(request):
    """
    Print labels for multiple prescriptions at once
    """
    if request.method == 'POST':
        prescription_ids = request.POST.getlist('prescription_ids')
        
        if not prescription_ids:
            return JsonResponse({'success': False, 'error': 'No prescriptions selected'})
        
        prescriptions = Prescription.objects.filter(
            id__in=prescription_ids,
            is_deleted=False
        ).select_related('drug', 'order__encounter__patient')
        
        # Get hospital settings
        from .models_settings import HospitalSettings
        hospital_settings = HospitalSettings.get_settings()
        
        context = {
            'title': 'Batch Medication Labels',
            'prescriptions': prescriptions,
            'hospital_settings': hospital_settings,
        }
        
        return render(request, 'hospital/pharmacy/batch_label_print.html', context)
    
    return JsonResponse({'success': False, 'error': 'POST method required'})





