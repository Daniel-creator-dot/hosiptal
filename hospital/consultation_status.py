"""
Shared consultation workflow helpers for diagnosis requirements and pharmacy gating.

Diagnosis stages:
- Preliminary (working): required before lab / imaging orders.
- Final: required before completing the consultation (after investigations).
"""


LAB_DIAGNOSIS_REQUIRED_MSG = (
    'Add a preliminary diagnosis for this visit before ordering lab tests.'
)
IMAGING_DIAGNOSIS_REQUIRED_MSG = (
    'Add a preliminary diagnosis for this visit before ordering imaging.'
)
FINAL_DIAGNOSIS_REQUIRED_MSG = (
    'Add a final diagnosis before completing the consultation '
    '(after reviewing lab/imaging results).'
)

# Types that satisfy the pre-investigation (preliminary) gate.
# Legacy primary/secondary/differential still count so older visits keep working.
PRELIMINARY_DIAGNOSIS_TYPES = frozenset({
    'preliminary',
    'provisional',
    'primary',
    'secondary',
    'differential',
    'final',  # final also implies a clinical diagnosis exists
})
FINAL_DIAGNOSIS_TYPES = frozenset({'final'})


def encounter_has_diagnosis(encounter) -> bool:
    """
    True when this encounter has at least one diagnosis recorded for the visit
    (any stage). Used as a general "has diagnosis" check.
    """
    return encounter_has_preliminary_diagnosis(encounter)


def encounter_has_preliminary_diagnosis(encounter) -> bool:
    """
    True when the visit has a working/preliminary diagnosis suitable for
    ordering investigations (lab/imaging).
    """
    if not encounter:
        return False
    if (getattr(encounter, 'diagnosis', None) or '').strip():
        return True
    try:
        from hospital.models_advanced import Diagnosis, ProblemList

        if Diagnosis.objects.filter(
            encounter=encounter,
            is_deleted=False,
            diagnosis_type__in=PRELIMINARY_DIAGNOSIS_TYPES,
        ).exists():
            return True
        # Untyped / unexpected types still count as preliminary for safety
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


def encounter_has_final_diagnosis(encounter) -> bool:
    """True when at least one final diagnosis is recorded for the visit."""
    if not encounter:
        return False
    try:
        from hospital.models_advanced import Diagnosis

        return Diagnosis.objects.filter(
            encounter=encounter,
            is_deleted=False,
            diagnosis_type__in=FINAL_DIAGNOSIS_TYPES,
        ).exists()
    except Exception:
        return False


def add_encounter_diagnosis(
    encounter,
    doctor=None,
    diagnosis_name='',
    icd10_code='',
    diagnosis_type='preliminary',
    description='',
):
    """
    Record a visit diagnosis (ProblemList + Diagnosis + encounter.diagnosis text).
    Returns the display name, or '' if nothing to add.
    """
    name = (diagnosis_name or '').strip()
    code = (icd10_code or '').strip()
    if not name and not code:
        return ''
    if not encounter:
        return ''

    from hospital.models_advanced import Diagnosis, ProblemList

    dtype = (diagnosis_type or 'preliminary').strip().lower() or 'preliminary'
    if dtype in ('provisional', 'working'):
        dtype = 'preliminary'
    if dtype not in (
        'preliminary', 'final', 'primary', 'secondary', 'differential'
    ):
        dtype = 'preliminary'

    display = name or code
    diagnosis_code_obj = None
    if code:
        try:
            from hospital.models_diagnosis import DiagnosisCode

            diagnosis_code_obj = DiagnosisCode.objects.filter(
                code=code,
                is_active=True,
                is_deleted=False,
            ).first()
            if diagnosis_code_obj:
                display = (
                    diagnosis_code_obj.short_description
                    or diagnosis_code_obj.description
                    or display
                )
                try:
                    diagnosis_code_obj.increment_usage()
                except Exception:
                    pass
        except Exception:
            diagnosis_code_obj = None

    ProblemList.objects.create(
        patient=encounter.patient,
        encounter=encounter,
        icd10_code=code,
        problem=display,
        description=(description or '').strip(),
        status='active',
        created_by=doctor,
    )
    Diagnosis.objects.create(
        encounter=encounter,
        patient=encounter.patient,
        icd10_code=code,
        diagnosis_code=diagnosis_code_obj,
        diagnosis=display,
        diagnosis_type=dtype,
        description=(description or '').strip(),
        diagnosed_by=doctor,
    )
    stage_tag = ' [Final]' if dtype == 'final' else ' [Preliminary]' if dtype == 'preliminary' else ''
    if code:
        line = f'{display} ({code}){stage_tag}'
    else:
        line = f'{display}{stage_tag}'
    encounter.diagnosis = f'{encounter.diagnosis or ""}\n{line}'.strip()
    encounter.save(update_fields=['diagnosis'])
    return display


def require_diagnosis_for_lab_order(encounter, doctor=None, diagnosis_name='', icd10_code=''):
    """
    Ensure a preliminary (working) diagnosis exists before lab orders.
    If none exists and diagnosis_name/icd10_code is provided, create as preliminary.
    Returns (ok, message).
    """
    if encounter_has_preliminary_diagnosis(encounter):
        return True, ''
    name = (diagnosis_name or '').strip()
    code = (icd10_code or '').strip()
    if name or code:
        try:
            add_encounter_diagnosis(
                encounter,
                doctor=doctor,
                diagnosis_name=name,
                icd10_code=code,
                diagnosis_type='preliminary',
            )
        except Exception:
            return False, LAB_DIAGNOSIS_REQUIRED_MSG
        if encounter_has_preliminary_diagnosis(encounter):
            return True, ''
    return False, LAB_DIAGNOSIS_REQUIRED_MSG


def require_diagnosis_for_imaging_order(encounter, doctor=None, diagnosis_name='', icd10_code=''):
    """Same as lab gate, for imaging orders."""
    if encounter_has_preliminary_diagnosis(encounter):
        return True, ''
    name = (diagnosis_name or '').strip()
    code = (icd10_code or '').strip()
    if name or code:
        try:
            add_encounter_diagnosis(
                encounter,
                doctor=doctor,
                diagnosis_name=name,
                icd10_code=code,
                diagnosis_type='preliminary',
            )
        except Exception:
            return False, IMAGING_DIAGNOSIS_REQUIRED_MSG
        if encounter_has_preliminary_diagnosis(encounter):
            return True, ''
    return False, IMAGING_DIAGNOSIS_REQUIRED_MSG


def require_final_diagnosis_for_complete(encounter, doctor=None, diagnosis_name='', icd10_code=''):
    """
    Ensure a final diagnosis exists before completing consultation.
    If diagnosis_name is provided, create/record it as final.
    Returns (ok, message).
    """
    if encounter_has_final_diagnosis(encounter):
        return True, ''
    name = (diagnosis_name or '').strip()
    code = (icd10_code or '').strip()
    if name or code:
        try:
            add_encounter_diagnosis(
                encounter,
                doctor=doctor,
                diagnosis_name=name,
                icd10_code=code,
                diagnosis_type='final',
            )
        except Exception:
            return False, FINAL_DIAGNOSIS_REQUIRED_MSG
        if encounter_has_final_diagnosis(encounter):
            return True, ''
    return False, FINAL_DIAGNOSIS_REQUIRED_MSG


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
