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

    def __init__(self, *, patient, payer, service_code=None, drug=None, reference_date=None):
        self.patient = patient
        self.payer = payer
        self.service_code = service_code
        self.drug = drug
        self.reference_date = reference_date or timezone.now().date()

    def evaluate(self) -> InsuranceExclusionResult:
        # CRITICAL: Exclusions only apply to insurance patients, NOT cash or corporate
        # Cash patients should never have exclusions applied
        if not self.payer:
            return InsuranceExclusionResult()
        
        # Skip exclusions for cash payers
        if self.payer.payer_type == 'cash':
            return InsuranceExclusionResult()
        
        # Corporate patients may have different rules, but for now we'll apply insurance-style exclusions
        # If you want corporate to also skip exclusions, uncomment the next line:
        # if self.payer.payer_type == 'corporate':
        #     return InsuranceExclusionResult()
        
        enrollment = self._find_active_enrollment()
        if not enrollment:
            return InsuranceExclusionResult()

        rules_qs = self._fetch_candidate_rules(enrollment)

        for rule in rules_qs:
            if not rule.is_effective(self.reference_date):
                continue
            if rule.matches_target(service_code=self.service_code, drug=self.drug):
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

        return qs.select_related('insurance_company', 'insurance_plan', 'service_code', 'drug')





