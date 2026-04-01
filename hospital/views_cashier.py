"""
Cashier Views - Payment Processing and Session Management
"""
import logging

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.utils import timezone
from django.db import transaction as db_transaction
from django.db.models import Sum, Count, Q
from django.core.paginator import Paginator
from decimal import Decimal

from .utils_billing import get_drug_price_for_prescription
from .services.auto_billing_service import AutoBillingService
from .models_accounting import PaymentReceipt, Transaction
from .models_workflow import CashierSession, PaymentRequest, Bill
from .models import Invoice
from .models_pharmacy_walkin import WalkInPharmacySale, WalkInPharmacySaleItem
from .utils_roles import user_has_cashier_access, user_can_waive
from .decorators import (
    block_pharmacy_from_invoice_and_payment,
    invoice_from_bill_remover_required,
    role_required,
    waiver_permission_required,
)

logger = logging.getLogger(__name__)


def _apply_cashier_imaging_display_prices(imaging_studies):
    """Set display_price on each study using batched InvoiceLine / ImagingCatalog queries (avoids N+1)."""
    from collections import defaultdict

    from .models import InvoiceLine
    from .models_advanced import ImagingCatalog

    if not imaging_studies:
        return
    encounter_ids = list({s.encounter_id for s in imaging_studies if getattr(s, 'encounter_id', None)})
    lines_by_enc = defaultdict(list)
    if encounter_ids:
        for ln in InvoiceLine.objects.filter(
            invoice__encounter_id__in=encounter_ids,
            invoice__is_deleted=False,
            is_deleted=False,
        ).select_related('invoice', 'service_code'):
            lines_by_enc[ln.invoice.encounter_id].append(ln)

    need_catalog = []
    for img in imaging_studies:
        patient = getattr(img, 'patient', None) or (
            img.order.encounter.patient if getattr(img, 'order', None) and img.order.encounter else None
        )
        if not patient:
            img.display_price = Decimal('50.00')
            continue
        pid = patient.id
        st = (img.study_type or '').strip()
        enc_id = img.encounter_id
        inv_line = None
        for ln in lines_by_enc.get(enc_id, []):
            if ln.invoice.patient_id != pid:
                continue
            if not st:
                inv_line = ln
                break
            sc_desc = (ln.service_code.description if ln.service_code else '') or ''
            desc = (ln.description or '') or ''
            sl = st.lower()
            if sl in sc_desc.lower() or sl in desc.lower():
                inv_line = ln
                break
        if inv_line:
            img.display_price = inv_line.unit_price or inv_line.line_total
        else:
            img.display_price = None
            need_catalog.append(img)

    modalities = {img.modality for img in need_catalog if getattr(img, 'modality', None)}
    catalog_rows = []
    if modalities:
        catalog_rows = list(
            ImagingCatalog.objects.filter(
                modality__in=modalities,
                is_active=True,
                is_deleted=False,
            )
        )
    for img in need_catalog:
        if img.display_price is not None:
            continue
        st = (img.study_type or '').strip()
        mod = getattr(img, 'modality', None)
        cat = None
        for c in catalog_rows:
            if mod and c.modality != mod:
                continue
            if st and (c.code == st or (c.name and c.name.lower() == st.lower())):
                cat = c
                break
        if cat and getattr(cat, 'price', None):
            img.display_price = cat.price
        else:
            img.display_price = Decimal('50.00')

    for img in imaging_studies:
        if getattr(img, 'display_price', None) is None:
            img.display_price = Decimal('50.00')


def is_cashier(user):
    """Only allow Administrators and Accounting to access cashier views."""
    return user_has_cashier_access(user)


def _patient_matches(patient, search):
    """Return True if patient name or MRN matches search (case-insensitive)."""
    if not search or not patient:
        return True
    s = search.lower()
    fn = (getattr(patient, 'first_name', None) or '').lower()
    ln = (getattr(patient, 'last_name', None) or '').lower()
    full = (getattr(patient, 'full_name', None) or f'{fn} {ln}'.strip()).lower()
    mrn = (getattr(patient, 'mrn', None) or '').lower()
    return s in full or s in fn or s in ln or s in mrn


