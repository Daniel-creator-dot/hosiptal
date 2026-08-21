"""
Insurance visits: first 3 lab tests on the encounter; extras need a reason and diagnosis.
Applies to NHIS / private / insurance payers (not cash or corporate).
"""
from __future__ import annotations

INSURANCE_LAB_TEST_LIMIT = 3
EXTRA_LAB_REASON_MIN_LEN = 5

EXTRA_LAB_JUSTIFICATION_MSG = (
    f'Insurance visits allow {INSURANCE_LAB_TEST_LIMIT} lab tests. '
    'Each additional test needs a reason and diagnosis.'
)


def encounter_is_insurance_lab_limited(encounter) -> bool:
    if not encounter:
        return False
    try:
        from hospital.services.insurance_exclusion_service import is_insurance_billing_payer
        from hospital.utils_billing import get_patient_payer_info

        info = get_patient_payer_info(getattr(encounter, 'patient', None), encounter)
        if is_insurance_billing_payer(info.get('payer')):
            return True
        payer_type = (info.get('type') or '').strip().lower()
        return payer_type in ('nhis', 'private', 'insurance')
    except Exception:
        return False


def count_encounter_lab_tests(encounter) -> int:
    if not encounter:
        return 0
    from hospital.models import LabResult

    return (
        LabResult.objects.filter(
            order__encounter=encounter,
            order__order_type='lab',
            order__is_deleted=False,
            is_deleted=False,
        )
        .exclude(status='cancelled')
        .count()
    )


def extra_lab_count(encounter, new_test_count: int) -> int:
    existing = count_encounter_lab_tests(encounter)
    try:
        new_n = int(new_test_count or 0)
    except (TypeError, ValueError):
        new_n = 0
    return max(0, existing + max(new_n, 0) - INSURANCE_LAB_TEST_LIMIT)


def extra_reason_and_diagnosis_from_request(request) -> tuple[str, str]:
    post = getattr(request, 'POST', {}) or {}
    reason = (post.get('extra_lab_reason') or '').strip()
    diagnosis = (
        post.get('extra_lab_diagnosis')
        or post.get('diagnosis_name')
        or post.get('lab_diagnosis')
        or ''
    ).strip()
    return reason, diagnosis


def require_insurance_extra_lab_justification(
    encounter,
    new_test_count: int,
    extra_reason: str = '',
    extra_diagnosis: str = '',
) -> tuple[bool, str]:
    """
    Returns (ok, error_message). Cash/corporate and batches within the cap pass.
    """
    extras = extra_lab_count(encounter, new_test_count)
    if extras <= 0:
        return True, ''
    if not encounter_is_insurance_lab_limited(encounter):
        return True, ''

    reason = (extra_reason or '').strip()
    diagnosis = (extra_diagnosis or '').strip()
    if not diagnosis:
        try:
            from hospital.lab_order_diagnosis import encounter_diagnosis_summary

            diagnosis = (encounter_diagnosis_summary(encounter) or '').strip()
        except Exception:
            diagnosis = ''

    missing = []
    if len(reason) < EXTRA_LAB_REASON_MIN_LEN:
        missing.append('a reason')
    if len(diagnosis) < 2:
        missing.append('a diagnosis')
    if missing:
        need = ' and '.join(missing)
        return False, f'{EXTRA_LAB_JUSTIFICATION_MSG} Enter {need} for the additional test(s).'
    return True, ''


def require_insurance_lab_limit_from_request(request, encounter, new_test_count: int) -> tuple[bool, str]:
    reason, diagnosis = extra_reason_and_diagnosis_from_request(request)
    return require_insurance_extra_lab_justification(
        encounter,
        new_test_count,
        extra_reason=reason,
        extra_diagnosis=diagnosis,
    )


def annotate_insurance_extra_labs(order, encounter, extra_reason: str = '', extra_diagnosis: str = '') -> None:
    """Attach extra-lab reason/diagnosis onto the order so laboratory can see it.

    Call after lab result rows for this batch exist (so the encounter count is current).
    """
    if not order:
        return
    reason = (extra_reason or '').strip()
    if not reason:
        return
    if not encounter_is_insurance_lab_limited(encounter):
        return
    if count_encounter_lab_tests(encounter) <= INSURANCE_LAB_TEST_LIMIT:
        return

    diagnosis = (extra_diagnosis or '').strip()
    line = f'Insurance extra labs (beyond {INSURANCE_LAB_TEST_LIMIT}): {reason}'
    if diagnosis:
        line = f'{line} | Diagnosis: {diagnosis}'

    notes = (getattr(order, 'notes', None) or '').strip()
    if line not in notes:
        order.notes = f'{notes}\n{line}'.strip() if notes else line

    indication = (getattr(order, 'clinical_indication', None) or '').strip()
    extra_ci = f'Extra tests: {reason}'
    if diagnosis:
        extra_ci = f'{extra_ci} | Diagnosis: {diagnosis}'
    if extra_ci not in indication:
        order.clinical_indication = f'{indication}; {extra_ci}'.strip('; ') if indication else extra_ci

    if getattr(order, 'pk', None):
        order.save(update_fields=['notes', 'clinical_indication'])


def insurance_lab_limit_template_context(encounter) -> dict:
    ordered = count_encounter_lab_tests(encounter)
    limited = encounter_is_insurance_lab_limited(encounter)
    remaining = max(0, INSURANCE_LAB_TEST_LIMIT - ordered) if limited else None
    return {
        'insurance_lab_limit': INSURANCE_LAB_TEST_LIMIT,
        'insurance_lab_limited': limited,
        'insurance_lab_ordered_count': ordered,
        'insurance_lab_remaining': remaining if remaining is not None else INSURANCE_LAB_TEST_LIMIT,
    }
