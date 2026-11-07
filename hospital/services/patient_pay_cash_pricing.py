"""
Cash tariff for insurance patients who pay excess labs and medication themselves.

Covered items stay on the insurance price. When a lab or drug is the patient's
excess (insurance exclusion / patient-pay cash), the cashier collects the cash
price: no insurance markup, still including the 10% sustainability increment.
"""
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


def _invoice_payer(invoice):
    if not invoice:
        return None
    payer = getattr(invoice, 'payer', None)
    if payer is not None:
        return payer
    payer_id = getattr(invoice, 'payer_id', None)
    if not payer_id:
        return None
    try:
        from hospital.models import Payer
        return Payer.objects.filter(pk=payer_id).first()
    except Exception:
        return None


def _is_drug_line(line):
    if getattr(line, 'prescription_id', None) or getattr(line, 'prescription', None):
        return True
    sc = getattr(line, 'service_code', None)
    code = (getattr(sc, 'code', None) or '').strip().upper()
    return code.startswith('DRUG-') or code.startswith('PHARM-')


def _is_lab_line(line):
    sc = getattr(line, 'service_code', None)
    code = (getattr(sc, 'code', None) or '').strip().upper()
    cat = (getattr(sc, 'category', None) or '').strip().lower()
    if code.startswith('LAB-') or code.startswith('LABTEST-'):
        return True
    return cat in ('lab', 'laboratory', 'laboratory services') or 'laboratory' in cat


def patient_pays_lab_or_drug_in_cash(*, patient, payer, drug=None, lab_test=None, service_code=None):
    """
    True when this insurance patient must pay the lab or drug in cash
    (formulary / company exclusion), so the cashier uses the cash tariff.
    """
    from hospital.services.insurance_exclusion_service import (
        InsuranceExclusionService,
        is_insurance_billing_payer,
    )

    if not is_insurance_billing_payer(payer):
        return False
    if not drug and not lab_test and not service_code:
        return False
    try:
        result = InsuranceExclusionService(
            patient=patient,
            payer=payer,
            service_code=service_code,
            drug=drug,
            lab_test=lab_test,
        ).evaluate()
    except Exception:
        logger.exception('insurance excess check failed')
        return False
    return bool(result.requires_patient_pay)


def payer_for_patient_cash_excess(*, patient, payer, drug=None, lab_test=None, service_code=None):
    """
    Payer to use for pricing. None means the cash tariff (no insurance markup).
    """
    if patient_pays_lab_or_drug_in_cash(
        patient=patient,
        payer=payer,
        drug=drug,
        lab_test=lab_test,
        service_code=service_code,
    ):
        return None
    return payer


def line_is_patient_pay_lab_or_drug(line):
    """Insurance invoice line the patient pays in cash for a lab or medication."""
    from hospital.services.insurance_exclusion_service import is_insurance_billing_payer

    if not line or not getattr(line, 'patient_pay_cash', False):
        return False
    if getattr(line, 'waived_at', None):
        return False
    invoice = getattr(line, 'invoice', None)
    if not is_insurance_billing_payer(_invoice_payer(invoice)):
        return False
    return _is_drug_line(line) or _is_lab_line(line)


def cash_unit_price_for_line(line):
    """
    Cash selling price for a patient-pay lab or drug line.
    None when the catalog price cannot be resolved (leave the stored price).
    """
    if not line_is_patient_pay_lab_or_drug(line):
        return None

    from hospital.utils_billing import (
        billed_lab_or_scan_catalog_price,
        get_drug_price_for_prescription,
    )

    price = None
    if _is_drug_line(line):
        from hospital.utils_invoice_line import resolve_drug_for_invoice_line
        drug = resolve_drug_for_invoice_line(line)
        if not drug:
            return None
        price = get_drug_price_for_prescription(drug, payer=None)
    elif _is_lab_line(line):
        from hospital.utils_invoice_line import resolve_lab_test_for_invoice_line
        lab = resolve_lab_test_for_invoice_line(line)
        if not lab:
            return None
        price = billed_lab_or_scan_catalog_price(
            getattr(lab, 'price', None), payer=None, kind='lab',
        )
    if price is None:
        return None
    price = Decimal(str(price)).quantize(Decimal('0.01'))
    if price <= 0:
        return None
    return price


def apply_cash_tariff_to_line_in_memory(line):
    """
    Set unit_price to the cash tariff when this excess line is patient-pay.
    Does not save. Returns True when unit_price changed.
    """
    cash = cash_unit_price_for_line(line)
    if cash is None:
        return False
    current = Decimal(str(getattr(line, 'unit_price', None) or 0)).quantize(Decimal('0.01'))
    if abs(current - cash) <= Decimal('0.02'):
        return False
    line.unit_price = cash
    return True


def _invoice_still_open(invoice):
    status = (getattr(invoice, 'status', '') or '').lower()
    if status in ('paid', 'cancelled'):
        return False
    total = Decimal(str(getattr(invoice, 'total_amount', None) or 0))
    balance = Decimal(str(getattr(invoice, 'balance', None) or 0))
    if total > 0 and balance <= 0:
        return False
    return True


def reprice_invoice_patient_pay_lines(invoice, *, refresh_totals=True):
    """
    Rewrite open patient-pay lab and drug lines on an insurance invoice
    to the cash tariff. Returns how many lines changed.
    """
    from hospital.services.insurance_exclusion_service import is_insurance_billing_payer

    if not invoice or not getattr(invoice, 'pk', None):
        return 0
    if not is_insurance_billing_payer(_invoice_payer(invoice)):
        return 0
    if not _invoice_still_open(invoice):
        return 0

    from hospital.models import InvoiceLine
    from hospital.utils_invoice_line import invoice_line_effective_total

    changed = 0
    lines = InvoiceLine.objects.filter(
        invoice=invoice,
        is_deleted=False,
        patient_pay_cash=True,
        waived_at__isnull=True,
    ).select_related(
        'service_code', 'prescription', 'prescription__drug', 'invoice', 'invoice__payer',
    )
    for line in lines:
        if not apply_cash_tariff_to_line_in_memory(line):
            continue
        line.line_total = invoice_line_effective_total(line)
        InvoiceLine.objects.filter(pk=line.pk).update(
            unit_price=line.unit_price,
            line_total=line.line_total,
        )
        changed += 1
    if changed and refresh_totals:
        try:
            invoice.update_totals()
        except Exception:
            logger.exception(
                'cash tariff refresh failed for invoice %s', getattr(invoice, 'pk', None),
            )
    return changed


def reprice_patient_pay_lines_for_patient(patient):
    """Reprice every open insurance invoice for this patient. Returns lines changed."""
    if not patient or not getattr(patient, 'pk', None):
        return 0
    from hospital.models import Invoice

    changed = 0
    invoices = Invoice.objects.filter(
        patient=patient,
        is_deleted=False,
        payer__payer_type__in=('nhis', 'private', 'insurance'),
    ).exclude(status__in=('paid', 'cancelled')).select_related('payer')
    for invoice in invoices:
        changed += reprice_invoice_patient_pay_lines(invoice)
    return changed
