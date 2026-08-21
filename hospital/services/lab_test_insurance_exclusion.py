"""
Sync lab-catalog insurance exclusions: all insurers or selected companies only.
"""
from __future__ import annotations

from typing import Iterable, Sequence
from uuid import UUID

from ..models import LabTest
from ..models_insurance_companies import InsuranceCompany, InsuranceExclusionRule
from .drug_formulary_insurance_exclusion import resolve_insurance_company_for_payer

FORMULARY_LAB_EXCLUSION_NOTE = 'formulary-lab-insurance-exclusion'


def _default_reason(lab_test: LabTest) -> str:
    return f'{lab_test.name} is not covered by insurance — patient must pay cash.'


def formulary_managed_lab_rules_qs(*, lab_test: LabTest):
    return InsuranceExclusionRule.objects.filter(
        lab_test=lab_test,
        rule_type='lab_test',
        notes=FORMULARY_LAB_EXCLUSION_NOTE,
        is_deleted=False,
    )


def selected_lab_formulary_company_ids(*, lab_test: LabTest) -> list[UUID]:
    return list(
        formulary_managed_lab_rules_qs(lab_test=lab_test)
        .values_list('insurance_company_id', flat=True)
    )


def lab_test_has_any_insurance_exclusion(*, lab_test: LabTest) -> bool:
    if getattr(lab_test, 'exclude_from_insurance', False):
        return True
    return formulary_managed_lab_rules_qs(lab_test=lab_test).filter(is_active=True).exists()


def lab_test_excluded_for_payer(*, lab_test: LabTest, payer) -> tuple[bool, str]:
    """Return (is_excluded, reason) for an insurance billing payer."""
    from .insurance_exclusion_service import is_insurance_billing_payer

    if not lab_test or not is_insurance_billing_payer(payer):
        return False, ''

    reason = (getattr(lab_test, 'insurance_exclusion_reason', '') or '').strip()

    if getattr(lab_test, 'exclude_from_insurance', False):
        return True, reason or _default_reason(lab_test)

    company = resolve_insurance_company_for_payer(payer)
    if not company:
        return False, ''

    rule = (
        formulary_managed_lab_rules_qs(lab_test=lab_test)
        .filter(insurance_company=company, is_active=True)
        .first()
    )
    if not rule:
        return False, ''

    rule_reason = (rule.reason or '').strip()
    return True, rule_reason or reason or _default_reason(lab_test)


def sync_lab_test_insurance_exclusions(
    *,
    lab_test: LabTest,
    exclude_all: bool,
    company_ids: Sequence[UUID | str],
    reason: str = '',
) -> None:
    """
    Persist catalog insurance exclusion settings for a lab test.

    - exclude_all=True: global flag on test; per-company rules cleared.
    - exclude_all=False with company_ids: global flag off; sync per-company rules.
    - exclude_all=False with no companies: clear all exclusions.
    """
    reason = (reason or '').strip()[:255]
    normalized_ids = {UUID(str(cid)) for cid in company_ids if cid}

    if exclude_all:
        lab_test.exclude_from_insurance = True
        lab_test.insurance_exclusion_reason = reason
        lab_test.save(update_fields=['exclude_from_insurance', 'insurance_exclusion_reason', 'modified'])
        _soft_delete_formulary_rules(lab_test=lab_test, keep_company_ids=())
        return

    lab_test.exclude_from_insurance = False
    lab_test.insurance_exclusion_reason = reason
    lab_test.save(update_fields=['exclude_from_insurance', 'insurance_exclusion_reason', 'modified'])

    if not normalized_ids:
        _soft_delete_formulary_rules(lab_test=lab_test, keep_company_ids=())
        return

    valid_company_ids = set(
        InsuranceCompany.objects.filter(
            id__in=normalized_ids,
            is_deleted=False,
            is_active=True,
        ).values_list('id', flat=True)
    )
    _soft_delete_formulary_rules(lab_test=lab_test, keep_company_ids=valid_company_ids)

    rule_reason = reason or _default_reason(lab_test)
    for company_id in valid_company_ids:
        rule = (
            formulary_managed_lab_rules_qs(lab_test=lab_test)
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
            lab_test=lab_test,
            rule_type='lab_test',
            apply_to_all_plans=True,
            enforcement_action='patient_pay',
            reason=rule_reason,
            notes=FORMULARY_LAB_EXCLUSION_NOTE,
            is_active=True,
        )


def _soft_delete_formulary_rules(*, lab_test: LabTest, keep_company_ids: Iterable[UUID]) -> None:
    keep = set(keep_company_ids)
    for rule in formulary_managed_lab_rules_qs(lab_test=lab_test):
        if rule.insurance_company_id not in keep:
            rule.is_deleted = True
            rule.save(update_fields=['is_deleted', 'modified'])
