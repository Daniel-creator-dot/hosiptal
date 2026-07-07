"""Encounter vitals, diagnosis, and patient safety context for pharmacy dispensing UIs."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from django.db.models import Case, IntegerField, When
from django.utils import timezone


def _clip_text(val: Any, max_len: Optional[int] = None) -> str:
    if val is None:
        s = ''
    elif isinstance(val, str):
        s = val.strip()
    else:
        s = str(val).strip()
    if max_len and len(s) > max_len:
        return s[: max_len - 1] + '…'
    return s


def _diagnosis_type_order() -> Case:
    """Primary before secondary before differential for stable pharmacy display."""
    return Case(
        When(diagnosis_type='primary', then=0),
        When(diagnosis_type='secondary', then=1),
        When(diagnosis_type='differential', then=2),
        default=3,
        output_field=IntegerField(),
    )


def encounter_clinical_snapshot_for_pharmacy(encounter, patient) -> Dict[str, Any]:
    """
    JSON-serializable snapshot: this visit (complaint, diagnosis, vitals, provider)
    plus patient-level allergies, chronic conditions, and home medications from the chart.

    Merges structured EMR data (Diagnosis rows, SOAP notes, problem list, admission)
    so pharmacy sees context even when Encounter.diagnosis free text is empty.
    """
    from .models import VitalSign
    from .models_advanced import ClinicalNote, Diagnosis, ProblemList

    out: Dict[str, Any] = {
        'chief_complaint': '',
        'diagnosis': '',
        'diagnosis_entries': [],
        'diagnosis_summary': '',
        'clinical_assessment': '',
        'clinical_plan': '',
        'active_problems': [],
        'admission_diagnosis': '',
        'encounter_notes': '',
        'provider_name': '',
        'encounter_type': '',
        'visit_started': '',
        'vitals': None,
        'vitals_set_count': 0,
        'patient_allergies': '',
        'patient_chronic_conditions': '',
        'patient_current_medications': '',
        'patient_blood_type': '',
    }
    if patient is not None:
        out['patient_allergies'] = _clip_text(getattr(patient, 'allergies', ''), 4000)
        out['patient_chronic_conditions'] = _clip_text(getattr(patient, 'chronic_conditions', ''), 4000)
        out['patient_current_medications'] = _clip_text(getattr(patient, 'medications', ''), 4000)
        out['patient_blood_type'] = _clip_text(getattr(patient, 'blood_type', ''), 20)

    if encounter is None:
        return out

    out['chief_complaint'] = _clip_text(getattr(encounter, 'chief_complaint', ''), 4000)
    out['diagnosis'] = _clip_text(getattr(encounter, 'diagnosis', ''), 4000)
    out['encounter_notes'] = _clip_text(getattr(encounter, 'notes', ''), 4000)

    prov = getattr(encounter, 'provider', None)
    if prov is not None:
        u = getattr(prov, 'user', None)
        if u is not None:
            nm = (u.get_full_name() or getattr(u, 'username', '') or '').strip()
            out['provider_name'] = nm
        else:
            out['provider_name'] = str(prov)

    et = getattr(encounter, 'encounter_type', '') or ''
    if et and hasattr(encounter, 'get_encounter_type_display'):
        out['encounter_type'] = encounter.get_encounter_type_display()
    else:
        out['encounter_type'] = str(et)

    started = getattr(encounter, 'started_at', None)
    if started:
        out['visit_started'] = timezone.localtime(started).strftime('%Y-%m-%d %H:%M')

    # Structured diagnoses for this encounter (ICD-linked rows)
    diag_entries: List[Dict[str, str]] = []
    for d in (
        Diagnosis.objects.filter(encounter=encounter, is_deleted=False)
        .select_related('diagnosis_code')
        .order_by(_diagnosis_type_order(), '-diagnosis_date', '-created')[:25]
    ):
        label = _clip_text(d.diagnosis_name, 300)
        code = _clip_text(d.display_code, 40)
        dtype = _clip_text(d.diagnosis_type, 50)
        desc = _clip_text(getattr(d, 'description', ''), 500)
        line = label
        if code:
            line = f'{label} ({code})' if label else code
        diag_entries.append(
            {
                'label': label,
                'code': code,
                'type': dtype,
                'description': desc,
                'line': line or label or code,
            }
        )
    out['diagnosis_entries'] = diag_entries
    if diag_entries:
        merged = '; '.join(e['line'] for e in diag_entries if e.get('line'))
        out['diagnosis_summary'] = _clip_text(merged, 4000)
        if not out['diagnosis']:
            out['diagnosis'] = out['diagnosis_summary']

    # Latest SOAP / consultation note (assessment & plan for pharmacy counseling)
    note = (
        ClinicalNote.objects.filter(encounter=encounter, is_deleted=False, note_type='consultation')
        .order_by('-created')
        .first()
    )
    if not note:
        note = (
            ClinicalNote.objects.filter(encounter=encounter, is_deleted=False, note_type='soap')
            .order_by('-created')
            .first()
        )
    if not note:
        note = (
            ClinicalNote.objects.filter(encounter=encounter, is_deleted=False)
            .exclude(note_type='progress')
            .order_by('-created')
            .first()
        )
    if note:
        out['clinical_assessment'] = _clip_text(note.assessment, 4000)
        out['clinical_plan'] = _clip_text(note.plan, 4000)

    # Active problem list (patient-level, capped)
    if patient is not None:
        problems: List[str] = []
        for pl in ProblemList.objects.filter(
            patient=patient,
            is_deleted=False,
            status__in=('active', 'chronic'),
        ).order_by('-created')[:8]:
            ptxt = _clip_text(pl.problem, 200)
            icd = _clip_text(pl.icd10_code, 20)
            if icd and ptxt:
                problems.append(f'{ptxt} ({icd})')
            elif ptxt:
                problems.append(ptxt)
        out['active_problems'] = problems

    # Inpatient admitting diagnosis (if linked)
    try:
        adm = getattr(encounter, 'admission', None)
        if adm is not None and not getattr(adm, 'is_deleted', False):
            parts = []
            dx = _clip_text(getattr(adm, 'diagnosis_icd10', ''), 500)
            if dx:
                parts.append(dx)
            n = _clip_text(getattr(adm, 'notes', ''), 800)
            if n:
                parts.append(n)
            if parts:
                out['admission_diagnosis'] = _clip_text(' — '.join(parts), 2000)
    except Exception:
        pass

    vitals_qs = VitalSign.objects.filter(encounter=encounter, is_deleted=False).order_by('-recorded_at')
    out['vitals_set_count'] = vitals_qs.count()
    latest = vitals_qs.select_related('recorded_by__user').first()
    if not latest:
        return out

    recorder = ''
    if getattr(latest, 'recorded_by_id', None):
        ru = getattr(latest.recorded_by, 'user', None)
        if ru is not None:
            recorder = (ru.get_full_name() or getattr(ru, 'username', '') or '').strip()

    def _fnum(x):
        if x is None:
            return None
        try:
            return float(x)
        except (TypeError, ValueError):
            return None

    out['vitals'] = {
        'recorded_at': timezone.localtime(latest.recorded_at).strftime('%Y-%m-%d %H:%M')
        if latest.recorded_at
        else '',
        'recorded_by': recorder,
        'systolic_bp': latest.systolic_bp,
        'diastolic_bp': latest.diastolic_bp,
        'pulse': latest.pulse,
        'temperature': _fnum(latest.temperature),
        'spo2': latest.spo2,
        'respiratory_rate': latest.respiratory_rate,
        'weight_kg': _fnum(latest.weight),
        'height_cm': _fnum(latest.height),
        'blood_glucose': _fnum(latest.blood_glucose),
        'poc_glucose_strip_type': getattr(latest, 'poc_glucose_strip_type', '') or '',
        'news2_score': latest.news2_score,
        'mews_score': latest.mews_score,
        'consciousness': latest.get_consciousness_level_display()
        if hasattr(latest, 'get_consciousness_level_display')
        else (latest.consciousness_level or ''),
        'pain_score': latest.pain_score,
        'supplemental_oxygen': bool(latest.supplemental_oxygen),
        'oxygen_flow_rate': _fnum(latest.oxygen_flow_rate),
        'is_critical': bool(latest.is_critical),
        'requires_escalation': bool(latest.requires_escalation),
        'notes': _clip_text(getattr(latest, 'notes', ''), 800),
    }
    return out