@login_required
@user_passes_test(is_cashier, login_url='/admin/login/')
def cashier_dashboard(request):
    """
    Unified Cashier Dashboard
    Shows ALL pending payments: Bills, Lab Tests, Prescriptions, Invoices
    Filters: patient name (search), date (for receipts and pending-by-date).
    """
    today = timezone.now().date()
    filter_patient_name = (request.GET.get('patient_name') or request.GET.get('search') or '').strip()
    filter_date_str = (request.GET.get('date') or '').strip()
    filter_today_pending = request.GET.get('today_pending') == '1'
    try:
        from datetime import datetime
        filter_date = datetime.strptime(filter_date_str, '%Y-%m-%d').date() if filter_date_str else today
    except (ValueError, TypeError):
        filter_date = today
    # Default to "today's pending" when no date/patient/search so first load is fast
    use_date_filter = bool(filter_date_str)
    if filter_today_pending:
        use_date_filter = True
        filter_date = today
    if not filter_patient_name and not filter_date_str and not filter_today_pending:
        use_date_filter = True
        filter_date = today
    # Empty when no ?date= so the picker does not imply a day filter; dashboard still uses today internally for labs/receipts.
    filter_date_display = filter_date_str
    is_filtered = bool(filter_patient_name or use_date_filter or filter_today_pending)
    receipts_date = filter_date if use_date_filter else today

    # Cap per type so unfiltered requests stay bounded (e.g. "Show all" with date)
    CASHIER_DASHBOARD_CAP = 500

    def _item_date(item, kind):
        try:
            if kind == 'lab':
                c = getattr(item, 'created', None)
                return c.date() if c else None
            if kind == 'pharmacy':
                # Use invoice line / dispensing activity so "Send to Cashier" shows on the right day
                _lines = getattr(item, 'invoice_lines', None)
                if _lines is not None:
                    for l in _lines.all():
                        if getattr(l, 'waived_at', None) or getattr(l, 'is_deleted', False):
                            continue
                        m = getattr(l, 'modified', None) or getattr(l, 'created', None)
                        if m:
                            return (
                                timezone.localtime(m).date()
                                if getattr(m, 'tzinfo', None)
                                else m.date()
                            )
                disp = getattr(item, 'dispensing_record', None)
                if disp:
                    m = getattr(disp, 'modified', None) or getattr(disp, 'created', None)
                    if m:
                        return (
                            timezone.localtime(m).date()
                            if getattr(m, 'tzinfo', None)
                            else m.date()
                        )
                c = getattr(item, 'created', None)
                if not c:
                    return None
                return (
                    timezone.localtime(c).date()
                    if getattr(c, 'tzinfo', None)
                    else c.date()
                )
            if kind == 'payment':
                c = getattr(item, 'requested_at', None) or getattr(item, 'created', None)
                return c.date() if c else None
            if kind == 'bill':
                c = getattr(item, 'issued_at', None) or getattr(item, 'created', None)
                return c.date() if c else None
            if kind == 'walkin':
                d = getattr(item, 'sale_date', None) or getattr(item, 'created', None)
                return d.date() if d else None
        except Exception:
            return None
        return None

    # Get or create open session
    session = CashierSession.objects.filter(
        cashier=request.user,
        status='open',
        is_deleted=False
    ).first()
    
    if not session:
        session = CashierSession.objects.create(
            cashier=request.user,
            opening_cash=Decimal('0.00'),
        )
    else:
        # Recalculate totals to ensure accuracy
        session.calculate_totals()
    
    # 🧪 PENDING LAB TESTS (not paid)
    from .models import LabResult, Prescription
    from django.db.models import Q
    
    # Include tests that are either verified OR explicitly sent to cashier; filter by date at DB when applicable
    all_labs = LabResult.objects.filter(
        is_deleted=False
    ).filter(
        Q(verified_by__isnull=False) | Q(release_record__sent_to_cashier_at__isnull=False)
    )
    if use_date_filter:
        all_labs = all_labs.filter(created__date=filter_date)
    all_labs = all_labs.select_related(
        'test',
        'order__encounter__patient',
        'release_record'
    ).order_by('-created')[:CASHIER_DASHBOARD_CAP]
    
    # DEDUPLICATION: Remove duplicates before processing
    seen_lab_keys = {}
    unique_labs = []
    for lab in all_labs:
        # Create unique key: patient + test + order
        key = (lab.order.encounter.patient_id if lab.order.encounter else None, lab.test_id, lab.order_id)
        if key not in seen_lab_keys:
            seen_lab_keys[key] = lab
            unique_labs.append(lab)
        else:
            # Keep the one with higher status or more recent
            existing = seen_lab_keys[key]
            existing_time = existing.verified_at or existing.created
            current_time = lab.verified_at or lab.created
            if current_time > existing_time or (lab.status == 'completed' and existing.status != 'completed'):
                # Replace with better one
                unique_labs.remove(existing)
                seen_lab_keys[key] = lab
                unique_labs.append(lab)
    
    pending_labs = []
    for lab in unique_labs:
        release_record = getattr(lab, 'release_record', None)

        # Skip if already paid
        if release_record and release_record.payment_receipt_id:
            continue

        # Do not create bill in dashboard loop; bill is created on first "Process payment" for this item
        pending_labs.append(lab)
    
    # 💊 PENDING PRESCRIPTIONS (not paid) – date filter at DB, cap, prefetch to avoid N+1
    from .models import InvoiceLine
    from django.db.models import Prefetch
    all_prescriptions = Prescription.objects.filter(
        is_deleted=False
    )
    if use_date_filter:
        # Do not use prescription.created only — Rx is often older than "Send to Cashier" (invoice line).
        all_prescriptions = all_prescriptions.filter(
            Q(created__date=filter_date)
            | Q(
                invoice_lines__is_deleted=False,
                invoice_lines__waived_at__isnull=True,
                invoice_lines__modified__date=filter_date,
            )
            | Q(
                invoice_lines__is_deleted=False,
                invoice_lines__waived_at__isnull=True,
                invoice_lines__created__date=filter_date,
            )
            | Q(
                dispensing_record__is_deleted=False,
                dispensing_record__modified__date=filter_date,
            )
        ).distinct()
    all_prescriptions = all_prescriptions.select_related(
        'drug',
        'order__encounter',
        'order__encounter__patient',
        'prescribed_by',
        'dispensing_record',
        'dispensing_record__substitute_drug',
    ).prefetch_related(
        Prefetch('invoice_lines', queryset=InvoiceLine.objects.filter(is_deleted=False))
    ).order_by('-created')[:CASHIER_DASHBOARD_CAP]
    
    # DEDUPLICATION: Remove duplicates before processing
    seen_prescription_keys = {}
    unique_prescriptions = []
    for rx in all_prescriptions:
        # Create unique key: patient + drug + order
        key = (rx.order.encounter.patient_id if rx.order.encounter else None, rx.drug_id, rx.order_id)
        if key not in seen_prescription_keys:
            seen_prescription_keys[key] = rx
            unique_prescriptions.append(rx)
        else:
            # Keep the more recent one
            existing = seen_prescription_keys[key]
            if rx.created > existing.created:
                # Replace with newer one
                unique_prescriptions.remove(existing)
                seen_prescription_keys[key] = rx
                unique_prescriptions.append(rx)
    
    pending_pharmacy = []
    seen_prescriptions = set()  # Track seen prescription IDs to prevent duplicates
    
    for rx in unique_prescriptions:
        # Skip if we've already added this prescription
        if rx.id in seen_prescriptions:
            continue
        
        # Use prefetched dispensing_record (no N+1)
        try:
            dispensing = getattr(rx, 'dispensing_record', None)
            if dispensing and dispensing.payment_receipt_id:
                continue  # Already paid
            # Do not show if pharmacy removed or cancelled this item
            if dispensing and (
                dispensing.dispensing_status == 'cancelled' or
                (dispensing.quantity_ordered or 0) <= 0
            ):
                continue
            if dispensing and (
                dispensing.dispensing_status == 'ready_to_dispense'
                and getattr(dispensing, 'payment_verified_at', None)
                and not dispensing.payment_receipt_id
            ):
                continue
            # Use pharmacy-edited drug and quantity for display
            effective_drug = dispensing.drug_to_dispense if dispensing else rx.drug
            effective_qty = (dispensing.quantity_ordered or 0) if dispensing else (rx.quantity or 0)
            if effective_drug:
                rx.display_drug_name = f"{effective_drug.name} {getattr(effective_drug, 'strength', '') or ''}".strip()
                rx.display_quantity = effective_qty
                rx._effective_drug = effective_drug
                rx._effective_qty = effective_qty
        except Exception:
            rx._effective_drug = None
            rx._effective_qty = None
        
        # Use prefetched invoice_lines (no N+1)
        try:
            _lines = getattr(rx, 'invoice_lines', None)
            invoice_line = next(
                (l for l in (_lines.all() if _lines is not None else [])
                if not getattr(l, 'waived_at', None)),
                None
            )
            if invoice_line:
                # Skip waived drugs - quantity returns to stock, not pending for payment
                if invoice_line.waived_at:
                    continue
                rx.requires_cash_payment = invoice_line.patient_pay_cash
                rx.exclusion_reason = invoice_line.insurance_exclusion_reason
                # Get price from invoice line (already reflects pharmacy edits when created via send-to-cashier)
                rx.total_price = invoice_line.line_total
            else:
                # Pharmacy has not sent to cashier yet — do not show as pending payment here
                continue
        except Exception:
            continue
        
        # Add to pending list and mark as seen
        pending_pharmacy.append(rx)
        seen_prescriptions.add(rx.id)

    # ----- Apply patient/date filters to labs and pharmacy -----
    if filter_patient_name:
        pending_labs = [lab for lab in pending_labs if _patient_matches(lab.order.encounter.patient, filter_patient_name)]
        pending_pharmacy = [rx for rx in pending_pharmacy if _patient_matches(rx.order.encounter.patient, filter_patient_name)]
    if use_date_filter:
        from datetime import timedelta
        _allowed_rx_dates = (today, today - timedelta(days=1)) if filter_date == today else (filter_date,)
        pending_labs = [lab for lab in pending_labs if _item_date(lab, 'lab') == filter_date]
        pending_pharmacy = [rx for rx in pending_pharmacy if _item_date(rx, 'pharmacy') in _allowed_rx_dates]
    
    # Revenue + activity stats (use selected date when date filter is on)
    todays_receipts_qs = PaymentReceipt.objects.filter(
        receipt_date__date=receipts_date,
        is_deleted=False
    )
    today_total = todays_receipts_qs.aggregate(total=Sum('amount_paid'))['total'] or Decimal('0.00')
    today_count = todays_receipts_qs.count()
    
    # Pending payment requests headed to cashier
    pending_payments_qs = PaymentRequest.objects.filter(
        is_deleted=False,
        status__in=['pending', 'processing']
    ).select_related('invoice', 'invoice__payer', 'patient').order_by('-requested_at')
    pending_payments = list(pending_payments_qs[:20])
    if filter_patient_name:
        pending_payments = [p for p in pending_payments if getattr(p, 'patient', None) and _patient_matches(p.patient, filter_patient_name)]
    if use_date_filter:
        pending_payments = [p for p in pending_payments if _item_date(p, 'payment') == filter_date]
    total_pending_payment_requests = len(pending_payments)
    
    # Unpaid bills (cash + insurance portions)
    unpaid_bills_qs = Bill.objects.filter(
        is_deleted=False,
        status__in=['issued', 'partially_paid']
    ).select_related('patient', 'invoice').order_by('-issued_at')
    unpaid_bills = list(unpaid_bills_qs[:20])
    if filter_patient_name:
        unpaid_bills = [b for b in unpaid_bills if getattr(b, 'patient', None) and _patient_matches(b.patient, filter_patient_name)]
    if use_date_filter:
        unpaid_bills = [b for b in unpaid_bills if _item_date(b, 'bill') == filter_date]
    
    # Accounts receivable snapshot (unchanged by filters)
    outstanding_invoices_qs = Invoice.objects.filter(
        is_deleted=False,
        status__in=['issued', 'partially_paid', 'overdue']
    )
    outstanding_debt = outstanding_invoices_qs.aggregate(total=Sum('balance'))['total'] or Decimal('0.00')
    patients_with_debt_count = outstanding_invoices_qs.values('patient_id').distinct().count()

    # Walk-in pharmacy (Prescribe) — filter at DB by date before [:20], else today's rows can be missing
    # when many older sales exist (slice-then-filter bug). Match centralized: waived excluded, cash payer only.
    from datetime import timedelta as _td
    pending_walkin_qs = WalkInPharmacySale.objects.filter(
        is_deleted=False,
        payment_status__in=['pending', 'partial'],
        waived_at__isnull=True,
    ).filter(
        Q(payer__isnull=True) | Q(payer__payer_type='cash')
    )
    if use_date_filter:
        if filter_date == today:
            last_24h = timezone.now() - _td(hours=24)
            pending_walkin_qs = pending_walkin_qs.filter(
                Q(sale_date__gte=last_24h)
                | Q(sale_date__date=today)
                | Q(sale_date__isnull=True, created__date=today)
            )
        else:
            pending_walkin_qs = pending_walkin_qs.filter(
                Q(sale_date__date=filter_date)
                | Q(sale_date__isnull=True, created__date=filter_date)
            )
    if filter_patient_name:
        sn = filter_patient_name.strip()
        pending_walkin_qs = pending_walkin_qs.filter(
            Q(patient__first_name__icontains=sn)
            | Q(patient__last_name__icontains=sn)
            | Q(patient__mrn__icontains=sn)
            | Q(customer_name__icontains=sn)
            | Q(sale_number__icontains=sn)
        )
    pending_walkin_qs = pending_walkin_qs.order_by('-sale_date')
    total_pending_walkin = pending_walkin_qs.count()
    pending_walkin_sales = list(pending_walkin_qs[:20])

    # Pending Imaging (scans) – unpaid imaging studies; date filter at DB, cap, no create_bill in loop
    from .models_advanced import ImagingStudy
    IMAGING_BILLABLE = ['in_progress', 'completed', 'quality_check', 'awaiting_report', 'reporting', 'reported', 'verified']
    all_imaging = ImagingStudy.objects.filter(
        is_deleted=False,
        status__in=IMAGING_BILLABLE
    )
    if use_date_filter:
        all_imaging = all_imaging.filter(
            Q(performed_at__date=filter_date) | Q(performed_at__isnull=True, created__date=filter_date)
        )
    all_imaging = list(
        all_imaging.select_related(
            'order__encounter__patient', 'patient', 'encounter'
        ).prefetch_related('release_record').order_by('-performed_at', '-created')[:CASHIER_DASHBOARD_CAP]
    )
    _apply_cashier_imaging_display_prices(all_imaging)
    pending_imaging = []
    for img in all_imaging:
        try:
            release = getattr(img, 'release_record', None)
            if release and getattr(release, 'payment_receipt_id', None):
                continue
            patient = getattr(img, 'patient', None) or (img.order.encounter.patient if getattr(img, 'order', None) else None)
            if not patient:
                continue
            pending_imaging.append(img)
        except Exception:
            continue
    if filter_patient_name:
        _img_patient = lambda i: getattr(i, 'patient', None) or (i.order.encounter.patient if getattr(i, 'order', None) else None)
        pending_imaging = [img for img in pending_imaging if _img_patient(img) and _patient_matches(_img_patient(img), filter_patient_name)]
    if use_date_filter:
        pending_imaging = [img for img in pending_imaging if ((getattr(img, 'performed_at', None) or getattr(img, 'created', None)) and (getattr(img, 'performed_at', None) or getattr(img, 'created', None)).date() == filter_date)]

    # Pending Consultation – same rules as cashier_all_pending_bills (consultation): active encounters, unpaid
    # by receipt rules, priced via get_consultation_price_for_encounter (invoice line optional; pricing fallback).
    pending_consultation = []
    try:
        from datetime import timedelta
        from django.db.models.functions import TruncDate

        from .models import Encounter
        from .utils_billing import (
            bulk_consultation_lines_for_encounters,
            get_consultation_price_for_encounter,
            local_datetime_bounds_for_date,
        )

        class _ConsultDashRow:
            __slots__ = ('patient', 'encounter', 'balance', 'consultation_display')

            def __init__(self, encounter, amount, label):
                self.patient = encounter.patient
                self.encounter = encounter
                self.balance = amount
                self.consultation_display = label

        consultation_paid_ids = set(
            PaymentReceipt.objects.filter(
                is_deleted=False,
                service_type='consultation',
                invoice__encounter_id__isnull=False,
            ).values_list('invoice__encounter_id', flat=True).distinct()
        )
        old_consultation_rows = PaymentReceipt.objects.filter(
            is_deleted=False,
            service_type='consultation',
            invoice__encounter_id__isnull=True,
        ).annotate(rd=TruncDate('receipt_date')).values_list('patient_id', 'rd')
        max_receipt_by_patient = {}
        for pid, rd in old_consultation_rows:
            if pid is None:
                continue
            prev = max_receipt_by_patient.get(pid)
            if prev is None or rd > prev:
                max_receipt_by_patient[pid] = rd

        # Match views_centralized_cashier.cashier_all_pending_bills: consultation rows use status=active only
        enc_qs = Encounter.objects.filter(
            is_deleted=False, status='active'
        ).select_related('patient').order_by('-started_at')
        # Consultation date scope is separate from the rest of the dashboard: when the user did not
        # pass ?date=, show a rolling window so unpaid visit fees are not hidden just because
        # nothing was booked today. Explicit date or "today pending" keeps a single-day/today scope.
        CONSULTATION_DEFAULT_LOOKBACK_DAYS = 30
        if filter_today_pending:
            last_24h = timezone.now() - timedelta(hours=24)
            d0, d1 = local_datetime_bounds_for_date(today)
            enc_qs = enc_qs.filter(
                Q(started_at__gte=d0, started_at__lt=d1) | Q(started_at__gte=last_24h)
            )
        elif filter_date_str:
            if filter_date == today:
                last_24h = timezone.now() - timedelta(hours=24)
                d0, d1 = local_datetime_bounds_for_date(filter_date)
                enc_qs = enc_qs.filter(
                    Q(started_at__gte=d0, started_at__lt=d1) | Q(started_at__gte=last_24h)
                )
            else:
                d0, d1 = local_datetime_bounds_for_date(filter_date)
                enc_qs = enc_qs.filter(started_at__gte=d0, started_at__lt=d1)
        else:
            since = timezone.now() - timedelta(days=CONSULTATION_DEFAULT_LOOKBACK_DAYS)
            enc_qs = enc_qs.filter(started_at__gte=since)
        enc_qs = enc_qs[:CASHIER_DASHBOARD_CAP]

        enc_list = list(enc_qs)
        consultation_line_by_enc = bulk_consultation_lines_for_encounters([e.id for e in enc_list])

        for e in enc_list:
            if e.id in consultation_paid_ids:
                continue
            line = consultation_line_by_enc.get(e.id)
            if line is not None:
                cp = get_consultation_price_for_encounter(e, preloaded_consultation_line=line)
            else:
                cp = get_consultation_price_for_encounter(e)
            if cp == Decimal('30.00'):
                cp = Decimal('150.00')
            if cp is None or cp <= 0:
                continue
            _sa = e.started_at
            if _sa and getattr(_sa, 'tzinfo', None):
                started_date = timezone.localtime(_sa).date()
            else:
                started_date = _sa.date() if _sa else None
            mr = max_receipt_by_patient.get(e.patient_id)
            if mr is not None and started_date and mr >= started_date:
                continue
            enc_type_lower = (e.encounter_type or '').lower()
            label = (
                'Specialist Consultation'
                if enc_type_lower == 'specialist'
                else f'{e.get_encounter_type_display()} Consultation'
            )
            pending_consultation.append(_ConsultDashRow(e, cp, label))
    except Exception:
        logger.exception('cashier_dashboard: pending_consultation (reception/front desk) failed')
    if filter_patient_name:
        pending_consultation = [
            row for row in pending_consultation if _patient_matches(getattr(row, 'patient', None), filter_patient_name)
        ]
    # Do not re-filter by date here — enc_qs already uses local day bounds (+ last 24h for "today").
    # A second pass compared row date to filter_date and dropped every row on timezone/naive-datetime edge cases.
    
    total_pending_payments = (
        total_pending_payment_requests
        + len(pending_labs)
        + len(pending_pharmacy)
        + total_pending_walkin
        + len(pending_imaging)
        + len(pending_consultation)
    )
    
    context = {
        'session': session,
        'pending_labs': pending_labs[:20],  # Limit to 20 for performance
        'pending_pharmacy': pending_pharmacy[:20],
        'pending_imaging': pending_imaging[:20],
        'pending_consultation': pending_consultation[:20],
        'total_pending_labs': len(pending_labs),
        'total_pending_pharmacy': len(pending_pharmacy),
        'total_pending_imaging': len(pending_imaging),
        'total_pending_consultation': len(pending_consultation),
        'today_total': today_total,
        'today_count': today_count,
        'pending_payments': pending_payments,
        'total_pending_payments': total_pending_payments,
        'total_pending_payment_requests': total_pending_payment_requests,
        'unpaid_bills': unpaid_bills,
        'outstanding_debt': outstanding_debt,
        'patients_with_debt_count': patients_with_debt_count,
        'pending_walkin_sales': pending_walkin_sales,
        'total_pending_walkin': total_pending_walkin,
        'filter_patient_name': filter_patient_name,
        'filter_date_str': filter_date_str,
        'filter_date_display': filter_date_display,
        'filter_today_pending': filter_today_pending,
        'use_date_filter': use_date_filter,
        'is_filtered': is_filtered,
        'receipts_date': receipts_date,
    }
    return render(request, 'hospital/cashier_dashboard.html', context)


