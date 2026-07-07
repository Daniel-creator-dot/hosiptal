"""
Sync drug formulary insurance exclusions: all insurers or selected companies only.
"""
from __future__ import annotations

from typing import Iterable, Optional, Sequence
from uuid import UUID

from ..models import Drug
from ..models_insurance_companies import InsuranceCompany, InsuranceExclusionRule

FORMULARY_DRUG_EXCLUSION_NOTE = 'formulary-drug-insurance-exclusion'


def _default_reason(drug: Drug) -> str:
    return f'{drug.name} is not covered by insurance — patient must pay cash.'


def formulary_managed_rules_qs(*, drug: Drug):
    return InsuranceExclusionRule.objects.filter(
        drug=drug,
        rule_type='drug',
        notes=FORMULARY_DRUG_EXCLUSION_NOTE,
        is_deleted=False,
    )


def selected_formulary_company_ids(*, drug: Drug) -> list[UUID]:
    return list(
        formulary_managed_rules_qs(drug=drug)
        .values_list('insurance_company_id', flat=True)
    )


def drug_has_any_insurance_exclusion(*, drug: Drug) -> bool:
    if getattr(drug, 'exclude_from_insurance', False):
        return True
    return formulary_managed_rules_qs(drug=drug).filter(is_active=True).exists()


def resolve_insurance_company_for_payer(payer) -> Optional[InsuranceCompany]:
    if not payer or not getattr(payer, 'name', None):
        return None
    return (
        InsuranceCompany.objects.filter(
            name__iexact=(payer.name or '').strip(),
            is_deleted=False,
            is_active=True,
        )
        .order_by('-status')
        .first()
    )


def drug_excluded_for_payer(*, drug: Drug, payer) -> tuple[bool, str]:
    """Return (is_excluded, reason) for an insurance billing payer."""
    from .insurance_exclusion_service import is_insurance_billing_payer

    if not drug or not is_insurance_billing_payer(payer):
        return False, ''

    reason = (getattr(drug, 'insurance_exclusion_reason', '') or '').strip()

    if getattr(drug, 'exclude_from_insurance', False):
        return True, reason or _default_reason(drug)

    company = resolve_insurance_company_for_payer(payer)
    if not company:
        return False, ''

    rule = (
        formulary_managed_rules_qs(drug=drug)
        .filter(insurance_company=company, is_active=True)
        .select_related('insurance_company')
        .first()
    )
    if not rule:
        return False, ''

    rule_reason = (rule.reason or '').strip()
    return True, rule_reason or reason or _default_reason(drug)


def sync_drug_formulary_insurance_exclusions(
    *,
    drug: Drug,
    exclude_all: bool,
    company_ids: Sequence[UUID | str],
    reason: str = '',
) -> None:
    """
    Persist formulary insurance exclusion settings for a drug.

    - exclude_all=True: global flag on drug; per-company formulary rules cleared.
    - exclude_all=False with company_ids: global flag off; sync per-company rules.
    - exclude_all=False with no companies: clear all exclusions.
    """
    reason = (reason or '').strip()[:255]
    normalized_ids = {UUID(str(cid)) for cid in company_ids if cid}

    if exclude_all:
        drug.exclude_from_insurance = True
        drug.insurance_exclusion_reason = reason
        drug.save(update_fields=['exclude_from_insurance', 'insurance_exclusion_reason', 'modified'])
        _soft_delete_formulary_rules(drug=drug, keep_company_ids=())
        return

    drug.exclude_from_insurance = False
    drug.insurance_exclusion_reason = reason
    drug.save(update_fields=['exclude_from_insurance', 'insurance_exclusion_reason', 'modified'])

    if not normalized_ids:
        _soft_delete_formulary_rules(drug=drug, keep_company_ids=())
        return

    valid_company_ids = set(
        InsuranceCompany.objects.filter(
            id__in=normalized_ids,
            is_deleted=False,
            is_active=True,
        ).values_list('id', flat=True)
    )
    _soft_delete_formulary_rules(drug=drug, keep_company_ids=valid_company_ids)

    rule_reason = reason or _default_reason(drug)
    for company_id in valid_company_ids:
        rule = (
            formulary_managed_rules_qs(drug=drug)
            .filter(insurance_company_id=company_id)
            .first()
        )
        if rule:
            changed = False
            if not rule.is_active:
                rule.is_active = True
                changed = True
            if rule.reason != rule_reason:
                rule.reason = rule_reason
                changed = True
            if rule.enforcement_action != 'patient_pay':
                rule.enforcement_action = 'patient_pay'
                changed = True
            if changed:
                rule.save()
            continue

        InsuranceExclusionRule.objects.create(
            insurance_company_id=company_id,
            drug=drug,
            rule_type='drug',
            apply_to_all_plans=True,
            enforcement_action='patient_pay',
            reason=rule_reason,
            notes=FORMULARY_DRUG_EXCLUSION_NOTE,
            is_active=True,
        )


def _soft_delete_formulary_rules(*, drug: Drug, keep_company_ids: Iterable[UUID]) -> None:
    keep = set(keep_company_ids)
    for rule in formulary_managed_rules_qs(drug=drug):
        if rule.insurance_company_id not in keep:
            rule.is_deleted = True
            rule.save(update_fields=['is_deleted', 'modified'])
