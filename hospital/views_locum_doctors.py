"""
Locum Doctor Service Tracking and Payment Views
For accountants to manage payments to visiting/locum doctors
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Sum, Count
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal

from .models import Staff, Patient, Encounter, Invoice, InvoiceLine
from .models_locum_doctors import LocumDoctorService, LocumDoctorPaymentBatch
from .forms_locum_doctors import LocumDoctorServiceForm
from .decorators import role_required
from .utils_roles import get_user_role


@login_required
@role_required('accountant', 'admin')
def locum_doctors_dashboard(request):
    """Dashboard for viewing and managing locum doctor services and payments"""
    # Get date range from request (default to current month)
    today = timezone.now().date()
    start_date = request.GET.get('start_date', today.replace(day=1).isoformat())
    end_date = request.GET.get('end_date', today.isoformat())
    
    try:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        start_date = today.replace(day=1)
        end_date = today
    
    # Get all locum services in date range
    services = LocumDoctorService.objects.filter(
        service_date__gte=start_date,
        service_date__lte=end_date,
        is_deleted=False
    ).select_related('doctor', 'doctor__user', 'patient')
    
    # Statistics
    total_services = services.count()
    pending_services = services.filter(payment_status='pending').count()
    paid_services = services.filter(payment_status='paid').count()
    
    # Financial summary
    summary = services.aggregate(
        total_service_charge=Sum('service_charge'),
        total_doctor_payment=Sum('doctor_payment'),
        total_tax=Sum('tax_amount'),
        total_net_payment=Sum('net_payment')
    )
    
    # Group by doctor
    doctors_summary = services.values(
        'doctor', 'doctor__user__first_name', 'doctor__user__last_name'
    ).annotate(
        service_count=Count('id'),
        total_payment=Sum('doctor_payment'),
        total_tax=Sum('tax_amount'),
        net_payment=Sum('net_payment'),
        pending_count=Count('id', filter=Q(payment_status='pending'))
    ).order_by('-total_payment')
    
    # Recent services
    recent_services = services.order_by('-service_date', '-created')[:20]
    
    context = {
        'title': 'Locum Doctors Payment Management',
        'start_date': start_date,
        'end_date': end_date,
        'total_services': total_services,
        'pending_services': pending_services,
        'paid_services': paid_services,
        'summary': summary,
        'doctors_summary': doctors_summary,
        'recent_services': recent_services,
    }
    
    return render(request, 'hospital/locum_doctors/dashboard.html', context)


@login_required
@role_required('accountant', 'admin')
def locum_doctor_services_list(request, doctor_id=None):
    """List all locum doctor services, optionally filtered by doctor"""
    # Get date range from request
    today = timezone.now().date()
    start_date = request.GET.get('start_date', today.replace(day=1).isoformat())
    end_date = request.GET.get('end_date', today.isoformat())
    
    try:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        start_date = today.replace(day=1)
        end_date = today
    
    # Get services
    services = LocumDoctorService.objects.filter(
        service_date__gte=start_date,
        service_date__lte=end_date,
        is_deleted=False
    ).select_related('doctor', 'doctor__user', 'patient')
    
    # Filter by doctor if specified
    doctor = None
    if doctor_id:
        doctor = get_object_or_404(Staff, id=doctor_id)
        services = services.filter(doctor=doctor)
    
    # Filter by payment status
    payment_status = request.GET.get('payment_status', '')
    if payment_status:
        services = services.filter(payment_status=payment_status)
    
    # Order by date
    services = services.order_by('-service_date', '-created')
    
    context = {
        'title': 'Locum Doctor Services',
        'services': services,
        'doctor': doctor,
        'start_date': start_date,
        'end_date': end_date,
        'payment_status': payment_status,
    }
    
    return render(request, 'hospital/locum_doctors/services_list.html', context)


@login_required
@role_required('accountant', 'admin')
def locum_doctor_payment_batch(request, doctor_id):
    """Create a payment batch for a specific doctor's services in a date range"""
    doctor = get_object_or_404(Staff, id=doctor_id)
    
    if request.method == 'POST':
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        payment_method = request.POST.get('payment_method', 'bank_transfer')
        
        try:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            messages.error(request, 'Invalid date format')
            return redirect('hospital:locum_doctor_services_list', doctor_id=doctor_id)
        
        # Get pending services for this doctor in date range
        services = LocumDoctorService.objects.filter(
            doctor=doctor,
            service_date__gte=start_date,
            service_date__lte=end_date,
            payment_status='pending',
            is_deleted=False
        )
        
        if not services.exists():
            messages.warning(request, 'No pending services found for the selected date range')
            return redirect('hospital:locum_doctor_services_list', doctor_id=doctor_id)
        
        # Create payment batch
        batch = LocumDoctorPaymentBatch.objects.create(
            doctor=doctor,
            period_start=start_date,
            period_end=end_date,
            payment_method=payment_method,
            processed_by=request.user
        )
        
        # Add services to batch
        batch.services.set(services)
        batch.save()  # This will calculate totals
        
        # Update services payment method
        services.update(payment_method=payment_method)
        
        messages.success(request, f'Payment batch created successfully. Total: GHS {batch.total_net_payment:.2f}')
        return redirect('hospital:locum_doctor_payment_batch_detail', batch_id=batch.id)
    
    # GET request - show form
    today = timezone.now().date()
    default_start = today.replace(day=1)
    default_end = today
    
    context = {
        'title': f'Create Payment Batch - {doctor.user.get_full_name()}',
        'doctor': doctor,
        'default_start': default_start,
        'default_end': default_end,
    }
    
    return render(request, 'hospital/locum_doctors/create_batch.html', context)


