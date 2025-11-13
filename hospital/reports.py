"""
Advanced reporting functionality for Hospital Management System.
"""
from django.db.models import Count, Sum, Avg, Q
from django.utils import timezone
from datetime import timedelta, datetime, date
from decimal import Decimal
from .models import (
    Patient, Encounter, Admission, Invoice, Order,
    Department, Staff, Ward, Bed
)


class ReportGenerator:
    """Base class for report generation"""
    
    @staticmethod
    def get_date_range(period='month'):
        """Get date range based on period"""
        today = timezone.now().date()
        
        if period == 'today':
            return today, today
        elif period == 'week':
            return today - timedelta(days=7), today
        elif period == 'month':
            return today.replace(day=1), today
        elif period == 'year':
            return today.replace(month=1, day=1), today
        elif period == 'quarter':
            quarter = (today.month - 1) // 3
            return today.replace(month=quarter*3+1, day=1), today
        else:
            return None, None


def generate_financial_report(period='month'):
    """Generate comprehensive financial report"""
    date_from, date_to = ReportGenerator.get_date_range(period)
    
    invoices = Invoice.objects.filter(
        is_deleted=False,
        issued_at__date__gte=date_from,
        issued_at__date__lte=date_to
    )
    
    total_invoiced = invoices.aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
    total_collected = invoices.filter(status='paid').aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
    outstanding = invoices.filter(status__in=['issued', 'partially_paid']).aggregate(total=Sum('balance'))['total'] or Decimal('0.00')
    
    by_status = invoices.values('status').annotate(
        count=Count('id'),
        total=Sum('total_amount')
    )
    
    by_payer = invoices.values('payer__name').annotate(
        count=Count('id'),
        total=Sum('total_amount')
    ).order_by('-total')
    
    return {
        'period': period,
        'date_from': date_from,
        'date_to': date_to,
        'total_invoiced': total_invoiced,
        'total_collected': total_collected,
        'outstanding': outstanding,
        'collection_rate': (total_collected / total_invoiced * 100) if total_invoiced > 0 else 0,
        'by_status': list(by_status),
        'by_payer': list(by_payer),
        'invoice_count': invoices.count(),
    }


def generate_patient_statistics_report(period='month'):
    """Generate patient statistics report"""
    date_from, date_to = ReportGenerator.get_date_range(period)
    
    new_patients = Patient.objects.filter(
        is_deleted=False,
        created__date__gte=date_from,
        created__date__lte=date_to
    )
    
    demographics = {
        'by_gender': dict(new_patients.values('gender').annotate(count=Count('id')).values_list('gender', 'count')),
        'by_age_group': {
            'pediatric': new_patients.filter(date_of_birth__gte=timezone.now().date() - timedelta(days=18*365)).count(),
            'adult': new_patients.filter(
                date_of_birth__gte=timezone.now().date() - timedelta(days=65*365),
                date_of_birth__lt=timezone.now().date() - timedelta(days=18*365)
            ).count(),
            'senior': new_patients.filter(date_of_birth__lt=timezone.now().date() - timedelta(days=65*365)).count(),
        },
        'by_blood_type': dict(new_patients.values('blood_type').annotate(count=Count('id')).filter(blood_type__isnull=False).values_list('blood_type', 'count')),
    }
    
    return {
        'period': period,
        'date_from': date_from,
        'date_to': date_to,
        'total_new_patients': new_patients.count(),
        'demographics': demographics,
    }


def generate_encounter_report(period='month'):
    """Generate encounter statistics report"""
    date_from, date_to = ReportGenerator.get_date_range(period)
    
    encounters = Encounter.objects.filter(
        is_deleted=False,
        started_at__date__gte=date_from,
        started_at__date__lte=date_to
    )
    
    by_type = encounters.values('encounter_type').annotate(
        count=Count('id')
    )
    
    by_status = encounters.values('status').annotate(
        count=Count('id')
    )
    
    completed_encounters = encounters.filter(status='completed', ended_at__isnull=False)
    avg_duration = None
    if completed_encounters.exists():
        # Calculate average duration
        durations = []
        for enc in completed_encounters:
            dur = enc.get_duration_minutes()
            if dur:
                durations.append(dur)
        if durations:
            avg_duration = sum(durations) / len(durations)
    
    return {
        'period': period,
        'date_from': date_from,
        'date_to': date_to,
        'total_encounters': encounters.count(),
        'by_type': list(by_type),
        'by_status': list(by_status),
        'average_duration_minutes': avg_duration,
        'completed_count': completed_encounters.count(),
    }


def generate_admission_report(period='month'):
    """Generate admission statistics report"""
    date_from, date_to = ReportGenerator.get_date_range(period)
    
    admissions = Admission.objects.filter(
        is_deleted=False,
        admit_date__date__gte=date_from,
        admit_date__date__lte=date_to
    )
    
    discharges = admissions.filter(
        status='discharged',
        discharge_date__isnull=False
    )
    
    by_ward = admissions.values('ward__name').annotate(
        count=Count('id')
    ).order_by('-count')
    
    avg_length_of_stay = None
    if discharges.exists():
        durations = [a.get_duration_days() for a in discharges]
        if durations:
            avg_length_of_stay = sum(durations) / len(durations)
    
    current_admissions = Admission.objects.filter(
        status='admitted',
        is_deleted=False
    )
    
    return {
        'period': period,
        'date_from': date_from,
        'date_to': date_to,
        'total_admissions': admissions.count(),
        'total_discharges': discharges.count(),
        'current_admissions': current_admissions.count(),
        'by_ward': list(by_ward),
        'average_length_of_stay_days': avg_length_of_stay,
    }


def generate_department_performance_report(period='month'):
    """Generate department performance report"""
    date_from, date_to = ReportGenerator.get_date_range(period)
    
    departments = Department.objects.filter(is_active=True, is_deleted=False)
    
    performance = []
    for dept in departments:
        encounters = Encounter.objects.filter(
            provider__department=dept,
            is_deleted=False,
            started_at__date__gte=date_from,
            started_at__date__lte=date_to
        )
        
        performance.append({
            'department': dept.name,
            'encounters': encounters.count(),
            'staff_count': dept.staff.filter(is_active=True, is_deleted=False).count(),
            'wards_count': dept.wards.filter(is_active=True, is_deleted=False).count(),
        })
    
    return {
        'period': period,
        'date_from': date_from,
        'date_to': date_to,
        'departments': performance,
    }


def generate_bed_utilization_report():
    """Generate bed utilization report"""
    wards = Ward.objects.filter(is_active=True, is_deleted=False)
    
    utilization = []
    for ward in wards:
        beds = ward.beds.filter(is_active=True, is_deleted=False)
        total_beds = beds.count()
        occupied = beds.filter(status='occupied').count()
        available = beds.filter(status='available').count()
        maintenance = beds.filter(status='maintenance').count()
        
        utilization_rate = (occupied / total_beds * 100) if total_beds > 0 else 0
        
        utilization.append({
            'ward': ward.name,
            'ward_type': ward.get_ward_type_display(),
            'total_beds': total_beds,
            'occupied': occupied,
            'available': available,
            'maintenance': maintenance,
            'utilization_rate': round(utilization_rate, 2),
        })
    
    return {
        'wards': utilization,
        'generated_at': timezone.now(),
    }

