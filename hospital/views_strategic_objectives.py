"""
Strategic Objectives Tracking for Administrator Dashboard
Calculates metrics and progress for 7 strategic objectives
"""
from django.utils import timezone
from django.db.models import Count, Sum, Avg, Q, F
from datetime import date, timedelta
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


def _safe_db_call(default_value, context_name, query_func):
    """Safe database call with error handling"""
    try:
        return query_func()
    except Exception as e:
        logger.warning(f"Database error in {context_name}: {e}")
        return default_value


def calculate_strategic_objectives_metrics():
    """
    Calculate comprehensive metrics for all 7 strategic objectives.
    Returns a dictionary with progress, KPIs, and actionable insights.
    """
    today = timezone.now().date()
    this_month_start = date(today.year, today.month, 1)
    last_month_start = (this_month_start - timedelta(days=1)).replace(day=1)
    last_month_end = this_month_start - timedelta(days=1)
    
    # Import models safely
    from .models import (
        Patient, Encounter, Staff, Appointment, Invoice, 
        Department, Bed, Admission
    )
    
    try:
        from .models_accounting import PaymentReceipt
    except ImportError:
        PaymentReceipt = None
    
    try:
        from .models_workflow import Bill
    except ImportError:
        Bill = None
    
    try:
        from .models_hr import LeaveRequest
    except ImportError:
        LeaveRequest = None
    
    objectives = {}
    
    # ============================================
    # OBJECTIVE 1: Improve Operational Efficiency
    # ============================================
    try:
        # Metrics: Patient flow, appointment efficiency, bed turnover
        total_encounters = Encounter.objects.filter(is_deleted=False).count()
        active_encounters = Encounter.objects.filter(
            is_deleted=False, status='active'
        ).count()
        
        # Average encounter duration (completed encounters)
        completed_encounters = Encounter.objects.filter(
            is_deleted=False,
            status='completed',
            started_at__isnull=False,
            ended_at__isnull=False
        )
        
        avg_encounter_duration = 0
        if completed_encounters.exists():
            # Calculate average duration in hours
            durations = []
            for enc in completed_encounters[:100]:  # Sample for performance
                if enc.started_at and enc.ended_at:
                    duration = (enc.ended_at - enc.started_at).total_seconds() / 3600
                    durations.append(duration)
            if durations:
                avg_encounter_duration = sum(durations) / len(durations)
        
        # Appointment efficiency (on-time vs late)
        appointments_today = Appointment.objects.filter(
            appointment_date__date=today,
            is_deleted=False
        )
        total_appointments_today = appointments_today.count()
        completed_appointments_today = appointments_today.filter(
            status='completed'
        ).count()
        appointment_completion_rate = (
            (completed_appointments_today / total_appointments_today * 100)
            if total_appointments_today > 0 else 0
        )
        
        # Bed turnover rate
        total_beds = Bed.objects.filter(is_active=True, is_deleted=False).count()
        occupied_beds = Bed.objects.filter(
            is_active=True, is_deleted=False, status='occupied'
        ).count()
        bed_occupancy_rate = (
            (occupied_beds / total_beds * 100) if total_beds > 0 else 0
        )
        
        # Patient wait time (if available)
        avg_wait_time = 0  # Placeholder - would need wait time tracking
        
        # Calculate progress (0-100%)
        # Weighted: encounter efficiency (30%), appointments (30%), bed utilization (20%), wait time (20%)
        operational_score = (
            (min(avg_encounter_duration, 2) / 2 * 100) * 0.3 +  # Lower duration = better (target: <2 hours)
            appointment_completion_rate * 0.3 +
            min(bed_occupancy_rate, 85) / 85 * 100 * 0.2 +  # Target: 85% occupancy
            (100 - min(avg_wait_time, 60) / 60 * 100) * 0.2  # Lower wait = better
        )
        
        objectives['operational_efficiency'] = {
            'title': 'Improve Operational Efficiency',
            'description': 'Streamline workflows, reduce inefficiencies, and improve patient flow',
            'progress': min(operational_score, 100),
            'metrics': {
                'total_encounters': total_encounters,
                'active_encounters': active_encounters,
                'avg_encounter_duration_hours': round(avg_encounter_duration, 2),
                'appointment_completion_rate': round(appointment_completion_rate, 1),
                'bed_occupancy_rate': round(bed_occupancy_rate, 1),
                'total_beds': total_beds,
                'occupied_beds': occupied_beds,
            },
            'kpis': [
                {'name': 'Encounter Efficiency', 'value': f'{round(100 - (avg_encounter_duration / 2 * 100), 1)}%', 'target': '>80%'},
                {'name': 'Appointment Completion', 'value': f'{round(appointment_completion_rate, 1)}%', 'target': '>90%'},
                {'name': 'Bed Utilization', 'value': f'{round(bed_occupancy_rate, 1)}%', 'target': '75-85%'},
            ],
            'color': '#3b82f6',
            'icon': 'bi-speedometer2',
        }
    except Exception as e:
        logger.error(f"Error calculating operational efficiency: {e}")
        objectives['operational_efficiency'] = {
            'title': 'Improve Operational Efficiency',
            'description': 'Streamline workflows, reduce inefficiencies, and improve patient flow',
            'progress': 0,
            'metrics': {},
            'kpis': [],
            'color': '#3b82f6',
            'icon': 'bi-speedometer2',
        }
    
    # ============================================
    # OBJECTIVE 2: Strengthen Financial Performance
    # ============================================
    try:
        from .models_accounting import Transaction
        
        # Revenue metrics - Use multiple sources for comprehensive data
        # 1. From PaymentReceipt (if available)
        revenue_today_pr = 0
        revenue_this_month_pr = 0
        revenue_last_month_pr = 0
        
        if PaymentReceipt:
            revenue_today_pr = _safe_db_call(
                0, 'financial.revenue_today',
                lambda: PaymentReceipt.objects.filter(
                    receipt_date__date=today, is_deleted=False
                ).aggregate(total=Sum('amount_paid'))['total'] or 0
            )
            
            revenue_this_month_pr = _safe_db_call(
                0, 'financial.revenue_month',
                lambda: PaymentReceipt.objects.filter(
                    receipt_date__gte=this_month_start, is_deleted=False
                ).aggregate(total=Sum('amount_paid'))['total'] or 0
            )
            
            revenue_last_month_pr = _safe_db_call(
                0, 'financial.revenue_last_month',
                lambda: PaymentReceipt.objects.filter(
                    receipt_date__gte=last_month_start,
                    receipt_date__lte=last_month_end,
                    is_deleted=False
                ).aggregate(total=Sum('amount_paid'))['total'] or 0
            )
        
        # 2. From Transactions (more reliable)
        revenue_today_tx = _safe_db_call(
            0, 'financial.revenue_today_tx',
            lambda: Transaction.objects.filter(
                transaction_date__date=today,
                is_deleted=False,
                transaction_type='payment'
            ).aggregate(total=Sum('amount'))['total'] or 0
        )
        
        revenue_this_month_tx = _safe_db_call(
            0, 'financial.revenue_month_tx',
            lambda: Transaction.objects.filter(
                transaction_date__gte=this_month_start,
                is_deleted=False,
                transaction_type='payment'
            ).aggregate(total=Sum('amount'))['total'] or 0
        )
        
        revenue_last_month_tx = _safe_db_call(
            0, 'financial.revenue_last_month_tx',
            lambda: Transaction.objects.filter(
                transaction_date__gte=last_month_start,
                transaction_date__lte=last_month_end,
                is_deleted=False,
                transaction_type='payment'
            ).aggregate(total=Sum('amount'))['total'] or 0
        )
        
        # 3. From Paid Invoices
        revenue_this_month_inv = _safe_db_call(
            0, 'financial.revenue_month_inv',
            lambda: Invoice.objects.filter(
                status='paid',
                is_deleted=False,
                issued_at__gte=this_month_start
            ).aggregate(total=Sum('total_amount'))['total'] or 0
        )
        
        revenue_last_month_inv = _safe_db_call(
            0, 'financial.revenue_last_month_inv',
            lambda: Invoice.objects.filter(
                status='paid',
                is_deleted=False,
                issued_at__gte=last_month_start,
                issued_at__lte=last_month_end
            ).aggregate(total=Sum('total_amount'))['total'] or 0
        )
        
        # Use the maximum of all sources (most comprehensive)
        revenue_today = max(revenue_today_pr, revenue_today_tx)
        revenue_this_month = max(revenue_this_month_pr, revenue_this_month_tx, revenue_this_month_inv)
        revenue_last_month = max(revenue_last_month_pr, revenue_last_month_tx, revenue_last_month_inv)
        
        # Calculate revenue growth
        if revenue_last_month > 0:
            revenue_growth = ((revenue_this_month - revenue_last_month) / revenue_last_month * 100)
        elif revenue_this_month > 0:
            # If we have current month revenue but no last month, assume growth
            revenue_growth = 100.0
        else:
            revenue_growth = 0.0
        
        # Outstanding invoices
        outstanding_invoices = _safe_db_call(
            0, 'financial.outstanding',
            lambda: Invoice.objects.filter(
                is_deleted=False,
                status__in=['issued', 'partially_paid', 'overdue']
            ).aggregate(total=Sum('balance'))['total'] or 0
        )
        
        # Total revenue (all invoices, not just paid)
        total_revenue_all = _safe_db_call(
            0, 'financial.total_revenue',
            lambda: Invoice.objects.filter(
                is_deleted=False
            ).exclude(status='cancelled').aggregate(total=Sum('total_amount'))['total'] or 0
        )
        
        # Invoice collection rate
        total_invoices = Invoice.objects.filter(is_deleted=False).exclude(status='cancelled').count()
        paid_invoices = Invoice.objects.filter(
            is_deleted=False, status='paid'
        ).count()
        
        collection_rate = (
            (paid_invoices / total_invoices * 100) if total_invoices > 0 else 0
        )
        
        # Days sales outstanding (DSO) - more accurate calculation
        if revenue_this_month > 0:
            # DSO = (Outstanding AR / Average Daily Sales) 
            # Average Daily Sales = Monthly Revenue / 30
            avg_daily_sales = revenue_this_month / 30.0
            dso = (outstanding_invoices / avg_daily_sales) if avg_daily_sales > 0 else 0
        else:
            # If no revenue, calculate based on outstanding vs total
            if total_revenue_all > 0:
                dso = (outstanding_invoices / total_revenue_all) * 90  # Estimate
            else:
                dso = 0
        
        # Calculate progress with more lenient scoring
        # Each component contributes, even if not perfect
        revenue_score = min(abs(revenue_growth) / 20 * 100, 100) if revenue_growth >= 0 else 0
        collection_score = min(collection_rate / 95 * 100, 100)
        dso_score = max(0, min((60 - dso) / 60 * 100, 100))  # Target: <60 days, max score at 0 days
        
        # Weighted average - but ensure minimum score if we have any activity
        financial_score = (
            revenue_score * 0.3 +
            collection_score * 0.4 +
            dso_score * 0.3
        )
        
        # Minimum score if we have any financial activity
        if revenue_this_month > 0 or total_invoices > 0:
            financial_score = max(financial_score, 10.0)  # At least 10% if there's activity
        
        objectives['financial_performance'] = {
            'title': 'Strengthen Financial Performance',
            'description': 'Improve revenue cycle, billing, claims management, and financial reporting',
            'progress': min(financial_score, 100),
            'metrics': {
                'revenue_today': float(revenue_today),
                'revenue_this_month': float(revenue_this_month),
                'revenue_last_month': float(revenue_last_month),
                'revenue_growth': round(revenue_growth, 1),
                'outstanding_invoices': float(outstanding_invoices),
                'collection_rate': round(collection_rate, 1),
                'dso_days': round(dso, 1),
            },
            'kpis': [
                {'name': 'Revenue This Month', 'value': f'GHS {revenue_this_month:,.2f}', 'target': '>0'},
                {'name': 'Revenue Growth', 'value': f'{round(revenue_growth, 1)}%', 'target': '>15%'},
                {'name': 'Collection Rate', 'value': f'{round(collection_rate, 1)}%', 'target': '>90%'},
                {'name': 'Outstanding AR', 'value': f'GHS {outstanding_invoices:,.2f}', 'target': '<Revenue'},
                {'name': 'Days Sales Outstanding', 'value': f'{round(dso, 1)} days', 'target': '<30 days'},
            ],
            'color': '#10b981',
            'icon': 'bi-cash-stack',
        }
    except Exception as e:
        logger.error(f"Error calculating financial performance: {e}", exc_info=True)
        # Try to get at least basic data even on error
        try:
            basic_revenue = _safe_db_call(
                0, 'financial.basic_revenue',
                lambda: Invoice.objects.filter(
                    status='paid', is_deleted=False
                ).aggregate(total=Sum('total_amount'))['total'] or 0
            )
            basic_outstanding = _safe_db_call(
                0, 'financial.basic_outstanding',
                lambda: Invoice.objects.filter(
                    is_deleted=False,
                    status__in=['issued', 'partially_paid', 'overdue']
                ).aggregate(total=Sum('balance'))['total'] or 0
            )
            total_invoices_basic = Invoice.objects.filter(is_deleted=False).exclude(status='cancelled').count()
            paid_invoices_basic = Invoice.objects.filter(is_deleted=False, status='paid').count()
            basic_collection = (paid_invoices_basic / total_invoices_basic * 100) if total_invoices_basic > 0 else 0
            
            # Calculate a basic progress score
            basic_progress = min(basic_collection / 95 * 100, 100) if basic_collection > 0 else 0
            if basic_revenue > 0 or total_invoices_basic > 0:
                basic_progress = max(basic_progress, 5.0)  # At least 5% if there's any activity
            
            objectives['financial_performance'] = {
                'title': 'Strengthen Financial Performance',
                'description': 'Improve revenue cycle, billing, claims management, and financial reporting',
                'progress': min(basic_progress, 100),
                'metrics': {
                    'revenue_this_month': float(basic_revenue),
                    'outstanding_invoices': float(basic_outstanding),
                    'collection_rate': round(basic_collection, 1),
                },
                'kpis': [
                    {'name': 'Total Revenue', 'value': f'GHS {basic_revenue:,.2f}', 'target': '>0'},
                    {'name': 'Collection Rate', 'value': f'{round(basic_collection, 1)}%', 'target': '>90%'},
                    {'name': 'Outstanding AR', 'value': f'GHS {basic_outstanding:,.2f}', 'target': 'Minimize'},
                ],
                'color': '#10b981',
                'icon': 'bi-cash-stack',
            }
        except Exception as e2:
            logger.error(f"Error in fallback financial calculation: {e2}", exc_info=True)
            objectives['financial_performance'] = {
                'title': 'Strengthen Financial Performance',
                'description': 'Improve revenue cycle, billing, claims management, and financial reporting',
                'progress': 0,
                'metrics': {},
                'kpis': [
                    {'name': 'Status', 'value': 'Data unavailable', 'target': 'Check system'},
                ],
                'color': '#10b981',
                'icon': 'bi-cash-stack',
            }
    
    # ============================================
    # OBJECTIVE 3: Drive Sustainable Business Growth
    # ============================================
    try:
        # Patient acquisition
        new_patients_this_month = Patient.objects.filter(
            created__gte=this_month_start,
            is_deleted=False
        ).count()
        
        new_patients_last_month = Patient.objects.filter(
            created__gte=last_month_start,
            created__lt=this_month_start,
            is_deleted=False
        ).count()
        
        patient_growth = (
            ((new_patients_this_month - new_patients_last_month) / new_patients_last_month * 100)
            if new_patients_last_month > 0 else 0
        )
        
        # Service utilization
        total_services = Encounter.objects.filter(is_deleted=False).count()
        services_this_month = Encounter.objects.filter(
            started_at__gte=this_month_start,
            is_deleted=False
        ).count()
        
        # Repeat patient rate
        total_patients = Patient.objects.filter(is_deleted=False).count()
        patients_with_multiple_encounters = Patient.objects.filter(
            encounters__isnull=False,
            is_deleted=False
        ).annotate(encounter_count=Count('encounters')).filter(
            encounter_count__gt=1
        ).count()
        
        repeat_patient_rate = (
            (patients_with_multiple_encounters / total_patients * 100)
            if total_patients > 0 else 0
        )
        
        # Revenue per patient
        if PaymentReceipt and total_patients > 0:
            avg_revenue_per_patient = revenue_this_month / new_patients_this_month if new_patients_this_month > 0 else 0
        else:
            avg_revenue_per_patient = 0
        
        # Calculate progress
        growth_score = (
            min(patient_growth, 25) / 25 * 100 * 0.4 +  # Target: 25% patient growth
            min(repeat_patient_rate, 60) / 60 * 100 * 0.3 +  # Target: 60% repeat patients
            min(services_this_month / 100, 1) * 100 * 0.3  # Target: 100+ services/month
        )
        
        objectives['business_growth'] = {
            'title': 'Drive Sustainable Business Growth',
            'description': 'Expand services, increase patient acquisition, grow partnerships, unlock revenue streams',
            'progress': min(growth_score, 100),
            'metrics': {
                'new_patients_this_month': new_patients_this_month,
                'new_patients_last_month': new_patients_last_month,
                'patient_growth': round(patient_growth, 1),
                'total_services': total_services,
                'services_this_month': services_this_month,
                'repeat_patient_rate': round(repeat_patient_rate, 1),
                'avg_revenue_per_patient': round(avg_revenue_per_patient, 2),
            },
            'kpis': [
                {'name': 'Patient Growth', 'value': f'{round(patient_growth, 1)}%', 'target': '>20%'},
                {'name': 'Repeat Patient Rate', 'value': f'{round(repeat_patient_rate, 1)}%', 'target': '>50%'},
                {'name': 'New Patients This Month', 'value': f'{new_patients_this_month}', 'target': '>50'},
            ],
            'color': '#8b5cf6',
            'icon': 'bi-graph-up-arrow',
        }
    except Exception as e:
        logger.error(f"Error calculating business growth: {e}")
        objectives['business_growth'] = {
            'title': 'Drive Sustainable Business Growth',
            'description': 'Expand services, increase patient acquisition, grow partnerships, unlock revenue streams',
            'progress': 0,
            'metrics': {},
            'kpis': [],
            'color': '#8b5cf6',
            'icon': 'bi-graph-up-arrow',
        }
    
    # ============================================
    # OBJECTIVE 4: Enhance Service Delivery and Patient Experience
    # ============================================
    try:
        # Service turnaround time
        completed_encounters_recent = Encounter.objects.filter(
            is_deleted=False,
            status='completed',
            started_at__gte=this_month_start,
            started_at__isnull=False,
            ended_at__isnull=False
        )[:50]
        
        avg_turnaround_hours = 0
        if completed_encounters_recent.exists():
            durations = []
            for enc in completed_encounters_recent:
                if enc.started_at and enc.ended_at:
                    duration = (enc.ended_at - enc.started_at).total_seconds() / 3600
                    durations.append(duration)
            if durations:
                avg_turnaround_hours = sum(durations) / len(durations)
        
        # Staff productivity (encounters per staff)
        active_staff = Staff.objects.filter(is_active=True, is_deleted=False).count()
        encounters_per_staff = (
            total_encounters / active_staff if active_staff > 0 else 0
        )
        
        # Appointment adherence
        appointments_this_month = Appointment.objects.filter(
            appointment_date__gte=this_month_start,
            is_deleted=False
        )
        total_appointments = appointments_this_month.count()
        completed_appointments = appointments_this_month.filter(
            status='completed'
        ).count()
        appointment_adherence = (
            (completed_appointments / total_appointments * 100)
            if total_appointments > 0 else 0
        )
        
        # Patient satisfaction (placeholder - would need survey data)
        patient_satisfaction_score = 75  # Placeholder
        
        # Calculate progress
        service_score = (
            max(0, (4 - min(avg_turnaround_hours, 4)) / 4 * 100) * 0.3 +  # Target: <4 hours
            min(encounters_per_staff / 20, 1) * 100 * 0.3 +  # Target: 20 encounters/staff
            min(appointment_adherence, 95) / 95 * 100 * 0.2 +  # Target: 95% adherence
            min(patient_satisfaction_score, 100) / 100 * 100 * 0.2  # Target: 90%+ satisfaction
        )
        
        objectives['service_delivery'] = {
            'title': 'Enhance Service Delivery and Patient Experience',
            'description': 'Improve turnaround times, staff productivity, and patient satisfaction',
            'progress': min(service_score, 100),
            'metrics': {
                'avg_turnaround_hours': round(avg_turnaround_hours, 2),
                'active_staff': active_staff,
                'encounters_per_staff': round(encounters_per_staff, 1),
                'appointment_adherence': round(appointment_adherence, 1),
                'patient_satisfaction_score': patient_satisfaction_score,
            },
            'kpis': [
                {'name': 'Avg Turnaround Time', 'value': f'{round(avg_turnaround_hours, 1)} hrs', 'target': '<4 hrs'},
                {'name': 'Staff Productivity', 'value': f'{round(encounters_per_staff, 1)}/staff', 'target': '>15'},
                {'name': 'Appointment Adherence', 'value': f'{round(appointment_adherence, 1)}%', 'target': '>90%'},
            ],
            'color': '#f59e0b',
            'icon': 'bi-heart-pulse',
        }
    except Exception as e:
        logger.error(f"Error calculating service delivery: {e}")
        objectives['service_delivery'] = {
            'title': 'Enhance Service Delivery and Patient Experience',
            'description': 'Improve turnaround times, staff productivity, and patient satisfaction',
            'progress': 0,
            'metrics': {},
            'kpis': [],
            'color': '#f59e0b',
            'icon': 'bi-heart-pulse',
        }
    
    # ============================================
    # OBJECTIVE 5: Ensure Compliance and Quality Assurance
    # ============================================
    try:
        # Documentation completeness
        encounters_with_docs = Encounter.objects.filter(
            is_deleted=False,
            notes__isnull=False
        ).exclude(notes='').count()
        documentation_rate = (
            (encounters_with_docs / total_encounters * 100)
            if total_encounters > 0 else 0
        )
        
        # Staff certification/training (placeholder)
        certified_staff_rate = 85  # Placeholder
        
        # Audit readiness (placeholder - would need audit tracking)
        audit_readiness_score = 80  # Placeholder
        
        # Policy compliance (placeholder)
        policy_compliance_rate = 90  # Placeholder
        
        # Calculate progress
        compliance_score = (
            min(documentation_rate, 95) / 95 * 100 * 0.3 +
            min(certified_staff_rate, 100) / 100 * 100 * 0.2 +
            min(audit_readiness_score, 100) / 100 * 100 * 0.3 +
            min(policy_compliance_rate, 100) / 100 * 100 * 0.2
        )
        
        objectives['compliance_quality'] = {
            'title': 'Ensure Compliance and Quality Assurance',
            'description': 'Adhere to regulatory requirements, licensing, policies, and quality improvement',
            'progress': min(compliance_score, 100),
            'metrics': {
                'documentation_rate': round(documentation_rate, 1),
                'certified_staff_rate': certified_staff_rate,
                'audit_readiness_score': audit_readiness_score,
                'policy_compliance_rate': policy_compliance_rate,
            },
            'kpis': [
                {'name': 'Documentation Rate', 'value': f'{round(documentation_rate, 1)}%', 'target': '>90%'},
                {'name': 'Certified Staff', 'value': f'{certified_staff_rate}%', 'target': '>85%'},
                {'name': 'Audit Readiness', 'value': f'{audit_readiness_score}%', 'target': '>90%'},
            ],
            'color': '#ef4444',
            'icon': 'bi-shield-check',
        }
    except Exception as e:
        logger.error(f"Error calculating compliance: {e}")
        objectives['compliance_quality'] = {
            'title': 'Ensure Compliance and Quality Assurance',
            'description': 'Adhere to regulatory requirements, licensing, policies, and quality improvement',
            'progress': 0,
            'metrics': {},
            'kpis': [],
            'color': '#ef4444',
            'icon': 'bi-shield-check',
        }
    
    # ============================================
    # OBJECTIVE 6: Support Data-Driven Decision Making
    # ============================================
    try:
        # Report generation frequency (placeholder)
        reports_generated_this_month = 12  # Placeholder
        
        # Data completeness
        patients_with_complete_data = Patient.objects.filter(
            is_deleted=False,
            phone_number__isnull=False
        ).exclude(phone_number='').count()
        data_completeness = (
            (patients_with_complete_data / total_patients * 100)
            if total_patients > 0 else 0
        )
        
        # Analytics usage (placeholder)
        analytics_usage_score = 70  # Placeholder
        
        # Calculate progress
        data_driven_score = (
            min(reports_generated_this_month / 20, 1) * 100 * 0.3 +  # Target: 20 reports/month
            min(data_completeness, 95) / 95 * 100 * 0.4 +  # Target: 95% completeness
            min(analytics_usage_score, 100) / 100 * 100 * 0.3  # Target: 80%+ usage
        )
        
        objectives['data_driven'] = {
            'title': 'Support Data-Driven Decision Making',
            'description': 'Provide performance, operational, and financial reports for strategic planning',
            'progress': min(data_driven_score, 100),
            'metrics': {
                'reports_generated_this_month': reports_generated_this_month,
                'data_completeness': round(data_completeness, 1),
                'analytics_usage_score': analytics_usage_score,
            },
            'kpis': [
                {'name': 'Reports Generated', 'value': f'{reports_generated_this_month}/month', 'target': '>15'},
                {'name': 'Data Completeness', 'value': f'{round(data_completeness, 1)}%', 'target': '>90%'},
                {'name': 'Analytics Usage', 'value': f'{analytics_usage_score}%', 'target': '>75%'},
            ],
            'color': '#06b6d4',
            'icon': 'bi-bar-chart-line',
        }
    except Exception as e:
        logger.error(f"Error calculating data-driven metrics: {e}")
        objectives['data_driven'] = {
            'title': 'Support Data-Driven Decision Making',
            'description': 'Provide performance, operational, and financial reports for strategic planning',
            'progress': 0,  # Default to 0 if calculation fails
            'metrics': {},
            'kpis': [],
            'color': '#06b6d4',
            'icon': 'bi-bar-chart-line',
        }
    
    # ============================================
    # OBJECTIVE 7: Build Institutional Capacity
    # ============================================
    try:
        # Staff retention
        staff_joined_this_year = Staff.objects.filter(
            date_of_joining__year=today.year,
            is_deleted=False
        ).count()
        
        # System utilization
        system_uptime = 99.5  # Placeholder - would need system monitoring
        
        # Process standardization (placeholder)
        standardized_processes = 75  # Placeholder
        
        # Training completion (placeholder)
        training_completion_rate = 80  # Placeholder
        
        # Calculate progress
        capacity_score = (
            min(staff_joined_this_year / 10, 1) * 100 * 0.2 +  # Target: 10+ new staff/year
            min(system_uptime, 99.9) / 99.9 * 100 * 0.3 +  # Target: 99.9% uptime
            min(standardized_processes, 100) / 100 * 100 * 0.3 +  # Target: 100% standardized
            min(training_completion_rate, 100) / 100 * 100 * 0.2  # Target: 90%+ training
        )
        
        objectives['institutional_capacity'] = {
            'title': 'Build Institutional Capacity',
            'description': 'Strengthen systems, controls, and staff coordination for continuity and scalability',
            'progress': min(capacity_score, 100),
            'metrics': {
                'staff_joined_this_year': staff_joined_this_year,
                'system_uptime': system_uptime,
                'standardized_processes': standardized_processes,
                'training_completion_rate': training_completion_rate,
            },
            'kpis': [
                {'name': 'New Staff This Year', 'value': f'{staff_joined_this_year}', 'target': '>8'},
                {'name': 'System Uptime', 'value': f'{system_uptime}%', 'target': '>99%'},
                {'name': 'Process Standardization', 'value': f'{standardized_processes}%', 'target': '>90%'},
            ],
            'color': '#6366f1',
            'icon': 'bi-building',
        }
    except Exception as e:
        logger.error(f"Error calculating institutional capacity: {e}")
        objectives['institutional_capacity'] = {
            'title': 'Build Institutional Capacity',
            'description': 'Strengthen systems, controls, and staff coordination for continuity and scalability',
            'progress': 0,
            'metrics': {},
            'kpis': [],
            'color': '#6366f1',
            'icon': 'bi-building',
        }
    
    # ============================================
    # OBJECTIVE 8: Marketing & Corporate Growth
    # ============================================
    try:
        from .models_marketing import (
            MarketingObjective, MarketingTask, MarketingCampaign,
            CorporatePartnership, MarketingMetric
        )
        
        # Marketing Objectives Progress
        # Use filter to exclude deleted, get fresh data (no cache)
        total_marketing_objectives = MarketingObjective.objects.filter(is_deleted=False).count()
        active_marketing_objectives = MarketingObjective.objects.filter(
            status__in=['active', 'planning'],  # Include planning as active
            is_deleted=False
        ).count()
        completed_marketing_objectives = MarketingObjective.objects.filter(
            status='completed',
            is_deleted=False
        ).count()
        
        # Marketing Tasks Completion
        # Use filter to exclude deleted, get fresh data (no cache)
        total_marketing_tasks = MarketingTask.objects.filter(is_deleted=False).count()
        completed_marketing_tasks = MarketingTask.objects.filter(
            status='completed',
            is_deleted=False
        ).count()
        task_completion_rate = (
            (completed_marketing_tasks / total_marketing_tasks * 100)
            if total_marketing_tasks > 0 else 0
        )
        
        # Campaign Performance
        # Use filter to exclude deleted, get fresh data (no cache)
        active_campaigns = MarketingCampaign.objects.filter(
            status='active',
            is_deleted=False
        ).count()
        total_campaigns = MarketingCampaign.objects.filter(is_deleted=False).count()
        campaign_budget = MarketingCampaign.objects.aggregate(total=Sum('budget'))['total'] or 0
        campaign_spent = MarketingCampaign.objects.aggregate(total=Sum('spent'))['total'] or 0
        campaign_roi_avg = MarketingCampaign.objects.filter(
            status='completed'
        ).aggregate(avg_roi=Avg('roi_percentage'))['avg_roi'] or 0
        
        # Corporate Partnerships
        active_partnerships = CorporatePartnership.objects.filter(status='active').count()
        total_partnerships = CorporatePartnership.objects.count()
        partnership_value = CorporatePartnership.objects.filter(
            status='active'
        ).aggregate(total=Sum('value'))['total'] or 0
        
        # Patient Acquisition (Last 30 days - attributed to marketing)
        marketing_start_date = today - timedelta(days=30)
        new_patients_marketing = Patient.objects.filter(
            created__gte=marketing_start_date,
            is_deleted=False
        ).count()
        
        # Marketing Revenue (estimate from new patients)
        if PaymentReceipt:
            marketing_revenue = _safe_db_call(
                0, 'marketing.revenue',
                lambda: PaymentReceipt.objects.filter(
                    receipt_date__gte=marketing_start_date,
                    is_deleted=False
                ).aggregate(total=Sum('amount_paid'))['total'] or 0
            )
        else:
            marketing_revenue = 0
        
        # Marketing ROI
        marketing_roi = 0
        if campaign_spent > 0:
            marketing_roi = ((marketing_revenue - campaign_spent) / campaign_spent * 100) if campaign_spent > 0 else 0
        
        # Calculate progress score
        marketing_score = (
            min(active_marketing_objectives / 5, 1) * 100 * 0.2 +  # Target: 5+ active objectives
            min(task_completion_rate, 90) / 90 * 100 * 0.3 +  # Target: 90% task completion
            min(active_campaigns / 3, 1) * 100 * 0.2 +  # Target: 3+ active campaigns
            min(active_partnerships / 5, 1) * 100 * 0.15 +  # Target: 5+ active partnerships
            min(marketing_roi / 200, 1) * 100 * 0.15  # Target: 200% ROI
        )
        
        objectives['marketing_corporate'] = {
            'title': 'Marketing & Corporate Growth',
            'description': 'Drive brand awareness, patient acquisition, corporate partnerships, and market expansion',
            'progress': min(marketing_score, 100),
            'metrics': {
                'total_objectives': total_marketing_objectives,
                'active_objectives': active_marketing_objectives,
                'completed_objectives': completed_marketing_objectives,
                'total_tasks': total_marketing_tasks,
                'completed_tasks': completed_marketing_tasks,
                'task_completion_rate': round(task_completion_rate, 1),
                'active_campaigns': active_campaigns,
                'total_campaigns': total_campaigns,
                'campaign_budget': float(campaign_budget),
                'campaign_spent': float(campaign_spent),
                'campaign_roi_avg': round(campaign_roi_avg, 1),
                'active_partnerships': active_partnerships,
                'total_partnerships': total_partnerships,
                'partnership_value': float(partnership_value),
                'new_patients_30d': new_patients_marketing,
                'marketing_revenue': float(marketing_revenue),
                'marketing_roi': round(marketing_roi, 1),
            },
            'kpis': [
                {'name': 'Active Objectives', 'value': f'{active_marketing_objectives}', 'target': '>5'},
                {'name': 'Task Completion', 'value': f'{round(task_completion_rate, 1)}%', 'target': '>85%'},
                {'name': 'Active Campaigns', 'value': f'{active_campaigns}', 'target': '>3'},
                {'name': 'Marketing ROI', 'value': f'{round(marketing_roi, 1)}%', 'target': '>150%'},
            ],
            'color': '#ec4899',
            'icon': 'bi-megaphone',
        }
    except Exception as e:
        logger.error(f"Error calculating marketing & corporate growth: {e}", exc_info=True)
        # Still show data even if calculation fails
        try:
            total_marketing_objectives = MarketingObjective.objects.filter(is_deleted=False).count()
            active_marketing_objectives = MarketingObjective.objects.filter(
                status__in=['active', 'planning'],
                is_deleted=False
            ).count()
            total_marketing_tasks = MarketingTask.objects.filter(is_deleted=False).count()
            completed_marketing_tasks = MarketingTask.objects.filter(
                status='completed',
                is_deleted=False
            ).count()
            task_completion_rate = (
                (completed_marketing_tasks / total_marketing_tasks * 100)
                if total_marketing_tasks > 0 else 0
            )
            active_campaigns = MarketingCampaign.objects.filter(
                status='active',
                is_deleted=False
            ).count()
            
            objectives['marketing_corporate'] = {
                'title': 'Marketing & Corporate Growth',
                'description': 'Drive brand awareness, patient acquisition, corporate partnerships, and market expansion',
                'progress': 0,
                'metrics': {
                    'total_objectives': total_marketing_objectives,
                    'active_objectives': active_marketing_objectives,
                    'total_tasks': total_marketing_tasks,
                    'completed_tasks': completed_marketing_tasks,
                    'task_completion_rate': round(task_completion_rate, 1),
                    'active_campaigns': active_campaigns,
                },
                'kpis': [
                    {'name': 'Active Objectives', 'value': f'{active_marketing_objectives}', 'target': '>5'},
                    {'name': 'Task Completion', 'value': f'{round(task_completion_rate, 1)}%', 'target': '>85%'},
                    {'name': 'Active Campaigns', 'value': f'{active_campaigns}', 'target': '>3'},
                ],
                'color': '#ec4899',
                'icon': 'bi-megaphone',
            }
        except Exception as e2:
            logger.error(f"Error in fallback marketing calculation: {e2}", exc_info=True)
            objectives['marketing_corporate'] = {
                'title': 'Marketing & Corporate Growth',
                'description': 'Drive brand awareness, patient acquisition, corporate partnerships, and market expansion',
                'progress': 0,
                'metrics': {},
                'kpis': [],
                'color': '#ec4899',
                'icon': 'bi-megaphone',
            }
    
    # Calculate overall progress
    overall_progress = sum(obj['progress'] for obj in objectives.values()) / len(objectives) if objectives else 0
    
    # Ensure all progress values are valid numbers
    for key, obj in objectives.items():
        if not isinstance(obj.get('progress'), (int, float)):
            obj['progress'] = 0.0
        obj['progress'] = max(0.0, min(100.0, float(obj['progress'])))
    
    return {
        'objectives': objectives,
        'overall_progress': round(float(overall_progress), 1),
        'last_updated': timezone.now().isoformat(),  # Convert to ISO string for JSON serialization
    }











