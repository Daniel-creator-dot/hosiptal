"""
Unified patient search: normalized query, consistent Q objects, and in-memory matching.
"""
from __future__ import annotations

from django.db.models import Q


def normalize_query(q: str) -> str:
    if not q:
        return ''
    return ' '.join(q.split())


def _name_lookups(prefix: str, lookup_suffix: str, value: str) -> Q:
    p = prefix or ''
    return (
        Q(**{f'{p}first_name{lookup_suffix}': value})
        | Q(**{f'{p}middle_name{lookup_suffix}': value})
        | Q(**{f'{p}last_name{lookup_suffix}': value})
    )


def patient_filter_q(raw_query: str, *, prefix: str = '', include_email: bool = False) -> Q:
    """
    Build a Q for filtering patients (direct Patient model or related via prefix e.g. 'patient__').

    - Single string matches against first/middle/last, MRN, national_id, phone (and optionally email).
    - Multi-word: first/last chunk combinations (both orders) plus each token must appear in
      at least one name field (replaces noisy per-word OR across only first/last).
    """
    q = normalize_query(raw_query)
    if not q:
        return Q(pk__in=[])

    p = prefix or ''
    parts = q.split()

    search_q = _name_lookups(p, '__icontains', q) | Q(**{f'{p}mrn__icontains': q}) | Q(
        **{f'{p}national_id__icontains': q}
    ) | Q(**{f'{p}phone_number__icontains': q})
    if include_email:
        search_q |= Q(**{f'{p}email__icontains': q})

    if len(parts) >= 2:
        first_part = parts[0]
        last_parts = ' '.join(parts[1:])
        search_q |= Q(**{f'{p}first_name__icontains': first_part}) & Q(
            **{f'{p}last_name__icontains': last_parts}
        )
        search_q |= Q(**{f'{p}first_name__icontains': last_parts}) & Q(
            **{f'{p}last_name__icontains': first_part}
        )

        token_q: Q | None = None
        for t in parts:
            if not t:
                continue
            clause = (
                Q(**{f'{p}first_name__icontains': t})
                | Q(**{f'{p}middle_name__icontains': t})
                | Q(**{f'{p}last_name__icontains': t})
            )
            token_q = clause if token_q is None else token_q & clause
        if token_q is not None:
            search_q |= token_q

    return search_q


def _phone_digits_match(query_digits: str, phone_digits: str) -> bool:
    if not query_digits or len(query_digits) < 3:
        return False
    if query_digits in phone_digits:
        return True
    if query_digits.startswith('0') and len(query_digits) > 1 and query_digits[1:] in phone_digits:
        return True
    return False


def patient_matches_search(patient, search: str) -> bool:
    """In-memory filter aligned with DB search: substring, multi-word tokens, MRN, phone digits."""
    if not search:
        return True
    if not patient:
        return True

    q = normalize_query(search)
    if not q:
        return True

    ql = q.lower()
    fn = (getattr(patient, 'first_name', None) or '').lower()
    ln = (getattr(patient, 'last_name', None) or '').lower()
    mn = (getattr(patient, 'middle_name', None) or '').lower()
    full = (getattr(patient, 'full_name', None) or f'{fn} {mn} {ln}'.strip()).lower()
    mrn = (getattr(patient, 'mrn', None) or '').lower()

    phone_raw = getattr(patient, 'phone_number', None) or ''
    phone_digits = ''.join(c for c in phone_raw if c.isdigit())
    q_digits = ''.join(c for c in ql if c.isdigit())

    if ql in full or ql in mrn:
        return True
    if _phone_digits_match(q_digits, phone_digits):
        return True

    parts = [t for t in ql.split() if t]
    for t in parts:
        in_name = t in fn or t in mn or t in ln
        in_mrn = t in mrn
        t_digits = ''.join(c for c in t if c.isdigit())
        in_phone = bool(t_digits) and _phone_digits_match(t_digits, phone_digits)
        if not (in_name or in_mrn or in_phone):
            return False
    return True


def patient_encounter_name_q(raw_query: str, *, patient_prefix: str = 'patient__') -> Q:
    """
    Patient name/MRN/phone/national_id for Encounter (and similar) querysets.
    Does not include email (encounters historically searched name + complaint only).
    """
    return patient_filter_q(raw_query, prefix=patient_prefix, include_email=False)


def legacy_patient_filter_q(raw_query: str) -> Q:
    """Same matching rules as patient_filter_q for LegacyPatient (fname/lname/mname/pid/phone/mrn)."""
    q = normalize_query(raw_query)
    if not q:
        return Q(pk__in=[])

    parts = q.split()
    search_q = (
        Q(fname__icontains=q)
        | Q(lname__icontains=q)
        | Q(mname__icontains=q)
        | Q(pid__icontains=q)
        | Q(phone_cell__icontains=q)
        | Q(pmc_mrn__icontains=q)
    )

    if len(parts) >= 2:
        first_part = parts[0]
        last_parts = ' '.join(parts[1:])
        search_q |= Q(fname__icontains=first_part) & Q(lname__icontains=last_parts)
        search_q |= Q(fname__icontains=last_parts) & Q(lname__icontains=first_part)

        token_q: Q | None = None
        for t in parts:
            if not t:
                continue
            clause = Q(fname__icontains=t) | Q(mname__icontains=t) | Q(lname__icontains=t)
            token_q = clause if token_q is None else token_q & clause
        if token_q is not None:
            search_q |= token_q

    return search_q
