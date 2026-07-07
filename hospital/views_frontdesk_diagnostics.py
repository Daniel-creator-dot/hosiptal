"""
Front desk / reception diagnostics overview — pending labs & imaging with charts.
"""
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import render
from django.utils import timezone

from .decorators import role_required
from .diagnostics_status import (
    IMAGING_COMPLETE_STATUSES,
    IMAGING_FRONTDESK_PENDING_STATUSES,
    LAB_PENDING_STATUSES,
    imaging_is_pending,
)
from .models import LabResult, Order
from .models_advanced import ImagingStudy


def _parse_lookback_days(request, default=7):
    try:
        days = int(request.GET.get('days', default))
    except (TypeError, ValueError):
        days = default
    return max(1, min(days, 30))


@login_required
@role_required('receptionist', 'admin')
def frontdesk_diagnostics_dashboard(request):
    """Visual overview of pending and completed lab tests and imaging studies."""
    today = timezone.now().date()
    lookback_days = _parse_lookback_days(request)
    since = today - timedelta(days=lookback_days - 1)
    today_only = request.GET.get('today') == '1'

    date_filter_lab = Q(created__date__gte=since)
    date_filter_imaging = Q(created__date__gte=since)
    if today_only:
        date_filter_lab = Q(created__date=today)
        date_filter_imaging = Q(created__date=today)

    lab_pending_qs = LabResult.objects.filter(
        status__in=LAB_PENDING_STATUSES,
        is_deleted=False,
    ).filter(date_filter_lab).select_related(
        'test', 'order__encounter__patient', 'order__requested_by__user',
    ).order_by('-created')[:80]

    lab_completed_today = LabResult.objects.filter(
        status='completed',
        is_deleted=False,
        verified_at__date=today,
    ).count()

    imaging_pending_qs = ImagingStudy.objects.filter(
        status__in=IMAGING_FRONTDESK_PENDING_STATUSES,
        is_deleted=False,
    ).filter(date_filter_imaging).select_related(
        'patient', 'order__encounter', 'order__requested_by__user',
    ).order_by('-created')[:80]

    imaging_completed_today = ImagingStudy.objects.filter(
        status__in=IMAGING_COMPLETE_STATUSES,
        is_deleted=False,
    ).filter(
        Q(report_verified_at__date=today) | Q(modified__date=today),
    ).count()

    lab_status_counts = dict(
        LabResult.objects.filter(is_deleted=False)
        .filter(date_filter_lab)
        .values('status')
        .annotate(c=Count('id'))
        .values_list('status', 'c')
    )
    imaging_status_counts = dict(
        ImagingStudy.objects.filter(is_deleted=False)
        .filter(date_filter_imaging)
        .values('status')
        .annotate(c=Count('id'))
        .values_list('status', 'c')
    )

    lab_pending_orders = Order.objects.filter(
        order_type='lab',
        status__in=['pending', 'in_progress'],
        is_deleted=False,
        created__date__gte=since if not today_only else today,
    ).select_related('encounter__patient').order_by('-created')[:30]

    imaging_pending_orders = Order.objects.filter(
        order_type='imaging',
        status__in=['pending', 'in_progress'],
        is_deleted=False,
        created__date__gte=since if not today_only else today,
    ).select_related('encounter__patient').order_by('-created')[:30]

    lab_pending_total = LabResult.objects.filter(
        status__in=LAB_PENDING_STATUSES, is_deleted=False,
    ).filter(date_filter_lab).count()
    imaging_pending_total = ImagingStudy.objects.filter(
        status__in=IMAGING_FRONTDESK_PENDING_STATUSES, is_deleted=False,
    ).filter(date_filter_imaging).count()

    lab_completed_in_range = LabResult.objects.filter(
        status='completed', is_deleted=False,
    ).filter(date_filter_lab).count()
    imaging_completed_in_range = ImagingStudy.objects.filter(
        status__in=IMAGING_COMPLETE_STATUSES, is_deleted=False,
    ).filter(date_filter_imaging).count()

    context = {
        'title': 'Diagnostics Overview',
        'today': today,
        'lookback_days': lookback_days,
        'today_only': today_only,
        'since': since,
        'lab_pending_results': lab_pending_qs,
        'imaging_pending_studies': imaging_pending_qs,
        'lab_pending_orders': lab_pending_orders,
        'imaging_pending_orders': imaging_pending_orders,
        'lab_pending_total': lab_pending_total,
        'imaging_pending_total': imaging_pending_total,
        'lab_completed_today': lab_completed_today,
        'imaging_completed_today': imaging_completed_today,
        'lab_completed_in_range': lab_completed_in_range,
        'imaging_completed_in_range': imaging_completed_in_range,
        'lab_status_counts': lab_status_counts,
        'imaging_status_counts': imaging_status_counts,
        'lab_status_labels': dict(LabResult._meta.get_field('status').choices),
        'imaging_status_labels': dict(ImagingStudy._meta.get_field('status').choices),
        'lab_status_counts_json': lab_status_counts,
        'imaging_status_counts_json': imaging_status_counts,
        'lab_status_labels_json': dict(LabResult._meta.get_field('status').choices),
        'imaging_status_labels_json': dict(ImagingStudy._meta.get_field('status').choices),
        'imaging_is_pending': imaging_is_pending,
    }
    return render(request, 'hospital/frontdesk/diagnostics_dashboard.html', context)
