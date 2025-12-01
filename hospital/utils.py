"""
Utility functions for Hospital Management System
"""
from django.db.models import Count, Sum, Avg, Q, F
from django.utils import timezone
from datetime import timedelta, date
from decimal import Decimal
from .models import (
    Patient, Encounter, Admission, Invoice, InvoiceLine,
    Order, Appointment, LabResult, PharmacyStock, Bed, Ward
)


def get_dashboard_stats():
    """Get dashboard statistics"""
    today = timezone.now().date()
    
    # Patient stats
    # Include both new Django patients AND imported legacy patients
    django_patients = Patient.objects.filter(is_deleted=False).count()
    
    # Safely get legacy patient count - handle if table doesn't exist
    legacy_patients = 0
    try:
        from .models_legacy_patients import LegacyPatient
        try:
            legacy_patients = LegacyPatient.objects.count()
        except Exception:
            # Table doesn't exist or other database error
            legacy_patients = 0
    except ImportError:
        # Model doesn't exist
        legacy_patients = 0
    
    total_patients = django_patients + legacy_patients
    new_patients_today = Patient.objects.filter(
        created__date=today,
        is_deleted=False
    ).count()
    
    # Encounter stats
    total_encounters = Encounter.objects.filter(is_deleted=False).count()
    active_encounters = Encounter.objects.filter(
        status='active',
        is_deleted=False
    ).count()
    encounters_today = Encounter.objects.filter(
        started_at__date=today,
        is_deleted=False
    ).count()
    
    # Admission stats
    total_admissions = Admission.objects.filter(is_deleted=False).count()
    current_admissions = Admission.objects.filter(
        status='admitted',
        is_deleted=False
    ).count()
    
    # Financial stats
    invoices_total = Invoice.objects.filter(is_deleted=False).count()
    invoices_paid = Invoice.objects.filter(
        status='paid',
        is_deleted=False
    ).count()
    
    # Revenue today should be based on PAYMENTS RECEIVED today, not invoices issued
    from hospital.models_accounting import PaymentReceipt
    revenue_today = PaymentReceipt.objects.filter(
        receipt_date__date=today,
        is_deleted=False
    ).aggregate(Sum('amount_paid'))['amount_paid__sum'] or Decimal('0.00')
    
    # Total revenue = all payments ever received
    total_revenue = PaymentReceipt.objects.filter(
        is_deleted=False
    ).aggregate(Sum('amount_paid'))['amount_paid__sum'] or Decimal('0.00')
    
    outstanding_balance = Invoice.objects.filter(
        status__in=['issued', 'partially_paid', 'overdue'],
        balance__gt=0,
        is_deleted=False
    ).aggregate(Sum('balance'))['balance__sum'] or Decimal('0.00')
    
    # Bed stats
    total_beds = Bed.objects.filter(is_deleted=False).count()
    occupied_beds = Bed.objects.filter(
        status='occupied',
        is_deleted=False
    ).count()
    available_beds = Bed.objects.filter(
        status='available',
        is_deleted=False
    ).count()
    bed_occupancy_rate = round((occupied_beds / total_beds * 100), 1) if total_beds > 0 else 0
    
    # Appointments
    appointments_today = Appointment.objects.filter(
        appointment_date__date=today,
        is_deleted=False
    ).count()
    
    upcoming_appointments = Appointment.objects.filter(
        appointment_date__gte=timezone.now(),
        status__in=['scheduled', 'confirmed'],
        is_deleted=False
    ).count()
    
    # Additional stats for template
    from datetime import datetime
    first_day_of_month = today.replace(day=1)
    patients_this_month = Patient.objects.filter(
        created__date__gte=first_day_of_month,
        is_deleted=False
    ).count()
    
    # Urgent orders
    from datetime import timedelta
    urgent_orders = Order.objects.filter(
        priority='urgent',
        status__in=['pending', 'in_progress'],
        is_deleted=False
    ).count()
    
    stat_orders = Order.objects.filter(
        priority='stat',
        status__in=['pending', 'in_progress'],
        is_deleted=False
    ).count()
    
    urgent_orders = urgent_orders + stat_orders
    
    # Revenue growth (simplified - comparing to previous month)
    # Use PaymentReceipts for accurate revenue tracking (when money was actually received)
    last_month_start = (first_day_of_month - timedelta(days=1)).replace(day=1)
    last_month_end = first_day_of_month - timedelta(days=1)
    revenue_last_month = PaymentReceipt.objects.filter(
        receipt_date__date__gte=last_month_start,
        receipt_date__date__lte=last_month_end,
        is_deleted=False
    ).aggregate(Sum('amount_paid'))['amount_paid__sum'] or Decimal('0.00')
    
    revenue_this_month = PaymentReceipt.objects.filter(
        receipt_date__date__gte=first_day_of_month,
        receipt_date__date__lte=today,
        is_deleted=False
    ).aggregate(Sum('amount_paid'))['amount_paid__sum'] or Decimal('0.00')
    
    revenue_growth = 0.0
    if revenue_last_month > 0:
        revenue_growth = round(((revenue_this_month - revenue_last_month) / revenue_last_month) * 100, 1)
    elif revenue_this_month > 0 and revenue_last_month == 0:
        revenue_growth = 100.0  # New revenue
    
    # Generate monthly trends data for chart
    monthly_patients = []
    monthly_encounters = []
    month_labels = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    
    current_month = today.month
    current_year = today.year
    
    for month_num in range(1, 13):
        if month_num == current_month:
            # Current month - use actual data from start of month to today
            month_start = today.replace(day=1)
            month_patients = Patient.objects.filter(
                created__date__gte=month_start,
                created__date__lte=today,
                is_deleted=False
            ).count()
            
            month_encounters = Encounter.objects.filter(
                started_at__date__gte=month_start,
                started_at__date__lte=today,
                is_deleted=False
            ).count()
            
            monthly_patients.append(month_patients)
            monthly_encounters.append(month_encounters)
        elif month_num < current_month:
            # Past months in current year - get actual data
            month_start = today.replace(month=month_num, day=1)
            if month_num == 12:
                month_end = today.replace(year=current_year + 1, month=1, day=1) - timedelta(days=1)
            else:
                month_end = today.replace(month=month_num + 1, day=1) - timedelta(days=1)
            
            month_patients = Patient.objects.filter(
                created__date__gte=month_start,
                created__date__lte=month_end,
                is_deleted=False
            ).count()
            
            month_encounters = Encounter.objects.filter(
                started_at__date__gte=month_start,
                started_at__date__lte=month_end,
                is_deleted=False
            ).count()
            
            monthly_patients.append(month_patients)
            monthly_encounters.append(month_encounters)
        else:
            # Future months - zero
            monthly_patients.append(0)
            monthly_encounters.append(0)
    
    return {
        # Flattened for template access
        'total_patients': total_patients,
        'patients_today': new_patients_today,
        'total_encounters': total_encounters,
        'active_encounters': active_encounters,
        'encounters_today': encounters_today,
        'total_admissions': total_admissions,
        'current_admissions': current_admissions,
        'total_revenue': total_revenue,
        'revenue_today': revenue_today,
        'total_revenue_this_month': total_revenue,  # Simplified
        'outstanding_balance': outstanding_balance,
        'total_invoices': invoices_total,
        'invoices_paid': invoices_paid,
        'total_beds': total_beds,
        'occupied_beds': occupied_beds,
        'available_beds': available_beds,
        'bed_occupancy_rate': bed_occupancy_rate,
        'appointments_today': appointments_today,
        'upcoming_appointments': upcoming_appointments,
        'patients_this_month': patients_this_month,
        'urgent_orders': urgent_orders,
        'revenue_growth': revenue_growth,
        'monthly_patients': monthly_patients,
        'monthly_encounters': monthly_encounters,
        'month_labels': month_labels,
        # Keep nested structure for backwards compatibility
        'patients': {
            'total': total_patients,
            'new_today': new_patients_today,
        },
        'encounters': {
            'total': total_encounters,
            'active': active_encounters,
            'today': encounters_today,
        },
        'admissions': {
            'total': total_admissions,
            'current': current_admissions,
        },
        'financial': {
            'total_revenue': total_revenue,
            'revenue_today': revenue_today,
            'outstanding_balance': outstanding_balance,
            'invoices_total': invoices_total,
            'invoices_paid': invoices_paid,
        },
        'beds': {
            'total': total_beds,
            'occupied': occupied_beds,
            'available': available_beds,
            'occupancy_rate': bed_occupancy_rate,
        },
        'appointments': {
            'today': appointments_today,
            'upcoming': upcoming_appointments,
        },
        'total_revenue_this_month': float(revenue_this_month) if revenue_this_month else 0.0,  # Fixed: use actual this month revenue
        'revenue_today': revenue_today,  # Add today's revenue
        'month_labels': month_labels,  # Add month labels for chart
    }


