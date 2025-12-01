"""
Primecare accounting automation tasks.
Schedules nightly revenue matching to satisfy the 24/48-hour rules
outlined in the accounting guide.
"""
from datetime import timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model
from celery import shared_task
import logging

logger = logging.getLogger(__name__)
User = get_user_model()


def _get_service_user():
    """Return a fallback user for automated journal entries."""
    user = (
        User.objects.filter(is_superuser=True, is_active=True)
        .order_by('id')
        .first()
    )
    if not user:
        user = (
            User.objects.filter(is_staff=True, is_active=True)
            .order_by('id')
            .first()
        )
    return user


@shared_task
def auto_match_cash_revenue():
    """
    Match undeposited cash receipts to revenue accounts
    once entries are at least 24 hours old.
    """
    from hospital.models_primecare_accounting import UndepositedFunds

    cutoff_date = timezone.now().date() - timedelta(days=1)
    pending_entries = UndepositedFunds.objects.filter(
        status='pending',
        entry_date__lte=cutoff_date,
    )

    if not pending_entries.exists():
        logger.info("auto_match_cash_revenue: no entries eligible for matching.")
        return "No entries matched"

    service_user = _get_service_user()
    if not service_user:
        logger.error("auto_match_cash_revenue: no service user available.")
        raise RuntimeError("No user available to post automated cash revenue matches.")

    matched = 0
    for entry in pending_entries:
        try:
            entry.match_to_revenue(service_user)
            matched += 1
        except Exception as exc:
            logger.exception(
                "Failed to match undeposited funds %s: %s",
                entry.entry_number,
                exc,
            )

    logger.info("auto_match_cash_revenue: matched %s entries.", matched)
    return f"Matched {matched} cash entries"


@shared_task
def auto_match_credit_revenue():
    """
    Match insurance / corporate credit sales to revenue
    once entries are at least 48 hours old.
    """
    from hospital.models_primecare_accounting import InsuranceReceivableEntry

    cutoff_date = timezone.now().date() - timedelta(days=2)
    pending_entries = InsuranceReceivableEntry.objects.filter(
        status='pending',
        entry_date__lte=cutoff_date,
    )

    if not pending_entries.exists():
        logger.info("auto_match_credit_revenue: no entries eligible for matching.")
        return "No entries matched"

    service_user = _get_service_user()
    if not service_user:
        logger.error("auto_match_credit_revenue: no service user available.")
        raise RuntimeError("No user available to post automated credit revenue matches.")

    matched = 0
    for entry in pending_entries:
        try:
            entry.match_to_revenue(service_user)
            matched += 1
        except Exception as exc:
            logger.exception(
                "Failed to match receivable %s (%s): %s",
                entry.entry_number,
                entry.payer.name,
                exc,
            )

    logger.info("auto_match_credit_revenue: matched %s entries.", matched)
    return f"Matched {matched} credit entries"