@login_required
@user_passes_test(is_cashier, login_url='/admin/login/')
def payment_receipt(request, receipt_id):
    """View payment receipt (digital) with items paid for."""
    from .views_unified_payments import _receipt_items_paid_for
    receipt = get_object_or_404(PaymentReceipt, pk=receipt_id, is_deleted=False)
    receipt_items = _receipt_items_paid_for(receipt)
    context = {
        'receipt': receipt,
        'receipt_items': receipt_items,
    }
    return render(request, 'hospital/payment_receipt.html', context)


@login_required
@user_passes_test(is_cashier, login_url='/admin/login/')
def cashier_receipts_list(request):
    """List all payment receipts for cashier - grouped by patient (one name, combined receipts)."""
    from datetime import datetime
    from django.db.models import Sum
    from collections import OrderedDict

    query = (request.GET.get('q') or request.GET.get('search') or '').strip()
    date_from_str = (request.GET.get('date_from') or '').strip()
    date_to_str = (request.GET.get('date_to') or '').strip()

    receipts_qs = (
        PaymentReceipt.objects.filter(is_deleted=False)
        .select_related('patient', 'invoice', 'received_by')
        .order_by('-receipt_date')
    )
    if date_from_str:
        try:
            date_from = datetime.strptime(date_from_str, '%Y-%m-%d').date()
            receipts_qs = receipts_qs.filter(receipt_date__date__gte=date_from)
        except ValueError:
            pass
    if date_to_str:
        try:
            date_to = datetime.strptime(date_to_str, '%Y-%m-%d').date()
            receipts_qs = receipts_qs.filter(receipt_date__date__lte=date_to)
        except ValueError:
            pass
    if query:
        receipts_qs = receipts_qs.filter(
            Q(receipt_number__icontains=query) |
            Q(patient__first_name__icontains=query) |
            Q(patient__last_name__icontains=query) |
            Q(patient__mrn__icontains=query)
        )

    # Prefer hiding "Part of combined bill" piece receipts so one combined receipt shows per payment
    # If that would show no rows, show all receipts so the list is never empty when data exists
    qs_no_pieces = receipts_qs.exclude(notes__icontains='Part of combined bill')
    receipts_list = list(qs_no_pieces[:500])
    if not receipts_list:
        receipts_list = list(receipts_qs[:500])
    total_count = receipts_qs.count()
    total_amount = receipts_qs.aggregate(s=Sum('amount_paid'))['s'] or Decimal('0.00')

    # Group by patient: one name, all receipts combined under that person
    by_patient = OrderedDict()
    for r in receipts_list:
        pid = r.patient_id
        patient = getattr(r, 'patient', None)
        if patient is None and pid is None:
            continue
        if pid not in by_patient:
            by_patient[pid] = {'patient': patient, 'receipts': [], 'total_amount': Decimal('0.00')}
        by_patient[pid]['receipts'].append(r)
        by_patient[pid]['total_amount'] += (r.amount_paid or Decimal('0.00'))
    receipts_by_patient = sorted(
        [g for g in by_patient.values() if g['patient'] is not None],
        key=lambda x: max((r.receipt_date for r in x['receipts']), default=timezone.now()),
        reverse=True
    )

    context = {
        'receipts_by_patient': receipts_by_patient,
        'total_amount': total_amount,
        'total_count': total_count,
        'query': query,
        'date_from': date_from_str,
        'date_to': date_to_str,
    }
    return render(request, 'hospital/cashier_receipts_list.html', context)


