"""
Centralized logic for evaluating insurance exclusion rules.
"""
from dataclasses import dataclass
from typing import Optional

from django.db.models import Q
from django.utils import timezone

from ..models_insurance_companies import (
    PatientInsurance,
    InsuranceExclusionRule,
)


INSURANCE_PAYER_TYPES = frozenset({'nhis', 'private', 'insurance'})


def is_insurance_billing_payer(payer) -> bool:
    """True for NHIS/private insurance payers; corporate and cash are excluded."""
    if not payer:
        return False
    return (getattr(payer, 'payer_type', 'cash') or 'cash').strip().lower() in INSURANCE_PAYER_TYPES


@dataclass
class InsuranceExclusionResult:
    is_excluded: bool = False
    enforcement: str = 'allow'
    reason: str = ''
    rule: Optional[InsuranceExclusionRule] = None
    patient_insurance: Optional[PatientInsurance] = None

    @property
    def should_block(self) -> bool:
        return self.is_excluded and self.enforcement == 'block'

    @property
    def requires_patient_pay(self) -> bool:
        return self.is_excluded and self.enforcement == 'patient_pay'


class InsuranceExclusionService:
    """
    Helper that finds applicable exclusion rules for a given patient/payer context.
    """

    def __init__(self, *, patient, payer, service_code=None, drug=None, lab_test=None, reference_date=None):
        self.patient = patient
        self.payer = payer
        self.service_code = service_code
        self.drug = drug
        self.lab_test = lab_test
        self.reference_date = reference_date or timezone.now().date()

    def evaluate(self) -> InsuranceExclusionResult:
        # Exclusions apply to insurance patients only — not cash or corporate
        if not self.payer:
            return InsuranceExclusionResult()

        payer_type = (getattr(self.payer, 'payer_type', 'cash') or 'cash').strip().lower()
        if payer_type in ('cash', 'corporate'):
            return InsuranceExclusionResult()

        lab_test = self.lab_test
        if not lab_test and self.service_code:
            try:
                from ..utils_invoice_line import resolve_lab_test_for_service_code
                lab_test = resolve_lab_test_for_service_code(self.service_code)
            except Exception:
                lab_test = None

        imaging_catalog = getattr(self, 'imaging_catalog', None)
        if not imaging_catalog and self.service_code:
            try:
                from ..utils_invoice_line import resolve_imaging_catalog_for_invoice_line
                class _Line:
                    pass
                line = _Line()
                line.service_code = self.service_code
                imaging_catalog = resolve_imaging_catalog_for_invoice_line(line)
            except Exception:
                imaging_catalog = None

        # Formulary-level exclusion — drugs (all insurers or selected companies)
        if self.drug:
            from .drug_formulary_insurance_exclusion import drug_excluded_for_payer
            from .nhis_drug_formulary import nhis_uncovered_patient_pay_reason
            nhis_reason = nhis_uncovered_patient_pay_reason(payer=self.payer, drug=self.drug)
            if nhis_reason:
                return InsuranceExclusionResult(
                    is_excluded=True,
                    enforcement='patient_pay',
                    reason=nhis_reason,
                    rule=None,
                )
            excluded, reason = drug_excluded_for_payer(drug=self.drug, payer=self.payer)
            if excluded:
                return InsuranceExclusionResult(
                    is_excluded=True,
                    enforcement='patient_pay',
                    reason=reason,
                    rule=None,
                )

        # Formulary-level exclusion — lab tests (all insurers or selected companies)
        if lab_test:
            from .lab_test_insurance_exclusion import lab_test_excluded_for_payer
            from .nhis_drug_formulary import nhis_uncovered_patient_pay_reason
            nhis_reason = nhis_uncovered_patient_pay_reason(payer=self.payer, lab_test=lab_test)
            if nhis_reason:
                return InsuranceExclusionResult(
                    is_excluded=True,
                    enforcement='patient_pay',
                    reason=nhis_reason,
                    rule=None,
                )
            excluded, reason = lab_test_excluded_for_payer(lab_test=lab_test, payer=self.payer)
            if excluded:
                return InsuranceExclusionResult(
                    is_excluded=True,
                    enforcement='patient_pay',
                    reason=reason,
                    rule=None,
                )

        if imaging_catalog:
            from .nhis_drug_formulary import nhis_uncovered_patient_pay_reason
            nhis_reason = nhis_uncovered_patient_pay_reason(payer=self.payer, imaging_catalog=imaging_catalog)
            if nhis_reason:
                return InsuranceExclusionResult(
                    is_excluded=True,
                    enforcement='patient_pay',
                    reason=nhis_reason,
                    rule=None,
                )

        # Corporate patients are not subject to insurance exclusions (handled above).

        enrollment = self._find_active_enrollment()
        if not enrollment:
            return InsuranceExclusionResult()

        rules_qs = self._fetch_candidate_rules(enrollment)

        for rule in rules_qs:
            if not rule.is_effective(self.reference_date):
                continue
            if rule.matches_target(service_code=self.service_code, drug=self.drug, lab_test=lab_test):
                reason = rule.formatted_reason(service_code=self.service_code, drug=self.drug)
                return InsuranceExclusionResult(
                    is_excluded=rule.enforcement_action in ['block', 'patient_pay'],
                    enforcement=rule.enforcement_action,
                    reason=reason,
                    rule=rule,
                    patient_insurance=enrollment,
                )

        return InsuranceExclusionResult()

    def _find_active_enrollment(self) -> Optional[PatientInsurance]:
        if not self.patient or not self.payer:
            return None

        qs = PatientInsurance.objects.filter(
            patient=self.patient,
            insurance_company__name__iexact=self.payer.name,
            status='active',
            is_deleted=False,
            effective_date__lte=self.reference_date,
        ).filter(
            Q(expiry_date__isnull=True) | Q(expiry_date__gte=self.reference_date)
        ).order_by('-is_primary', '-effective_date')

        return qs.first()

    def _fetch_candidate_rules(self, enrollment: PatientInsurance):
        qs = InsuranceExclusionRule.objects.filter(
            insurance_company=enrollment.insurance_company,
            is_active=True,
            is_deleted=False,
        )

        # Limit to plan if specified
        if enrollment.insurance_plan:
            qs = qs.filter(
                Q(apply_to_all_plans=True) |
                Q(insurance_plan=enrollment.insurance_plan) |
                Q(insurance_plan__isnull=True)
            )
        else:
            qs = qs.filter(
                Q(apply_to_all_plans=True) |
                Q(insurance_plan__isnull=True)
            )

        return qs.select_related('insurance_company', 'insurance_plan', 'service_code', 'drug', 'lab_test')


