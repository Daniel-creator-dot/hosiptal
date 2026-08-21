"""
NHIS formulary: mark drugs, labs, and scans as NHIS-accessible.
Doctors see only covered catalog items; uncovered items are billed as patient cash.
"""
from __future__ import annotations

from typing import Iterable, Optional
from uuid import UUID

from django.db.models import Q, QuerySet

from ..models import Drug

NHIS_FORMULARY_ONLY_MESSAGE = (
    'This drug is not on the NHIS formulary. Choose an NHIS-listed medicine, '
    'or ask pharmacy to mark it as NHIS-covered.'
)
NHIS_SEARCH_EMPTY_HINT = 'No NHIS formulary drugs match this search.'


def is_nhis_payer(payer) -> bool:
    if not payer:
        return False
    payer_type = (getattr(payer, 'payer_type', '') or '').strip().lower()
    if payer_type == 'nhis':
        return True
    name = (getattr(payer, 'name', '') or '').strip().lower()
    if not name:
        return False
    return (
        name == 'nhis'
        or name.startswith('nhis ')
        or 'national health insurance' in name
    )


def payer_from_encounter(encounter):
    if not encounter or not getattr(encounter, 'patient_id', None):
        return None
    from ..utils_billing import get_patient_payer_info

    try:
        return get_patient_payer_info(encounter.patient, encounter).get('payer')
    except Exception:
        return None


def payer_from_patient(patient):
    if not patient:
        return None
    from ..utils_billing import get_patient_payer_info

    try:
        return get_patient_payer_info(patient, None).get('payer')
    except Exception:
        return getattr(patient, 'primary_insurance', None)


def restrict_nhis_covered_queryset(qs: QuerySet, payer) -> QuerySet:
    """NHIS visits only see catalog rows marked nhis_covered."""
    if is_nhis_payer(payer):
        return qs.filter(nhis_covered=True)
    return qs


def restrict_drug_queryset_for_payer(qs: QuerySet, payer) -> QuerySet:
    """NHIS visits only see drugs marked nhis_covered. Cash/other payers see the full list."""
    return restrict_nhis_covered_queryset(qs, payer)


def filter_catalog_items_for_payer(items, payer):
    """In-memory filter for cached lab/scan/drug lists on NHIS visits."""
    seq = list(items or [])
    if not is_nhis_payer(payer):
        return seq
    return [item for item in seq if getattr(item, 'nhis_covered', False)]


def item_is_on_nhis_formulary(item) -> bool:
    return bool(getattr(item, 'nhis_covered', False))


def nhis_uncovered_patient_pay_reason(*, payer, drug=None, lab_test=None, imaging_catalog=None) -> str:
    """Cash-pay reason when an NHIS visit uses a catalog item that is not NHIS-listed."""
    if not is_nhis_payer(payer):
        return ''
    if drug is not None and not item_is_on_nhis_formulary(drug):
        name = getattr(drug, 'name', None) or 'This drug'
        return f'{name} is not on the NHIS formulary — patient pays cash at cashier.'
    if lab_test is not None and not item_is_on_nhis_formulary(lab_test):
        name = getattr(lab_test, 'name', None) or 'This lab test'
        return f'{name} is not on the NHIS lab panel — patient pays cash at cashier.'
    if imaging_catalog is not None and not item_is_on_nhis_formulary(imaging_catalog):
        name = getattr(imaging_catalog, 'name', None) or 'This scan'
        return f'{name} is not on the NHIS scan list — patient pays cash at cashier.'
    return ''


def drug_is_on_nhis_formulary(drug) -> bool:
    return bool(getattr(drug, 'nhis_covered', False))


def nhis_prescribe_block_reason(*, drug, payer) -> str:
    """Return an error message when an NHIS patient cannot receive this drug, else empty."""
    if is_nhis_payer(payer) and not drug_is_on_nhis_formulary(drug):
        name = getattr(drug, 'name', None) or 'This drug'
        return f'{name}: {NHIS_FORMULARY_ONLY_MESSAGE}'
    return ''


def parse_nhis_flag(value) -> bool:
    text = str(value or '').strip().lower()
    return text in {
        '1', 'y', 'yes', 'true', 't', 'on', 'x', 'nhis', 'covered', 'nhis covered',
    }


def parse_nhis_flag_optional(value):
    """Return True/False when the cell is explicit, else None to leave the drug unchanged."""
    if value is None:
        return None
    text = str(value).strip().lower()
    if text == '':
        return None
    if text in {'0', 'n', 'no', 'false', 'f', 'off', 'not covered'}:
        return False
    if parse_nhis_flag(text):
        return True
    return None


def apply_nhis_flags_from_rows(rows: Iterable[dict]) -> dict:
    """
    Update Drug.nhis_covered from import rows.

    Each row may include: id, name, strength, nhis (truthy/falsey).
    Blank NHIS cells are skipped so a partial file does not unmark other drugs.
    Matches by UUID first, then name+strength, then unique name.
    """
    stats = {'updated': 0, 'already': 0, 'unmatched': 0, 'skipped': 0}
    unmatched_names = []

    for raw in rows:
        if not isinstance(raw, dict):
            stats['skipped'] += 1
            continue
        wanted = parse_nhis_flag_optional(raw.get('nhis'))
        if wanted is None:
            stats['skipped'] += 1
            continue
        drug = _match_import_drug(raw)
        if not drug:
            stats['unmatched'] += 1
            unmatched_names.append((raw.get('name') or raw.get('id') or '').strip())
            continue
        if bool(drug.nhis_covered) == wanted:
            stats['already'] += 1
            continue
        drug.nhis_covered = wanted
        drug.save(update_fields=['nhis_covered', 'modified'])
        stats['updated'] += 1

    stats['unmatched_names'] = unmatched_names[:20]
    return stats


def _match_import_drug(raw: dict) -> Optional[Drug]:
    drug_id = str(raw.get('id') or '').strip()
    if drug_id:
        try:
            UUID(drug_id)
            return Drug.objects.filter(pk=drug_id, is_deleted=False).first()
        except (ValueError, TypeError, AttributeError):
            pass

    name = (raw.get('name') or '').strip()
    if not name:
        return None
    strength = (raw.get('strength') or '').strip()
    qs = Drug.objects.filter(is_deleted=False).filter(
        Q(name__iexact=name) | Q(generic_name__iexact=name)
    )
    if strength:
        by_strength = qs.filter(strength__iexact=strength)
        if by_strength.count() == 1:
            return by_strength.first()
        if by_strength.exists():
            return by_strength.order_by('name').first()
    matches = list(qs[:3])
    if len(matches) == 1:
        return matches[0]
    return None
