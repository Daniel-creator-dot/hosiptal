"""
Utility functions for Hospital Management System
"""
from django.db.models import Count, Sum, Avg, Q, F
from django.db.models.expressions import RawSQL
from django.utils import timezone
from django.core.cache import cache
from datetime import timedelta, date
from decimal import Decimal
from .models import (
    Patient, Encounter, Admission, Invoice, InvoiceLine,
    Order, Appointment, LabResult, PharmacyStock, Bed, Ward
)


def get_dashboard_stats():
    """Get dashboard statistics - AGGRESSIVELY CACHED for 300+ users"""
    today = timezone.now().date()
    cache_key = f'hms:dashboard_stats_{today}'
    
    # Try to get from cache first (15 minute cache for high concurrency)
    cached_stats = cache.get(cache_key)
    if cached_stats is not None:
        return cached_stats
    
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
    
    # Generate monthly trends data for chart - OPTIMIZED with single queries
    monthly_patients = []
    monthly_encounters = []
    month_labels = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    
    current_month = today.month
    current_year = today.year
    
    # OPTIMIZATION: Get all monthly data in fewer queries using date extraction
    # Get all patients for current year grouped by month
    from django.db.models.functions import ExtractMonth
    patients_by_month = dict(
        Patient.objects.filter(
            created__year=current_year,
            is_deleted=False
        ).annotate(
            month=ExtractMonth('created')
        ).values('month').annotate(count=Count('id')).values_list('month', 'count')
    )
    
    encounters_by_month = dict(
        Encounter.objects.filter(
            started_at__year=current_year,
            is_deleted=False
        ).annotate(
            month=ExtractMonth('started_at')
        ).values('month').annotate(count=Count('id')).values_list('month', 'count')
    )
    
    # Build monthly arrays (use existing monthly dicts; no extra queries for current month)
    for month_num in range(1, 13):
        if month_num <= current_month:
            monthly_patients.append(patients_by_month.get(month_num, 0))
            monthly_encounters.append(encounters_by_month.get(month_num, 0))
        else:
            monthly_patients.append(0)
            monthly_encounters.append(0)
    
    stats = {
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
    
    # Cache for 15 minutes (900 seconds) for high concurrency - reduces DB load significantly
    cache.set(cache_key, stats, 900)
    return stats


def get_patient_demographics():
    """Get patient demographics statistics - CACHED for performance.
    Age bucketing is done in the database (no Python loop over all patients).
    """
    cache_key = 'patient_demographics'
    cached_demographics = cache.get(cache_key)
    if cached_demographics is not None:
        return cached_demographics

    base = Patient.objects.filter(is_deleted=False)

    # Gender: single aggregated query
    gender_counts = base.values('gender').annotate(count=Count('id'))
    gender_data = {item['gender']: item['count'] for item in gender_counts}

    # Age groups: database-level age and bucketing (PostgreSQL AGE + conditional Count)
    # Exclude null DOB so we don't compute age for them (matches previous behavior)
    patients_with_dob = base.exclude(date_of_birth__isnull=True)
    table = Patient._meta.db_table
    age_sql = f"EXTRACT(YEAR FROM AGE(CURRENT_DATE, {table}.date_of_birth))::integer"
    age_agg = patients_with_dob.annotate(
        age=RawSQL(age_sql, [])
    ).aggregate(
        g_0_18=Count('id', filter=Q(age__lte=18)),
        g_19_35=Count('id', filter=Q(age__gte=19, age__lte=35)),
        g_36_50=Count('id', filter=Q(age__gte=36, age__lte=50)),
        g_51_65=Count('id', filter=Q(age__gte=51, age__lte=65)),
        g_65_plus=Count('id', filter=Q(age__gt=65)),
    )
    age_groups = {
        '0-18': age_agg['g_0_18'],
        '19-35': age_agg['g_19_35'],
        '36-50': age_agg['g_36_50'],
        '51-65': age_agg['g_51_65'],
        '65+': age_agg['g_65_plus'],
    }

    demographics = {
        'gender': gender_data,
        'age_groups': age_groups,
        'total': base.count(),
    }

    # Cache for 30 minutes - demographics change slowly
    cache.set(cache_key, demographics, 1800)
    return demographics


def get_encounter_statistics():
    """Get encounter type statistics - CACHED for performance. Two queries only."""
    cache_key = 'encounter_statistics'
    cached_stats = cache.get(cache_key)
    if cached_stats is not None:
        return cached_stats

    base = Encounter.objects.filter(is_deleted=False)
    type_counts = base.values('encounter_type').annotate(count=Count('id'))
    type_data = {item['encounter_type']: item['count'] for item in type_counts}
    status_counts = base.values('status').annotate(count=Count('id'))
    status_data = {item['status']: item['count'] for item in status_counts}
    total = sum(type_data.values())  # avoid third query (encounters.count())

    stats = {
        'by_type': type_data,
        'by_status': status_data,
        'total': total,
    }
    cache.set(cache_key, stats, 300)
    return stats


def get_dashboard_extra_stats(today_date):
    """Cached dashboard extra stats (financial, department, alerts counts).
    Keyed by date, TTL 5 min, to cut per-request queries on the main dashboard.
    """
    cache_key = f'hms:dashboard_extra_{today_date}'
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    from .models import Prescription, Staff
    from .models_accounting import PaymentReceipt

    month_start = today_date.replace(day=1)
    today_payments = PaymentReceipt.objects.filter(
        receipt_date__date=today_date,
        is_deleted=False
    )
    today_revenue = today_payments.aggregate(Sum('amount_paid'))['amount_paid__sum'] or Decimal('0')
    today_payment_count = today_payments.count()
    month_payments = PaymentReceipt.objects.filter(
        receipt_date__date__gte=month_start,
        receipt_date__date__lte=today_date,
        is_deleted=False
    )
    month_revenue = month_payments.aggregate(Sum('amount_paid'))['amount_paid__sum'] or Decimal('0')

    prescriptions_today = Prescription.objects.filter(
        created__date=today_date,
        is_deleted=False
    ).count()
    active_orders = Order.objects.filter(
        status__in=['pending', 'in_progress'],
        is_deleted=False
    ).count()
    discharges_today = Admission.objects.filter(
        discharge_date__date=today_date,
        status='discharged',
        is_deleted=False
    ).count()
    staff_on_duty = Staff.objects.filter(
        is_active=True,
        is_deleted=False
    ).count()

    pending_bills_count = 0
    try:
        from .models_advanced import ImagingStudy
        pending_lab = LabResult.objects.filter(status='completed', is_deleted=False).count()
        pending_pharmacy = Prescription.objects.filter(is_deleted=False).count()
        pending_imaging = ImagingStudy.objects.filter(status='completed', is_deleted=False).count()
        pending_bills_count = pending_lab + pending_pharmacy + pending_imaging
    except Exception:
        pass

    lab_pending = LabResult.objects.filter(
        status__in=['pending', 'in_progress'],
        is_deleted=False
    ).count()
    lab_completed_today = LabResult.objects.filter(
        status='completed',
        created__date=today_date,
        is_deleted=False
    ).count()

    pharmacy_pending = Prescription.objects.filter(is_deleted=False).count()
    pharmacy_dispensed_today = 0
    try:
        from .models_advanced import PharmacyDispensing
        pharmacy_pending = Prescription.objects.filter(is_deleted=False).exclude(
            id__in=PharmacyDispensing.objects.values_list('prescription_id', flat=True)
        ).count()
        pharmacy_dispensed_today = PharmacyDispensing.objects.filter(
            dispensed_at__date=today_date,
            is_deleted=False
        ).count()
    except Exception:
        pass

    imaging_pending = 0
    imaging_completed_today = 0
    try:
        from .models_advanced import ImagingStudy
        imaging_pending = ImagingStudy.objects.filter(
            status__in=['pending', 'in_progress'],
            is_deleted=False
        ).count()
        imaging_completed_today = ImagingStudy.objects.filter(
            status='completed',
            created_at__date=today_date,
            is_deleted=False
        ).count()
    except Exception:
        pass

    expiring_contracts = 0
    expiring_certs = 0
    try:
        from .models_contracts import Contract, Certificate
        expiring_contracts = Contract.objects.filter(
            end_date__gte=today_date,
            end_date__lte=today_date + timedelta(days=30),
            is_deleted=False
        ).count()
        expiring_certs = Certificate.objects.filter(
            expiry_date__gte=today_date,
            expiry_date__lte=today_date + timedelta(days=60),
            is_deleted=False
        ).count()
    except Exception:
        pass

    result = {
        'today_revenue': today_revenue,
        'today_payment_count': today_payment_count,
        'month_revenue': month_revenue,
        'prescriptions_today': prescriptions_today,
        'active_orders': active_orders,
        'discharges_today': discharges_today,
        'staff_on_duty': staff_on_duty,
        'pending_bills_count': pending_bills_count,
        'lab_pending': lab_pending,
        'lab_completed_today': lab_completed_today,
        'pharmacy_pending': pharmacy_pending,
        'pharmacy_dispensed_today': pharmacy_dispensed_today,
        'imaging_pending': imaging_pending,
        'imaging_completed_today': imaging_completed_today,
        'expiring_contracts': expiring_contracts,
        'expiring_certs': expiring_certs,
    }
    cache.set(cache_key, result, 300)  # 5 min
    return result


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
    """Generate daily activity report with real-time data"""
    from django.db.models import Q, Sum, Count
    from decimal import Decimal
    
    if not report_date:
        report_date = timezone.now().date()
    
    # Use date filtering instead of datetime for better performance and accuracy
    start_datetime = timezone.make_aware(
        timezone.datetime.combine(report_date, timezone.datetime.min.time())
    )
    end_datetime = timezone.make_aware(
        timezone.datetime.combine(report_date, timezone.datetime.max.time())
    )
    
    try:
        # New patients - use datetime range for compatibility
        new_patients = Patient.objects.filter(
            created__gte=start_datetime,
            created__lte=end_datetime,
            is_deleted=False
        ).count()
        
        # New encounters - use datetime range
        new_encounters = Encounter.objects.filter(
            started_at__gte=start_datetime,
            started_at__lte=end_datetime,
            is_deleted=False
        ).count()
        
        # Completed encounters (encounters that ended on this date)
        completed_encounters = Encounter.objects.filter(
            ended_at__gte=start_datetime,
            ended_at__lte=end_datetime,
            ended_at__isnull=False,
            status__in=['completed', 'discharged', 'closed'],
            is_deleted=False
        ).count()
        
        # New admissions
        new_admissions = 0
        try:
            from .models_advanced import Admission
            new_admissions = Admission.objects.filter(
                admit_date__gte=start_datetime.date() if hasattr(start_datetime, 'date') else report_date,
                admit_date__lte=end_datetime.date() if hasattr(end_datetime, 'date') else report_date,
                is_deleted=False
            ).count()
        except (ImportError, AttributeError, Exception) as e:
            # Admission model might not exist or field might be datetime
            try:
                from .models_advanced import Admission
                new_admissions = Admission.objects.filter(
                    admit_date__gte=start_datetime,
                    admit_date__lte=end_datetime,
                    is_deleted=False
                ).count()
            except:
                pass
        
        # Discharges
        discharges = 0
        try:
            from .models_advanced import Admission
            discharges = Admission.objects.filter(
                discharge_date__gte=start_datetime.date() if hasattr(start_datetime, 'date') else report_date,
                discharge_date__lte=end_datetime.date() if hasattr(end_datetime, 'date') else report_date,
                status='discharged',
                is_deleted=False
            ).count()
        except (ImportError, AttributeError, Exception):
            # Try datetime filtering
            try:
                from .models_advanced import Admission
                discharges = Admission.objects.filter(
                    discharge_date__gte=start_datetime,
                    discharge_date__lte=end_datetime,
                    status='discharged',
                    is_deleted=False
                ).count()
            except:
                pass
        
        # Invoices issued (not just paid) - use datetime range
        invoices_issued = 0
        try:
            invoices_issued = Invoice.objects.filter(
                issued_at__gte=start_datetime,
                issued_at__lte=end_datetime,
                is_deleted=False
            ).count()
        except (AttributeError, Exception):
            # Try alternative field names
            try:
                invoices_issued = Invoice.objects.filter(
                    created__gte=start_datetime,
                    created__lte=end_datetime,
                    is_deleted=False
                ).count()
            except:
                pass
        
        # Revenue (from payment receipts for real-time accuracy)
        revenue = Decimal('0.00')
        try:
            from .models_accounting import PaymentReceipt
            revenue_result = PaymentReceipt.objects.filter(
                receipt_date__gte=start_datetime,
                receipt_date__lte=end_datetime,
                is_deleted=False
            ).aggregate(Sum('amount_paid'))['amount_paid__sum']
            if revenue_result:
                revenue = revenue_result
        except (ImportError, AttributeError, Exception):
            # Fallback to Invoice if PaymentReceipt not available
            try:
                revenue_result = Invoice.objects.filter(
                    issued_at__gte=start_datetime,
                    issued_at__lte=end_datetime,
                    status='paid',
                    is_deleted=False
                ).aggregate(Sum('total_amount'))['total_amount__sum']
                if revenue_result:
                    revenue = revenue_result
            except:
                pass
        
        return {
            'date': report_date,
            'new_patients': new_patients,
            'new_encounters': new_encounters,
            'completed_encounters': completed_encounters,
            'admissions': new_admissions,  # Template expects 'admissions'
            'new_admissions': new_admissions,  # Keep for backward compatibility
            'discharges': discharges,
            'invoices_issued': invoices_issued,
            'revenue': revenue,
        }
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error generating daily report: {e}", exc_info=True)
        # Return safe defaults on error
        return {
            'date': report_date,
            'new_patients': 0,
            'new_encounters': 0,
            'completed_encounters': 0,
            'admissions': 0,
            'new_admissions': 0,
            'discharges': 0,
            'invoices_issued': 0,
            'revenue': Decimal('0.00'),
        }