@login_required
@user_passes_test(is_cashier, login_url='/admin/login/')
def close_session(request, session_id):
    """Close cashier session and reconcile"""
    session = get_object_or_404(CashierSession, pk=session_id, is_deleted=False, cashier=request.user)
    
    if request.method == 'POST':
        actual_cash = Decimal(request.POST.get('actual_cash', 0))
        closing_notes = request.POST.get('notes', '')
        denomination_breakdown = request.POST.get('denomination_breakdown', '')
        
        # VALIDATION: Require denomination breakdown
        if not denomination_breakdown:
            messages.error(request, 'You must count and enter all cash denominations before closing the session.')
            session.calculate_totals()
            context = {'session': session}
            return render(request, 'hospital/close_session.html', context)
        
        # VALIDATION: Verify denomination breakdown matches actual cash
        try:
            import json
            breakdown = json.loads(denomination_breakdown)
            calculated_total = Decimal('0.00')
            for denom, data in breakdown.items():
                count = Decimal(str(data.get('count', 0)))
                denom_value = Decimal(str(data.get('denomination', 0)))
                calculated_total += count * denom_value
            
            # Allow small rounding differences (up to 0.01)
            if abs(calculated_total - actual_cash) > Decimal('0.01'):
                messages.error(
                    request, 
                    f'Denomination breakdown total (GH¢{calculated_total:,.2f}) does not match entered total (GH¢{actual_cash:,.2f}). Please recount.'
                )
                session.calculate_totals()
                context = {'session': session}
                return render(request, 'hospital/close_session.html', context)
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            messages.error(request, f'Invalid denomination breakdown format. Please recount all denominations. Error: {str(e)}')
            session.calculate_totals()
            context = {'session': session}
            return render(request, 'hospital/close_session.html', context)
        
        # VALIDATION: Recalculate totals from transactions to ensure accuracy
        session.calculate_totals()
        session.refresh_from_db()
        
        # VALIDATION: Verify actual cash matches expected cash (with tolerance for small variances)
        variance = actual_cash - session.expected_cash
        variance_tolerance = Decimal('0.50')  # Allow up to 50 pesewas variance
        
        # If variance is significant, require explanation
        if abs(variance) > variance_tolerance:
            variance_percent = abs(variance) / session.expected_cash * 100 if session.expected_cash > 0 else 0
            if variance_percent > 1:
                # Require notes for large variances
                if not closing_notes or len(closing_notes.strip()) < 10:
                    messages.error(
                        request,
                        f'⚠️ REQUIRED: Cash variance of GH¢{abs(variance):,.2f} ({variance_percent:.2f}%) requires an explanation. '
                        f'Expected: GH¢{session.expected_cash:,.2f}, Actual: GH¢{actual_cash:,.2f}. '
                        f'Please provide detailed notes explaining the variance before closing.'
                    )
                    session.calculate_totals()
                    context = {'session': session}
                    return render(request, 'hospital/close_session.html', context)
                else:
                    messages.warning(
                        request,
                        f'⚠️ WARNING: Cash variance of GH¢{abs(variance):,.2f} ({variance_percent:.2f}%) exceeds normal tolerance. '
                        f'Expected: GH¢{session.expected_cash:,.2f}, Actual: GH¢{actual_cash:,.2f}. '
                        f'Your explanation has been recorded for review.'
                    )
        
        # Get forensic information
        close_datetime = timezone.now()
        ip_address = request.META.get('REMOTE_ADDR', 'Unknown')
        user_agent = request.META.get('HTTP_USER_AGENT', 'Unknown')
        forward_ip = request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip() if request.META.get('HTTP_X_FORWARDED_FOR') else None
        effective_ip = forward_ip if forward_ip else ip_address
        
        # Calculate session duration
        session_duration = close_datetime - session.opened_at
        duration_hours = int(session_duration.total_seconds() // 3600)
        duration_minutes = int((session_duration.total_seconds() % 3600) // 60)
        duration_seconds = int(session_duration.total_seconds() % 60)
        
        # Build forensic audit trail notes
        notes_parts = []
        notes_parts.append("=" * 80)
        notes_parts.append("CASHIER SESSION CLOSURE - FORENSIC AUDIT TRAIL")
        notes_parts.append("=" * 80)
        notes_parts.append("")
        
        # Timestamp Information
        notes_parts.append("TIMESTAMP INFORMATION:")
        notes_parts.append("-" * 80)
        notes_parts.append(f"  Closure Date/Time (UTC):     {close_datetime.strftime('%Y-%m-%d %H:%M:%S')} UTC")
        notes_parts.append(f"  Closure Date/Time (Local):   {close_datetime.astimezone(timezone.get_current_timezone()).strftime('%Y-%m-%d %H:%M:%S %Z')}")
        notes_parts.append(f"  Session Opened At:           {session.opened_at.strftime('%Y-%m-%d %H:%M:%S')} UTC")
        notes_parts.append(f"  Session Duration:            {duration_hours:02d}h {duration_minutes:02d}m {duration_seconds:02d}s")
        notes_parts.append("")
        
        # User Information
        notes_parts.append("USER INFORMATION:")
        notes_parts.append("-" * 80)
        notes_parts.append(f"  User ID:                     {request.user.id}")
        notes_parts.append(f"  Username:                    {request.user.username}")
        notes_parts.append(f"  Full Name:                   {request.user.get_full_name() or 'N/A'}")
        notes_parts.append(f"  Email:                       {request.user.email or 'N/A'}")
        notes_parts.append(f"  Session Cashier:             {session.cashier.get_full_name() or session.cashier.username}")
        notes_parts.append("")
        
        # System Information
        notes_parts.append("SYSTEM INFORMATION:")
        notes_parts.append("-" * 80)
        notes_parts.append(f"  IP Address:                  {effective_ip}")
        if forward_ip and forward_ip != ip_address:
            notes_parts.append(f"  Original IP:                 {ip_address}")
        notes_parts.append(f"  User Agent:                  {user_agent[:100] if len(user_agent) > 100 else user_agent}")
        notes_parts.append(f"  Session ID:                  {session.session_number}")
        notes_parts.append("")
        
        # Session Summary
        notes_parts.append("SESSION SUMMARY:")
        notes_parts.append("-" * 80)
        notes_parts.append(f"  Opening Cash:                GH¢{session.opening_cash:,.2f}")
        notes_parts.append(f"  Total Payments Received:     GH¢{session.total_payments:,.2f}")
        notes_parts.append(f"  Total Refunds Issued:        GH¢{session.total_refunds:,.2f}")
        notes_parts.append(f"  Expected Cash:               GH¢{session.expected_cash:,.2f}")
        notes_parts.append(f"  Total Transactions:          {session.total_transactions:,}")
        notes_parts.append("")
        
        # Payment Method Breakdown
        from .models_accounting import Transaction
        from datetime import timedelta
        session_end = session.closed_at if session.closed_at else timezone.now()
        session_start = session.opened_at
        
        payment_methods_breakdown = Transaction.objects.filter(
            processed_by=session.cashier,
            transaction_date__gte=session_start,
            transaction_date__lte=session_end + timedelta(days=1),
            transaction_type='payment_received',
            is_deleted=False
        ).values('payment_method').annotate(
            total_amount=Sum('amount'),
            count=Count('id')
        ).order_by('-total_amount')
        
        if payment_methods_breakdown:
            notes_parts.append("=" * 80)
            notes_parts.append("PAYMENT METHOD BREAKDOWN:")
            notes_parts.append("=" * 80)
            notes_parts.append("")
            notes_parts.append(f"{'Payment Method':<25} {'Count':>10} {'Total Amount':>20}")
            notes_parts.append("-" * 80)
            
            method_labels = {
                'cash': 'Cash',
                'mobile_money': 'Mobile Money (MOMO)',
                'card': 'Card',
                'bank_transfer': 'Bank Transfer',
                'cheque': 'Cheque',
                'insurance': 'Insurance'
            }
            
            for method_data in payment_methods_breakdown:
                method = method_data['payment_method']
                method_label = method_labels.get(method, method.replace('_', ' ').title())
                count = method_data['count']
                total = method_data['total_amount']
                notes_parts.append(f"  {method_label:<23} {count:10,d} {total:>20,.2f}")
            
            notes_parts.append("-" * 80)
            total_all_methods = sum(m['total_amount'] for m in payment_methods_breakdown)
            notes_parts.append(f"  {'TOTAL':<23} {sum(m['count'] for m in payment_methods_breakdown):10,d} {total_all_methods:>20,.2f}")
            notes_parts.append("")
        
        # Cash Count by Denomination
        if denomination_breakdown:
            try:
                import json
                breakdown = json.loads(denomination_breakdown)
                if breakdown:
                    notes_parts.append("=" * 80)
                    notes_parts.append("CASH COUNT BY DENOMINATION:")
                    notes_parts.append("=" * 80)
                    notes_parts.append("")
                    notes_parts.append(f"{'Denomination':<20} {'Count':>10} {'Value Each':>15} {'Subtotal':>20}")
                    notes_parts.append("-" * 80)
                    
                    # Sort by denomination value (highest first)
                    sorted_denoms = sorted(breakdown.items(), key=lambda x: float(x[0]), reverse=True)
                    for denom, data in sorted_denoms:
                        count = int(data['count'])
                        value = data['denomination']
                        subtotal = data['subtotal']
                        if value >= 1:
                            denom_label = f"GH¢{value:,.0f}"
                            value_label = f"GH¢{value:,.0f}"
                        else:
                            pesewas = int(value * 100)
                            denom_label = f"{pesewas}p"
                            value_label = f"GH¢{value:.2f}"
                        notes_parts.append(f"  {denom_label:<15} {count:10,d} × {value_label:>10} {subtotal:>20,.2f}")
                    
                    notes_parts.append("-" * 80)
                    notes_parts.append(f"  {'TOTAL COUNTED':<15} {'':>10} {'':>10} {actual_cash:>20,.2f}")
                    notes_parts.append("")
            
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                notes_parts.append("=" * 80)
                notes_parts.append("CASH COUNT BY DENOMINATION:")
                notes_parts.append("=" * 80)
                notes_parts.append("  ERROR: Could not parse denomination breakdown")
                notes_parts.append(f"  Error: {str(e)}")
                notes_parts.append(f"  Total Counted: GH¢{actual_cash:,.2f}")
                notes_parts.append("")
        else:
            notes_parts.append("=" * 80)
            notes_parts.append("CASH COUNT:")
            notes_parts.append("=" * 80)
            notes_parts.append(f"  Total Counted: GH¢{actual_cash:,.2f}")
            notes_parts.append("  NOTE: Denomination breakdown not provided")
            notes_parts.append("")
        
        # Variance Analysis
        notes_parts.append("=" * 80)
        notes_parts.append("VARIANCE ANALYSIS:")
        notes_parts.append("=" * 80)
        notes_parts.append(f"  Expected Cash:               GH¢{session.expected_cash:,.2f}")
        notes_parts.append(f"  Actual Cash Counted:          GH¢{actual_cash:,.2f}")
        if abs(variance) < 0.01:
            notes_parts.append(f"  Variance:                     GH¢0.00 (EXACT MATCH)")
            notes_parts.append("  Status:                       ✓ NO DISCREPANCY")
        elif variance > 0:
            notes_parts.append(f"  Variance:                     +GH¢{variance:,.2f} (OVER COUNT)")
            notes_parts.append(f"  Status:                       ⚠ DISCREPANCY - Over by GH¢{variance:,.2f}")
        else:
            notes_parts.append(f"  Variance:                     -GH¢{abs(variance):,.2f} (SHORT COUNT)")
            notes_parts.append(f"  Status:                       ⚠ DISCREPANCY - Short by GH¢{abs(variance):,.2f}")
        notes_parts.append("")
        
        # Daily Cash Sales Notes (if provided)
        if session.daily_cash_notes:
            notes_parts.append("=" * 80)
            notes_parts.append("DAILY CASH SALES NOTES:")
            notes_parts.append("=" * 80)
            notes_parts.append(session.daily_cash_notes)
            notes_parts.append("")
        
        # Additional Notes
        if closing_notes:
            notes_parts.append("=" * 80)
            notes_parts.append("ADDITIONAL NOTES:")
            notes_parts.append("=" * 80)
            notes_parts.append(closing_notes)
            notes_parts.append("")
        
        # Footer
        notes_parts.append("=" * 80)
        notes_parts.append("END OF FORENSIC AUDIT TRAIL")
        notes_parts.append("=" * 80)
        notes_parts.append("")
        notes_parts.append(f"This document serves as a legal audit trail of the cashier session closure.")
        notes_parts.append(f"All timestamps, amounts, and actions have been recorded and are tamper-evident.")
        notes_parts.append(f"Generated by: Hospital Management System (HMS)")
        notes_parts.append(f"System Version: Django 4.2.7")
        
        final_notes = "\n".join(notes_parts)
        
        # Save session with forensic information
        session.closing_cash = actual_cash
        session.actual_cash = actual_cash
        session.notes = final_notes
        session.closed_at = close_datetime
        session.status = 'closed'
        session.save()
        
        # Log for audit (if audit middleware is enabled)
        import logging
        logger = logging.getLogger('hospital.audit')
        logger.info(
            f"Cashier session closed: {session.session_number} | "
            f"Cashier: {request.user.username} | "
            f"Expected: GH¢{session.expected_cash:,.2f} | "
            f"Actual: GH¢{actual_cash:,.2f} | "
            f"Variance: GH¢{variance:,.2f} | "
            f"IP: {effective_ip}"
        )
        
        messages.success(request, f'Session closed successfully. Total counted: GH¢{actual_cash:,.2f}. You can now print the closure report.')
        # Redirect to print page after closing - cashier can print to attach to money for account office
        return redirect('hospital:cashier_session_print', session_id=session.pk)
    
    # Calculate expected totals
    session.calculate_totals()
    
    context = {
        'session': session,
    }
    return render(request, 'hospital/close_session.html', context)


@login_required
@user_passes_test(is_cashier, login_url='/admin/login/')
def cashier_session_detail(request):
    """
    Show the cashier's active session (or open a new one) with quick stats.
    All totals and tables use the SESSION time window (opened_at to now/closed_at) so data is real.
    """
    session = CashierSession.objects.filter(
        cashier=request.user,
        status='open',
        is_deleted=False
    ).first()

    if not session:
        session = CashierSession.objects.create(
            cashier=request.user,
            opening_cash=Decimal('0.00'),
        )

    session.calculate_totals()

    # Use session time window so tables match session totals (opened_at → closed_at or now)
    session_end = session.closed_at if session.closed_at else timezone.now()
    session_start = session.opened_at

    recent_transactions = Transaction.objects.filter(
        processed_by=session.cashier,
        transaction_date__gte=session_start,
        transaction_date__lte=session_end,
        is_deleted=False
    ).order_by('-transaction_date')[:50]

    session_receipts_qs = PaymentReceipt.objects.filter(
        received_by=session.cashier,
        receipt_date__gte=session_start,
        receipt_date__lte=session_end,
        is_deleted=False
    ).select_related('patient', 'transaction').order_by('-receipt_date')
    session_receipts = list(session_receipts_qs)
    recent_receipts = session_receipts[:50]

    # Group receipts by payment method for reconciliation (Cash, Card, MoMo, Deposit, etc.)
    method_display = {
        'cash': 'Cash',
        'card': 'Card',
        'mobile_money': 'Mobile Money (MoMo)',
        'bank_transfer': 'Bank Transfer',
        'cheque': 'Cheque',
        'insurance': 'Insurance',
        'deposit': 'Deposit (Patient Credit)',
    }
    receipts_by_method = {}
    for method in ['cash', 'card', 'mobile_money', 'bank_transfer', 'cheque', 'insurance', 'deposit']:
        method_receipts = [r for r in session_receipts if r.payment_method == method]
        total = sum(r.amount_paid for r in method_receipts)
        if method_receipts or total:
            receipts_by_method[method] = {
                'label': method_display.get(method, method.replace('_', ' ').title()),
                'total': total,
                'receipts': method_receipts,
                'count': len(method_receipts),
            }

    today = timezone.now().date()
    context = {
        'session': session,
        'recent_transactions': recent_transactions,
        'recent_receipts': recent_receipts,
        'receipts_by_method': receipts_by_method,
        'today': today,
        'session_start': session_start,
        'session_end': session_end,
    }
    return render(request, 'hospital/cashier_session_detail.html', context)


@login_required
@user_passes_test(is_cashier, login_url='/admin/login/')
def cashier_sessions_list(request):
    """
    List all cashier sessions
    Accountants can see all sessions, cashiers see only their own
    """
    from .utils_roles import get_user_role
    
    user_role = get_user_role(request.user)
    
    # Accountants and admins can see all sessions
    if user_role in ['admin', 'accountant']:
        sessions = CashierSession.objects.filter(is_deleted=False).select_related('cashier').order_by('-opened_at')
    else:
        # Cashiers see only their own sessions
        sessions = CashierSession.objects.filter(
            cashier=request.user,
            is_deleted=False
        ).select_related('cashier').order_by('-opened_at')
    
    # Filter by status if provided
    status_filter = request.GET.get('status', '')
    if status_filter:
        sessions = sessions.filter(status=status_filter)
    
    # Filter by date range if provided
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    if date_from:
        sessions = sessions.filter(opened_at__date__gte=date_from)
    if date_to:
        sessions = sessions.filter(opened_at__date__lte=date_to)
    
    # Calculate totals and variance for each session
    for session in sessions:
        session.calculate_totals()
        # Calculate variance for display
        if session.actual_cash is not None:
            session.variance = session.actual_cash - session.expected_cash
        else:
            session.variance = None
    
    # Pagination
    paginator = Paginator(sessions, 25)  # Show 25 sessions per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Statistics
    total_sessions = sessions.count()
    open_sessions = sessions.filter(status='open').count()
    closed_sessions = sessions.filter(status='closed').count()
    
    total_payments = sessions.aggregate(
        total=Sum('total_payments')
    )['total'] or Decimal('0.00')
    
    total_refunds = sessions.aggregate(
        total=Sum('total_refunds')
    )['total'] or Decimal('0.00')
    
    context = {
        'sessions': page_obj,
        'page_obj': page_obj,
        'status_filter': status_filter,
        'date_from': date_from,
        'date_to': date_to,
        'total_sessions': total_sessions,
        'open_sessions': open_sessions,
        'closed_sessions': closed_sessions,
        'total_payments': total_payments,
        'total_refunds': total_refunds,
        'user_role': user_role,
    }
    
    return render(request, 'hospital/cashier_sessions_list.html', context)


@login_required
@user_passes_test(is_cashier, login_url='/admin/login/')
def cashier_session_print(request, session_id):
    """
    Print-friendly session closure report
    Cashiers can print after closing session to attach to money for account office
    """
    from .utils_roles import get_user_role
    from django.conf import settings
    
    session = get_object_or_404(CashierSession, pk=session_id, is_deleted=False)
    
    # Check permissions - cashiers can only print their own sessions unless admin/accountant
    user_role = get_user_role(request.user)
    if user_role not in ['admin', 'accountant'] and session.cashier != request.user:
        messages.error(request, 'You can only print your own sessions.')
        return redirect('hospital:cashier_sessions_list')
    
    # Calculate variance if session is closed
    variance = None
    if session.actual_cash is not None and session.expected_cash is not None:
        variance = session.actual_cash - session.expected_cash
    
    # Get transactions for this session
    from datetime import timedelta
    session_end = session.closed_at if session.closed_at else timezone.now()
    session_start = session.opened_at
    
    transactions = Transaction.objects.filter(
        processed_by=session.cashier,
        transaction_date__gte=session_start,
        transaction_date__lte=session_end + timedelta(days=1),
        is_deleted=False
    ).select_related('invoice', 'invoice__patient').order_by('transaction_date')
    
    # Get receipts for this session
    receipts = PaymentReceipt.objects.filter(
        received_by=session.cashier,
        receipt_date__gte=session_start,
        receipt_date__lte=session_end + timedelta(days=1),
        is_deleted=False
    ).select_related('patient').order_by('receipt_date')
    
    # Get payment method breakdown for this session
    payment_methods_breakdown = Transaction.objects.filter(
        processed_by=session.cashier,
        transaction_date__gte=session_start,
        transaction_date__lte=session_end + timedelta(days=1),
        transaction_type='payment_received',
        is_deleted=False
    ).values('payment_method').annotate(
        total_amount=Sum('amount'),
        count=Count('id')
    ).order_by('-total_amount')
    
    # Get detailed transactions grouped by payment method
    from .models import InvoiceLine
    detailed_transactions = Transaction.objects.filter(
        processed_by=session.cashier,
        transaction_date__gte=session_start,
        transaction_date__lte=session_end + timedelta(days=1),
        transaction_type='payment_received',
        is_deleted=False
    ).select_related(
        'patient', 
        'invoice', 
        'invoice__patient'
    ).prefetch_related(
        'invoice__lines__service_code'
    ).order_by('payment_method', 'transaction_date')
    
    # Format payment method breakdown for template
    method_labels = {
        'cash': 'Cash',
        'mobile_money': 'Mobile Money (MOMO)',
        'card': 'Card',
        'bank_transfer': 'Bank Transfer',
        'cheque': 'Cheque',
        'insurance': 'Insurance'
    }
    
    payment_method_summary = []
    for method_data in payment_methods_breakdown:
        method = method_data['payment_method']
        
        # Get transactions for this payment method
        method_transactions = [
            txn for txn in detailed_transactions 
            if txn.payment_method == method
        ]
        
        # Build detailed list with patient names and services
        transaction_details = []
        for txn in method_transactions:
            # Get patient name
            patient_name = 'N/A'
            if txn.patient:
                patient_name = txn.patient.full_name or f"{txn.patient.first_name} {txn.patient.last_name}".strip()
            elif txn.invoice and txn.invoice.patient:
                patient_name = txn.invoice.patient.full_name or f"{txn.invoice.patient.first_name} {txn.invoice.patient.last_name}".strip()
            
            # Get services from invoice lines (exclude waived)
            services = []
            if txn.invoice:
                invoice_lines = list(txn.invoice.billable_lines)
                for line in invoice_lines:
                    service_desc = line.description or 'Service'
                    if line.service_code:
                        if line.description:
                            service_desc = f"{line.service_code.code} - {line.description}"
                        else:
                            service_desc = line.service_code.description or line.service_code.code
                    services.append({
                        'description': service_desc,
                        'quantity': float(line.quantity),
                        'unit_price': float(line.unit_price),
                        'line_total': float(line.line_total)
                    })
            
            # If no invoice lines, try to get from notes or use generic description
            if not services:
                if txn.notes:
                    services.append({'description': txn.notes, 'quantity': 1, 'unit_price': txn.amount, 'line_total': txn.amount})
                else:
                    services.append({'description': 'Payment', 'quantity': 1, 'unit_price': txn.amount, 'line_total': txn.amount})
            
            transaction_details.append({
                'transaction_number': txn.transaction_number,
                'patient_name': patient_name,
                'patient_mrn': txn.patient.mrn if txn.patient else (txn.invoice.patient.mrn if txn.invoice and txn.invoice.patient else ''),
                'amount': txn.amount,
                'reference_number': txn.reference_number or '',
                'transaction_date': txn.transaction_date,
                'services': services,
                'invoice_number': txn.invoice.invoice_number if txn.invoice else ''
            })
        
        payment_method_summary.append({
            'method': method,
            'label': method_labels.get(method, method.replace('_', ' ').title()),
            'count': method_data['count'],
            'total': method_data['total_amount'],
            'transactions': transaction_details
        })
    
    # Get hospital name from settings
    hospital_name = getattr(settings, 'HOSPITAL_NAME', 'Hospital Management System')
    
    # Parse denomination breakdown if available
    denomination_breakdown = None
    if session.notes:
        try:
            import json
            # Try to extract denomination breakdown from notes
            if 'CASH COUNT BY DENOMINATION' in session.notes:
                # Extract JSON from notes if embedded
                import re
                json_match = re.search(r'\{[^}]+\}', session.notes)
                if json_match:
                    denomination_breakdown = json.loads(json_match.group())
        except:
            pass
    
    context = {
        'session': session,
        'transactions': transactions,
        'receipts': receipts,
        'variance': variance,
        'hospital_name': hospital_name,
        'denomination_breakdown': denomination_breakdown,
        'payment_method_summary': payment_method_summary,
        'title': f'Session Closure Report - {session.session_number}',
    }
    
    return render(request, 'hospital/cashier_session_print.html', context)


@login_required
@role_required('accountant', 'senior_account_officer', 'admin')
def cashier_history(request, cashier_id):
    """
    View cashier activity history and sales
    Accountants can click on cashier name to see their history
    """
    from django.contrib.auth.models import User
    from .utils_roles import get_user_role
    
    cashier = get_object_or_404(User, pk=cashier_id)
    
    # Get all sessions for this cashier
    sessions = CashierSession.objects.filter(
        cashier=cashier,
        is_deleted=False
    ).select_related('cashier').order_by('-opened_at')
    
    # Calculate variance for each session
    for session in sessions:
        session.calculate_totals()
        if session.actual_cash is not None:
            session.variance = session.actual_cash - session.expected_cash
        else:
            session.variance = None
    
    # Filter by date range if provided
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    if date_from:
        sessions = sessions.filter(opened_at__date__gte=date_from)
    if date_to:
        sessions = sessions.filter(opened_at__date__lte=date_to)
    
    # Get transactions for this cashier
    transactions = Transaction.objects.filter(
        processed_by=cashier,
        is_deleted=False
    ).select_related('invoice', 'invoice__patient').order_by('-transaction_date')
    
    # Filter transactions by date if provided
    if date_from:
        transactions = transactions.filter(transaction_date__date__gte=date_from)
    if date_to:
        transactions = transactions.filter(transaction_date__date__lte=date_to)
    
    # Get receipts for this cashier
    receipts = PaymentReceipt.objects.filter(
        received_by=cashier,
        is_deleted=False
    ).select_related('patient').order_by('-receipt_date')
    
    # Filter receipts by date if provided
    if date_from:
        receipts = receipts.filter(receipt_date__date__gte=date_from)
    if date_to:
        receipts = receipts.filter(receipt_date__date__lte=date_to)
    
    # Statistics
    stats = {
        'total_sessions': sessions.count(),
        'open_sessions': sessions.filter(status='open').count(),
        'closed_sessions': sessions.filter(status='closed').count(),
        'total_payments': sessions.aggregate(total=Sum('total_payments'))['total'] or Decimal('0.00'),
        'total_refunds': sessions.aggregate(total=Sum('total_refunds'))['total'] or Decimal('0.00'),
        'total_transactions': transactions.count(),
        'total_receipts': receipts.count(),
        'total_transaction_amount': transactions.aggregate(total=Sum('amount'))['total'] or Decimal('0.00'),
        'total_receipt_amount': receipts.aggregate(total=Sum('amount_paid'))['total'] or Decimal('0.00'),
    }
    
    # Pagination for sessions
    paginator = Paginator(sessions, 20)
    page_number = request.GET.get('page')
    sessions_page = paginator.get_page(page_number)
    
    # Limit transactions and receipts display
    transactions = transactions[:50]
    receipts = receipts[:50]
    
    context = {
        'cashier': cashier,
        'sessions': sessions_page,
        'transactions': transactions,
        'receipts': receipts,
        'stats': stats,
        'date_from': date_from,
        'date_to': date_to,
        'title': f'Cashier History - {cashier.get_full_name() or cashier.username}',
    }
    
    return render(request, 'hospital/cashier_history.html', context)


@login_required
@user_passes_test(is_cashier, login_url='/admin/login/')
def create_session(request):
    """Create a new cashier session for the day"""
    from .utils_roles import get_user_role
    
    user_role = get_user_role(request.user)
    
    # Check if user already has an open session
    existing_open_session = CashierSession.objects.filter(
        cashier=request.user,
        status='open',
        is_deleted=False
    ).first()
    
    if existing_open_session and user_role not in ['admin', 'accountant']:
        messages.warning(request, f'You already have an open session ({existing_open_session.session_number}). Please close it before creating a new one.')
        return redirect('hospital:cashier_sessions_list')
    
    if request.method == 'POST':
        opening_cash = Decimal(request.POST.get('opening_cash', 0))
        notes = request.POST.get('notes', '')
        daily_cash_notes = request.POST.get('daily_cash_notes', '')
        
        # Create new session
        session = CashierSession.objects.create(
            cashier=request.user,
            opening_cash=opening_cash,
            notes=notes,
            daily_cash_notes=daily_cash_notes,
        )
        
        messages.success(request, f'Session {session.session_number} created successfully!')
        return redirect('hospital:cashier_session_detail')
    
    # Get today's date for context
    today = timezone.now().date()
    
    # Get yesterday's closed session to suggest opening cash
    yesterday_session = CashierSession.objects.filter(
        cashier=request.user,
        status='closed',
        is_deleted=False
    ).order_by('-closed_at').first()
    
    suggested_opening_cash = Decimal('0.00')
    if yesterday_session and yesterday_session.actual_cash:
        suggested_opening_cash = yesterday_session.actual_cash
    
    context = {
        'today': today,
        'suggested_opening_cash': suggested_opening_cash,
        'existing_open_session': existing_open_session,
    }
    return render(request, 'hospital/create_session.html', context)


@login_required
@user_passes_test(is_cashier, login_url='/admin/login/')
def update_session_notes(request, session_id):
    """Update session notes and daily cash notes"""
    session = get_object_or_404(CashierSession, pk=session_id, is_deleted=False)
    
    # Check permissions - cashiers can only update their own sessions
    from .utils_roles import get_user_role
    user_role = get_user_role(request.user)
    
    if user_role not in ['admin', 'accountant'] and session.cashier != request.user:
        messages.error(request, 'You can only update your own sessions.')
        return redirect('hospital:cashier_sessions_list')
    
    if request.method == 'POST':
        session.notes = request.POST.get('notes', '')
        session.daily_cash_notes = request.POST.get('daily_cash_notes', '')
        session.save()
        
        messages.success(request, 'Session notes updated successfully!')
        
        # Redirect based on where they came from
        if request.GET.get('redirect') == 'detail':
            return redirect('hospital:cashier_session_detail')
        return redirect('hospital:cashier_sessions_list')
    
    context = {
        'session': session,
    }
    return render(request, 'hospital/update_session_notes.html', context)


# Placeholder functions for other cashier views that might be referenced
@login_required
@user_passes_test(is_cashier, login_url='/admin/login/')
def cashier_bills(request):
    """View cashier bills - shows PaymentReceipt objects"""
    from .models_accounting import PaymentReceipt
    from django.db.models import Q, Sum
    from decimal import Decimal
    from datetime import timedelta, datetime
    
    status_filter = request.GET.get('status', '')
    query = request.GET.get('q', '')
    filter_date_str = request.GET.get('date', '').strip()
    filter_date = None
    if filter_date_str:
        try:
            filter_date = datetime.strptime(filter_date_str, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            filter_date = None
    
    # Exclude per-service "piece" receipts so only the one combined receipt shows per payment
    receipts = (
        PaymentReceipt.objects.filter(is_deleted=False)
        .exclude(notes__icontains='Part of combined bill')
        .select_related('patient', 'invoice', 'received_by', 'transaction')
        .order_by('-receipt_date')
    )
    
    # Search filter
    if query:
        receipts = receipts.filter(
            Q(receipt_number__icontains=query) |
            Q(patient__first_name__icontains=query) |
            Q(patient__last_name__icontains=query) |
            Q(patient__mrn__icontains=query)
        )
    
    # Date filter: when no date and no search, default to last 30 days so page stays fast
    if filter_date:
        receipts = receipts.filter(receipt_date__date=filter_date)
    elif not query:
        thirty_days_ago = timezone.now() - timedelta(days=30)
        receipts = receipts.filter(receipt_date__gte=thirty_days_ago)
    
    # Status filter (all receipts are paid, but we can filter by service_type)
    if status_filter:
        if status_filter == 'paid':
            # All receipts are paid, so show all
            pass
        elif status_filter == 'issued':
            # Show receipts from last 30 days
            thirty_days_ago = timezone.now() - timedelta(days=30)
            receipts = receipts.filter(receipt_date__gte=thirty_days_ago)
    
    # Limit for performance, then group by patient (receipts put together under person's name)
    receipts_list = list(receipts[:500])
    bills_count = receipts.count()

    # Group by patient: list of { 'patient': patient, 'receipts': [...], 'total_amount': sum }
    from collections import OrderedDict
    by_patient = OrderedDict()
    for r in receipts_list:
        pid = r.patient_id
        if pid not in by_patient:
            by_patient[pid] = {'patient': r.patient, 'receipts': [], 'total_amount': Decimal('0.00')}
        by_patient[pid]['receipts'].append(r)
        by_patient[pid]['total_amount'] += (r.amount_paid or Decimal('0.00'))
    # Sort groups by most recent receipt date (newest first)
    bills_by_patient = sorted(
        by_patient.values(),
        key=lambda x: max((r.receipt_date for r in x['receipts']), default=timezone.now()),
        reverse=True
    )

    # Calculate statistics
    thirty_days_ago = timezone.now() - timedelta(days=30)
    total_issued = receipts.filter(receipt_date__gte=thirty_days_ago).count()
    total_paid = receipts.count()
    total_outstanding = Decimal('0.00')  # Receipts are already paid

    context = {
        'bills_by_patient': bills_by_patient,
        'bills_count': bills_count,
        'total_issued': total_issued,
        'total_paid': total_paid,
        'total_outstanding': total_outstanding,
        'status_filter': status_filter,
        'query': query,
        'filter_date': filter_date_str,
    }

    return render(request, 'hospital/cashier_bills.html', context)


@login_required
@user_passes_test(is_cashier, login_url='/admin/login/')
def cashier_invoices(request):
    """View cashier invoices with statistics and filtering"""
    from .models import Invoice
    from django.core.paginator import Paginator
    from django.db.models import Sum, Q
    from decimal import Decimal
    
    # Get filter parameters
    query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '').strip()
    
    # Handle multiple status filters (comma-separated)
    status_filters = []
    if status_filter:
        status_filters = [s.strip() for s in status_filter.split(',') if s.strip()]
    
    # all_objects: default manager hides total_amount=0 (draft encounter bills) and skews gynae/OPD visibility
    all_invoices = (
        Invoice.all_objects.filter(is_deleted=False)
        .exclude(
            issued_at__date__gte=Invoice.WRITE_OFF_START,
            issued_at__date__lte=Invoice.WRITE_OFF_END,
        )
        .select_related('patient', 'payer', 'encounter')
    )
    
    # Calculate statistics from ALL invoices
    total_invoices = all_invoices.count()
    
    # Total Revenue = sum of all paid invoices
    total_revenue = all_invoices.filter(
        status='paid'
    ).aggregate(Sum('total_amount'))['total_amount__sum'] or Decimal('0.00')
    
    # Outstanding Balance = sum of balances from unpaid invoices
    outstanding_balance = all_invoices.filter(
        status__in=['issued', 'partially_paid', 'overdue'],
        balance__gt=0
    ).aggregate(Sum('balance'))['balance__sum'] or Decimal('0.00')
    
    # Filter invoices for display
    invoices = all_invoices.order_by('-issued_at', '-created')
    
    # Apply search filter
    if query:
        invoices = invoices.filter(
            Q(invoice_number__icontains=query) |
            Q(patient__first_name__icontains=query) |
            Q(patient__last_name__icontains=query) |
            Q(patient__mrn__icontains=query) |
            Q(patient__phone_number__icontains=query)
        )
    
    # Apply status filter
    if status_filters:
        invoices = invoices.filter(status__in=status_filters)
    
    # Pagination
    paginator = Paginator(invoices, 25)
    page = request.GET.get('page', 1)
    try:
        invoices_page = paginator.get_page(page)
    except:
        invoices_page = paginator.get_page(1)
    
    context = {
        'invoices': invoices_page,
        'total_revenue': total_revenue,
        'outstanding_balance': outstanding_balance,
        'total_invoices': total_invoices,
        'query': query,
        'status_filter': status_filter,  # Original string for form
        'status_filters': status_filters,  # List for template checks
    }
    return render(request, 'hospital/cashier_invoices.html', context)


@login_required
@block_pharmacy_from_invoice_and_payment
@user_passes_test(is_cashier, login_url='/admin/login/')
def cashier_invoice_detail(request, pk):
    """View cashier invoice detail (uses all_objects so write-off period invoices are viewable)"""
    from .models import Invoice, InvoiceLine
    from .models_accounting import Transaction
    
    invoice = get_object_or_404(
        Invoice.all_objects.select_related('patient', 'payer', 'encounter'),
        pk=pk,
        is_deleted=False
    )
    try:
        from .utils_invoice_line import heal_invoice_zero_line_prices
        heal_invoice_zero_line_prices(invoice)
    except Exception:
        logger.exception('heal_invoice_zero_line_prices failed')
    # Reconcile totals from line totals (includes discounts) - fixes stale totals when waivers applied
    invoice.update_totals()
    
    # Get invoice lines (exclude waived - they contribute 0 and should not appear)
    invoice_lines = InvoiceLine.objects.filter(
        invoice=invoice,
        is_deleted=False,
        waived_at__isnull=True
    ).select_related('service_code').order_by('created')
    
    # Get payment transactions
    transactions = Transaction.objects.filter(
        invoice=invoice,
        is_deleted=False
    ).select_related('processed_by').order_by('-transaction_date')
    
    context = {
        'invoice': invoice,
        'invoice_lines': invoice_lines,
        'transactions': transactions,
        'can_waive': user_can_waive(request.user) if hasattr(request, 'user') else False,
    }
    return render(request, 'hospital/cashier_invoice_detail.html', context)


@login_required
@waiver_permission_required
def waive_invoice_line(request):
    """
    Waive (remove) an invoice line - for patients migrating from old system who already paid
    (e.g. registration fee, etc.). Only administrators can waive; accountants and cashiers cannot.
    """
    from .models import InvoiceLine
    from django.db import transaction

    if request.method != 'POST':
        messages.error(request, 'Invalid request.')
        return redirect('hospital:cashier_invoices')

    line_id = request.POST.get('line_id', '').strip()
    waiver_reason = (request.POST.get('waiver_reason') or '').strip() or 'Waived - patient from old system'

    if not line_id:
        messages.error(request, 'No line specified.')
        return redirect('hospital:cashier_invoices')

    try:
        line = InvoiceLine.objects.select_related('invoice', 'service_code').get(
            pk=line_id,
            is_deleted=False
        )
    except (InvoiceLine.DoesNotExist, ValueError):
        messages.error(request, 'Invoice line not found.')
        return redirect('hospital:cashier_invoices')

    if line.waived_at:
        messages.info(request, f'{line.description} was already waived.')
        redirect_url = request.POST.get('redirect_url', '').strip()
        if redirect_url and redirect_url.startswith('/'):
            from django.http import HttpResponseRedirect
            return HttpResponseRedirect(redirect_url)
        return redirect('hospital:cashier_invoice_detail', pk=line.invoice_id)

    # Full discount = waive the line (line_total becomes 0)
    subtotal = Decimal(str(line.quantity)) * Decimal(str(line.unit_price))
    tax = Decimal(str(line.tax_amount)) if line.tax_amount else Decimal('0')
    full_waive_amount = subtotal + tax  # discount this much so line_total = 0

    with transaction.atomic():
        line.discount_amount = full_waive_amount
        line.waived_at = timezone.now()
        line.waived_by = request.user
        line.waiver_reason = waiver_reason[:255]
        line.save()  # save() recalculates line_total from discount_amount

        line.invoice.update_totals()

        # If this is a drug/prescription line: cancel PharmacyDispensing so quantity returns to stock.
        # Waived drugs were never paid for - stock should only be affected by paid dispensations.
        if line.prescription_id:
            from .models_payment_verification import PharmacyDispensing
            PharmacyDispensing.objects.filter(prescription=line.prescription).update(
                dispensing_status='cancelled',
                quantity_ordered=0
            )

    messages.success(
        request,
        f'Waived: {line.description} (GHS {full_waive_amount:.2f}). '
        f'Reason: {waiver_reason[:80]}{"…" if len(waiver_reason) > 80 else ""}'
    )
    # Support redirect back to combined patient view (accountant)
    redirect_url = request.POST.get('redirect_url', '').strip()
    if redirect_url and redirect_url.startswith('/'):
        from django.http import HttpResponseRedirect
        return HttpResponseRedirect(redirect_url)
    return redirect('hospital:cashier_invoice_detail', pk=line.invoice_id)


@login_required
@invoice_from_bill_remover_required
def remove_invoice_from_bill(request):
    """
    Remove an invoice from the total bill (status → cancelled).

    - Deposit that was applied to this invoice is reversed back to the patient’s
      deposit balance so money and the bill stay consistent.
    - Invoices with cash/MoMo/card or combined (non-deposit) payments cannot be
      removed here; use accounting adjustment/refund instead.
    - Remaining open invoices/lines on the total bill then add up to the new amount due.
    """
    if request.method != 'POST':
        messages.error(request, 'Invalid request.')
        return redirect('hospital:cashier_patient_bills')

    invoice_id = (request.POST.get('invoice_id') or '').strip()
    if not invoice_id:
        messages.error(request, 'No invoice specified.')
        return redirect('hospital:cashier_patient_bills')

    try:
        invoice = Invoice.all_objects.get(
            pk=invoice_id,
            is_deleted=False
        )
    except (Invoice.DoesNotExist, ValueError):
        messages.error(request, 'Invoice not found.')
        return redirect('hospital:cashier_patient_bills')

    from .services.deposit_payment_service import (
        invoice_has_non_deposit_payment_recorded,
        reverse_deposit_payments_for_invoice,
    )

    if invoice.status == 'paid' and invoice_has_non_deposit_payment_recorded(invoice):
        messages.error(
            request,
            'Cannot remove this invoice: it has cash, mobile money, card, or combined payment on file. '
            'Use accounting to adjust or refund; deposit-only paid invoices can be removed.',
        )
        redirect_url = request.POST.get('redirect_url', '').strip()
        if redirect_url and redirect_url.startswith('/'):
            from django.http import HttpResponseRedirect
            return HttpResponseRedirect(redirect_url)
        return redirect('hospital:cashier_patient_bills')

    with db_transaction.atomic():
        inv = Invoice.all_objects.select_for_update().get(pk=invoice.pk, is_deleted=False)
        reversed_amt = reverse_deposit_payments_for_invoice(inv)
        inv.refresh_from_db()
        inv.status = 'cancelled'
        inv.save(update_fields=['status', 'modified'])
        inv.update_totals()

    if reversed_amt > Decimal('0.00'):
        messages.success(
            request,
            f'Invoice {inv.invoice_number} removed from the bill. '
            f'GHS {reversed_amt:.2f} that had been paid from the patient’s deposit on this invoice was reversed '
            f'back to their deposit balance. The remaining items on the total bill now add up to the updated amount due.',
        )
    else:
        messages.success(
            request,
            f'Invoice {inv.invoice_number} removed from the bill. '
            f'It no longer appears here and no longer counts toward this patient’s open charges. '
            f'The remaining lines add up to the updated totals (no deposit had been applied to this invoice).',
        )

    redirect_url = request.POST.get('redirect_url', '').strip()
    if redirect_url and redirect_url.startswith('/'):
        from django.http import HttpResponseRedirect
        return HttpResponseRedirect(redirect_url)
    if invoice.patient_id:
        return redirect('hospital:cashier_patient_total_bill', patient_id=invoice.patient_id)
    return redirect('hospital:cashier_patient_bills')


@login_required
@waiver_permission_required
def waive_prescribe_sale(request):
    """
    Waive (write off) a Prescribe Sale when the patient does not pay.
    Stock was already changed when prescribed; waiving only stops charging the patient.
    Only administrators may waive; accountants use remove-invoice-from-bill for invoices only.
    """
    if request.method != 'POST':
        messages.error(request, 'Invalid request.')
        return redirect('hospital:cashier_patient_bills')
    sale_id = request.POST.get('sale_id', '').strip()
    waiver_reason = (request.POST.get('waiver_reason') or '').strip() or 'Waived - patient did not pay'
    if not sale_id:
        messages.error(request, 'No Prescribe Sale specified.')
        return redirect('hospital:cashier_patient_bills')
    try:
        sale = WalkInPharmacySale.objects.select_related('patient').get(
            pk=sale_id,
            is_deleted=False
        )
    except (WalkInPharmacySale.DoesNotExist, ValueError):
        messages.error(request, 'Prescribe Sale not found.')
        return redirect('hospital:cashier_patient_bills')
    if sale.waived_at:
        messages.info(request, f'Prescribe Sale {sale.sale_number} was already waived.')
    else:
        sale.waived_at = timezone.now()
        sale.waived_by = request.user
        sale.waiver_reason = waiver_reason[:255]
        sale.save()
        try:
            from .services.pharmacy_invoice_payment_link import waive_invoice_lines_for_prescribe_sale
            n_lines = waive_invoice_lines_for_prescribe_sale(
                sale, waived_by_user=request.user, reason=waiver_reason
            )
        except Exception as e:
            logger.warning('waive_invoice_lines_for_prescribe_sale: %s', e)
            n_lines = 0
        extra = f' {n_lines} invoice line(s) removed from bill.' if n_lines else ''
        messages.success(
            request,
            f'Waived Prescribe Sale {sale.sale_number} (GHS {sale.amount_due:.2f}). '
            f'Reason: {waiver_reason[:80]}{"…" if len(waiver_reason) > 80 else ""}{extra}'
        )
    redirect_url = request.POST.get('redirect_url', '').strip()
    if redirect_url and redirect_url.startswith('/'):
        from django.http import HttpResponseRedirect
        return HttpResponseRedirect(redirect_url)
    if sale.patient_id:
        from django.urls import reverse
        return redirect('hospital:cashier_patient_total_bill', patient_id=sale.patient_id)
    return redirect('hospital:cashier_patient_bills')


@login_required
@waiver_permission_required
def waive_prescribe_sale_line(request):
    """
    Waive a single line (item) of a Prescribe Sale. Amount for that line becomes 0; sale total is recalculated.
    Only administrators may waive.
    """
    if request.method != 'POST':
        messages.error(request, 'Invalid request.')
        return redirect('hospital:cashier_patient_bills')
    sale_item_id = request.POST.get('sale_item_id', '').strip()
    waiver_reason = (request.POST.get('waiver_reason') or '').strip() or 'Line waived (administrator)'
    if not sale_item_id:
        messages.error(request, 'No line specified.')
        return redirect('hospital:cashier_patient_bills')
    try:
        item = WalkInPharmacySaleItem.objects.select_related('sale', 'drug').get(
            pk=sale_item_id,
            is_deleted=False,
            sale__is_deleted=False,
        )
    except (WalkInPharmacySaleItem.DoesNotExist, ValueError):
        messages.error(request, 'Sale line not found.')
        return redirect('hospital:cashier_patient_bills')
    # Support servers where migration 1100 not yet applied (no waived_at on WalkInPharmacySaleItem)
    if not hasattr(item, 'waived_at'):
        messages.warning(
            request,
            'Line-level waiver is not available yet. Please run database migrations (e.g. python manage.py migrate).'
        )
        redirect_url = request.POST.get('redirect_url', '').strip()
        if redirect_url and redirect_url.startswith('/'):
            from django.http import HttpResponseRedirect
            return HttpResponseRedirect(redirect_url)
        if item.sale.patient_id:
            return redirect('hospital:cashier_patient_total_bill', patient_id=item.sale.patient_id)
        return redirect('hospital:cashier_patient_bills')
    if getattr(item, 'waived_at', None):
        messages.info(request, f'{item.drug.name} was already waived.')
    else:
        amount_waived = item.line_total
        try:
            item.waived_at = timezone.now()
            item.waived_by = request.user
            item.waiver_reason = waiver_reason[:255]
            item.save()
            messages.success(
                request,
                f'Waived: {item.drug.name} (GHS {amount_waived:.2f}). '
                f'Reason: {waiver_reason[:80]}{"…" if len(waiver_reason) > 80 else ""}'
            )
        except Exception:
            messages.warning(
                request,
                'Line-level waiver could not be saved. Please run database migrations (python manage.py migrate).'
            )
    redirect_url = request.POST.get('redirect_url', '').strip()
    if redirect_url and redirect_url.startswith('/'):
        from django.http import HttpResponseRedirect
        return HttpResponseRedirect(redirect_url)
    if item.sale.patient_id:
        return redirect('hospital:cashier_patient_total_bill', patient_id=item.sale.patient_id)
    return redirect('hospital:cashier_patient_bills')


@login_required
@user_passes_test(is_cashier, login_url='/admin/login/')
def customer_debt(request):
    """View customer debt - shows all outstanding patient debts"""
    try:
        from .models import Patient, Invoice, LabResult, Prescription, Admission
        from .models_accounting import PaymentReceipt
        from django.db.models import Q, Sum
        
        # Get filter parameters
        query = request.GET.get('q', '').strip()
        min_debt = request.GET.get('min_debt', '').strip()
        filter_date_str = request.GET.get('date', '').strip()
        filter_date = None
        if filter_date_str:
            try:
                from datetime import datetime
                filter_date = datetime.strptime(filter_date_str, '%Y-%m-%d').date()
            except (ValueError, TypeError):
                filter_date = None
        try:
            min_debt_amount = Decimal(min_debt) if min_debt else Decimal('0.00')
        except (ValueError, TypeError):
            min_debt_amount = Decimal('0.00')
        
        # Get patients with potential debt - start with patients who have unpaid invoices
        # Invoice status: draft, issued, partially_paid, overdue (NOT 'pending' - doesn't exist)
        if query:
            # If searching, filter by query first
            all_patients = Patient.objects.filter(
                is_deleted=False
            ).filter(
                Q(first_name__icontains=query) |
                Q(last_name__icontains=query) |
                Q(mrn__icontains=query) |
                Q(phone_number__icontains=query)
            )[:1000]  # Limit search results
        else:
            # Reverse FK uses Invoice.objects (VisibleManager); use all_objects so draft/zero-total encounter bills count
            _open_pids = (
                Invoice.all_objects.filter(
                    is_deleted=False,
                    status__in=['draft', 'issued', 'partially_paid', 'overdue'],
                )
                .exclude(
                    issued_at__date__gte=Invoice.WRITE_OFF_START,
                    issued_at__date__lte=Invoice.WRITE_OFF_END,
                )
                .values_list('patient_id', flat=True)
                .distinct()
            )
            patients_with_invoices = Patient.objects.filter(pk__in=_open_pids)[:1000]
            
            # Also get patients with active admissions (bed charges)
            patients_with_admissions = Patient.objects.filter(
                encounters__admission__status='admitted',
                encounters__admission__is_deleted=False
            ).distinct()[:500]
            
            # Combine and deduplicate
            all_patients = (patients_with_invoices | patients_with_admissions).distinct()[:1000]
        
        # Calculate debt for each patient
        patient_debts = []
        total_debt = Decimal('0.00')
        total_invoice_debt = Decimal('0.00')
        total_lab_debt = Decimal('0.00')
        total_pharmacy_debt = Decimal('0.00')
        total_bed_debt = Decimal('0.00')
        
        for patient in all_patients:
            # Invoice debt
            unpaid_invoices = Invoice.all_objects.filter(
                patient=patient,
                is_deleted=False
            ).exclude(
                status__in=['paid', 'cancelled']
            ).exclude(
                issued_at__date__gte=Invoice.WRITE_OFF_START,
                issued_at__date__lte=Invoice.WRITE_OFF_END,
            )
            if filter_date:
                unpaid_invoices = unpaid_invoices.filter(issued_at__date=filter_date)
            
            invoice_debt = unpaid_invoices.aggregate(
                total=Sum('balance')
            )['total'] or Decimal('0.00')
            
            # Lab test debt (completed/verified but not paid)
            # LabResult -> Order -> Encounter -> Patient
            # Check if lab has payment via payment_verifications or release_record
            from .models_payment_verification import LabResultRelease
            
            all_labs = LabResult.objects.filter(
                order__encounter__patient=patient,
                is_deleted=False,
                status__in=['completed', 'verified']
            ).select_related('test', 'order__encounter__patient').prefetch_related('payment_verifications')
            if filter_date:
                all_labs = all_labs.filter(created__date=filter_date)
            
            # Filter in Python to check payment status
            unpaid_labs = []
            for lab in all_labs:
                # Check if lab has payment verification
                has_payment = False
                try:
                    # Check via payment_verifications relationship
                    if lab.payment_verifications.filter(verification_status='verified').exists():
                        has_payment = True
                    # Also check via release_record if it exists
                    try:
                        release = lab.release_record
                        if release and release.payment_verified_at:
                            has_payment = True
                    except LabResultRelease.DoesNotExist:
                        pass
                except Exception:
                    pass
                
                if not has_payment:
                    unpaid_labs.append(lab)
            
            lab_debt = sum(
                (lab.test.price or Decimal('0.00')) for lab in unpaid_labs
            )
            
            # Pharmacy debt (prescriptions not paid/dispensed)
            # Prescription -> Order -> Encounter -> Patient
            all_prescriptions = Prescription.objects.filter(
                order__encounter__patient=patient,
                is_deleted=False
            ).select_related(
                'drug',
                'order__encounter',
                'order__encounter__patient',
                'dispensing_record',
                'dispensing_record__substitute_drug',
            ).prefetch_related('payment_verifications')
            if filter_date:
                all_prescriptions = all_prescriptions.filter(created__date=filter_date)
            
            # Filter in Python to check payment status
            unpaid_prescriptions = []
            for rx in all_prescriptions:
                # Check if prescription has payment verification
                has_payment = False
                try:
                    # Check via payment_verifications relationship
                    if rx.payment_verifications.filter(verification_status='verified').exists():
                        has_payment = True
                    # Also check via dispensing_record if it exists (OneToOne relationship)
                    try:
                        if hasattr(rx, 'dispensing_record') and rx.dispensing_record:
                            if rx.dispensing_record.payment_verified_at:
                                has_payment = True
                    except Exception:
                        pass
                except Exception:
                    pass
                
                if not has_payment:
                    unpaid_prescriptions.append(rx)
            
            pharmacy_debt = Decimal('0.00')
            for rx in unpaid_prescriptions:
                if not rx.drug:
                    continue
                enc = getattr(getattr(rx, 'order', None), 'encounter', None)
                pat = getattr(enc, 'patient', None) if enc else patient
                payer = AutoBillingService._ensure_payer(pat, enc)
                try:
                    disp = getattr(rx, 'dispensing_record', None)
                    drug = disp.drug_to_dispense if disp and disp.drug_to_dispense else rx.drug
                    q = (
                        disp.quantity_ordered
                        if disp and (disp.quantity_ordered or 0) > 0
                        else rx.quantity
                    )
                except Exception:
                    drug = rx.drug
                    q = rx.quantity
                unit = get_drug_price_for_prescription(drug, payer=payer)
                pharmacy_debt += unit * Decimal(str(q or 0))
            
            unpaid_labs_count = len(unpaid_labs)
            unpaid_prescriptions_count = len(unpaid_prescriptions)
            
            # Bed charges debt (active admissions)
            # Admission -> Encounter -> Patient
            active_admissions = Admission.objects.filter(
                encounter__patient=patient,
                is_deleted=False,
                status='admitted'
            )
            
            bed_debt = Decimal('0.00')
            for admission in active_admissions:
                # Check if admission has bed_charges relationship
                try:
                    if hasattr(admission, 'bed_charges') and admission.bed_charges:
                        bed_debt += (admission.bed_charges.current_charges or Decimal('0.00'))
                    elif admission.ward and hasattr(admission.ward, 'daily_rate') and admission.ward.daily_rate:
                        # Calculate based on days admitted
                        if hasattr(admission, 'admission_date') and admission.admission_date:
                            days = (timezone.now().date() - admission.admission_date).days + 1
                            if days > 0:
                                bed_debt += (admission.ward.daily_rate * Decimal(str(days)))
                except Exception:
                    # Skip if there's an error calculating bed charges
                    pass
            
            # Total debt for this patient
            total_patient_debt = invoice_debt + lab_debt + pharmacy_debt + bed_debt
            
            # Filter by minimum debt
            if total_patient_debt < min_debt_amount:
                continue
            
            # Only include patients with debt
            if total_patient_debt > 0:
                patient_debts.append({
                    'patient': patient,
                    'total_debt': total_patient_debt,
                    'invoice_debt': invoice_debt,
                    'invoice_count': unpaid_invoices.count(),
                    'invoices': list(unpaid_invoices[:10]),  # Limit for display
                    'lab_debt': lab_debt,
                    'unpaid_labs_count': unpaid_labs_count,
                    'unpaid_labs': unpaid_labs[:10],  # Limit for display
                    'pharmacy_debt': pharmacy_debt,
                    'unpaid_prescriptions_count': unpaid_prescriptions_count,
                    'unpaid_prescriptions': unpaid_prescriptions[:10],  # Limit for display
                    'bed_debt': bed_debt,
                    'active_admissions_count': active_admissions.count(),
                    'active_admissions': list(active_admissions[:10]),  # Limit for display
                })
                
                # Add to totals
                total_debt += total_patient_debt
                total_invoice_debt += invoice_debt
                total_lab_debt += lab_debt
                total_pharmacy_debt += pharmacy_debt
                total_bed_debt += bed_debt
    
        # Sort by total debt (highest first)
        patient_debts.sort(key=lambda x: x['total_debt'], reverse=True)
        
        # Pagination
        paginator = Paginator(patient_debts, 20)
        page_number = request.GET.get('page', 1)
        try:
            patient_debts_page = paginator.page(page_number)
        except:
            patient_debts_page = paginator.page(1)
        
        context = {
            'patient_debts': patient_debts_page,
            'total_debt': total_debt,
            'patient_count': len(patient_debts),
            'total_invoice_debt': total_invoice_debt,
            'total_lab_debt': total_lab_debt,
            'total_pharmacy_debt': total_pharmacy_debt,
            'total_bed_debt': total_bed_debt,
            'query': query,
            'min_debt': min_debt,
            'filter_date': filter_date_str,
        }
        
        return render(request, 'hospital/customer_debt.html', context)
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error in customer_debt view: {str(e)}", exc_info=True)
        messages.error(request, f'Error loading customer debt report: {str(e)}')
        return redirect('hospital:cashier_dashboard')


def _build_cashier_patient_invoices_context(patient):
    """
    Shared context for cashier patient invoice list and print view.
    """
    from .models import Invoice
    from django.db.models import Sum, Q
    from decimal import Decimal

    invoices = (
        Invoice.all_objects.filter(patient=patient, is_deleted=False)
        .exclude(status='cancelled')
        .exclude(
            issued_at__date__gte=Invoice.WRITE_OFF_START,
            issued_at__date__lte=Invoice.WRITE_OFF_END,
        )
        .order_by('-issued_at', '-created')
    )

    total_paid = (
        PaymentReceipt.objects.filter(patient=patient, is_deleted=False)
        .aggregate(s=Sum('amount_paid'))['s'] or Decimal('0.00')
    )
    if total_paid == 0:
        invoice_paid = (
            Invoice.all_objects.filter(patient=patient, is_deleted=False).exclude(status='cancelled').aggregate(s=Sum('total_amount'))['s'] or Decimal('0.00')
        ) - (
            Invoice.all_objects.filter(patient=patient, is_deleted=False).exclude(status='cancelled').aggregate(s=Sum('balance'))['s'] or Decimal('0.00')
        )
        if invoice_paid > 0:
            total_paid = invoice_paid

    total_amount = Decimal('0.00')
    outstanding = Decimal('0.00')
    for inv in invoices:
        inv.calculate_totals()
        total_amount += (inv.total_amount or Decimal('0.00'))
        outstanding += (inv.balance or Decimal('0.00'))

    total_invoices = invoices.count()

    deposit_balance = getattr(patient, 'deposit_balance', Decimal('0.00'))
    if isinstance(deposit_balance, (int, float)):
        deposit_balance = Decimal(str(deposit_balance))

    effective_outstanding = max(Decimal('0.00'), outstanding - deposit_balance)

    deposit_applied_to_bill = Decimal('0.00')
    try:
        _inv_ids = list(invoices.values_list('pk', flat=True))
        if _inv_ids:
            deposit_applied_to_bill = (
                PaymentReceipt.objects.filter(
                    invoice_id__in=_inv_ids,
                    is_deleted=False,
                ).filter(
                    Q(payment_method='deposit') |
                    Q(service_details__deposit_applied=True) |
                    Q(notes__icontains='Deposit applied to bill')
                ).aggregate(s=Sum('amount_paid'))['s'] or Decimal('0.00')
            )
    except Exception:
        pass

    from .utils_invoice_line import heal_invoice_zero_line_prices
    combined_lines = []
    for inv in invoices.order_by('issued_at', 'created'):
        try:
            heal_invoice_zero_line_prices(inv)
        except Exception:
            pass
        for line in inv.billable_lines:
            combined_lines.append({'line': line, 'invoice_number': inv.invoice_number})
    combined_total = sum(
        (cl['line'].display_line_total or Decimal('0.00')) for cl in combined_lines
    )
    combined_balance = combined_total - total_paid

    return {
        'patient': patient,
        'invoices': invoices,
        'total_invoices': total_invoices,
        'outstanding': outstanding,
        'deposit_balance': deposit_balance,
        'effective_outstanding': effective_outstanding,
        'total_paid': total_paid,
        'total_amount': total_amount,
        'combined_lines': combined_lines,
        'combined_total': combined_total,
        'combined_balance': combined_balance,
        'deposit_applied_to_bill': deposit_applied_to_bill,
        'hospital_name': _get_hospital_name(),
    }


@login_required
@user_passes_test(is_cashier, login_url='/admin/login/')
def patient_invoices(request, patient_id):
    """View patient invoices"""
    from .models import Patient

    patient = get_object_or_404(Patient, pk=patient_id, is_deleted=False)
    context = _build_cashier_patient_invoices_context(patient)
    return render(request, 'hospital/cashier_patient_invoices.html', context)


@login_required
@user_passes_test(is_cashier, login_url='/admin/login/')
def patient_invoices_print(request, patient_id):
    """Print-friendly invoice summary (no app chrome). Open in new tab or use Print to PDF."""
    from .models import Patient

    patient = get_object_or_404(Patient, pk=patient_id, is_deleted=False)
    context = _build_cashier_patient_invoices_context(patient)
    try:
        from .models_settings import HospitalSettings
        context['hospital_settings'] = HospitalSettings.get_settings()
    except Exception:
        context['hospital_settings'] = None
    context['auto_print'] = (request.GET.get('auto_print') or '').strip() == '1'
    return render(request, 'hospital/cashier_patient_invoices_print.html', context)


def _get_hospital_name():
    """Return facility name for print headers."""
    try:
        from .models_settings import HospitalSettings
        s = HospitalSettings.get_settings()
        return getattr(s, 'hospital_name', None) or 'Hospital'
    except Exception:
        return 'Hospital'


@login_required
@block_pharmacy_from_invoice_and_payment
def process_payment(request, payment_request_id=None, bill_id=None, invoice_id=None):
    """Process payment for invoice, bill, or payment request"""
    from decimal import Decimal
    from django.contrib import messages
    from django.shortcuts import get_object_or_404, redirect, render
    # Import Invoice from models.py, Bill and PaymentRequest from models_workflow.py
    from .models import Invoice
    from .models_workflow import Bill, PaymentRequest
    invoice = None
    bill = None
    patient = None
    payment_request = None
    
    # Get the object to process payment for (all_objects so write-off period invoices are findable)
    if invoice_id:
        invoice = get_object_or_404(Invoice.all_objects, pk=invoice_id, is_deleted=False)
        patient = invoice.patient
    elif bill_id:
        bill = get_object_or_404(Bill, pk=bill_id, is_deleted=False)
        patient = bill.patient
        if bill.invoice:
            invoice = bill.invoice
    elif payment_request_id:
        payment_request = get_object_or_404(PaymentRequest, pk=payment_request_id, is_deleted=False)
        if payment_request.invoice:
            invoice = payment_request.invoice
            patient = invoice.patient
        elif payment_request.bill:
            bill = payment_request.bill
            patient = bill.patient
    
    if not invoice and not bill:
        messages.error(request, 'Invalid payment request. No invoice or bill found.')
        return redirect('hospital:cashier_dashboard')
    
    # Handle POST - process the payment
    if request.method == 'POST':
        try:
            amount = Decimal(request.POST.get('amount', '0'))
            payment_method = request.POST.get('payment_method', 'cash')
            reference_number = request.POST.get('reference_number', '').strip()
            notes = request.POST.get('notes', '').strip()
            
            # Validate amount
            if amount <= 0:
                messages.error(request, 'Payment amount must be greater than zero.')
                return render(request, 'hospital/process_payment.html', {
                    'invoice': invoice,
                    'bill': bill,
                    'patient': patient,
                    'payment_request': payment_request,
                })
            
            # Check balance
            if invoice:
                if amount > invoice.balance:
                    messages.error(request, f'Payment amount (GHS {amount}) exceeds outstanding balance (GHS {invoice.balance}).')
                    return render(request, 'hospital/process_payment.html', {
                        'invoice': invoice,
                        'bill': bill,
                        'patient': patient,
                        'payment_request': payment_request,
                    })
            elif bill:
                if amount > bill.patient_portion:
                    messages.error(request, f'Payment amount (GHS {amount}) exceeds patient portion (GHS {bill.patient_portion}).')
                    return render(request, 'hospital/process_payment.html', {
                        'invoice': invoice,
                        'bill': bill,
                        'patient': patient,
                        'payment_request': payment_request,
                    })
            
            # Process payment: use invoice.mark_as_paid so PaymentReceipt is created and
            # balance reflects correctly on combined bill and everywhere (calculate_totals uses receipts)
            if invoice:
                try:
                    transaction = invoice.mark_as_paid(
                        amount=amount,
                        payment_method=payment_method,
                        processed_by=request.user,
                        reference_number=reference_number,
                        validate=False,
                    )
                    if transaction and (reference_number or notes):
                        if reference_number:
                            transaction.reference_number = reference_number
                        if notes:
                            transaction.notes = notes
                        transaction.save()
                    messages.success(
                        request,
                        f'✅ Payment of GHS {amount} recorded successfully. '
                        f'Invoice balance: GHS {invoice.balance}'
                    )
                    # Redirect to cashier total bill if user came from cashier so combined invoice updates
                    referrer = (request.META.get('HTTP_REFERER') or '')
                    if 'cashier' in referrer or 'total-bill' in referrer or 'hms/cashier' in referrer:
                        return redirect('hospital:cashier_patient_total_bill', patient.id)
                    return redirect('hospital:invoice_detail', invoice.pk)
                except Exception as e:
                    messages.error(request, getattr(e, 'message', str(e)) or 'Failed to process payment.')
            elif bill:
                # For bills, we need to handle differently
                # Create transaction manually
                from .models import Transaction
                from django.utils import timezone
                
                transaction = Transaction.objects.create(
                    transaction_type='payment_received',
                    bill=bill,
                    patient=patient,
                    amount=amount,
                    payment_method=payment_method,
                    reference_number=reference_number or None,
                    notes=notes or None,
                    processed_by=request.user,
                )
                
                # Update bill
                bill.paid_amount = (bill.paid_amount or Decimal('0')) + amount
                if bill.paid_amount >= bill.patient_portion:
                    bill.status = 'paid'
                bill.save()
                
                messages.success(
                    request,
                    f'✅ Payment of GHS {amount} recorded successfully for bill {bill.bill_number}.'
                )
                
                # Redirect to bill detail if available, otherwise dashboard
                return redirect('hospital:cashier_dashboard')
            
        except ValueError as e:
            messages.error(request, f'Invalid payment amount: {str(e)}')
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error processing payment: {str(e)}", exc_info=True)
            messages.error(request, f'Error processing payment: {str(e)}')
    
    # GET request - show payment form
    # Support payment for particular item: ?amount=X or ?line_id=Y
    default_amount = None
    if invoice:
        amount_param = request.GET.get('amount')
        line_id_param = request.GET.get('line_id')
        if amount_param:
            try:
                default_amount = Decimal(str(amount_param))
                default_amount = min(default_amount, invoice.balance)
            except (ValueError, TypeError):
                pass
        elif line_id_param:
            from .models import InvoiceLine
            try:
                line = InvoiceLine.objects.get(pk=line_id_param, invoice=invoice, is_deleted=False)
                default_amount = min(line.line_total, invoice.balance)
            except (InvoiceLine.DoesNotExist, ValueError, TypeError):
                pass
        if default_amount is None:
            default_amount = invoice.balance
    elif bill:
        default_amount = bill.patient_portion
    
    from .models_accounting import Transaction
    return render(request, 'hospital/process_payment.html', {
        'invoice': invoice,
        'bill': bill,
        'patient': patient,
        'default_amount': default_amount,
        'payment_request': payment_request,
        'payment_methods': Transaction.PAYMENT_METHODS,
    })