def get_patient_demographics():
    """Get patient demographics statistics"""
    patients = Patient.objects.filter(is_deleted=False).only('gender', 'date_of_birth')
    
    gender_counts = patients.values('gender').annotate(count=Count('id'))
    gender_data = {item['gender']: item['count'] for item in gender_counts}
    
    # Age groups - optimized calculation
    from datetime import date
    today = date.today()
    age_groups = {
        '0-18': 0,
        '19-35': 0,
        '36-50': 0,
        '51-65': 0,
        '65+': 0,
    }
    
    # Use database-level filtering instead of Python iteration
    for patient in patients.values('date_of_birth'):
        if not patient['date_of_birth']:
            continue
        try:
            age = (today - patient['date_of_birth']).days // 365
            if age <= 18:
                age_groups['0-18'] += 1
            elif age <= 35:
                age_groups['19-35'] += 1
            elif age <= 50:
                age_groups['36-50'] += 1
            elif age <= 65:
                age_groups['51-65'] += 1
            else:
                age_groups['65+'] += 1
        except (ValueError, TypeError):
            continue
    
    return {
        'gender': gender_data,
        'age_groups': age_groups,
        'total': patients.count(),
    }


def get_encounter_statistics():
    """Get encounter type statistics"""
    encounters = Encounter.objects.filter(is_deleted=False)
    
    type_counts = encounters.values('encounter_type').annotate(count=Count('id'))
    type_data = {item['encounter_type']: item['count'] for item in type_counts}
    
    status_counts = encounters.values('status').annotate(count=Count('id'))
    status_data = {item['status']: item['count'] for item in status_counts}
    
    return {
        'by_type': type_data,
        'by_status': status_data,
        'total': encounters.count(),
    }


