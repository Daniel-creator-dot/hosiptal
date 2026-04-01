"""
Doctor Performance Tracking for Finance/Accounting
Real-time tracking of doctor-patient interactions and services rendered
"""
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db.models import (
    Count, Sum, Q, F, Case, When, Value, IntegerField,
    DecimalField, Avg, Max, Min
)
from django.db.models.functions import TruncDate, Coalesce
from django.utils import timezone
from django.core.paginator import Paginator
from datetime import datetime, timedelta, date
from decimal import Decimal
import logging

from .models import Staff, Patient, Encounter, Invoice, InvoiceLine, ServiceCode
from .decorators import role_required
from .utils_roles import get_user_role

logger = logging.getLogger(__name__)


def is_finance_user(user):
    """Check if user has finance/accounting access"""
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    role = get_user_role(user)
    return role in ('accountant', 'senior_account_officer', 'admin')


@login_required
@role_required('accountant', 'senior_account_officer', 'admin')
def doctor_performance_dashboard(request):
    """
    Real-time Doctor Performance Dashboard for Finance
    Shows patient visits, services rendered, and revenue per doctor
    """
    today = timezone.now().date()
    start_of_month = today.replace(day=1)
    start_of_week = today - timedelta(days=today.weekday())
    
    # Date range filter
    date_filter = request.GET.get('period', 'month')  # today, week, month, all
    start_date = None
    end_date = today
    
    if date_filter == 'today':
        start_date = today
    elif date_filter == 'week':
        start_date = start_of_week
    elif date_filter == 'month':
        start_date = start_of_month
    # 'all' means no date filter
    
    # Get all doctors (optimized query)
    doctors = Staff.objects.filter(
        profession='doctor',
        is_deleted=False,
        is_active=True
    ).select_related('user', 'department').prefetch_related(
        'user__groups'
    ).order_by('user__last_name', 'user__first_name')
    
    # Build performance data for each doctor
    doctor_performance = []
    
    for doctor in doctors:
        if not doctor.user:
            continue
        
        # Base query for encounters
        encounters_query = Encounter.objects.filter(
            provider=doctor,
            is_deleted=False
        )
        
        if start_date:
            encounters_query = encounters_query.filter(started_at__date__gte=start_date)
        
        encounters_query = encounters_query.filter(started_at__date__lte=end_date)
        
        # Patient count (unique patients)
        unique_patients = encounters_query.values('patient').distinct().count()
        
        # Total encounters
        total_encounters = encounters_query.count()
        
        # Get invoices for these encounters (optimized query)
        invoices = Invoice.objects.filter(
            encounter__provider=doctor,
            encounter__is_deleted=False,
            is_deleted=False
        )
        
        if start_date:
            invoices = invoices.filter(encounter__started_at__date__gte=start_date)
        invoices = invoices.filter(encounter__started_at__date__lte=end_date)
        
        # Get invoice lines (services) for these invoices (optimized with select_related)
        invoice_lines = InvoiceLine.objects.filter(
            invoice__in=invoices,
            is_deleted=False
        ).select_related(
            'service_code',
            'invoice',
            'invoice__encounter',
            'invoice__encounter__patient',
            'invoice__encounter__provider'
        )
        
        # Service statistics
        total_services = invoice_lines.count()
        
        # Revenue from services
        total_revenue = invoice_lines.aggregate(
            total=Sum('line_total')
        )['total'] or Decimal('0.00')
        
        # Services by category
        services_by_category = invoice_lines.values(
            'service_code__category'
        ).annotate(
            count=Count('id'),
            revenue=Sum('line_total')
        ).order_by('-revenue')
        
        # Services by type
        services_by_type = invoice_lines.values(
            'service_code__code',
            'service_code__description',
            'service_code__category'
        ).annotate(
            count=Count('id'),
            revenue=Sum('line_total'),
            avg_price=Avg('unit_price')
        ).order_by('-revenue')[:10]  # Top 10 services
        
        # Encounter types breakdown
        encounter_types = encounters_query.values('encounter_type').annotate(
            count=Count('id')
        ).order_by('-count')
        
        # Recent patients (last 10)
        recent_encounters = encounters_query.select_related(
            'patient'
        ).order_by('-started_at')[:10]
        
        recent_patients = []
        for enc in recent_encounters:
            if enc.patient:
                recent_patients.append({
                    'patient_name': enc.patient.full_name or f"{enc.patient.first_name} {enc.patient.last_name}".strip() or enc.patient.mrn,
                    'mrn': enc.patient.mrn or '-',
                    'encounter_type': enc.get_encounter_type_display(),
                    'date': enc.started_at.date() if enc.started_at else None,
                    'encounter_id': str(enc.id),
                })
        
        # Daily activity (last 30 days)
        daily_activity = []
        if start_date:
            activity_start = max(start_date, today - timedelta(days=30))
        else:
            activity_start = today - timedelta(days=30)
        
        daily_stats = encounters_query.filter(
            started_at__date__gte=activity_start
        ).annotate(
            date=TruncDate('started_at')
        ).values('date').annotate(
            patient_count=Count('patient', distinct=True),
            encounter_count=Count('id')
        ).order_by('date')
        
        for stat in daily_stats:
            daily_activity.append({
                'date': stat['date'],
                'patients': stat['patient_count'],
                'encounters': stat['encounter_count'],
            })
        
        # Calculate performance metrics
        avg_patients_per_day = 0
        if start_date:
            days = (end_date - start_date).days + 1
            if days > 0:
                avg_patients_per_day = round(unique_patients / days, 2)
        
        # Average revenue per patient
        avg_revenue_per_patient = Decimal('0.00')
        if unique_patients > 0:
            avg_revenue_per_patient = total_revenue / Decimal(str(unique_patients))
        
        # Average revenue per encounter
        avg_revenue_per_encounter = Decimal('0.00')
        if total_encounters > 0:
            avg_revenue_per_encounter = total_revenue / Decimal(str(total_encounters))
        
        doctor_performance.append({
            'doctor': doctor,
            'doctor_name': doctor.user.get_full_name() or doctor.user.username if doctor.user else 'Unknown',
            'employee_id': doctor.employee_id or '-',
            'department': doctor.department.name if doctor.department else '-',
            'unique_patients': unique_patients,
            'total_encounters': total_encounters,
            'total_services': total_services,
            'total_revenue': total_revenue,
            'avg_patients_per_day': avg_patients_per_day,
            'avg_revenue_per_patient': avg_revenue_per_patient,
            'avg_revenue_per_encounter': avg_revenue_per_encounter,
            'services_by_category': list(services_by_category),
            'top_services': list(services_by_type),
            'encounter_types': list(encounter_types),
            'recent_patients': recent_patients,
            'daily_activity': daily_activity,
        })
    
    # Sort by total revenue (descending)
    doctor_performance.sort(key=lambda x: x['total_revenue'], reverse=True)
    
    # Summary statistics
    total_doctors = len(doctor_performance)
    total_all_patients = sum(d['unique_patients'] for d in doctor_performance)
    total_all_encounters = sum(d['total_encounters'] for d in doctor_performance)
    total_all_services = sum(d['total_services'] for d in doctor_performance)
    total_all_revenue = sum(d['total_revenue'] for d in doctor_performance)
    
    # Pagination
    paginator = Paginator(doctor_performance, 20)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    context = {
        'doctor_performance': page_obj,
        'date_filter': date_filter,
        'start_date': start_date,
        'end_date': end_date,
        'today': today,
        'summary': {
            'total_doctors': total_doctors,
            'total_patients': total_all_patients,
            'total_encounters': total_all_encounters,
            'total_services': total_all_services,
            'total_revenue': total_all_revenue,
        },
    }
    
    return render(request, 'hospital/accountant/doctor_performance_dashboard.html', context)


