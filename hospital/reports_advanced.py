"""
Advanced reporting and KPI generation for Hospital Management System
"""
from django.db.models import Count, Avg, F, ExpressionWrapper, fields, Sum, Q, Max, Min
from django.utils import timezone
from decimal import Decimal
from datetime import timedelta, date
from collections import defaultdict
from .models import (
    Patient, Encounter, Admission, LabResult, Invoice, InvoiceLine,
    Order, Appointment, Staff
)
from .models_advanced import (
    ClinicalNote, ProblemList, CarePlan, Queue, Triage,
    TheatreSchedule, MedicationAdministrationRecord,
    SampleCollection, ClaimsBatch, ConsumablesInventory,
    MedicalEquipment
)


def get_clinical_kpis(start_date=None, end_date=None):
    """Generates key clinical performance indicators."""
    if not start_date:
        start_date = timezone.now().date() - timedelta(days=30)
    if not end_date:
        end_date = timezone.now().date()
    
    # Length of Stay (LOS)
    admissions_completed = Admission.objects.filter(
        discharge_date__gte=start_date,
        discharge_date__lte=end_date,
        status='discharged'
    )
    
    avg_los = 0
    if admissions_completed.exists():
        total_days = sum([
            (admission.discharge_date - admission.admit_date).days
            for admission in admissions_completed
            if admission.discharge_date and admission.admit_date
        ])
        avg_los = round(total_days / admissions_completed.count(), 1) if admissions_completed.count() > 0 else 0
    
    # Readmission Rate (simple: admitted again within 30 days of discharge)
    readmissions = 0
    readmission_rate = 0.0
    if admissions_completed.exists():
        for admission in admissions_completed:
            if admission.discharge_date and admission.encounter and admission.encounter.patient:
                readmission_window = admission.discharge_date + timedelta(days=30)
                readmissions += Admission.objects.filter(
                    encounter__patient=admission.encounter.patient,
                    admit_date__gt=admission.discharge_date,
                    admit_date__lte=readmission_window,
                    is_deleted=False
                ).exclude(pk=admission.pk).count()
        
        total_discharges = admissions_completed.count()
        readmission_rate = round((readmissions / total_discharges * 100), 2) if total_discharges > 0 else 0
    
    # Mortality Rate
    # Note: Patient model doesn't currently have date_of_death field
    # This functionality will be available once the field is added to the model
    mortality_count = 0
    
    total_admissions = Admission.objects.filter(
        admit_date__gte=start_date,
        admit_date__lte=end_date
    ).count()
    
    mortality_rate = 0.0  # Set to 0 until date_of_death field is added to Patient model
    
    return {
        'average_los': avg_los,
        'readmission_rate': readmission_rate,
        'readmissions': readmissions,
        'total_discharges': admissions_completed.count(),
        'mortality_count': mortality_count,
        'mortality_rate': mortality_rate,
        'total_clinical_notes': ClinicalNote.objects.filter(
            created__date__gte=start_date,
            created__date__lte=end_date
        ).count(),
        'active_care_plans': CarePlan.objects.filter(status='active', is_deleted=False).count(),
        'total_problem_list_entries': ProblemList.objects.filter(is_deleted=False).count(),
    }


def get_operational_kpis(start_date=None, end_date=None):
    """Generates operational performance indicators."""
    if not start_date:
        start_date = timezone.now().date() - timedelta(days=30)
    if not end_date:
        end_date = timezone.now().date()
    
    # Bed Occupancy
    from .models import Bed
    total_beds = Bed.objects.filter(is_deleted=False).count()
    occupied_beds = Bed.objects.filter(status='occupied', is_deleted=False).count()
    bed_occupancy_rate = round((occupied_beds / total_beds * 100), 1) if total_beds > 0 else 0
    
    # OT Utilization (simplified - based on scheduled hours)
    theatre_schedules = TheatreSchedule.objects.filter(
        scheduled_start__date__gte=start_date,
        scheduled_start__date__lte=end_date,
        is_deleted=False
    )
    
    total_ot_hours = 0
    for schedule in theatre_schedules:
        if schedule.scheduled_end and schedule.scheduled_start:
            duration = schedule.scheduled_end - schedule.scheduled_start
            total_ot_hours += duration.total_seconds() / 3600
    
    # Assume 8 hours per day, 30 days = 240 hours per theatre
    # This is simplified - adjust based on actual theatre count
    theatre_count = 2  # Placeholder
    available_hours = theatre_count * 240
    ot_utilization = round((total_ot_hours / available_hours * 100), 1) if available_hours > 0 else 0
    
    # No-Show Rate for Appointments
    appointments_total = Appointment.objects.filter(
        appointment_date__date__gte=start_date,
        appointment_date__date__lte=end_date
    ).count()
    
    appointments_no_show = Appointment.objects.filter(
        appointment_date__date__gte=start_date,
        appointment_date__date__lte=end_date,
        status='no_show'
    ).count()
    
    no_show_rate = round((appointments_no_show / appointments_total * 100), 1) if appointments_total > 0 else 0
    
    # Average Wait Time (using Queue model)
    queues_completed = Queue.objects.filter(
        called_at__isnull=False,
        checked_in_at__isnull=False,
        called_at__date__gte=start_date,
        called_at__date__lte=end_date
    )
    
    avg_wait_minutes = 0
    if queues_completed.exists():
        wait_times = []
        for queue in queues_completed:
            if queue.called_at and queue.checked_in_at:
                wait = (queue.called_at - queue.checked_in_at).total_seconds() / 60
                wait_times.append(wait)
        
        if wait_times:
            avg_wait_minutes = round(sum(wait_times) / len(wait_times), 1)
    
    return {
        'bed_occupancy_rate': bed_occupancy_rate,
        'total_beds': total_beds,
        'occupied_beds': occupied_beds,
        'available_beds': total_beds - occupied_beds,
        'ot_utilization': ot_utilization,
        'total_ot_hours': total_ot_hours,
        'no_show_rate': no_show_rate,
        'appointments_total': appointments_total,
        'appointments_no_show': appointments_no_show,
        'average_wait_time_minutes': avg_wait_minutes,
    }


