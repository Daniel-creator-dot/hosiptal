"""
Shared consultation workflow helpers for diagnosis requirements and pharmacy gating.
"""


def encounter_has_diagnosis(encounter) -> bool:
    """
    True when this encounter has at least one diagnosis recorded for the visit.

    Counts encounter.diagnosis text, Diagnosis rows, or ProblemList rows linked
    to this encounter. Prior-visit patient problems alone do not count.
    """
    if not encounter:
        return False
    if (getattr(encounter, 'diagnosis', None) or '').strip():
        return True
    try:
        from hospital.models_advanced import Diagnosis, ProblemList

        if Diagnosis.objects.filter(encounter=encounter, is_deleted=False).exists():
            return True
        if ProblemList.objects.filter(
            encounter=encounter,
            is_deleted=False,
        ).exists():
            return True
    except Exception:
        pass
    return False


def prescription_is_start_dose(prescription) -> bool:
    return bool(getattr(prescription, 'is_start_dose', False))


def encounter_consultation_complete(encounter) -> bool:
    """
    True when pharmacy may treat OPD prescriptions as released.

    IPD (active admission) is always complete for pharmacy purposes.
    OPD requires encounter.status == 'completed' or ended_at set.
    """
    if not encounter:
        return False
    from hospital.services.auto_billing_service import AutoBillingService

    if AutoBillingService._encounter_is_inpatient_active(encounter):
        return True
    return (
        getattr(encounter, 'status', None) == 'completed'
        or bool(getattr(encounter, 'ended_at', None))
    )
