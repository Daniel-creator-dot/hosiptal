"""
Pharmacy Patient List View
Shows patients with pharmacy-related activities
"""
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Count
from django.core.paginator import Paginator
from django.utils import timezone
from datetime import timedelta

from .models import Patient, Prescription, Order
from .models_payment_verification import PharmacyDispensing


@login_required
def pharmacy_patients_list(request):
    """
    List patients with pharmacy-related activities (prescriptions, pending dispensing, etc.)
    """
    query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', 'all')
    
    # Get patients with pharmacy activity
    patients_with_prescriptions = Patient.objects.filter(
        encounters__orders__order_type='medication',
        encounters__orders__is_deleted=False,
        is_deleted=False
    ).distinct()
    
    # Apply search filter
    if query:
        patients_with_prescriptions = patients_with_prescriptions.filter(
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(mrn__icontains=query) |
            Q(phone_number__icontains=query)
        )
    
    # Get recent activity for each patient
    patients_data = []
    for patient in patients_with_prescriptions[:100]:  # Limit for performance
        # Get recent prescriptions
        recent_prescriptions = Prescription.objects.filter(
            order__encounter__patient=patient,
            is_deleted=False
        ).select_related('drug', 'order__encounter').order_by('-created')[:5]
        
        # Get pending dispensing
        pending_dispensing = PharmacyDispensing.objects.filter(
            patient=patient,
            dispensing_status__in=['pending_payment', 'ready_to_dispense'],
            is_deleted=False
        ).select_related('prescription__drug').order_by('-created')[:5]
        
        # Get recent orders
        recent_orders = Order.objects.filter(
            encounter__patient=patient,
            order_type='medication',
            is_deleted=False
        ).select_related('encounter').order_by('-requested_at')[:5]
        
        # Determine status
        has_pending = pending_dispensing.exists()
        has_ready = pending_dispensing.filter(dispensing_status='ready_to_dispense').exists()
        
        if has_ready:
            status = 'ready'
        elif has_pending:
            status = 'pending'
        else:
            status = 'completed'
        
        # Apply status filter
        if status_filter != 'all':
            if status_filter == 'pending' and not has_pending:
                continue
            elif status_filter == 'ready' and not has_ready:
                continue
            elif status_filter == 'completed' and (has_pending or has_ready):
                continue
        
        patients_data.append({
            'patient': patient,
            'recent_prescriptions': recent_prescriptions,
            'pending_dispensing': pending_dispensing,
            'recent_orders': recent_orders,
            'status': status,
            'pending_count': pending_dispensing.count(),
        })
    
    # Sort by status priority and recent activity
    status_priority = {'ready': 0, 'pending': 1, 'completed': 2}
    patients_data.sort(key=lambda x: (status_priority.get(x['status'], 3), x['pending_count']), reverse=True)
    
    # Pagination
    paginator = Paginator(patients_data, 25)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    # Statistics
    stats = {
        'total': len(patients_data),
        'ready': sum(1 for p in patients_data if p['status'] == 'ready'),
        'pending': sum(1 for p in patients_data if p['status'] == 'pending'),
        'completed': sum(1 for p in patients_data if p['status'] == 'completed'),
    }
    
    context = {
        'title': 'Pharmacy Patients',
        'page_obj': page_obj,
        'patients_data': page_obj,
        'query': query,
        'status_filter': status_filter,
        'stats': stats,
    }
    
    return render(request, 'hospital/pharmacy_patients_list.html', context)