def get_financial_kpis(start_date=None, end_date=None):
    """Generates financial performance indicators based on actual payments and accounting."""
    from .models_accounting import Transaction, PaymentReceipt, GeneralLedger
    from .models import Payer
    
    if not start_date:
        start_date = timezone.now().date() - timedelta(days=30)
    if not end_date:
        end_date = timezone.now().date()
    
    # Convert dates to datetime for filtering
    start_datetime = timezone.make_aware(timezone.datetime.combine(start_date, timezone.datetime.min.time()))
    end_datetime = timezone.make_aware(timezone.datetime.combine(end_date, timezone.datetime.max.time()))
    
    # Total Revenue - Use actual payment transactions
    revenue_transactions = Transaction.objects.filter(
        transaction_date__gte=start_datetime,
        transaction_date__lte=end_datetime,
        transaction_type='payment_received',
        is_deleted=False
    )
    total_revenue = revenue_transactions.aggregate(Sum('amount'))['amount__sum'] or Decimal('0')
    
    # Alternative: Get revenue from PaymentReceipts for verification
    try:
        payment_receipts_for_revenue = PaymentReceipt.objects.filter(
            receipt_date__gte=start_datetime,
            receipt_date__lte=end_datetime,
            is_deleted=False
        )
        receipt_revenue = payment_receipts_for_revenue.aggregate(Sum('amount_paid'))['amount_paid__sum'] or Decimal('0')
        
        # Use receipt revenue if it's higher (more accurate)
        if receipt_revenue > total_revenue:
            total_revenue = receipt_revenue
    except:
        pass  # If receipts not available, use transaction-based revenue
    
    # Total AR (accounts receivable from unpaid invoices)
    invoices_unpaid = Invoice.objects.filter(
        status__in=['issued', 'overdue'],
        balance__gt=0,
        is_deleted=False
    )
    total_ar = invoices_unpaid.aggregate(Sum('balance'))['balance__sum'] or Decimal('0')
    
    # AR Aging
    today = timezone.now().date()
    ar_aging = {
        '0-30': Decimal('0'),
        '31-60': Decimal('0'),
        '61-90': Decimal('0'),
        '90+': Decimal('0'),
    }
    
    for invoice in invoices_unpaid:
        # If no due date, treat as current (0-30)
        if not invoice.due_at:
            ar_aging['0-30'] += invoice.balance
            continue
            
        # Get due date and calculate days overdue
        try:
            due_date = invoice.due_at.date() if hasattr(invoice.due_at, 'date') else invoice.due_at
        except:
            # If any error getting date, treat as current
            ar_aging['0-30'] += invoice.balance
            continue
            
        days_overdue = (today - due_date).days
        
        # Current: Not yet due OR up to 30 days overdue
        if days_overdue <= 30:
            ar_aging['0-30'] += invoice.balance
        # 31-60 days overdue
        elif days_overdue <= 60:
            ar_aging['31-60'] += invoice.balance
        # 61-90 days overdue
        elif days_overdue <= 90:
            ar_aging['61-90'] += invoice.balance
        # Over 90 days overdue
        else:
            ar_aging['90+'] += invoice.balance
    
    # Payer Mix - Based on actual payments
    payer_mix = {}
    
    # Get payment receipts in date range
    payment_receipts = PaymentReceipt.objects.filter(
        receipt_date__gte=start_datetime,
        receipt_date__lte=end_datetime,
        is_deleted=False
    ).select_related('transaction', 'patient', 'invoice')
    
    total_payment_amount = payment_receipts.aggregate(Sum('amount_paid'))['amount_paid__sum'] or Decimal('1')
    
    for receipt in payment_receipts:
        # Try to get payer from patient or invoice
        payer_name = 'Cash/Self Pay'
        
        if receipt.patient and receipt.patient.primary_insurance:
            payer_name = receipt.patient.primary_insurance.name
        elif receipt.invoice and receipt.invoice.payer:
            payer_name = receipt.invoice.payer.name
        
        if payer_name not in payer_mix:
            payer_mix[payer_name] = {
                'amount': Decimal('0'),
                'count': 0
            }
        payer_mix[payer_name]['amount'] += receipt.amount_paid
        payer_mix[payer_name]['count'] += 1
    
    # Calculate percentages
    for payer, data in payer_mix.items():
        data['percentage'] = round((data['amount'] / total_payment_amount * 100), 1) if total_payment_amount > 0 else 0
    
    # Count statistics
    invoices_all = Invoice.objects.filter(
        issued_at__gte=start_datetime,
        issued_at__lte=end_datetime,
        is_deleted=False
    )
    invoices_paid = Invoice.objects.filter(
        status='paid',
        issued_at__gte=start_datetime,
        issued_at__lte=end_datetime,
        is_deleted=False
    )
    
    return {
        'total_revenue': total_revenue,
        'total_ar': total_ar,
        'ar_aging': ar_aging,
        'payer_mix': payer_mix,
        'total_invoices': invoices_all.count(),
        'paid_invoices': invoices_paid.count(),
        'unpaid_invoices': invoices_unpaid.count(),
        'total_payments': revenue_transactions.count(),
        'total_payment_receipts': payment_receipts.count(),
    }


