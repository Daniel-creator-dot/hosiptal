"""
Cascade prescription changes to pharmacy, invoice, and cashier.
When a doctor deletes or edits a prescription, this service ensures:
- Invoice lines for that prescription are waived (so cashier/invoice no longer charge for it)
- Pharmacy dispensing record is cancelled so it drops from pharmacy queue
"""
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


def cascade_prescription_deleted(prescription, waived_by_user=None):
    """
    Call when a prescription is soft-deleted. Waives invoice lines and cancels
    pharmacy dispensing so the change is reflected in pharmacy, invoice, and cashier.

    Args:
        prescription: Prescription instance (may already have is_deleted=True)
        waived_by_user: User to record as waiver author (optional)

    Returns:
        dict with keys: lines_waived (int), dispensing_cancelled (bool), message (str)
    """
    from hospital.models import InvoiceLine
    from hospital.models_payment_verification import PharmacyDispensing

    lines_waived = 0
    dispensing_cancelled = False

    try:
        # Waive all invoice lines linked to this prescription (cashier/invoice no longer show charge)
        qs = InvoiceLine.objects.filter(
            prescription=prescription,
            is_deleted=False,
            waived_at__isnull=True,
        ).select_related("invoice")
        invoice_ids = set()
        for line in qs:
            line.waived_at = timezone.now()
            line.waiver_reason = "Prescription removed by doctor"
            if waived_by_user:
                line.waived_by = waived_by_user
            # Full save so waived line_total/discount_amount persist (see InvoiceLine.save).
            line.save()
            lines_waived += 1
            if line.invoice_id:
                invoice_ids.add(line.invoice_id)
        for inv_id in invoice_ids:
            try:
                from hospital.models import Invoice
                inv_obj = Invoice.all_objects.filter(pk=inv_id).first()
                if inv_obj and hasattr(inv_obj, "update_totals"):
                    inv_obj.update_totals()
            except Exception as e:
                logger.warning("Could not update totals for invoice %s: %s", inv_id, e)

        # Cancel pharmacy dispensing so it drops from pharmacy queue
        try:
            try:
                disp = prescription.dispensing_record
            except Exception:
                disp = None
            if disp and not getattr(disp, "is_dispensed", False):
                disp.dispensing_status = "cancelled"
                disp.quantity_ordered = 0
                disp.save(update_fields=["dispensing_status", "quantity_ordered", "modified"])
                dispensing_cancelled = True
        except Exception as e:
            logger.warning("Could not cancel pharmacy dispensing for prescription %s: %s", prescription.pk, e)

        msg = f"Waived {lines_waived} invoice line(s), cancelled pharmacy dispensing."
        logger.info("Prescription cascade delete: rx=%s %s", prescription.pk, msg)
        return {"lines_waived": lines_waived, "dispensing_cancelled": dispensing_cancelled, "message": msg}
    except Exception as e:
        logger.exception("Error cascading prescription delete for %s: %s", prescription.pk, e)
        return {"lines_waived": lines_waived, "dispensing_cancelled": dispensing_cancelled, "message": str(e)}


def cascade_prescription_updated(prescription, waived_by_user=None):
    """
    Call after a prescription is updated (drug, quantity, dose, frequency, duration).
    Updates invoice line and pharmacy dispensing to match, if they exist and are not yet paid/dispensed.

    Args:
        prescription: Prescription instance (already saved with new values)
        waived_by_user: User for audit (optional)

    Returns:
        dict with keys: invoice_updated (bool), dispensing_updated (bool), message (str)
    """
    from hospital.models import InvoiceLine
    from hospital.models_payment_verification import PharmacyDispensing
    from decimal import Decimal

    invoice_updated = False
    dispensing_updated = False

    try:
        drug = prescription.drug
        qty = int(prescription.quantity or 0)

        # Update invoice line if present and not waived/paid
        line = (
            InvoiceLine.objects.filter(
                prescription=prescription,
                is_deleted=False,
                waived_at__isnull=True,
            )
            .select_related("invoice")
            .first()
        )
        if line and line.invoice and getattr(line.invoice, "status", None) != "paid":
            # Recompute quantity and line_total; keep existing unit_price when set (locked quote).
            line.quantity = Decimal(str(qty))
            if getattr(line, "unit_price", None) is None or line.unit_price == 0:
                from hospital.utils_billing import get_drug_price_for_prescription

                inv_payer = getattr(line.invoice, "payer", None)
                line.unit_price = get_drug_price_for_prescription(drug, payer=inv_payer)
            line.line_total = line.quantity * line.unit_price
            line.description = f"{drug.name} x{qty}"
            line.save(update_fields=["quantity", "unit_price", "line_total", "description", "modified"])
            if hasattr(line.invoice, "update_totals"):
                line.invoice.update_totals()
            invoice_updated = True

        # Update pharmacy dispensing if present and not yet dispensed
        try:
            try:
                disp = prescription.dispensing_record
            except Exception:
                disp = None
            if disp and not getattr(disp, "is_dispensed", False):
                disp.quantity_ordered = qty
                disp.save(update_fields=["quantity_ordered", "modified"])
                dispensing_updated = True
        except Exception:
            pass

        msg = "Invoice and pharmacy updated to match prescription."
        logger.info("Prescription cascade update: rx=%s %s", prescription.pk, msg)
        return {"invoice_updated": invoice_updated, "dispensing_updated": dispensing_updated, "message": msg}
    except Exception as e:
        logger.exception("Error cascading prescription update for %s: %s", prescription.pk, e)
        return {"invoice_updated": invoice_updated, "dispensing_updated": dispensing_updated, "message": str(e)}