def catalog_exclusion_info(*, item, payer=None) -> dict:
    """
    Exclusion metadata for Drug or LabTest rows (autocomplete / consultation UI).
    is_insurance_excluded is True when the item is excluded for this payer (insurance only).
    """
    from ..models import Drug, LabTest
    from .nhis_drug_formulary import nhis_uncovered_patient_pay_reason

    reason = (getattr(item, 'insurance_exclusion_reason', '') or '').strip()
    payer_is_insurance = is_insurance_billing_payer(payer)

    nhis_kwargs = {}
    if isinstance(item, Drug):
        nhis_kwargs['drug'] = item
    elif isinstance(item, LabTest):
        nhis_kwargs['lab_test'] = item
    else:
        try:
            from ..models_advanced import ImagingCatalog
            if isinstance(item, ImagingCatalog):
                nhis_kwargs['imaging_catalog'] = item
        except Exception:
            pass
    nhis_reason = nhis_uncovered_patient_pay_reason(payer=payer, **nhis_kwargs) if nhis_kwargs else ''
    if nhis_reason:
        return {
            'exclude_from_insurance': True,
            'is_insurance_excluded': True,
            'insurance_exclusion_reason': nhis_reason,
        }

    if isinstance(item, Drug):
        from .drug_formulary_insurance_exclusion import (
            drug_excluded_for_payer,
            drug_has_any_insurance_exclusion,
        )
        has_config = drug_has_any_insurance_exclusion(drug=item)
        if payer_is_insurance:
            excluded, payer_reason = drug_excluded_for_payer(drug=item, payer=payer)
            return {
                'exclude_from_insurance': has_config,
                'is_insurance_excluded': excluded,
                'insurance_exclusion_reason': payer_reason if excluded else '',
            }
        return {
            'exclude_from_insurance': has_config,
            'is_insurance_excluded': False,
            'insurance_exclusion_reason': reason if has_config else '',
        }

    if isinstance(item, LabTest):
        from .lab_test_insurance_exclusion import (
            lab_test_excluded_for_payer,
            lab_test_has_any_insurance_exclusion,
        )
        has_config = lab_test_has_any_insurance_exclusion(lab_test=item)
        if payer_is_insurance:
            excluded, payer_reason = lab_test_excluded_for_payer(lab_test=item, payer=payer)
            return {
                'exclude_from_insurance': has_config,
                'is_insurance_excluded': excluded,
                'insurance_exclusion_reason': payer_reason if excluded else '',
            }
        return {
            'exclude_from_insurance': has_config,
            'is_insurance_excluded': False,
            'insurance_exclusion_reason': reason if has_config else '',
        }

    excluded = bool(getattr(item, 'exclude_from_insurance', False))
    if not excluded:
        return {
            'exclude_from_insurance': False,
            'is_insurance_excluded': False,
            'insurance_exclusion_reason': '',
        }
    if not reason:
        name = getattr(item, 'name', 'This item')
        reason = f'{name} is not covered by insurance — patient must pay cash.'
    return {
        'exclude_from_insurance': True,
        'is_insurance_excluded': payer_is_insurance,
        'insurance_exclusion_reason': reason,
    }