def search_patients(query):
    """Search patients by name, MRN, phone, or email"""
    return Patient.objects.filter(
        Q(first_name__icontains=query) |
        Q(last_name__icontains=query) |
        Q(mrn__icontains=query) |
        Q(phone_number__icontains=query) |
        Q(email__icontains=query),
        is_deleted=False
    )[:50]  # Limit to 50 results


def generate_daily_report(report_date=None):
    """Generate daily activity report"""
    if not report_date:
        report_date = timezone.now().date()
    
    start_datetime = timezone.make_aware(
        timezone.datetime.combine(report_date, timezone.datetime.min.time())
    )
    end_datetime = timezone.make_aware(
        timezone.datetime.combine(report_date, timezone.datetime.max.time())
    )
    
    # New patients
    new_patients = Patient.objects.filter(
        created__gte=start_datetime,
        created__lte=end_datetime,
        is_deleted=False
    ).count()
    
    # New encounters
    new_encounters = Encounter.objects.filter(
        started_at__gte=start_datetime,
        started_at__lte=end_datetime,
        is_deleted=False
    ).count()
    
    # New admissions
    new_admissions = Admission.objects.filter(
        admit_date__gte=start_datetime,
        admit_date__lte=end_datetime,
        is_deleted=False
    ).count()
    
    # Discharges
    discharges = Admission.objects.filter(
        discharge_date__gte=start_datetime,
        discharge_date__lte=end_datetime,
        status='discharged',
        is_deleted=False
    ).count()
    
    # Revenue
    revenue = Invoice.objects.filter(
        issued_at__gte=start_datetime,
        issued_at__lte=end_datetime,
        status='paid',
        is_deleted=False
    ).aggregate(Sum('total_amount'))['total_amount__sum'] or Decimal('0.00')
    
    # Appointments
    appointments = Appointment.objects.filter(
        appointment_date__gte=start_datetime,
        appointment_date__lte=end_datetime,
        is_deleted=False
    ).count()
    
    # Lab tests ordered
    lab_orders = Order.objects.filter(
        created__gte=start_datetime,
        created__lte=end_datetime,
        order_type='lab',
        is_deleted=False
    ).count()
    
    return {
        'date': report_date,
        'new_patients': new_patients,
        'new_encounters': new_encounters,
        'new_admissions': new_admissions,
        'discharges': discharges,
        'revenue': revenue,
        'appointments': appointments,
        'lab_orders': lab_orders,
    }
