"""
🔒 PHARMACY DISPENSING - PAYMENT ENFORCED
Cannot dispense drugs without payment verification
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.db import transaction, OperationalError, connection
from django.db.models import Q, DateTimeField
from django.db.models.functions import Coalesce
from decimal import Decimal, InvalidOperation
from datetime import datetime
import time
import logging

from .models import Prescription, Patient, Staff
from .models_accounting import PaymentReceipt
from .models_payment_verification import (
    PharmacyDispensing,
    PharmacyDispenseHistory,
    PharmacyStockDeductionLog,
)
from .pharmacy_stock_utils import reduce_pharmacy_stock_once
from .services.auto_billing_service import AutoBillingService
from .services.pharmacy_invoice_payment_link import (
    reconcile_pending_pharmacy_dispensing_with_invoices,
)
from .models_pharmacy_walkin import WalkInPharmacySale
from .utils_billing import get_drug_price_for_prescription

logger = logging.getLogger(__name__)

DB_LOCK_RETRY_ATTEMPTS = 3


def _money_decimal(val):
    """Finite, template-safe money value (avoids NaN/invalid → empty floatformat output)."""
    try:
        if val is None:
            return Decimal('0.00')
        d = Decimal(str(val))
        if not d.is_finite():
            return Decimal('0.00')
        return d
    except (InvalidOperation, TypeError, ValueError):
        return Decimal('0.00')


def _parse_filter_date(param):
    if not param:
        return None
    try:
        return datetime.strptime(str(param).strip()[:10], '%Y-%m-%d').date()
    except ValueError:
        return None


def _get_user_display_name(staff, user):
    """Return a human-friendly name for logging purposes."""
    if staff and staff.user:
        full_name = staff.user.get_full_name()
        return full_name or staff.user.username
    if user:
        full_name = getattr(user, 'get_full_name', lambda: '')()
        return full_name or getattr(user, 'username', 'Unknown User')
    return ''


@login_required
def pharmacy_pending_dispensing(request):
    """
    Show prescriptions awaiting payment or ready for dispensing
    Pharmacists use this to see what can/cannot be dispensed
    """
    # Ensure every prescription has a dispensing record
    missing_dispensing = Prescription.objects.filter(
        is_deleted=False,
        dispensing_record__isnull=True
    ).select_related('drug')[:100]
    
    for rx in missing_dispensing:
        AutoBillingService.create_pharmacy_dispensing_record_only(rx)
    
    from .models import InvoiceLine
    
    # Exclude prescriptions whose invoice line was waived - waived drugs return to stock,
    # they were never paid for, so pharmacy should not see them as pending
    waived_prescription_ids = InvoiceLine.objects.filter(
        prescription__isnull=False,
        is_deleted=False,
        waived_at__isnull=False
    ).values_list('prescription_id', flat=True)
    
    base_dispensing_qs = PharmacyDispensing.objects.select_related(
        'prescription__drug',
        'prescription__order__encounter__patient',
        'prescription__prescribed_by__user',
        'patient',
        'patient__primary_insurance',
        'payment_receipt__invoice__payer',
        'dispensed_by__user'
    ).prefetch_related(
        'prescription__invoice_lines'
    ).exclude(
        prescription_id__in=waived_prescription_ids
    ).order_by('-created')

    # Safety net: rows still pending after invoice was settled (legacy / edge paths)
    try:
        reconcile_pending_pharmacy_dispensing_with_invoices()
    except Exception:
        logger.exception('reconcile_pending_pharmacy_dispensing_with_invoices failed')

    # Pending payment = not yet paid (must not appear in queue once paid)
    pending_payment_qs = base_dispensing_qs.filter(
        dispensing_status='pending_payment',
        payment_receipt_id__isnull=True,
    )
    # Paid – ready to dispense: built after date params (prescribed date vs paid/ready date)
    paid_ready_base = base_dispensing_qs.filter(
        Q(dispensing_status='ready_to_dispense') | Q(payment_receipt_id__isnull=False)
    ).exclude(
        dispensing_status__in=['partially_dispensed', 'fully_dispensed']
    )
    dispensed_qs = base_dispensing_qs.filter(dispensing_status__in=['partially_dispensed', 'fully_dispensed'])

    date_from = _parse_filter_date(request.GET.get('date_from'))
    date_to = _parse_filter_date(request.GET.get('date_to'))
    date_filter_active = date_from is not None or date_to is not None

    paid_from = _parse_filter_date(request.GET.get('paid_from'))
    paid_to = _parse_filter_date(request.GET.get('paid_to'))
    paid_date_filter_active = paid_from is not None or paid_to is not None

    payment_filter = (request.GET.get('payment') or 'all').strip().lower()
    if payment_filter not in ('all', 'cash', 'corporate', 'insurance'):
        payment_filter = 'all'
    read_filter_active = paid_date_filter_active or payment_filter != 'all'

    from .utils_billing import get_patient_payer_info, local_datetime_bounds_for_date
    from .models import Invoice

    bounds_start = None
    bounds_end_excl = None
    if date_from:
        bounds_start, _ = local_datetime_bounds_for_date(date_from)
    if date_to:
        _, bounds_end_excl = local_datetime_bounds_for_date(date_to)

    paid_bounds_start = None
    paid_bounds_end_excl = None
    if paid_from:
        paid_bounds_start, _ = local_datetime_bounds_for_date(paid_from)
    if paid_to:
        _, paid_bounds_end_excl = local_datetime_bounds_for_date(paid_to)

    if bounds_start:
        pending_payment_qs = pending_payment_qs.filter(prescription__created__gte=bounds_start)
        dispensed_qs = dispensed_qs.filter(dispensed_at__gte=bounds_start)
    if bounds_end_excl:
        pending_payment_qs = pending_payment_qs.filter(prescription__created__lt=bounds_end_excl)
        dispensed_qs = dispensed_qs.filter(dispensed_at__lt=bounds_end_excl)

    # Right column (paid / ready): optional paid-queue date; else same as prescribed-date filter
    if paid_date_filter_active:
        paid_ready_qs = paid_ready_base.annotate(
            _ready_at=Coalesce(
                'payment_verified_at',
                'payment_receipt__receipt_date',
                'created',
                output_field=DateTimeField(),
            )
        ).order_by('-payment_verified_at', '-payment_receipt__receipt_date', '-created')
        if paid_bounds_start:
            paid_ready_qs = paid_ready_qs.filter(_ready_at__gte=paid_bounds_start)
        if paid_bounds_end_excl:
            paid_ready_qs = paid_ready_qs.filter(_ready_at__lt=paid_bounds_end_excl)
    else:
        paid_ready_qs = paid_ready_base.order_by(
            '-payment_verified_at', '-payment_receipt__receipt_date', '-created'
        )
        if bounds_start:
            paid_ready_qs = paid_ready_qs.filter(prescription__created__gte=bounds_start)
        if bounds_end_excl:
            paid_ready_qs = paid_ready_qs.filter(prescription__created__lt=bounds_end_excl)

    filtered_rx_dispensing = base_dispensing_qs
    if bounds_start:
        filtered_rx_dispensing = filtered_rx_dispensing.filter(
            prescription__created__gte=bounds_start
        )
    if bounds_end_excl:
        filtered_rx_dispensing = filtered_rx_dispensing.filter(
            prescription__created__lt=bounds_end_excl
        )
    enc_invoice_cache = {}

    def _rx_payer_channel(disp):
        """cash | corporate | insurance — receipt/invoice first; else patient primary (pending often has no invoice yet)."""
        try:
            pr = getattr(disp, 'payment_receipt', None)
            if pr and getattr(pr, 'invoice', None) and pr.invoice.payer_id:
                pt = pr.invoice.payer.payer_type
                if pt == 'corporate':
                    return 'corporate'
                if pt in ('nhis', 'private', 'insurance'):
                    return 'insurance'
                return 'cash'
        except Exception:
            pass
        try:
            enc = disp.prescription.order.encounter if disp.prescription_id and getattr(disp.prescription, 'order', None) else None
            if enc and getattr(enc, 'id', None):
                if enc.id not in enc_invoice_cache:
                    inv = Invoice.objects.filter(encounter_id=enc.id, is_deleted=False).select_related('payer').first()
                    enc_invoice_cache[enc.id] = inv
                inv = enc_invoice_cache[enc.id]
                if inv and inv.payer_id:
                    pt = inv.payer.payer_type
                    if pt == 'corporate':
                        return 'corporate'
                    if pt in ('nhis', 'private', 'insurance'):
                        return 'insurance'
                    if pt == 'cash':
                        return 'cash'
        except Exception:
            pass
        try:
            pi = getattr(disp.patient, 'primary_insurance', None)
            if pi and not getattr(pi, 'is_deleted', False):
                pt = (getattr(pi, 'payer_type', None) or '').strip()
                if pt == 'corporate':
                    return 'corporate'
                if pt in ('nhis', 'private', 'insurance'):
                    return 'insurance'
                if pt == 'cash':
                    return 'cash'
        except Exception:
            pass
        return 'cash'

    def _payer_name_for_disp(disp):
        name = None
        enc = None
        try:
            enc = disp.prescription.order.encounter if disp.prescription_id and getattr(disp.prescription, 'order', None) else None
            if enc and getattr(enc, 'id', None):
                if enc.id not in enc_invoice_cache:
                    inv = Invoice.objects.filter(encounter_id=enc.id, is_deleted=False).select_related('payer').first()
                    enc_invoice_cache[enc.id] = inv
                inv = enc_invoice_cache[enc.id]
                if inv and inv.payer_id and getattr(inv.payer, 'payer_type', '') != 'cash':
                    name = getattr(inv.payer, 'name', None)
        except Exception:
            pass
        if not name:
            try:
                info = get_patient_payer_info(disp.patient, enc)
                name = info.get('name') if info.get('is_insurance_or_corporate') else None
            except Exception:
                pass
        if not name:
            pi = getattr(disp.patient, 'primary_insurance', None)
            if pi and getattr(pi, 'payer_type', '') != 'cash' and getattr(pi, 'name', None):
                name = pi.name
        return name

    def _catalog_display_totals(disp, qty_ord):
        """List/catalog price × pharmacy quantity (when invoice line missing or unusable)."""
        enc = None
        payer_for_price = None
        try:
            if disp.prescription_id and getattr(disp.prescription, 'order', None):
                enc = disp.prescription.order.encounter
                pinfo = get_patient_payer_info(disp.patient, enc)
                payer_for_price = pinfo.get('payer')
        except Exception:
            pass
        if not payer_for_price:
            payer_for_price = getattr(disp.patient, 'primary_insurance', None)
        try:
            ed = disp.effective_drug
            if ed:
                up = _money_decimal(get_drug_price_for_prescription(ed, payer=payer_for_price))
            else:
                up = Decimal('0.00')
        except Exception:
            up = Decimal('0.00')
        disp.display_unit_price = up
        disp.display_line_total = up * _money_decimal(qty_ord)
        disp.display_qty_for_breakdown = qty_ord

    def _annotate_disp(disp):
        try:
            invoice_line = None
            try:
                invoice_line = InvoiceLine.objects.filter(
                    prescription=disp.prescription,
                    is_deleted=False,
                    waived_at__isnull=True,
                ).first()
                if invoice_line:
                    disp.requires_cash_payment = getattr(invoice_line, 'patient_pay_cash', False)
                    disp.exclusion_reason = getattr(invoice_line, 'insurance_exclusion_reason', '') or ''
                else:
                    disp.requires_cash_payment = False
                    disp.exclusion_reason = ''
            except Exception:
                disp.requires_cash_payment = False
                disp.exclusion_reason = ''
                invoice_line = None
            try:
                disp.effective_drug = disp.drug_to_dispense or (
                    disp.prescription.drug if disp.prescription_id else None
                )
            except Exception:
                disp.effective_drug = None
            disp.payer_name = _payer_name_for_disp(disp)
            disp.payer_channel = _rx_payer_channel(disp)
            qty_ord = int(disp.quantity_ordered or 0)

            # Billed amount on pending card must match cashier invoice (discount/tax); fall back if line is broken/empty.
            if invoice_line:
                qty_bill = _money_decimal(invoice_line.quantity)
                unit_raw = _money_decimal(invoice_line.unit_price)
                disc = _money_decimal(getattr(invoice_line, 'discount_amount', 0))
                tax = _money_decimal(getattr(invoice_line, 'tax_amount', 0))
                lt = _money_decimal(invoice_line.line_total)
                computed = qty_bill * unit_raw - disc + tax
                if computed < 0:
                    computed = Decimal('0.00')
                if lt <= 0 and computed > 0:
                    lt = computed
                if qty_bill > 0 and lt > 0:
                    disp.display_line_total = lt
                    disp.display_unit_price = (lt / qty_bill).quantize(Decimal('0.01'))
                    try:
                        disp.display_qty_for_breakdown = (
                            int(qty_bill) if qty_bill == int(qty_bill) else qty_bill
                        )
                    except Exception:
                        disp.display_qty_for_breakdown = qty_bill
                else:
                    _catalog_display_totals(disp, qty_ord)
            else:
                _catalog_display_totals(disp, qty_ord)
        except Exception:
            logger.exception(
                'pharmacy_pending _annotate_disp failed for dispensing %s',
                getattr(disp, 'pk', None),
            )
            try:
                qty_ord = int(disp.quantity_ordered or 0)
            except Exception:
                qty_ord = 0
            disp.requires_cash_payment = False
            disp.exclusion_reason = ''
            disp.effective_drug = None
            disp.payer_name = ''
            disp.payer_channel = 'cash'
            disp.display_unit_price = Decimal('0.00')
            disp.display_line_total = Decimal('0.00')
            disp.display_qty_for_breakdown = qty_ord

    pending_limit = 500 if date_filter_active else 40
    pending_payment = list(pending_payment_qs[:pending_limit])
    for disp in pending_payment:
        _annotate_disp(disp)
    paid_ready_to_dispense = list(paid_ready_qs[:pending_limit])
    for disp in paid_ready_to_dispense:
        # If cash was paid (receipt set) but status not updated, fix it so pharmacy sees as paid
        if disp.payment_receipt_id and disp.dispensing_status != 'ready_to_dispense':
            disp.dispensing_status = 'ready_to_dispense'
            disp.save(update_fields=['dispensing_status'])
        _annotate_disp(disp)

    def _walkin_payer_channel(sale):
        if not sale.payer_id:
            return 'cash'
        pt = getattr(sale.payer, 'payer_type', None) or 'cash'
        if pt == 'corporate':
            return 'corporate'
        if pt in ('nhis', 'private', 'insurance'):
            return 'insurance'
        return 'cash'

    if payment_filter == 'cash':
        pending_payment = [d for d in pending_payment if _rx_payer_channel(d) == 'cash']
        paid_ready_to_dispense = [d for d in paid_ready_to_dispense if _rx_payer_channel(d) == 'cash']
    elif payment_filter == 'corporate':
        pending_payment = [d for d in pending_payment if _rx_payer_channel(d) == 'corporate']
        paid_ready_to_dispense = [d for d in paid_ready_to_dispense if _rx_payer_channel(d) == 'corporate']
    elif payment_filter == 'insurance':
        pending_payment = [d for d in pending_payment if _rx_payer_channel(d) == 'insurance']
        paid_ready_to_dispense = [d for d in paid_ready_to_dispense if _rx_payer_channel(d) == 'insurance']

    recent_limit = 100 if date_filter_active else 20
    recently_dispensed = list(dispensed_qs.order_by('-dispensed_at', '-created')[:recent_limit])

    history_qs = PharmacyDispenseHistory.objects.select_related(
        'prescription__drug',
        'patient',
        'dispensed_by__user',
        'payment_receipt'
    ).order_by('-dispensed_at')[:100]

    walkin_pending_qs = WalkInPharmacySale.objects.filter(
        is_deleted=False,
        payment_status__in=['pending', 'partial']
    ).select_related('payer').order_by('-sale_date')
    walkin_ready_qs = WalkInPharmacySale.objects.filter(
        is_deleted=False,
        payment_status='paid',
        is_dispensed=False
    ).select_related('payer').order_by('-sale_date')
    walkin_dispensed_qs = WalkInPharmacySale.objects.filter(
        is_deleted=False,
        is_dispensed=True
    ).order_by('-dispensed_at')

    if bounds_start:
        walkin_pending_qs = walkin_pending_qs.filter(sale_date__gte=bounds_start)
        walkin_dispensed_qs = walkin_dispensed_qs.filter(dispensed_at__gte=bounds_start)
    if bounds_end_excl:
        walkin_pending_qs = walkin_pending_qs.filter(sale_date__lt=bounds_end_excl)
        walkin_dispensed_qs = walkin_dispensed_qs.filter(dispensed_at__lt=bounds_end_excl)

    # Right column prescribe sales: sale date when using prescribed filter; paid/ready date when set
    if paid_date_filter_active:
        if paid_bounds_start:
            walkin_ready_qs = walkin_ready_qs.filter(sale_date__gte=paid_bounds_start)
        if paid_bounds_end_excl:
            walkin_ready_qs = walkin_ready_qs.filter(sale_date__lt=paid_bounds_end_excl)
    else:
        if bounds_start:
            walkin_ready_qs = walkin_ready_qs.filter(sale_date__gte=bounds_start)
        if bounds_end_excl:
            walkin_ready_qs = walkin_ready_qs.filter(sale_date__lt=bounds_end_excl)

    walkin_list_limit = 200 if date_filter_active else 50
    walkin_pending_all = list(walkin_pending_qs[:walkin_list_limit])
    if payment_filter == 'cash':
        walkin_pending_all = [s for s in walkin_pending_all if _walkin_payer_channel(s) == 'cash']
    elif payment_filter == 'corporate':
        walkin_pending_all = [s for s in walkin_pending_all if _walkin_payer_channel(s) == 'corporate']
    elif payment_filter == 'insurance':
        walkin_pending_all = [s for s in walkin_pending_all if _walkin_payer_channel(s) == 'insurance']
    walkin_pending_cash = [s for s in walkin_pending_all if _walkin_payer_channel(s) == 'cash']
    walkin_pending_insurance = [s for s in walkin_pending_all if _walkin_payer_channel(s) in ('corporate', 'insurance')]
    walkin_pending = walkin_pending_all
    walkin_ready = list(walkin_ready_qs[:pending_limit])
    if payment_filter == 'cash':
        walkin_ready = [s for s in walkin_ready if _walkin_payer_channel(s) == 'cash']
    elif payment_filter == 'corporate':
        walkin_ready = [s for s in walkin_ready if _walkin_payer_channel(s) == 'corporate']
    elif payment_filter == 'insurance':
        walkin_ready = [s for s in walkin_ready if _walkin_payer_channel(s) == 'insurance']
    walkin_recently_dispensed = list(walkin_dispensed_qs[:recent_limit])

    stats = {
        'pending_payment': pending_payment_qs.count(),
        'paid_ready': paid_ready_qs.count(),
        'dispensed': dispensed_qs.count(),
        'total': filtered_rx_dispensing.count(),
        'history_total': PharmacyDispenseHistory.objects.count(),
        'walkin_pending': walkin_pending_qs.count(),
        'walkin_ready': walkin_ready_qs.count(),
        'walkin_dispensed': walkin_dispensed_qs.count(),
    }
    stats['walkin_pending_insurance'] = len(walkin_pending_insurance)
    stats['walkin_pending_cash'] = len(walkin_pending_cash)
    stats['pending_payment_total'] = stats['pending_payment'] + stats['walkin_pending']
    stats['paid_ready_total'] = stats['paid_ready'] + stats['walkin_ready']
    if read_filter_active:
        stats['paid_ready_total'] = len(paid_ready_to_dispense) + len(walkin_ready)
        if payment_filter != 'all':
            stats['pending_payment_total'] = len(pending_payment) + len(walkin_pending_all)
    stats['dispensed_total'] = stats['dispensed'] + stats['walkin_dispensed']
    stats['total_all'] = stats['total'] + stats['walkin_pending'] + stats['walkin_ready'] + stats['walkin_dispensed']
    # Ensure template always has numeric stats (avoid KeyError)
    stats.setdefault('pending_insurance_count', 0)

    # Count pending prescription items needing Send to Insurance (insurance/corporate patients)
    pending_insurance_count = 0
    try:
        from .models import Payer
        for disp in pending_payment_qs.select_related('patient', 'prescription'):
            payer = getattr(disp.patient, 'primary_insurance', None)
            if payer and getattr(payer, 'payer_type', '') in ('insurance', 'nhis', 'private', 'corporate'):
                pending_insurance_count += 1
    except Exception:
        pass
    stats['pending_insurance_count'] = pending_insurance_count

    context = {
        'title': '💊 Pharmacy Dispensing - Payment Enforced',
        'pending_payment': pending_payment,
        'paid_ready_to_dispense': paid_ready_to_dispense,
        'recently_dispensed': recently_dispensed,
        'dispense_history': history_qs,
        'history_total': stats['history_total'],
        'stats': stats,
        'walkin_pending': walkin_pending,
        'walkin_pending_cash': walkin_pending_cash,
        'walkin_pending_insurance': walkin_pending_insurance,
        'walkin_ready': walkin_ready,
        'walkin_recently_dispensed': walkin_recently_dispensed,
        'filter_date_from': date_from.isoformat() if date_from else '',
        'filter_date_to': date_to.isoformat() if date_to else '',
        'date_filter_active': date_filter_active,
        'filter_paid_from': paid_from.isoformat() if paid_from else '',
        'filter_paid_to': paid_to.isoformat() if paid_to else '',
        'paid_date_filter_active': paid_date_filter_active,
        'payment_filter': payment_filter,
        'read_filter_active': read_filter_active,
    }
    return render(request, 'hospital/pharmacy_dispensing_enforced.html', context)


@login_required
@require_POST
def send_prescribe_sale_to_insurance(request, sale_id):
    """
    Push a prescribe sale to insurance. If sale is already under Insurance/Corporate, use that payer.
    If sale is cash, use the linked patient's primary_insurance (if any) and then push.
    """
    sale = get_object_or_404(
        WalkInPharmacySale.objects.select_related('payer'),
        pk=sale_id,
        is_deleted=False
    )
    from .services.pharmacy_walkin_service import WalkInPharmacyService
    patient = WalkInPharmacyService.ensure_sale_patient(sale)

    # If not already billed to company, try to set payer from patient's primary_insurance
    if not sale.is_billed_to_company:
        payer = getattr(patient, 'primary_insurance', None)
        if not payer or getattr(payer, 'payer_type', '') not in ('insurance', 'private', 'nhis', 'corporate'):
            messages.error(
                request,
                'No Insurance/Corporate on file for this patient. Set Payer on the sale (View Sale → edit) or add primary insurance to the patient.'
            )
            return redirect('hospital:pharmacy_pending_dispensing')
        sale.payer = payer
        sale.save(update_fields=['payer', 'modified'])

    try:
        WalkInPharmacyService.ensure_sale_invoice(sale, patient)
        sale.amount_paid = sale.total_amount
        sale.payment_status = 'paid'
        sale.save(update_fields=['amount_paid', 'payment_status', 'amount_due', 'modified'])
        messages.success(
            request,
            f'Bill sent to {sale.payer.name}. Sale {sale.sale_number} is now ready to dispense.'
        )
    except Exception as e:
        logger.exception('Send prescribe sale to insurance failed: %s', e)
        messages.error(request, f'Could not send to insurance: {str(e)}')
    return redirect('hospital:pharmacy_pending_dispensing')


@login_required
@require_POST
def send_prescription_to_payer(request, prescription_id):
    """
    Create or update the invoice line for this prescription only (same billing path as
    send-to-cashier for the full order, without touching other Rx on the order).
    """
    from .utils_roles import is_pharmacy_user
    from .utils_billing import get_patient_payer_info

    if not (is_pharmacy_user(request.user) or getattr(request.user, 'is_superuser', False)):
        messages.error(request, 'Only pharmacy staff can send prescriptions to payer.')
        return redirect('hospital:pharmacy_pending_dispensing')

    prescription = get_object_or_404(
        Prescription.objects.select_related('order__encounter__patient'),
        id=prescription_id,
        is_deleted=False,
    )
    encounter = prescription.order.encounter
    patient = encounter.patient if encounter else None
    if not patient:
        messages.error(request, 'Patient information missing for this prescription.')
        return redirect('hospital:pharmacy_pending_dispensing')

    try:
        payer_info = get_patient_payer_info(patient, encounter)
    except Exception:
        payer_info = {'type': 'cash', 'name': 'Cash', 'is_insurance_or_corporate': False, 'payer': None}
    if not payer_info.get('is_insurance_or_corporate'):
        pi = getattr(patient, 'primary_insurance', None)
        if pi and getattr(pi, 'payer_type', '') != 'cash':
            payer_info = {
                'type': getattr(pi, 'payer_type', 'corporate'),
                'name': getattr(pi, 'name', ''),
                'is_insurance_or_corporate': True,
                'payer': pi,
            }
    payer = payer_info.get('payer') or getattr(patient, 'primary_insurance', None)

    dispensing_record = PharmacyDispensing.objects.filter(
        prescription=prescription,
        is_deleted=False,
    ).first()
    if not dispensing_record:
        ensure = AutoBillingService.create_pharmacy_dispensing_record_only(prescription)
        if not ensure.get('success'):
            messages.error(
                request,
                ensure.get('message') or ensure.get('error') or 'Could not add prescription to pharmacy queue.',
            )
            return redirect('hospital:pharmacy_dispense_enforced', prescription_id=prescription.id)
        dispensing_record = PharmacyDispensing.objects.filter(
            prescription=prescription,
            is_deleted=False,
        ).first()

    qty = int(dispensing_record.quantity_ordered or prescription.quantity or 0)
    if qty <= 0:
        messages.error(request, 'Set a quantity greater than zero before sending to payer.')
        return redirect('hospital:pharmacy_dispense_enforced', prescription_id=prescription.id)

    substitute_drug = dispensing_record.substitute_drug if dispensing_record.substitute_drug_id else None

    billing_result = AutoBillingService.create_pharmacy_bill(
        prescription,
        substitute_drug=substitute_drug,
        quantity_override=qty,
        payer=payer,
        invoice=None,
    )

    if billing_result.get('success'):
        inv = billing_result.get('invoice')
        if inv:
            try:
                inv.update_totals()
            except Exception:
                logger.exception('update_totals after send_prescription_to_payer')
        msg = billing_result.get('message') or 'Bill sent to payer.'
        payer_type = getattr(payer, 'payer_type', '') if payer else ''
        if payer_type in ('insurance', 'private', 'nhis', 'corporate'):
            messages.success(
                request,
                f'{msg} This medication is approved for dispensing (billed to company or insurer).',
            )
        else:
            messages.success(request, f'{msg} Patient can pay at cashier.')
        return redirect('hospital:pharmacy_dispense_enforced', prescription_id=prescription.id)

    err = billing_result.get('message') or billing_result.get('error') or 'Unable to send to payer.'
    messages.error(request, err)
    return redirect('hospital:pharmacy_dispense_enforced', prescription_id=prescription.id)


@login_required
def pharmacy_dispense_enforced(request, prescription_id):
    """
    Dispense medication - with integrated payment option
    """
    prescription = get_object_or_404(Prescription, id=prescription_id, is_deleted=False)
    patient = prescription.order.encounter.patient

    # Get or create dispensing record (no bill yet – pharmacy must Send to Cashier/Payer first)
    try:
        dispensing_record = prescription.dispensing_record
    except Exception:
        AutoBillingService.create_pharmacy_dispensing_record_only(prescription)
        try:
            dispensing_record = prescription.dispensing_record
        except Exception:
            dispensing_record = None

    drug = (
        dispensing_record.drug_to_dispense
        if dispensing_record
        else prescription.drug
    )
    qty_for_price = (
        int(dispensing_record.quantity_ordered or 0)
        if dispensing_record
        else int(prescription.quantity or 0)
    )

    # Payer/company from patient file (for display and pricing)
    encounter = prescription.order.encounter
    from .utils_billing import get_patient_payer_info
    try:
        payer_info = get_patient_payer_info(patient, encounter)
    except Exception:
        payer_info = {'type': 'cash', 'name': 'Cash', 'is_insurance_or_corporate': False, 'payer': None}
    if not payer_info.get('is_insurance_or_corporate'):
        pi = getattr(patient, 'primary_insurance', None)
        if pi and getattr(pi, 'payer_type', '') != 'cash':
            payer_info = {'type': getattr(pi, 'payer_type', 'corporate'), 'name': getattr(pi, 'name', ''), 'is_insurance_or_corporate': True, 'payer': pi}
    payer = payer_info.get('payer') or getattr(patient, 'primary_insurance', None)

    # Check invoice line (waived vs active) and insurance exclusion flags
    requires_cash_payment = False
    exclusion_reason = ''
    invoice_line = None
    try:
        from .models import InvoiceLine

        line_any = InvoiceLine.objects.filter(
            prescription=prescription,
            is_deleted=False,
        ).first()
        if line_any and line_any.waived_at:
            messages.info(
                request,
                'This medication was waived from the bill. Quantity has been returned to stock.',
            )
            return redirect('hospital:pharmacy_pending_dispensing')
        if line_any and not line_any.waived_at:
            invoice_line = line_any
            requires_cash_payment = invoice_line.patient_pay_cash
            exclusion_reason = invoice_line.insurance_exclusion_reason or ''
    except Exception:
        pass

    if invoice_line:
        qty_bill = Decimal(str(invoice_line.quantity or 0))
        lt = Decimal(str(invoice_line.line_total or 0))
        total_cost = lt
        if qty_bill > 0:
            unit_price = (lt / qty_bill).quantize(Decimal('0.01'))
        else:
            unit_price = Decimal(str(invoice_line.unit_price or 0))
    else:
        unit_price = get_drug_price_for_prescription(drug, payer=payer)
        total_cost = unit_price * Decimal(str(qty_for_price or 0))
    
    # Check payment status
    payment_status = AutoBillingService.check_payment_status('pharmacy', prescription_id)
    is_already_dispensed = bool(dispensing_record and dispensing_record.dispensing_status in ['partially_dispensed', 'fully_dispensed'])
    # Corporate/insurance: can dispense when status is ready_to_dispense (bill sent to company; no cash receipt)
    is_corporate_insurance = payer_info.get('is_insurance_or_corporate')
    can_dispense_corporate = is_corporate_insurance and dispensing_record and dispensing_record.dispensing_status == 'ready_to_dispense'
    can_dispense = payment_status['paid'] or can_dispense_corporate

    # Check payment BEFORE allowing any action
    if request.method == 'POST':
        action = request.POST.get('action')
        
        # ENFORCE: Payment must be made at CASHIER first (or approved for corporate/insurance)
        if action == 'dispense':
            if is_already_dispensed:
                messages.info(request, 'This medication has already been dispensed. No further action required.')
                return redirect('hospital:pharmacy_dispense_enforced', prescription_id=prescription.id)
            if not can_dispense:
                messages.error(
                    request,
                    f'🔒 PAYMENT REQUIRED AT CASHIER! Patient must pay at cashier FIRST. '
                    f'Amount: GHS {total_cost}. Status: {payment_status["message"]}'
                )
                return redirect('hospital:pharmacy_dispense_enforced', prescription_id=prescription.id)
            
            # Payment verified (or corporate/insurance approved) - can dispense
            try:
                success = False
                for attempt in range(DB_LOCK_RETRY_ATTEMPTS):
                    try:
                        with transaction.atomic():
                            dispensing_record = prescription.dispensing_record
                            
                            # Get current staff
                            try:
                                current_staff = Staff.objects.get(user=request.user, is_active=True)
                            except:
                                current_staff = None
                            
                            # Record dispensing details
                            quantity = int(request.POST.get('quantity', prescription.quantity))
                            instructions = request.POST.get('instructions', f"{prescription.dose}, {prescription.frequency}, {prescription.duration}")
                            counselling_given = request.POST.get('counselling_given') == 'on'
                            notes = request.POST.get('notes', '')
                            
                            # Handle consumables
                            consumables_added = []
                            from .models import ServiceCode, InvoiceLine
                            from .utils_billing import get_or_create_encounter_invoice
                            from .services.pricing_engine_service import pricing_engine
                            
                            encounter = prescription.order.encounter
                            patient = encounter.patient
                            
                            # Process consumables if any
                            consumable_codes = [k for k in request.POST.keys() if k.startswith('consumable_code_')]
                            if consumable_codes:
                                invoice = get_or_create_encounter_invoice(encounter)
                                if invoice:
                                    payer = patient.primary_insurance
                                    if not payer:
                                        from .models import Payer
                                        payer = Payer.objects.filter(payer_type='cash', is_active=True, is_deleted=False).first()
                                    
                                    for key in consumable_codes:
                                        consumable_code = request.POST.get(key)
                                        if not consumable_code:
                                            continue
                                        
                                        index = key.replace('consumable_code_', '')
                                        qty_key = f'consumable_qty_{index}'
                                        qty = int(request.POST.get(qty_key, 1))
                                        
                                        if qty <= 0:
                                            continue
                                        
                                        try:
                                            service_code = ServiceCode.objects.get(
                                                code=consumable_code,
                                                category='Clinical Consumables',
                                                is_active=True,
                                                is_deleted=False
                                            )
                                            
                                            unit_price = pricing_engine.get_service_price(
                                                service_code=service_code,
                                                patient=patient,
                                                payer=payer
                                            ) if payer else Decimal('0.00')
                                            
                                            if unit_price <= 0:
                                                unit_price = Decimal('30.00')  # Default
                                            
                                            line_total = Decimal(str(qty)) * unit_price
                                            
                                            InvoiceLine.objects.create(
                                                invoice=invoice,
                                                service_code=service_code,
                                                description=f"{service_code.description} (Pharmacy Consumable)",
                                                quantity=qty,
                                                unit_price=unit_price,
                                                line_total=line_total
                                            )
                                            
                                            consumables_added.append(f"{service_code.description} x{qty}")
                                            
                                        except ServiceCode.DoesNotExist:
                                            pass
                                    
                                    if consumables_added:
                                        invoice.update_totals()
                                        if invoice.status == 'draft':
                                            invoice.status = 'issued'
                                            invoice.save()
                            
                            # Check if patient is inpatient - create MAR if needed
                            is_inpatient = encounter.encounter_type == 'inpatient'
                            
                            # Prevent overdosing
                            quantity = min(quantity, dispensing_record.quantity_ordered)
                            
                            # Update dispensing record manually to guarantee status change
                            dispensing_record.quantity_dispensed = min(
                                dispensing_record.quantity_dispensed + quantity,
                                dispensing_record.quantity_ordered
                            )
                            
                            if dispensing_record.quantity_dispensed >= dispensing_record.quantity_ordered:
                                dispensing_record.dispensing_status = 'fully_dispensed'
                            else:
                                dispensing_record.dispensing_status = 'partially_dispensed'
                            
                            dispensing_record.dispensed_by = current_staff or dispensing_record.dispensed_by
                            dispensing_record.dispensed_at = timezone.now()
                            dispensing_record.dispensing_instructions = instructions
                            dispensing_record.dispensing_notes = notes
                            dispensing_record.counselling_given = counselling_given
                            if current_staff:
                                dispensing_record.counselled_by = current_staff
                            
                            dispensing_record.save(update_fields=[
                                'quantity_dispensed',
                                'dispensing_status',
                                'dispensed_by',
                                'dispensed_at',
                                'dispensing_instructions',
                                'dispensing_notes',
                                'counselling_given',
                                'counselled_by'
                            ])
                            
                            dispensed_timestamp = dispensing_record.dispensed_at or timezone.now()
                            
                            disp_hist = PharmacyDispenseHistory.objects.create(
                                dispensing_record=dispensing_record,
                                prescription=prescription,
                                patient=patient,
                                patient_name=getattr(patient, 'full_name', str(patient)),
                                drug=drug,
                                drug_name=getattr(drug, 'name', str(drug)),
                                quantity_dispensed=quantity,
                                instructions=instructions,
                                notes=notes,
                                counselling_given=counselling_given,
                                dispensed_by=current_staff,
                                dispensed_by_name=_get_user_display_name(current_staff, request.user),
                                payment_receipt=dispensing_record.payment_receipt,
                                dispensed_at=dispensed_timestamp,
                            )
                            
                            # Reduce pharmacy stock when drugs are dispensed (skip if already reduced at Send to Payer)
                            # Skip only when insurer/corporate billing already deducted full qty (stock_reduced_at).
                            if not getattr(dispensing_record, 'stock_reduced_at', None):
                                drug_to_dispense = dispensing_record.drug_to_dispense or prescription.drug
                                if drug_to_dispense:
                                    shortfall = reduce_pharmacy_stock_once(
                                        drug_to_dispense,
                                        quantity,
                                        PharmacyStockDeductionLog.SOURCE_DISPENSE_HISTORY,
                                        disp_hist.id,
                                    )
                                    if shortfall > 0:
                                        messages.warning(request, f'⚠️ Insufficient stock for {drug_to_dispense.name}. Short by {shortfall} units.')
                            else:
                                logger.info(
                                    "Skipping dispense-time stock deduction for dispensing %s; pre-deduct recorded at %s",
                                    getattr(dispensing_record, 'id', None),
                                    getattr(dispensing_record, 'stock_reduced_at', None),
                                )
                            
                            is_already_dispensed = dispensing_record.is_dispensed
                            
                            # If inpatient, create MAR schedule
                            if is_inpatient:
                                try:
                                    from hospital.services.mar_generator import create_mar_schedule
                                    create_mar_schedule(prescription)
                                    messages.info(request, '📋 MAR schedule created for inpatient medication administration')
                                except Exception as e:
                                    logger.error(f"Error creating MAR: {str(e)}")
                            
                            success = True
                            break
                    except OperationalError as oe:
                        if 'database is locked' in str(oe).lower() and attempt < DB_LOCK_RETRY_ATTEMPTS - 1:
                            wait_time = 0.5 * (attempt + 1)
                            logger.warning(
                                "SQLite database locked while dispensing %s (attempt %s). Retrying in %.1fs",
                                prescription.id,
                                attempt + 1,
                                wait_time
                            )
                            connection.close()
                            time.sleep(wait_time)
                            continue
                        raise
                
                if not success:
                    raise OperationalError('database is locked')
                
                is_already_dispensed = True
                
                receipt_msg = ''
                if payment_status.get('receipt'):
                    receipt_msg = f' Payment verified via receipt {payment_status["receipt"].receipt_number}.'
                else:
                    receipt_msg = ' Billed to company/insurer.'
                messages.success(
                    request,
                    f'✅ Medication dispensed to {patient.full_name}.{receipt_msg}'
                )
                
                # Do not send payment/dispensing feedback SMS for insurance/corporate billing.
                patient_payer = getattr(patient, 'primary_insurance', None)
                payer_type = getattr(patient_payer, 'payer_type', '') if patient_payer else ''
                should_send_feedback_sms = payer_type not in ('insurance', 'private', 'nhis', 'corporate')
                if should_send_feedback_sms:
                    try:
                        from .services.patient_feedback_service import send_customer_service_review_sms
                        send_customer_service_review_sms(
                            patient,
                            message_type='pharmacy_dispensing_feedback',
                            related_object_id=dispensing_record.id if hasattr(dispensing_record, 'id') else None,
                            related_object_type='PharmacyDispensing',
                        )
                    except Exception as e:
                        logger.warning("Could not send customer service review SMS: %s", e)
                
                # Redirect to label print page with auto-print
                from django.urls import reverse
                label_url = reverse('hospital:pharmacy_label_print', args=[prescription.id]) + '?auto_print=1'
                return redirect(label_url)
            
            except OperationalError as e:
                logger.warning(f"Operational error while dispensing medication: {str(e)}", exc_info=True)
                if 'database is locked' in str(e).lower():
                    messages.error(request, '❌ Pharmacy database is busy. Please wait a few seconds and try again.')
                else:
                    messages.error(request, f'❌ Error dispensing: {str(e)}')
                return redirect('hospital:pharmacy_dispense_enforced', prescription_id=prescription.id)
            except Exception as e:
                logger.error(f"Error dispensing medication: {str(e)}", exc_info=True)
                messages.error(request, f'❌ Error dispensing: {str(e)}')
                return redirect('hospital:pharmacy_dispense_enforced', prescription_id=prescription.id)
    
    # Get dispensing record
    try:
        dispensing_record = prescription.dispensing_record
    except:
        dispensing_record = None
    
    # Check for existing receipts for this patient (in case payment was made but not linked)
    recent_receipts = PaymentReceipt.objects.filter(
        patient=patient,
        service_type='pharmacy',
        is_deleted=False
    ).order_by('-created')[:5]
    
    # Get consumables for selection
    from .models import ServiceCode
    consumables = ServiceCode.objects.filter(
        category='Clinical Consumables',
        is_active=True,
        is_deleted=False
    ).order_by('code', 'description')
    
    context = {
        'title': f'Dispense Medication - {drug.name}',
        'prescription': prescription,
        'patient': patient,
        'drug': drug,
        'unit_price': unit_price,
        'total_cost': total_cost,
        'payment_status': payment_status,
        'can_dispense': can_dispense,
        'dispensing_record': dispensing_record,
        'receipt': payment_status.get('receipt'),
        'is_already_dispensed': is_already_dispensed,
        'recent_receipts': recent_receipts,
        'requires_cash_payment': requires_cash_payment,
        'exclusion_reason': exclusion_reason,
        'invoice_line': invoice_line,
        'consumables': consumables,
        'payer_info': payer_info,
    }
    return render(request, 'hospital/pharmacy_dispense_enforced.html', context)


@login_required
def check_pharmacy_payment_required(request, prescription_id):
    """
    API to check if prescription requires payment
    Used by pharmacists before dispensing
    """
    payment_status = AutoBillingService.check_payment_status('pharmacy', prescription_id)
    
    return JsonResponse({
        'paid': payment_status['paid'],
        'status': payment_status['status'],
        'message': payment_status['message'],
        'receipt_number': payment_status['receipt'].receipt_number if payment_status.get('receipt') else None
    })