def get_lab_tat_report(start_date=None, end_date=None):
    """Lab turnaround time report."""
    if not start_date:
        start_date = timezone.now().date() - timedelta(days=30)
    if not end_date:
        end_date = timezone.now().date()
    
    lab_results = LabResult.objects.filter(
        verified_at__gte=timezone.make_aware(timezone.datetime.combine(start_date, timezone.datetime.min.time())),
        verified_at__lte=timezone.make_aware(timezone.datetime.combine(end_date, timezone.datetime.max.time())),
        status='verified'
    ).select_related('test', 'order')
    
    tat_by_test = defaultdict(lambda: {'total_hours': 0, 'count': 0})
    
    for result in lab_results:
        if result.order and result.order.created and result.verified_at:
            tat_hours = (result.verified_at - result.order.created).total_seconds() / 3600
            test_name = result.test.name if result.test else 'Unknown'
            tat_by_test[test_name]['total_hours'] += tat_hours
            tat_by_test[test_name]['count'] += 1
    
    # Calculate averages
    lab_tat = {}
    for test_name, data in tat_by_test.items():
        lab_tat[test_name] = {
            'average_tat_hours': round(data['total_hours'] / data['count'], 2) if data['count'] > 0 else 0,
            'count': data['count']
        }
    
    return lab_tat


def get_theatre_utilization_report(start_date=None, end_date=None):
    """Theatre utilization report."""
    if not start_date:
        start_date = timezone.now().date() - timedelta(days=30)
    if not end_date:
        end_date = timezone.now().date()
    
    schedules = TheatreSchedule.objects.filter(
        scheduled_start__date__gte=start_date,
        scheduled_start__date__lte=end_date,
        is_deleted=False
    )
    
    by_theatre = defaultdict(lambda: {'hours': 0, 'procedures': 0})
    
    for schedule in schedules:
        theatre = schedule.theatre_name
        if schedule.scheduled_end and schedule.scheduled_start:
            duration_hours = (schedule.scheduled_end - schedule.scheduled_start).total_seconds() / 3600
            by_theatre[theatre]['hours'] += duration_hours
            by_theatre[theatre]['procedures'] += 1
    
    return dict(by_theatre)


def get_comprehensive_report(start_date=None, end_date=None):
    """Generate a comprehensive report with all KPIs."""
    return {
        'clinical': get_clinical_kpis(start_date, end_date),
        'operational': get_operational_kpis(start_date, end_date),
        'financial': get_financial_kpis(start_date, end_date),
        'lab_tat': get_lab_tat_report(start_date, end_date),
        'theatre_utilization': get_theatre_utilization_report(start_date, end_date),
        'period': {
            'start_date': start_date.isoformat() if start_date else None,
            'end_date': end_date.isoformat() if end_date else None,
        }
    }
