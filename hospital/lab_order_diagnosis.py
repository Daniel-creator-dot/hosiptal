"""
Diagnosis text attached to lab orders so laboratory staff see clinical context.
"""
from __future__ import annotations


def encounter_diagnosis_summary(encounter) -> str:
    """Build a single-line diagnosis summary for an encounter (for new lab orders)."""
    if not encounter:
        return ''

    lines: list[str] = []
    try:
        from hospital.models_advanced import Diagnosis, ProblemList

        for d in (
            Diagnosis.objects.filter(encounter=encounter, is_deleted=False)
            .select_related('diagnosis_code')
            .order_by('diagnosis_type', '-diagnosis_date')
        ):
            code = (d.icd10_code or '').strip()
            name = (getattr(d, 'diagnosis_name', None) or d.diagnosis or '').strip()
            if name and code:
                lines.append(f'{name} ({code})')
            elif name:
                lines.append(name)
            elif code:
                lines.append(code)

        if not lines:
            for p in ProblemList.objects.filter(
                patient_id=encounter.patient_id,
                status='active',
                is_deleted=False,
            ).order_by('-created')[:10]:
                code = (p.icd10_code or '').strip()
                prob = (p.problem or '').strip()
                if prob and code:
                    lines.append(f'{prob} ({code})')
                elif prob:
                    lines.append(prob)
                elif code:
                    lines.append(code)
    except ImportError:
        pass

    if not lines:
        enc_dx = (getattr(encounter, 'diagnosis', None) or '').strip()
        if enc_dx:
            # Use first non-empty line from encounter free-text diagnosis
            for part in enc_dx.replace('\r', '\n').split('\n'):
                part = part.strip()
                if part:
                    lines.append(part)

    # Deduplicate while preserving order
    seen = set()
    unique: list[str] = []
    for line in lines:
        key = line.lower()
        if key not in seen:
            seen.add(key)
            unique.append(line)
    return '; '.join(unique)


def order_lab_diagnosis_display(order) -> str:
    """Diagnosis / clinical indication shown on lab work lists (stored or live lookup)."""
    if not order:
        return ''

    stored = (getattr(order, 'clinical_indication', None) or '').strip()
    if stored:
        return stored

    encounter = getattr(order, 'encounter', None)
    if encounter:
        live = encounter_diagnosis_summary(encounter)
        if live:
            return live

    notes = (getattr(order, 'notes', None) or '').strip()
    if notes.lower().startswith('diagnosis:'):
        return notes.split('\n', 1)[0].replace('Diagnosis:', '', 1).strip()
    return ''