@login_required
@role_required('accountant', 'admin')
def locum_doctor_payment_batch_detail(request, batch_id):
    """View and process payment for a payment batch"""
    batch = get_object_or_404(LocumDoctorPaymentBatch, id=batch_id)
    
    if request.method == 'POST':
        # Process payment
        payment_date = request.POST.get('payment_date')
        payment_reference = request.POST.get('payment_reference', '')
        notes = request.POST.get('notes', '')
        
        try:
            payment_date = datetime.strptime(payment_date, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            payment_date = timezone.now().date()
        
        # Mark batch as paid
        batch.payment_status = 'paid'
        batch.payment_date = payment_date
        batch.payment_reference = payment_reference
        batch.notes = notes
        batch.save()
        
        # Mark all services in batch as paid
        for service in batch.services.all():
            service.mark_as_paid(
                payment_date=payment_date,
                payment_reference=payment_reference,
                paid_by=request.user,
                notes=notes
            )
        
        messages.success(request, f'Payment processed successfully for batch {batch.batch_number}')
        return redirect('hospital:locum_doctors_dashboard')
    
    # Get services in batch
    services = batch.services.all().select_related('patient').order_by('service_date')
    
    context = {
        'title': f'Payment Batch {batch.batch_number}',
        'batch': batch,
        'services': services,
    }
    
    return render(request, 'hospital/locum_doctors/batch_detail.html', context)


@login_required
@role_required('accountant', 'admin')
def locum_doctor_service_detail(request, service_id):
    """View details of a specific locum doctor service"""
    service = get_object_or_404(LocumDoctorService, id=service_id)
    
    context = {
        'title': 'Locum Doctor Service Details',
        'service': service,
    }
    
    return render(request, 'hospital/locum_doctors/service_detail.html', context)


@login_required
@role_required('accountant', 'admin')
def locum_doctor_service_create(request):
    """Create a new locum doctor service record"""
    if request.method == 'POST':
        form = LocumDoctorServiceForm(request.POST)
        if form.is_valid():
            service = form.save()
            messages.success(request, f'Service record created successfully. Doctor payment: ₵{service.doctor_payment:.2f}')
            return redirect('hospital:locum_doctor_service_detail', service_id=service.id)
    else:
        form = LocumDoctorServiceForm()
    
    context = {
        'title': 'Add Locum Doctor Service',
        'form': form,
    }
    
    return render(request, 'hospital/locum_doctors/service_form.html', context)


@login_required
@role_required('accountant', 'admin')
def locum_doctor_service_edit(request, service_id):
    """Edit a locum doctor service record"""
    service = get_object_or_404(LocumDoctorService, id=service_id)
    
    if request.method == 'POST':
        form = LocumDoctorServiceForm(request.POST, instance=service)
        if form.is_valid():
            service = form.save()
            messages.success(request, 'Service record updated successfully')
            return redirect('hospital:locum_doctor_service_detail', service_id=service.id)
    else:
        form = LocumDoctorServiceForm(instance=service)
    
    context = {
        'title': 'Edit Locum Doctor Service',
        'form': form,
        'service': service,
    }
    
    return render(request, 'hospital/locum_doctors/service_form.html', context)

