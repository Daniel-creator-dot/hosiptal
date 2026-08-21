"""Shared helpers for marking lab results complete (independent of TAT)."""
from __future__ import annotations

from typing import Any, Optional


def lab_result_has_values(result) -> bool:
    """True when the result row has entered data worth treating as done."""
    value = (getattr(result, 'value', None) or '')
    if hasattr(value, 'strip'):
        value = value.strip()
    if value:
        return True

    qualitative = (getattr(result, 'qualitative_result', None) or '')
    if hasattr(qualitative, 'strip'):
        qualitative = qualitative.strip()
    if qualitative:
        return True

    details = getattr(result, 'details', None)
    if isinstance(details, dict):
        for val in details.values():
            if val is not None and str(val).strip():
                return True

    attachment = getattr(result, 'attachment', None)
    if attachment:
        try:
            if getattr(attachment, 'name', None):
                return True
        except Exception:
            return True

    # Edit-lab uploads often live only on PatientDocument
    try:
        from hospital.models_medical_records import PatientDocument
        if PatientDocument.objects.filter(
            lab_result_id=getattr(result, 'pk', None),
            is_deleted=False,
            document_type='lab_report',
        ).exclude(file='').exclude(file__isnull=True).exists():
            return True
    except Exception:
        pass

    return False


def sync_lab_order_status(order) -> None:
    """Align parent lab order status with its result rows."""
    if not order or getattr(order, 'order_type', None) != 'lab':
        return

    qs = order.lab_results.filter(is_deleted=False).exclude(status='cancelled')
    if not qs.exists():
        return

    if qs.filter(status__in=['pending', 'in_progress']).exists():
        if order.status == 'pending':
            order.status = 'in_progress'
            order.save(update_fields=['status', 'modified'])
        return

    if qs.filter(status='completed').count() == qs.count():
        if order.status != 'completed':
            order.status = 'completed'
            order.save(update_fields=['status', 'modified'])


def apply_lab_result_workflow(
    result,
    user,
    *,
    status_from_post: Optional[str] = None,
    has_values: Optional[bool] = None,
) -> None:
    """
    Update lab result status after save.

    Manual completion always wins over turnaround-time expectations.
    Entering result values defaults to completed unless user chose in_progress.
    """
    from django.utils import timezone

    from .models import Staff

    if has_values is None:
        has_values = lab_result_has_values(result)

    requested = (status_from_post or '').strip().lower()
    force_complete = requested == 'completed'
    keep_in_progress = requested == 'in_progress'

    if force_complete or (has_values and not keep_in_progress):
        result.status = 'completed'
        if not result.verified_at:
            result.verified_at = timezone.now()
        if not result.verified_by and user and getattr(user, 'is_authenticated', False):
            staff = Staff.objects.filter(user=user, is_deleted=False).order_by('-created').first()
            if staff:
                result.verified_by = staff
    elif result.status == 'pending':
        result.status = 'in_progress'

    order = getattr(result, 'order', None)
    if order:
        sync_lab_order_status(order)