@login_required
@role_required('accountant', 'senior_account_officer', 'admin')
def doctor_performance_detail(request, staff_id):
    """
    Detailed view of a specific doctor's performance
    """
    doctor = get_object_or_404(Staff, pk=staff_id, profession='doctor', is_deleted=False)
    
    today = timezone.now().date()
    start_of_month = today.replace(day=1)
    
    # Date range filter
    date_filter = request.GET.get('period', 'month')
    start_date = None
    end_date = today
    
    if date_filter == 'today':
        start_date = today
    elif date_filter == 'week':
        start_date = today - timedelta(days=today.weekday())
    elif date_filter == 'month':
        start_date = start_of_month
    
    # Get all encounters for this doctor
    encounters_query = Encounter.objects.filter(
        provider=doctor,
        is_deleted=False
    )
    
    if start_date:
        encounters_query = encounters_query.filter(started_at__date__gte=start_date)
    encounters_query = encounters_query.filter(started_at__date__lte=end_date)
    
    # Get all patients
    patients = Patient.objects.filter(
        encounters__provider=doctor,
        encounters__is_deleted=False
    ).distinct()
    
    if start_date:
        patients = patients.filter(
            encounters__started_at__date__gte=start_date
        )
    
    # Get invoices and services
    invoices = Invoice.objects.filter(
        encounter__provider=doctor,
        encounter__is_deleted=False,
        is_deleted=False
    )
    
    if start_date:
        invoices = invoices.filter(encounter__started_at__date__gte=start_date)
    
    invoice_lines = InvoiceLine.objects.filter(
        invoice__in=invoices,
        is_deleted=False
    ).select_related('service_code', 'invoice', 'invoice__encounter', 'invoice__encounter__patient')
    
    # Detailed patient list with services
    patient_details = []
    for patient in patients.order_by('-encounters__started_at')[:50]:
        patient_encounters = encounters_query.filter(patient=patient)
        patient_invoices = invoices.filter(patient=patient)
        patient_services = invoice_lines.filter(invoice__patient=patient)
        
        patient_revenue = patient_services.aggregate(
            total=Sum('line_total')
        )['total'] or Decimal('0.00')
        
        patient_details.append({
            'patient': patient,
            'patient_name': patient.full_name or f"{patient.first_name} {patient.last_name}".strip() or patient.mrn,
            'mrn': patient.mrn or '-',
            'encounter_count': patient_encounters.count(),
            'service_count': patient_services.count(),
            'total_revenue': patient_revenue,
            'last_visit': patient_encounters.order_by('-started_at').first().started_at.date() if patient_encounters.exists() else None,
        })
    
    # Services breakdown
    services_breakdown = invoice_lines.values(
        'service_code__code',
        'service_code__description',
        'service_code__category'
    ).annotate(
        count=Count('id'),
        revenue=Sum('line_total'),
        avg_price=Avg('unit_price'),
        min_price=Min('unit_price'),
        max_price=Max('unit_price')
    ).order_by('-revenue')
    
    # Monthly trend
    monthly_trend = []
    if start_date:
        current = start_date.replace(day=1)
    else:
        current = (today - timedelta(days=365)).replace(day=1)
    
    while current <= today:
        month_start = current
        month_end = (current + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        
        month_encounters = encounters_query.filter(
            started_at__date__gte=month_start,
            started_at__date__lte=month_end
        )
        
        month_invoices = invoices.filter(
            encounter__started_at__date__gte=month_start,
            encounter__started_at__date__lte=month_end
        )
        
        month_lines = invoice_lines.filter(
            invoice__in=month_invoices
        )
        
        monthly_trend.append({
            'month': current.strftime('%B %Y'),
            'date': current,
            'patients': month_encounters.values('patient').distinct().count(),
            'encounters': month_encounters.count(),
            'services': month_lines.count(),
            'revenue': month_lines.aggregate(total=Sum('line_total'))['total'] or Decimal('0.00'),
        })
        
        # Move to next month
        if current.month == 12:
            current = current.replace(year=current.year + 1, month=1)
        else:
            current = current.replace(month=current.month + 1)
    
    # Summary
    total_patients = len(patient_details)
    total_encounters = encounters_query.count()
    total_services = invoice_lines.count()
    total_revenue = invoice_lines.aggregate(total=Sum('line_total'))['total'] or Decimal('0.00')
    
    context = {
        'doctor': doctor,
        'doctor_name': doctor.user.get_full_name() or doctor.user.username if doctor.user else 'Unknown',
        'date_filter': date_filter,
        'start_date': start_date,
        'end_date': end_date,
        'patient_details': patient_details,
        'services_breakdown': list(services_breakdown),
        'monthly_trend': monthly_trend,
        'summary': {
            'total_patients': total_patients,
            'total_encounters': total_encounters,
            'total_services': total_services,
            'total_revenue': total_revenue,
        },
    }
    
    return render(request, 'hospital/accountant/doctor_performance_detail.html', context)


@login_required
@role_required('accountant', 'senior_account_officer', 'admin')
def doctor_performance_api(request):
    """
    API endpoint for real-time doctor performance data
    Returns JSON for AJAX updates
    """
    today = timezone.now().date()
    start_of_month = today.replace(day=1)
    
    date_filter = request.GET.get('period', 'month')
    start_date = None
    end_date = today
    
    if date_filter == 'today':
        start_date = today
    elif date_filter == 'week':
        start_date = today - timedelta(days=today.weekday())
    elif date_filter == 'month':
        start_date = start_of_month
    
    # Quick summary for all doctors
    doctors = Staff.objects.filter(
        profession='doctor',
        is_deleted=False,
        is_active=True
    ).select_related('user')
    
    summary_data = []
    
    for doctor in doctors:
        if not doctor.user:
            continue
        
        encounters_query = Encounter.objects.filter(
            provider=doctor,
            is_deleted=False
        )
        
        if start_date:
            encounters_query = encounters_query.filter(started_at__date__gte=start_date)
        encounters_query = encounters_query.filter(started_at__date__lte=end_date)
        
        unique_patients = encounters_query.values('patient').distinct().count()
        total_encounters = encounters_query.count()
        
        invoices = Invoice.objects.filter(
            encounter__in=encounters_query,
            is_deleted=False
        )
        
        invoice_lines = InvoiceLine.objects.filter(
            invoice__in=invoices,
            is_deleted=False
        )
        
        total_services = invoice_lines.count()
        total_revenue = invoice_lines.aggregate(
            total=Sum('line_total')
        )['total'] or Decimal('0.00')
        
        summary_data.append({
            'doctor_id': str(doctor.id),
            'doctor_name': doctor.user.get_full_name() or doctor.user.username,
            'employee_id': doctor.employee_id or '-',
            'unique_patients': unique_patients,
            'total_encounters': total_encounters,
            'total_services': total_services,
            'total_revenue': float(total_revenue),
        })
    
    # Sort by revenue
    summary_data.sort(key=lambda x: x['total_revenue'], reverse=True)
    
    # Overall totals
    totals = {
        'total_doctors': len(summary_data),
        'total_patients': sum(d['unique_patients'] for d in summary_data),
        'total_encounters': sum(d['total_encounters'] for d in summary_data),
        'total_services': sum(d['total_services'] for d in summary_data),
        'total_revenue': sum(d['total_revenue'] for d in summary_data),
    }
    
    return JsonResponse({
        'success': True,
        'period': date_filter,
        'start_date': start_date.isoformat() if start_date else None,
        'end_date': end_date.isoformat(),
        'doctors': summary_data,
        'totals': totals,
        'timestamp': timezone.now().isoformat(),
    })
