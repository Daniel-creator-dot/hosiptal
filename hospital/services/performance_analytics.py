"""
Performance analytics generator for staff dashboards and HR reviews.
Aggregates operational KPIs per role and stores them as StaffPerformanceSnapshot records.
"""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.db.models import Avg, Count, DurationField, ExpressionWrapper, F, Q
from django.utils import timezone

from ..models import Encounter, LabResult, Order, Patient, Prescription, Staff, VitalSign
from ..models_advanced import MedicationAdministrationRecord
from ..models_audit import ActivityLog
from ..models_hr import StaffPerformanceSnapshot


DEFAULT_WINDOW_DAYS = 14


def _normalize_score(value: Decimal | int | float, target: int) -> Decimal:
    if target <= 0:
        return Decimal('0.00')
    ratio = min(Decimal('1.00'), Decimal(str(value)) / Decimal(str(target)))
    return (ratio * Decimal('5.0')).quantize(Decimal('0.01'))


def _safe_duration_minutes(expr):
    if not expr:
        return Decimal('0')
    return Decimal(str(expr.total_seconds() / 60)).quantize(Decimal('0.01'))


class PerformanceAnalyticsService:
    """Central service that calculates and persists staff performance snapshots."""

    def __init__(self, window_days: int = DEFAULT_WINDOW_DAYS):
        self.window_days = window_days

    def generate_snapshot(self, staff: Staff, days: int | None = None) -> StaffPerformanceSnapshot | None:
        if not staff:
            return None
        period_end = timezone.now().date()
        period_start = period_end - timedelta(days=(days or self.window_days) - 1)
        role = staff.profession

        calculators = {
            'doctor': self._doctor_metrics,
            'nurse': self._nurse_metrics,
            'lab_technician': self._lab_metrics,
            'pharmacist': self._pharmacy_metrics,
            'receptionist': self._frontdesk_metrics,
        }

        calculator = calculators.get(role)
        if not calculator:
            return None

        metrics_payload = calculator(staff, period_start, period_end)
        if not metrics_payload:
            return None

        snapshot, _ = StaffPerformanceSnapshot.objects.update_or_create(
            staff=staff,
            role=role,
            period_start=period_start,
            period_end=period_end,
            defaults={
                'metrics': metrics_payload['metrics'],
                'productivity_score': metrics_payload['productivity'],
                'quality_score': metrics_payload['quality'],
                'engagement_score': metrics_payload['engagement'],
                'overall_index': metrics_payload['overall'],
                'data_points': metrics_payload.get('data_points', 0),
            },
        )
        return snapshot

    def ensure_recent_snapshot(self, staff: Staff) -> StaffPerformanceSnapshot | None:
        snapshot = (
            staff.performance_snapshots.filter(role=staff.profession)
            .order_by('-period_end')
            .first()
        )
        if not snapshot or (timezone.now().date() - snapshot.period_end).days >= 3:
            return self.generate_snapshot(staff)
        return snapshot

    def get_recent_snapshots(self, staff: Staff, limit: int = 4):
        return staff.performance_snapshots.filter(role=staff.profession).order_by('-period_end')[:limit]

    # ----- Role calculators -------------------------------------------------

    def _doctor_metrics(self, staff, start, end):
        encounters = Encounter.objects.filter(
            provider=staff,
            started_at__date__gte=start,
            started_at__date__lte=end,
            is_deleted=False,
        )
        total_encounters = encounters.count()
        completed = encounters.filter(status='completed').count()
        avg_duration_expr = encounters.exclude(ended_at__isnull=True).annotate(
            duration=ExpressionWrapper(F('ended_at') - F('started_at'), output_field=DurationField())
        ).aggregate(avg=Avg('duration'))['avg']
        avg_duration = _safe_duration_minutes(avg_duration_expr) if avg_duration_expr else Decimal('0')

        prescriptions = Prescription.objects.filter(
            prescribed_by=staff,
            created__date__gte=start,
            created__date__lte=end,
            is_deleted=False,
        ).count()

        lab_orders = Order.objects.filter(
            requested_by=staff,
            order_type='lab',
            created__date__gte=start,
            created__date__lte=end,
            is_deleted=False,
        ).count()

        completion_rate = (completed / total_encounters) if total_encounters else 0

        metrics = {
            'counts': {
                'encounters_total': total_encounters,
                'encounters_completed': completed,
                'prescriptions_written': prescriptions,
                'lab_orders_requested': lab_orders,
            },
            'quality': {
                'completion_rate': round(completion_rate * 100, 1),
                'avg_consult_minutes': float(avg_duration),
            },
            'highlights': [
                f"{completed} of {total_encounters} encounters closed",
                f"{prescriptions} prescriptions issued",
            ],
        }

        productivity = _normalize_score(total_encounters, target=20)
        quality = _normalize_score(completion_rate * 100, target=90)
        engagement = _normalize_score(prescriptions + lab_orders, target=15)

        return {
            'metrics': metrics,
            'productivity': productivity,
            'quality': quality,
            'engagement': engagement,
            'overall': (productivity + quality + engagement) / 3 if productivity else Decimal('0.00'),
            'data_points': total_encounters,
        }

    def _nurse_metrics(self, staff, start, end):
        vitals = VitalSign.objects.filter(
            recorded_by=staff,
            recorded_at__date__gte=start,
            recorded_at__date__lte=end,
        ).count()

        mar_entries = MedicationAdministrationRecord.objects.filter(
            administered_by=staff,
            administered_time__date__gte=start,
            administered_time__date__lte=end,
        ).count()

        missed_doses = MedicationAdministrationRecord.objects.filter(
            administered_by=staff,
            status__in=['missed', 'refused', 'held'],
            administered_time__date__gte=start,
            administered_time__date__lte=end,
        ).count()

        coverage_rate = (mar_entries / (mar_entries + missed_doses)) if (mar_entries + missed_doses) else 0

        metrics = {
            'counts': {
                'vital_signs_recorded': vitals,
                'medications_administered': mar_entries,
                'doses_missed_or_refused': missed_doses,
            },
            'quality': {
                'medication_coverage_pct': round(coverage_rate * 100, 1),
            },
            'highlights': [
                f"{vitals} vitals captured",
                f"{mar_entries} medications administered",
            ],
        }

        productivity = _normalize_score(vitals + mar_entries, target=30)
        quality = _normalize_score(coverage_rate * 100, target=95)
        engagement = _normalize_score(vitals, target=20)

        return {
            'metrics': metrics,
            'productivity': productivity,
            'quality': quality,
            'engagement': engagement,
            'overall': (productivity + quality + engagement) / 3 if productivity else Decimal('0.00'),
            'data_points': vitals + mar_entries,
        }

    def _lab_metrics(self, staff, start, end):
        try:
            tests_completed = LabResult.objects.filter(
                verified_by=staff,
                verified_at__date__gte=start,
                verified_at__date__lte=end,
                status='completed',
                is_deleted=False,
            )
            completed_count = tests_completed.count()
            
            # Check for abnormal results
            try:
                critical_flags = tests_completed.filter(is_abnormal=True).count()
            except Exception:
                critical_flags = 0

            # Calculate turnaround time
            try:
                tat_expr = tests_completed.exclude(
                    verified_at__isnull=True
                ).exclude(
                    order__isnull=True
                ).exclude(
                    order__created__isnull=True
                ).annotate(
                    tat=ExpressionWrapper(
                        F('verified_at') - F('order__created'),
                        output_field=DurationField()
                    )
                ).aggregate(avg=Avg('tat'))['avg']
                avg_tat = _safe_duration_minutes(tat_expr) if tat_expr else Decimal('0')
            except Exception:
                avg_tat = Decimal('0')
        except Exception as e:
            # Return safe defaults if any error occurs
            completed_count = 0
            critical_flags = 0
            avg_tat = Decimal('0')

        metrics = {
            'counts': {
                'tests_completed': completed_count,
                'critical_results_flagged': critical_flags,
            },
            'quality': {
                'avg_turnaround_minutes': float(avg_tat),
            },
            'highlights': [
                f"{completed_count} lab tests performed",
                f"{critical_flags} critical results escalated",
            ],
        }

        productivity = _normalize_score(completed_count, target=40)
        quality = _normalize_score(max(Decimal('1'), Decimal('120') - avg_tat), target=100)
        engagement = _normalize_score(critical_flags, target=5) if critical_flags else Decimal('3.5')

        return {
            'metrics': metrics,
            'productivity': productivity,
            'quality': quality,
            'engagement': engagement,
            'overall': (productivity + quality + engagement) / 3 if productivity else Decimal('0.00'),
            'data_points': completed_count,
        }

    def _pharmacy_metrics(self, staff, start, end):
        dispensed = Prescription.objects.filter(
            dispensed_by=staff,
            dispensed_at__date__gte=start,
            dispensed_at__date__lte=end,
            status='dispensed',
        )
        dispensed_count = dispensed.count()

        turnaround_expr = dispensed.annotate(
            tat=ExpressionWrapper(
                F('dispensed_at') - F('created'),
                output_field=DurationField()
            )
        ).aggregate(avg=Avg('tat'))['avg']
        avg_dispense_time = _safe_duration_minutes(turnaround_expr) if turnaround_expr else Decimal('0')

        pending_count = Prescription.objects.filter(
            status='pending',
            created__date__gte=start,
            created__date__lte=end,
        ).count()

        metrics = {
            'counts': {
                'prescriptions_dispensed': dispensed_count,
                'pending_queue': pending_count,
            },
            'quality': {
                'avg_dispense_minutes': float(avg_dispense_time),
            },
            'highlights': [
                f"{dispensed_count} prescriptions dispensed",
                f"{pending_count} awaiting action",
            ],
        }

        productivity = _normalize_score(dispensed_count, target=35)
        quality = _normalize_score(max(Decimal('1'), Decimal('60') - avg_dispense_time), target=50)
        engagement = _normalize_score(dispensed_count - pending_count, target=20)

        return {
            'metrics': metrics,
            'productivity': productivity,
            'quality': quality,
            'engagement': engagement,
            'overall': (productivity + quality + engagement) / 3 if productivity else Decimal('0.00'),
            'data_points': dispensed_count,
        }

    def _frontdesk_metrics(self, staff, start, end):
        if not ActivityLog:
            return None

        def _count_activity(keywords):
            if not keywords:
                return 0
            q_objects = Q()
            for kw in keywords:
                q_objects |= Q(description__icontains=kw)
            return ActivityLog.objects.filter(
                user=staff.user,
                created__date__gte=start,
                created__date__lte=end,
            ).filter(q_objects).count()

        patient_regs = _count_activity(['/hms/patient-registration', '/hms/patients/new'])
        appointment_creations = _count_activity(['/hms/frontdesk/appointments/create', '/hms/appointments/new'])
        queue_actions = _count_activity(['/hms/queues', '/hms/patient-checkin'])

        metrics = {
            'counts': {
                'registrations_completed': patient_regs,
                'appointments_scheduled': appointment_creations,
                'queue_events_handled': queue_actions,
            },
            'quality': {
                'service_mix': f"{appointment_creations}/{max(1, patient_regs)} appointments per registration",
            },
            'highlights': [
                f"{patient_regs} new registrations",
                f"{appointment_creations} appointments booked",
            ],
        }

        productivity = _normalize_score(patient_regs + appointment_creations, target=30)
        quality = _normalize_score(appointment_creations, target=20)
        engagement = _normalize_score(queue_actions, target=25)

        return {
            'metrics': metrics,
            'productivity': productivity,
            'quality': quality,
            'engagement': engagement,
            'overall': (productivity + quality + engagement) / 3 if productivity else Decimal('0.00'),
            'data_points': patient_regs + appointment_creations + queue_actions,
        }


performance_analytics_service = PerformanceAnalyticsService()

