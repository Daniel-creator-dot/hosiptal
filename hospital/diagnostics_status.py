"""
Shared lab / imaging workflow status helpers for dashboards and patient-facing views.
"""

# ImagingStudy statuses that mean the report is ready for clinical use / patient pickup
IMAGING_COMPLETE_STATUSES = frozenset({'verified', 'reported'})

# Active work — scan or report still in progress
IMAGING_IN_PROGRESS_STATUSES = frozenset({
    'arrived', 'in_progress', 'completed', 'quality_check',
    'awaiting_report', 'reporting',
})

# Not yet started or only scheduled
IMAGING_PENDING_STATUSES = frozenset({'scheduled'})

# Front desk / reception: anything not finished and not cancelled
IMAGING_FRONTDESK_PENDING_STATUSES = frozenset({
    'scheduled', 'arrived', 'in_progress', 'completed', 'quality_check',
    'awaiting_report', 'reporting',
})

LAB_COMPLETE_STATUSES = frozenset({'completed'})
LAB_PENDING_STATUSES = frozenset({'pending', 'in_progress'})


def imaging_is_complete(status):
    return status in IMAGING_COMPLETE_STATUSES


def imaging_is_pending(status):
    """True when study is still in workflow (not report-ready, not cancelled)."""
    return status in IMAGING_FRONTDESK_PENDING_STATUSES


def imaging_status_badge_class(status):
    """Bootstrap badge class for ImagingStudy.status."""
    if status in IMAGING_COMPLETE_STATUSES:
        return 'bg-success'
    if status in ('reporting', 'awaiting_report'):
        return 'bg-info'
    if status in ('completed', 'quality_check'):
        return 'bg-primary'
    if status in ('in_progress', 'arrived'):
        return 'bg-warning text-dark'
    if status == 'cancelled':
        return 'bg-secondary'
    return 'bg-light text-dark'


def imaging_status_sheet_class(status):
    """CSS class suffix for patient record sheet status-badge."""
    if status in IMAGING_COMPLETE_STATUSES:
        return 'completed'
    if status in IMAGING_IN_PROGRESS_STATUSES:
        return 'in_progress'
    if status == 'cancelled':
        return 'cancelled'
    return 'pending'


def lab_status_sheet_class(status):
    if status == 'completed':
        return 'completed'
    if status == 'in_progress':
        return 'in_progress'
    if status == 'cancelled':
        return 'cancelled'
    return 'pending'
