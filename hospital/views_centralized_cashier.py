"""
💰 CENTRALIZED CASHIER SYSTEM
All payments processed through cashier first
Complete payment control and audit trail
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.cache import never_cache
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Q, Sum, Count, Exists, OuterRef, Prefetch
from django.db.models.functions import Coalesce
from decimal import Decimal
import json
import logging

from .models import Patient, Encounter, LabResult, LabTest, Prescription, Admission, Invoice, InvoiceLine, ServiceCode, Payer
from .models_accounting import PaymentReceipt, Transaction
from .models_payment_verification import LabResultRelease, PharmacyDispensing, ImagingRelease
from .services.unified_receipt_service import (
    UnifiedReceiptService,
    LabPaymentService,
    PharmacyPaymentService,
    ImagingPaymentService,
    ConsultationPaymentService,
    BedPaymentService
)
from .services.auto_billing_service import AutoBillingService
from .services.pricing_engine_service import pricing_engine
from .services.deposit_payment_service import (
    estimate_amount_after_deposit,
    get_invoice_for_lab,
    get_invoice_for_prescription,
    get_invoice_for_imaging,
    link_deposit_receipt_to_release,
)
from .utils_roles import user_has_cashier_access, user_can_add_manual_charges, user_can_edit_invoice_line_amounts
from .models_pharmacy_walkin import WalkInPharmacySale, WalkInPharmacySaleItem
from .services.pharmacy_walkin_service import WalkInPharmacyService
from .utils_billing import (
    CONSULTATION_LINE_SERVICE_CODES,
    consultation_line_display_amount,
    get_consultation_line_for_encounter,
    get_consultation_price_for_encounter,
    get_drug_price_for_prescription,
    local_datetime_bounds_for_date,
)
from .utils_invoice_line import (
    create_or_merge_invoice_line,
    resolve_lab_test_for_invoice_line,
    drug_catalog_unit_price_for_line,
    imaging_catalog_unit_price_for_line,
    accommodation_unit_price_for_line,
    walkin_sale_item_unit_price_for_line,
)

logger = logging.getLogger(__name__)


def _invoice_all_objects_by_pk(pk):
    """all_objects lookup at module scope (avoids UnboundLocalError if a view shadows Invoice)."""
    return Invoice.all_objects.filter(pk=pk).first()


def _resolve_invoice_payer(invoice, patient):
    if invoice and getattr(invoice, 'payer', None):
        return invoice.payer
    return getattr(patient, 'primary_insurance', None)


def _compute_current_line_unit_price(line, patient, payer):
    """
    Compute latest billable unit price for an unpaid invoice line.
    """
    if getattr(line, 'prescription', None) and getattr(line.prescription, 'drug', None):
        return Decimal(str(get_drug_price_for_prescription(line.prescription.drug, payer=payer) or 0))
    if getattr(line, 'service_code', None):
        sc = line.service_code
        engine_price = Decimal(str(pricing_engine.get_service_price(sc, patient, payer=payer) or 0))
        if engine_price > 0:
            return engine_price
        # No flexible-pricing row for this code — use catalog-linked cashier items (LABTEST-*, IMGCAT-*).
        code = (getattr(sc, 'code', None) or '').strip()
        code_upper = code.upper()
        # Tier codes created at cashier — flexible pricing often has no row; use fixed amounts
        if code_upper == 'PHYSIO':
            return Decimal('250.00')
        if code_upper == 'PHYSIO-SUB':
            return Decimal('150.00')
        # Laboratory: always prefer LabTest catalog price when we can resolve the test,
        # then apply payer rules (cash = catalog; insurance/corporate = engine or markup on catalog).
        try:
            lab = resolve_lab_test_for_invoice_line(line)
            if lab:
                catalog = lab.price or Decimal('0.00')
                resolved = AutoBillingService._resolve_price(patient, payer, sc, catalog)
                if resolved is not None and resolved > 0:
                    return Decimal(str(resolved))
                if catalog > 0:
                    return Decimal(str(catalog))
        except Exception:
            pass
        # Pharmacy consumables / DRUG-<uuid> lines (no prescription FK)
        try:
            drug_unit = drug_catalog_unit_price_for_line(line, patient, payer)
            if drug_unit is not None and drug_unit > 0:
                return Decimal(str(drug_unit))
        except Exception:
            pass
        try:
            img_unit = imaging_catalog_unit_price_for_line(line, patient, payer)
            if img_unit is not None and img_unit > 0:
                return Decimal(str(img_unit))
        except Exception:
            pass
        try:
            bed_unit = accommodation_unit_price_for_line(line)
            if bed_unit is not None and bed_unit > 0:
                return Decimal(str(bed_unit))
        except Exception:
            pass
        try:
            walkin_unit = walkin_sale_item_unit_price_for_line(line)
            if walkin_unit is not None and walkin_unit > 0:
                return Decimal(str(walkin_unit))
        except Exception:
            pass
        _img_prefix = 'IMGCAT-'
        if code.upper().startswith(_img_prefix):
            try:
                from .models_advanced import ImagingCatalog
                rest = code[len(_img_prefix):]
                img = ImagingCatalog.objects.filter(pk=rest, is_deleted=False).first()
                if img and img.price is not None:
                    return Decimal(str(img.price))
            except Exception:
                pass
        # Keep amount already on the line (cashier-set, physio tiers, etc.)
        existing = Decimal(str(line.unit_price or 0))
        if existing > 0:
            return existing
        return engine_price
    return None


def _refresh_unpaid_invoice_line_prices_for_patient(patient, max_invoices=25):
    """
    Reprice open invoice lines so cashier always sees latest configured prices.
    """
    open_invoices = (
        Invoice.all_objects.filter(
            patient=patient,
            is_deleted=False,
            status__in=('draft', 'issued', 'partially_paid', 'overdue'),
            balance__gt=0,
        )
        .select_related('payer')
        .order_by('-created')[:max_invoices]
    )

    for inv in open_invoices:
        payer = _resolve_invoice_payer(inv, patient)
        changed = False
        lines = InvoiceLine.objects.filter(
            invoice=inv,
            is_deleted=False,
            waived_at__isnull=True,
        ).select_related('prescription__drug', 'service_code')
        for line in lines:
            new_unit = _compute_current_line_unit_price(line, patient, payer)
            if new_unit is None:
                continue
            old_unit = Decimal(str(line.unit_price or 0))
            # Never persist a repricing of 0 or negative — that wipes cashier/catalog lines.
            if new_unit <= 0:
                continue
            if old_unit != new_unit:
                qty = Decimal(str(line.quantity or 1))
                line.unit_price = new_unit
                line.line_total = (new_unit * qty).quantize(Decimal('0.01'))
                line.save(update_fields=['unit_price', 'line_total', 'modified'])
                changed = True
        if changed:
            inv.update_totals()


def _first_consult_line_for_reception_visit_banner(patient):
    """Open encounter invoices + first consult line for reception visit price banner."""
    open_inv_ids = Invoice.all_objects.filter(
        patient=patient,
        is_deleted=False,
        encounter__isnull=False,
    ).exclude(status__in=('paid', 'cancelled')).exclude(
        issued_at__date__gte=Invoice.WRITE_OFF_START,
        issued_at__date__lte=Invoice.WRITE_OFF_END,
    ).filter(balance__gt=0).values_list('pk', flat=True)
    return (
        InvoiceLine.objects.filter(
            invoice_id__in=open_inv_ids,
            service_code__code__in=CONSULTATION_LINE_SERVICE_CODES,
            is_deleted=False,
            waived_at__isnull=True,
        )
        .select_related('invoice', 'invoice__encounter', 'service_code')
        .order_by('-modified')
        .first()
    )


def _service_date_for_total_bill_filter(s):
    """Extract a calendar date from a pending-service dict for date filtering (module scope; no closure over view locals)."""
    obj = s.get('obj')
    if not obj:
        return None
    dt = (
        getattr(obj, 'created', None)
        or getattr(obj, 'sale_date', None)
        or getattr(obj, 'admit_date', None)
        or getattr(obj, 'issued_at', None)
        or getattr(obj, 'performed_at', None)
    )
    if dt is None:
        return None
    if hasattr(dt, 'date'):
        if getattr(dt, 'tzinfo', None) is not None:
            return timezone.localtime(dt).date()
        return dt.date()
    return None


def _walkin_invoice_dedupe_fingerprint(invoice):
    """
    Fingerprint for accidental duplicate walk-in invoices on Total Bill.
    We only dedupe invoices that:
      - are walk-in style (no encounter), and
      - every billable line contains a "(Sale PS...)" suffix.
    """
    if not invoice or getattr(invoice, 'encounter_id', None):
        return None
    rows = list(
        InvoiceLine.objects.filter(
            invoice=invoice,
            is_deleted=False,
            waived_at__isnull=True,
        ).values_list('description', 'quantity', 'unit_price')
    )
    if not rows:
        return None

    normalized = []
    sale_marker = '(sale ps'
    for desc, qty, unit in rows:
        text = (desc or '').strip()
        lower = text.lower()
        marker_idx = lower.rfind(sale_marker)
        if marker_idx < 0:
            return None
        if marker_idx > 0 and text.endswith(')'):
            text = text[:marker_idx].strip()
        normalized.append((text.lower(), str(qty or Decimal('0.00')), str(unit or Decimal('0.00'))))

    normalized.sort()
    return (
        'walkin_clone',
        str(getattr(invoice, 'total_amount', Decimal('0.00')) or Decimal('0.00')),
        tuple(normalized),
    )


# Imaging/scan studies with these statuses are billable at cashier (ordered through report complete)
IMAGING_BILLABLE_STATUSES = [
    'scheduled',        # Ordered/scheduled (some facilities bill at order)
    'arrived',         # Patient arrived for scan
    'in_progress',     # Scan in progress (some workflows bill here)
    'completed',       # Scan completed
    'quality_check',   # Quality check done
    'awaiting_report', # Awaiting radiology report
    'reporting',       # Being reported
    'reported',        # Report complete
    'verified',        # Report verified
]


def is_cashier(user):
    """Only Administrators and Accountants can access cashier tools."""
    return user_has_cashier_access(user)


def can_add_manual_charges(user):
    """Cashier and reception can add manual charges."""
    return user_can_add_manual_charges(user)


@login_required
@user_passes_test(is_cashier)
@never_cache
def centralized_cashier_dashboard(request):
    """
    Main cashier dashboard - shows all pending payments
    ALL payments must come through here first
    Filters: patient name (search), date (for receipts and optional pending-by-date).
    """
    today = timezone.now().date()

    # ----- Filters from GET -----
    filter_patient_name = (request.GET.get('patient_name') or request.GET.get('search') or '').strip()
    filter_date_str = (request.GET.get('date') or '').strip()
    filter_today_pending = request.GET.get('today_pending') == '1'
    try:
        from datetime import datetime
        filter_date = datetime.strptime(filter_date_str, '%Y-%m-%d').date() if filter_date_str else today
    except (ValueError, TypeError):
        filter_date = today
    use_date_filter = bool(filter_date_str)
    # When "Today's Pending" is on, filter pending items to today's date
    if filter_today_pending:
        use_date_filter = True
        filter_date = today
    # Default to "today's pending" when no date/patient/search so first load is fast
    if not filter_patient_name and not filter_date_str and not filter_today_pending:
        use_date_filter = True
        filter_date = today
    # For template date input: show selected date or today (so user sees current date by default)
    filter_date_display = filter_date_str if filter_date_str else filter_date.isoformat()
    is_filtered = bool(filter_patient_name or use_date_filter or filter_today_pending)

    CASHIER_DASHBOARD_CAP = 500

    def _patient_matches(patient, search):
        if not search:
            return True
        s = search.lower()
        fn = (getattr(patient, 'first_name', None) or '').lower()
        ln = (getattr(patient, 'last_name', None) or '').lower()
        full = (getattr(patient, 'full_name', None) or f'{fn} {ln}'.strip()).lower()
        mrn = (getattr(patient, 'mrn', None) or '').lower()
        return s in full or s in fn or s in ln or s in mrn

    def _item_date(item, kind):
        """Get the relevant date for an item (for date filter)."""
        try:
            if kind == 'lab':
                c = getattr(item, 'created', None)
                return c.date() if c else None
            if kind == 'pharmacy':
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
            if kind == 'imaging':
                dt = getattr(item, 'performed_at', None) or getattr(item, 'created', None)
                return dt.date() if dt else None
            if kind == 'admission':
                return getattr(item, 'admit_date', None)
            if kind == 'walkin':
                d = getattr(item, 'sale_date', None) or getattr(item, 'created', None)
                return d.date() if d else None
            if kind == 'consultation':
                dt = getattr(item, 'started_at', None)
                if not dt:
                    return None
                # Use local time for correct "today" grouping (encounter.started_at may be stored in UTC).
                if getattr(dt, 'tzinfo', None) is not None:
                    return timezone.localtime(dt).date()
                return dt.date()
        except Exception:
            return None
        return None

    # Get lab results; apply date filter at DB and cap when applicable
    all_labs = LabResult.objects.filter(
        is_deleted=False
    ).filter(
        Q(verified_by__isnull=False) | Q(release_record__sent_to_cashier_at__isnull=False)
    )
    if use_date_filter:
        all_labs = all_labs.filter(created__date=filter_date)
    all_labs = all_labs.select_related(
        'test', 'order__encounter__patient', 'release_record'
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
    
    # Filter for unpaid; do not create bill in dashboard loop
    pending_labs = []
    for lab in unique_labs:
        release_record = getattr(lab, 'release_record', None)
        if release_record:
            if release_record.payment_receipt_id:
                continue
            if release_record.sent_to_cashier_at or lab.verified_by_id:
                pending_labs.append(lab)
        else:
            pending_labs.append(lab)
    
    # Get prescriptions; date filter at DB, cap, prefetch to avoid N+1
    all_prescriptions = Prescription.objects.filter(
        is_deleted=False
    )
    if use_date_filter:
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
    # Prefetch invoice_lines: must use InvoiceLine queryset (FK lives on InvoiceLine), not Prescription,
    # so Django's prefetch can do queryset.filter(prescription__in=...) on InvoiceLine.
    all_prescriptions = all_prescriptions.select_related(
        'drug', 'order__encounter__patient', 'prescribed_by', 'dispensing_record'
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
    
    # Filter for unpaid and deduplicate
    pending_pharmacy = []
    seen_prescriptions = set()  # Track seen prescription IDs to prevent duplicates
    
    for rx in unique_prescriptions:
        # Skip if we've already added this prescription
        if rx.id in seen_prescriptions:
            continue
        
        try:
            # Use prefetched dispensing_record (no N+1)
            dispensing = getattr(rx, 'dispensing_record', None)
            if dispensing and dispensing.payment_receipt_id:
                continue  # Already paid, skip
            # Do not show at cashier if pharmacy removed or cancelled this item
            if dispensing and (
                dispensing.dispensing_status == 'cancelled' or
                (dispensing.quantity_ordered or 0) <= 0
            ):
                continue
            # Insurance/corporate send: billed to payer, not the till — hide from cashier queue
            if dispensing and (
                dispensing.dispensing_status == 'ready_to_dispense'
                and getattr(dispensing, 'payment_verified_at', None)
                and not dispensing.payment_receipt_id
            ):
                continue

            # Use prefetched invoice_lines (no N+1)
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
                # Use invoice line price (reflects pharmacy's edited drug/quantity)
                rx.display_price = invoice_line.unit_price * invoice_line.quantity
            else:
                # No invoice line yet: pharmacy has not sent to cashier/payer — do not bill or list at cashier
                continue

            # Add to pending list and mark as seen
            pending_pharmacy.append(rx)
            seen_prescriptions.add(rx.id)
            
        except Exception as e:
            logger.error(f"Error processing prescription {rx.id}: {str(e)}")
            # Skip this prescription if there's an error
            continue
    
    # Get active admissions (for bed charges); limit to recent to avoid N+1 on large sets
    from datetime import timedelta
    pending_admissions = []
    active_admissions = Admission.objects.filter(
        is_deleted=False,
        status='admitted'
    ).select_related('encounter__patient', 'ward', 'bed').order_by('-admit_date')
    if use_date_filter:
        active_admissions = active_admissions.filter(admit_date=filter_date)[:CASHIER_DASHBOARD_CAP]
    else:
        # Limit to last 90 days when not filtering by date
        ninety_days_ago = today - timedelta(days=90)
        active_admissions = active_admissions.filter(admit_date__gte=ninety_days_ago)[:CASHIER_DASHBOARD_CAP]
    
    for admission in active_admissions:
        try:
            # Calculate current bed charges
            from .services.bed_billing_service import bed_billing_service
            charges = bed_billing_service.get_bed_charges_summary(admission)
            admission.bed_charges = charges
            pending_admissions.append(admission)
        except Exception as e:
            logger.error(f"Error calculating bed charges for admission {admission.pk}: {str(e)}")
    
    # Walk-in pharmacy sales pending payment (exclude waived). Filter by date at DB before [:20] so
    # today's rows are not dropped when many older pending sales exist.
    walkin_sales_qs = WalkInPharmacySale.objects.filter(
        is_deleted=False,
        payment_status__in=['pending', 'partial'],
        waived_at__isnull=True
    ).select_related('patient')
    if use_date_filter:
        if filter_date == today:
            last_24h = timezone.now() - timedelta(hours=24)
            walkin_sales_qs = walkin_sales_qs.filter(
                Q(sale_date__gte=last_24h)
                | Q(sale_date__date=today)
                | Q(sale_date__isnull=True, created__date=today)
            )
        else:
            walkin_sales_qs = walkin_sales_qs.filter(
                Q(sale_date__date=filter_date)
                | Q(sale_date__isnull=True, created__date=filter_date)
            )
    walkin_sales_qs = walkin_sales_qs.order_by('-sale_date')
    pending_walkin_sales = list(walkin_sales_qs[:20])
    total_pending_walkin = walkin_sales_qs.count()

    # Get imaging studies (completed ones ready for payment); date filter at DB, cap, no create_bill in loop
    from .models_advanced import ImagingStudy
    from .models_payment_verification import ImagingRelease
    from .models_accounting import PaymentReceipt
    
    all_imaging = ImagingStudy.objects.filter(
        is_deleted=False
    ).filter(
        Q(status__in=IMAGING_BILLABLE_STATUSES) |
        Q(images__isnull=False)
    )
    if use_date_filter:
        all_imaging = all_imaging.filter(
            Q(performed_at__date=filter_date) | Q(performed_at__isnull=True, created__date=filter_date)
        )
    all_imaging = all_imaging.select_related(
        'order__encounter__patient', 'patient'
    ).prefetch_related('release_record').distinct().order_by('-performed_at', '-created')[:CASHIER_DASHBOARD_CAP]
    
    pending_imaging = []
    for imaging in all_imaging:
        try:
            release_record = getattr(imaging, 'release_record', None)
            if release_record and release_record.payment_receipt_id:
                continue  # Already paid, skip
        except Exception:
            pass
        # Do not create release/bill in dashboard loop; created on first "Process payment"
        
        # Get price for display
        try:
            invoice_line = InvoiceLine.objects.filter(
                invoice__encounter=imaging.encounter,
                invoice__patient=imaging.patient if hasattr(imaging, 'patient') else imaging.order.encounter.patient,
                is_deleted=False
            ).filter(
                Q(service_code__description__icontains=imaging.study_type or '') |
                Q(description__icontains=imaging.study_type or '')
            ).first()
            
            if invoice_line:
                imaging.display_price = invoice_line.unit_price or invoice_line.line_total
            else:
                # Try to get from ImagingCatalog
                from .models_advanced import ImagingCatalog
                catalog_item = ImagingCatalog.objects.filter(
                    Q(code=imaging.study_type) | Q(name__iexact=imaging.study_type),
                    modality=imaging.modality,
                    is_active=True,
                    is_deleted=False
                ).first()
                
                if catalog_item and catalog_item.price:
                    imaging.display_price = catalog_item.price
                else:
                    imaging.display_price = Decimal('50.00')  # Default
        except Exception as e:
            logger.warning(f"Error getting price for imaging {imaging.id}: {str(e)}")
            imaging.display_price = Decimal('50.00')
        
        # Add to pending list
        pending_imaging.append(imaging)

    # Get unpaid consultation encounters (Outpatient + Special Consultation) so cashier sees them with patient name
    consultations_query = Encounter.objects.filter(
        is_deleted=False,
        status='active'
    ).select_related('patient').order_by('-started_at')
    if use_date_filter:
        day_start, day_end = local_datetime_bounds_for_date(filter_date)
        if filter_date == today:
            last_24h = timezone.now() - timedelta(hours=24)
            consultations_query = consultations_query.filter(
                Q(started_at__gte=day_start, started_at__lt=day_end) | Q(started_at__gte=last_24h)
            )
        else:
            consultations_query = consultations_query.filter(
                started_at__gte=day_start, started_at__lt=day_end
            )
    consultations_query = consultations_query[:CASHIER_DASHBOARD_CAP]
    consultation_paid_encounter_ids = set(
        PaymentReceipt.objects.filter(
            is_deleted=False,
            service_type='consultation',
            invoice__encounter_id__isnull=False
        ).values_list('invoice__encounter_id', flat=True).distinct()
    )
    from django.db.models.functions import TruncDate
    old_consultation_paid_set = set(
        PaymentReceipt.objects.filter(
            is_deleted=False,
            service_type='consultation',
            invoice__encounter_id__isnull=True
        ).annotate(rd=TruncDate('receipt_date')).values_list('patient_id', 'rd')
    )
    pending_consultations = []
    for e in consultations_query:
        if e.id in consultation_paid_encounter_ids:
            continue
        _sa = e.started_at
        if _sa and getattr(_sa, 'tzinfo', None):
            started_date = timezone.localtime(_sa).date()
        else:
            started_date = _sa.date() if hasattr(_sa, 'date') else _sa
        if old_consultation_paid_set and any(pid == e.patient_id and rdate >= started_date for (pid, rdate) in old_consultation_paid_set):
            continue
        cp = get_consultation_price_for_encounter(e)
        if cp == Decimal('30.00'):
            cp = Decimal('150.00')
        e.display_price = cp
        # Label for Overview so "Specialist Consultation" is visible (same as Patient Bills list)
        enc_type_lower = (e.encounter_type or '').lower()
        e.consultation_display = 'Specialist Consultation' if enc_type_lower == 'specialist' else f"{e.get_encounter_type_display()} Consultation"
        pending_consultations.append(e)

    # ----- Apply filters: patient name and date -----
    if filter_patient_name:
        sn = filter_patient_name.lower()
        pending_labs = [lab for lab in pending_labs if _patient_matches(lab.order.encounter.patient, filter_patient_name)]
        pending_pharmacy = [rx for rx in pending_pharmacy if _patient_matches(rx.order.encounter.patient, filter_patient_name)]
        _img_patient = lambda img: getattr(img, 'patient', None) or (img.order.encounter.patient if (getattr(img, 'order', None) and getattr(img.order, 'encounter', None)) else None)
        pending_imaging = [img for img in pending_imaging if _img_patient(img) and _patient_matches(_img_patient(img), filter_patient_name)]
        pending_admissions = [a for a in pending_admissions if _patient_matches(a.encounter.patient, filter_patient_name)]
        # Walk-in: match patient, customer_name, or sale_number
        def _walkin_matches(s):
            p = getattr(s, 'patient', None)
            if p and _patient_matches(p, filter_patient_name):
                return True
            if sn in (getattr(s, 'customer_name', None) or '').lower():
                return True
            if sn in (getattr(s, 'sale_number', None) or '').lower():
                return True
            return False
        pending_walkin_sales = [s for s in pending_walkin_sales if _walkin_matches(s)]
        total_pending_walkin = len(pending_walkin_sales)
        pending_consultations = [c for c in pending_consultations if _patient_matches(c.patient, filter_patient_name)]
    if use_date_filter:
        # When "today", allow yesterday too so last-24h items (and specialist consultations) show
        from datetime import timedelta
        allowed_dates = (filter_date,) if filter_date != today else (today, today - timedelta(days=1))
        pending_labs = [lab for lab in pending_labs if _item_date(lab, 'lab') in allowed_dates]
        pending_pharmacy = [rx for rx in pending_pharmacy if _item_date(rx, 'pharmacy') in allowed_dates]
        pending_imaging = [img for img in pending_imaging if _item_date(img, 'imaging') in allowed_dates]
        pending_admissions = [a for a in pending_admissions if _item_date(a, 'admission') in allowed_dates]
        # Walk-in dates already applied on queryset (see walkin_sales_qs); do not filter again here
        pending_consultations = [c for c in pending_consultations if _item_date(c, 'consultation') in allowed_dates]

    # Group pharmacy by patient + encounter so cashier sees one row per patient (one invoice per encounter)
    pharmacy_groups = []
    seen_encounters = set()
    for rx in pending_pharmacy:
        enc = rx.order.encounter if rx.order else None
        if not enc:
            continue
        key = (enc.patient_id, enc.id)
        if key in seen_encounters:
            continue
        seen_encounters.add(key)
        encounter_rxs = [r for r in pending_pharmacy if r.order and r.order.encounter_id == enc.id]
        total = sum(getattr(r, 'display_price', None) or getattr(r, 'total_price', None) or Decimal('0.00') for r in encounter_rxs)
        pharmacy_groups.append({
            'patient': enc.patient,
            'patient_name': getattr(enc.patient, 'full_name', None) or f"{getattr(enc.patient, 'first_name', '')} {getattr(enc.patient, 'last_name', '')}".strip(),
            'encounter': enc,
            'encounter_id': enc.id,
            'items': encounter_rxs,
            'total': total,
            'date_display': encounter_rxs[0].created if encounter_rxs else enc.started_at,
        })

    # Date for receipts and stats (selected date or today)
    receipts_date = filter_date if use_date_filter else today

    # Today's receipts - exclude "piece" receipts so combined payment shows as one receipt
    todays_receipts_base = PaymentReceipt.objects.filter(
        receipt_date__date=receipts_date,
        is_deleted=False
    ).exclude(notes__icontains='Part of combined bill')
    
    # For display - with slice and relations
    todays_receipts_display = todays_receipts_base.select_related(
        'patient', 'received_by'
    ).order_by('-receipt_date')[:20]
    
    # Statistics - use PaymentReceipt as source of truth for cash received
    todays_revenue_total = todays_receipts_base.aggregate(Sum('amount_paid'))['amount_paid__sum'] or Decimal('0.00')
    todays_cash_received = todays_receipts_base.filter(payment_method='cash').aggregate(Sum('amount_paid'))['amount_paid__sum'] or Decimal('0.00')
    
    # Unpaid invoices (manual charges, consultation, etc)
    pending_invoices_count = Invoice.objects.filter(
        is_deleted=False,
        status__in=('issued', 'draft', 'partially_paid'),
        balance__gt=0
    ).count()
    
    stats = {
        'pending_lab': len(pending_labs),
        'pending_pharmacy': len(pharmacy_groups),  # One row per patient/encounter
        'pending_pharmacy_items': len(pending_pharmacy),
        'pending_consultations': len(pending_consultations),
        'pending_imaging': len(pending_imaging),
        'pending_admissions': len(pending_admissions),
        'pending_invoices': pending_invoices_count,
        'todays_receipts': todays_receipts_base.count(),
        'todays_revenue': todays_revenue_total,
        'todays_cash_received': todays_cash_received,
        'pending_walkin': total_pending_walkin,
    }
    
    # Revenue by payment method (all methods from Transaction.PAYMENT_METHODS)
    stats['by_method'] = {}
    for method in ['cash', 'card', 'mobile_money', 'bank_transfer', 'cheque', 'insurance']:
        amount = todays_receipts_base.filter(payment_method=method).aggregate(Sum('amount_paid'))['amount_paid__sum']
        stats['by_method'][method] = amount or Decimal('0.00')

    # Group receipts by payment method for reconciliation (Cash, Card, MoMo)
    method_display = {
        'cash': 'Cash',
        'card': 'Card',
        'mobile_money': 'Mobile Money (MoMo)',
        'bank_transfer': 'Bank Transfer',
        'cheque': 'Cheque',
        'insurance': 'Insurance',
    }
    receipts_by_method = {}
    for method in ['cash', 'card', 'mobile_money', 'bank_transfer', 'cheque', 'insurance']:
        method_receipts = list(todays_receipts_base.filter(payment_method=method).select_related(
            'patient', 'received_by', 'transaction'
        ).order_by('-receipt_date'))
        if method_receipts or stats['by_method'][method]:
            receipts_by_method[method] = {
                'label': method_display.get(method, method.replace('_', ' ').title()),
                'total': stats['by_method'][method],
                'receipts': method_receipts,
                'count': len(method_receipts),
            }
    
    # Debug logging
    logger.info(f"Cashier Dashboard: {len(pending_labs)} pending labs, {len(pending_pharmacy)} pending pharmacy, {len(pending_imaging)} pending imaging")
    
    context = {
        'title': '💰 Centralized Cashier Dashboard',
        'pending_labs': pending_labs[:20],  # Show more
        'pending_pharmacy': pending_pharmacy[:20],
        'pharmacy_groups': pharmacy_groups[:20],  # One row per patient (combined drugs)
        'pending_consultations': pending_consultations[:20],
        'pending_imaging': pending_imaging[:20],  # Show imaging studies
        'pending_admissions': pending_admissions[:20],  # Show bed charges
        'pending_walkin_sales': pending_walkin_sales,
        'total_pending_walkin': total_pending_walkin,
        'todays_receipts': todays_receipts_display,
        'receipts_by_method': receipts_by_method,
        'stats': stats,
        'total_pending_labs': len(pending_labs),
        'total_pending_pharmacy': len(pharmacy_groups),
        'total_pending_pharmacy_items': len(pending_pharmacy),
        'total_pending_consultations': len(pending_consultations),
        'total_pending_imaging': len(pending_imaging),
        'total_pending_admissions': len(pending_admissions),
        # Filters for template
        'filter_patient_name': filter_patient_name,
        'filter_date': filter_date,
        'filter_date_str': filter_date_str,
        'filter_date_display': filter_date_display,
        'filter_today_pending': filter_today_pending,
        'use_date_filter': use_date_filter,
        'is_filtered': is_filtered,
        'receipts_date': receipts_date,
    }
    return render(request, 'hospital/centralized_cashier_dashboard.html', context)


@login_required
@user_passes_test(is_cashier)
@never_cache
def cashier_patient_total_bill(request, patient_id):
    """
    View total bill for a specific patient.
    Uses same pending-services logic as Process Combined Payment so outstanding matches
    on Total Bill, Record Deposit, and Process Payment.
    """
    patient = get_object_or_404(Patient, pk=patient_id, is_deleted=False)
    # Do not call _refresh_unpaid_invoice_line_prices_for_patient here: repricing from the
    # flexible-pricing engine returns 0 for many cashier-added codes (LABTEST-*, IMGCAT-*,
    # PHYSIO, etc.) and was wiping unit_price on invoice/print. Consultation lines that need
    # live repricing are handled elsewhere; use heal_invoice_zero_line_prices on invoice views.

    # Heal duplicate prescribe (walk-in) invoices: same sale sometimes got two INV rows when the
    # default Invoice manager hid a draft (total_amount=0) or invoice list backfill raced.
    try:
        for sale in WalkInPharmacySale.objects.filter(
            patient=patient,
            is_deleted=False,
            payment_status__in=['pending', 'partial'],
            waived_at__isnull=True,
        ).order_by('-sale_date')[:15]:
            WalkInPharmacyService.ensure_sale_invoice(sale, patient)
    except Exception:
        logger.exception('Prescribe invoice dedupe on total bill failed for patient %s', patient_id)
    
    # Single source of truth: same logic as Process Combined Payment so outstanding matches everywhere (Total Bill, Record Deposit, Process Payment)
    services_list, total = _get_patient_pending_services_for_payment(patient)

    # When opened from Patient Bills with "Today's Pending" or date/service filter, apply same filter so Total Bill matches that view
    today_pending = request.GET.get('today_pending') == '1'
    filter_date = None
    filter_date_str = request.GET.get('filter_date', '').strip()
    if filter_date_str:
        try:
            from datetime import datetime
            filter_date = datetime.strptime(filter_date_str, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            pass
    if filter_date is None and today_pending:
        filter_date = timezone.now().date()
    if filter_date is not None and not filter_date_str:
        filter_date_str = filter_date.isoformat()
    service_filter = (request.GET.get('service_filter') or '').strip().lower()

    if filter_date is not None:
        services_list = [s for s in services_list if _service_date_for_total_bill_filter(s) == filter_date]
        total = sum(s.get('price', Decimal('0.00')) for s in services_list)
    if service_filter and service_filter != 'all':
        services_list = [s for s in services_list if s.get('type') == service_filter]
        total = sum(s.get('price', Decimal('0.00')) for s in services_list)

    services = _total_bill_services_to_display(services_list)
    services.sort(key=lambda x: x['date'] or timezone.now(), reverse=True)
    # Match table footer to visible rows only (avoids counting removed/paid rows still in services_list).
    total = sum((s.get('price') or Decimal('0.00')) for s in services)

    from .services.deposit_payment_service import deposit_amount_applied_to_invoices_for_display

    _inv_ids_set = set()
    invoice_objs_for_deposit = []
    for s in services:
        if s.get('type') not in ('invoice', 'invoice_line'):
            continue
        iid = s.get('invoice_id')
        if not iid:
            continue
        sid = str(iid)
        if sid in _inv_ids_set:
            continue
        _inv_ids_set.add(sid)
        inv_row = _invoice_all_objects_by_pk(sid)
        if inv_row:
            invoice_objs_for_deposit.append(inv_row)
    _inv_ids = list(_inv_ids_set)
    # Diagnostic counts from services_list only (no labs_query, rx_query, etc. - those were removed)
    diagnostic_info = {
        'labs_found': sum(1 for s in services_list if s.get('type') == 'lab'),
        'prescriptions_found': 0,
        'imaging_found': sum(1 for s in services_list if s.get('type') == 'imaging'),
        'invoices_found': sum(1 for s in services_list if s.get('type') == 'invoice'),
        'walkin_sales_found': sum(1 for s in services_list if s.get('type') == 'pharmacy_walkin'),
        'admissions_found': sum(1 for s in services_list if s.get('type') == 'bed'),
    }
    # Patient deposit balance - reduces amount due (temporary deduction); and full list for display
    patient_deposit_balance = Decimal('0.00')
    patient_deposits_list = []
    deposit_applied_to_bill = Decimal('0.00')  # Deposit already applied to invoices on this bill (so invoice shows it)
    try:
        from .models_patient_deposits import PatientDeposit
        from .services.deposit_payment_service import get_patient_deposit_balance_display
        patient_deposit_balance = get_patient_deposit_balance_display(patient)
        patient_deposits_list = list(
            PatientDeposit.objects.filter(patient=patient, is_deleted=False).order_by('-deposit_date')
        )
        # Deposit applied only to invoices still shown on this bill (deduped; matches Invoice.calculate_totals logic).
        deposit_applied_to_bill = deposit_amount_applied_to_invoices_for_display(invoice_objs_for_deposit)
    except Exception:
        patient_deposit_balance = Decimal('0.00')
    # Face value of rows above ≈ outstanding (total) + deposit already applied to those invoices
    initial_total = total + deposit_applied_to_bill
    from .services.patient_outstanding_service import (
        get_patient_outstanding,
        sum_payment_receipts_for_patient_in_date_range,
    )
    from urllib.parse import urlencode

    outstanding_data = get_patient_outstanding(patient)
    total_paid_all_time = outstanding_data['total_paid']

    payment_date_from_str = request.GET.get('payment_date_from', '').strip()
    payment_date_to_str = request.GET.get('payment_date_to', '').strip()
    payment_filter_active = False
    payment_date_from = None
    payment_date_to = None
    if payment_date_from_str or payment_date_to_str:
        from datetime import datetime as dt_parse

        raw_from = payment_date_from_str or payment_date_to_str
        raw_to = payment_date_to_str or payment_date_from_str
        try:
            payment_date_from = dt_parse.strptime(raw_from, '%Y-%m-%d').date()
            payment_date_to = dt_parse.strptime(raw_to, '%Y-%m-%d').date()
            if payment_date_to < payment_date_from:
                payment_date_from, payment_date_to = payment_date_to, payment_date_from
            payment_filter_active = True
            payment_date_from_str = payment_date_from.isoformat()
            payment_date_to_str = payment_date_to.isoformat()
        except (ValueError, TypeError):
            payment_filter_active = False
            payment_date_from_str = ''
            payment_date_to_str = ''

    if payment_filter_active:
        total_paid = sum_payment_receipts_for_patient_in_date_range(
            patient, payment_date_from, payment_date_to
        )
    else:
        total_paid = total_paid_all_time

    total_billed = outstanding_data['total_billed']
    # Patient-level outstanding (entire history) is still available via outstanding_data['total_outstanding'],
    # but for this Total Bill screen we want the bill figure (combined pending services) to be the single
    # source of truth that matches the combined payment amount.
    total_outstanding = outstanding_data['total_outstanding']
    bill_outstanding = total  # combined amount for services currently on this bill
    patient_deposit_balance = outstanding_data['deposit_balance']
    amount_due_after_deposit = outstanding_data['amount_due_after_deposit']
    credit_balance = outstanding_data.get('credit_balance', Decimal('0.00'))
    show_refund_credit = credit_balance > 0 and Encounter.objects.filter(
        patient=patient, is_deleted=False, billing_closed_at__isnull=True
    ).exists()
    
    # Debug info - count services by type
    service_counts = {}
    for service in services:
        service_type = service['type']
        service_counts[service_type] = service_counts.get(service_type, 0) + 1

    from .utils_roles import user_can_remove_invoice_from_bill, user_can_waive, user_can_apply_total_bill_discount
    from django.urls import reverse
    from .models_settings import HospitalSettings
    try:
        remove_invoice_from_bill_url = reverse('hospital:remove_invoice_from_bill')
    except Exception:
        remove_invoice_from_bill_url = None
    # Remove invoice from bill: Accountant/Admin groups. Waiving lines / prescribe sales: user_can_waive (admin only).
    can_remove_invoice_from_bill = user_can_remove_invoice_from_bill(request.user)
    added_items_display = request.session.pop('cashier_added_items', None)

    # Reception visit price: so cashier sees what reception set (Antenatal 235, Gynae 260, or custom)
    reception_visit_info = None
    try:
        first_consult_line = _first_consult_line_for_reception_visit_banner(patient)
        if first_consult_line and first_consult_line.invoice and first_consult_line.invoice.encounter:
            enc = first_consult_line.invoice.encounter
            enc_type = (enc.encounter_type or '').lower()
            amount = consultation_line_display_amount(first_consult_line) or Decimal('0.00')
            if 'antenatal' in enc_type:
                reception_visit_info = {'label': 'Antenatal', 'amount': amount, 'standard': Decimal('235.00')}
            elif enc_type == 'gynae':
                reception_visit_info = {'label': 'Gynae / Special', 'amount': amount, 'standard': Decimal('260.00')}
            else:
                reception_visit_info = {'label': enc.get_encounter_type_display() or 'Consultation', 'amount': amount, 'standard': None}
    except Exception as e:
        logger.debug('Reception visit info: %s', e)

    # Pass filter state so "Back to All Bills" and banner match Patient Bills view
    bills_list_query = ''
    if today_pending or filter_date_str or service_filter:
        parts = []
        if today_pending:
            parts.append('today_pending=1')
        if filter_date_str and not today_pending:
            parts.append(f'filter_date={filter_date_str}')
        if service_filter:
            parts.append(f'service_filter={service_filter}')
        bills_list_query = '?' + '&'.join(parts)

    preserve_q = {}
    if request.GET.get('today_pending') == '1':
        preserve_q['today_pending'] = '1'
    elif filter_date_str:
        preserve_q['filter_date'] = filter_date_str
    if service_filter:
        preserve_q['service_filter'] = service_filter
    if payment_filter_active:
        preserve_q['payment_date_from'] = payment_date_from_str
        preserve_q['payment_date_to'] = payment_date_to_str
    total_bill_preserve_query = urlencode(preserve_q)
    clear_payment_q = {k: v for k, v in preserve_q.items() if k not in ('payment_date_from', 'payment_date_to')}
    total_bill_clear_payment_query = urlencode(clear_payment_q)

    context = {
        'patient': patient,
        'services': services,
        'total': total,
        'initial_total': initial_total,
        'deposit_applied_to_bill': deposit_applied_to_bill,
        'total_outstanding': total_outstanding,
        'bill_outstanding': bill_outstanding,
        'amount_due_after_deposit': amount_due_after_deposit,
        'credit_balance': credit_balance,
        'show_refund_credit': show_refund_credit,
        'patient_deposit_balance': patient_deposit_balance,
        'patient_deposits': patient_deposits_list,
        'total_paid': total_paid,
        'total_paid_all_time': total_paid_all_time,
        'payment_filter_active': payment_filter_active,
        'payment_date_from_str': payment_date_from_str,
        'payment_date_to_str': payment_date_to_str,
        'total_bill_preserve_query': total_bill_preserve_query,
        'total_bill_clear_payment_query': total_bill_clear_payment_query,
        'services_count': len(services),
        'service_counts': service_counts,  # For debugging
        'diagnostic_info': diagnostic_info,  # For troubleshooting
        'can_waive': user_can_waive(request.user),
        'remove_invoice_from_bill_url': remove_invoice_from_bill_url,
        'can_remove_invoice_from_bill': can_remove_invoice_from_bill,
        'added_items_display': added_items_display,
        'today_pending': today_pending,
        'filter_date': filter_date,
        'filter_date_str': filter_date_str or '',
        'service_filter': service_filter,
        'bills_list_query': bills_list_query,
        'reception_visit_info': reception_visit_info,
        'can_apply_total_bill_discount': user_can_apply_total_bill_discount(request.user),
    }
    if request.GET.get('print') == '1':
        from collections import OrderedDict
        categories_order = [
            ('pharmacy_walkin', 'Pharmacy Services'),
            ('lab', 'Lab Services'),
            ('imaging', 'Imaging Services'),
            ('invoice', 'Invoice Charges'),
            ('invoice_line', 'Invoice Charges'),
            ('bed', 'Bed Charges'),
        ]
        type_to_category = dict(categories_order)
        grouped = OrderedDict()
        for cat_key, cat_name in categories_order:
            grouped[cat_name] = []
        for service in services:
            try:
                stype = service.get('type', '') or ''
                sid = str(service.get('id', ''))
                cat_name = type_to_category.get(stype, f'{str(stype).replace("_", " ").title()} Services')
                if cat_name not in grouped:
                    grouped[cat_name] = []
                if service.get('breakdown'):
                    for row in service['breakdown']:
                        if row.get('is_waived'):
                            continue
                        code = f"WALKIN-{sid[:12]}" if stype == 'pharmacy_walkin' else (f"INV-{sid[:8]}" if stype in ('invoice', 'invoice_line') else f"{str(stype).upper()[:6]}-1")
                        grouped[cat_name].append({
                            'code': code,
                            'description': str(row.get('description') or '—'),
                            'qty': row.get('quantity', 1),
                            'unit': row.get('unit_price', 0),
                            'total': row.get('amount', 0),
                            'date': row.get('date') or service.get('date'),
                        })
                else:
                    grouped[cat_name].append({
                        'code': str(stype).upper()[:8],
                        'description': str(service.get('name', '')),
                        'qty': 1,
                        'unit': service.get('price', 0),
                        'total': service.get('price', 0),
                        'date': service.get('date'),
                    })
            except Exception as e:
                logger.warning('Generate bill: skip service due to %s', e)
                continue
        charges_by_category = [{'category_name': name, 'lines': lines} for name, lines in grouped.items() if lines]
        total_invoice_items = sum(len(cat['lines']) for cat in charges_by_category)
        context['hospital_settings'] = HospitalSettings.get_settings()
        context['charges_by_category'] = charges_by_category
        context['total_invoice_items'] = total_invoice_items
        return render(request, 'hospital/cashier_patient_total_bill_invoice_print.html', context)
    return render(request, 'hospital/cashier_patient_total_bill.html', context)


@login_required
@never_cache
def cashier_apply_total_bill_discount(request, patient_id):
    """POST: apply admin/accountant discount across open invoices on the patient's total bill."""
    from decimal import Decimal, InvalidOperation

    from django.contrib import messages
    from django.urls import reverse

    from .services.combined_bill_discount_service import distribute_combined_bill_discount_across_invoices
    from .utils_roles import user_can_apply_total_bill_discount

    patient = get_object_or_404(Patient, pk=patient_id, is_deleted=False)
    redirect_url = reverse('hospital:cashier_patient_total_bill', kwargs={'patient_id': patient_id})
    preserve = []
    for key in ('today_pending', 'filter_date', 'service_filter'):
        val = request.POST.get(key) or request.GET.get(key)
        if val:
            preserve.append(f'{key}={val}')
    if preserve:
        redirect_url = f'{redirect_url}?{"&".join(preserve)}'

    if request.method != 'POST':
        return redirect(redirect_url)
    if not user_can_apply_total_bill_discount(request.user):
        messages.error(request, 'You do not have permission to apply total bill discounts.')
        return redirect(redirect_url)

    try:
        discount_amount = Decimal(str(request.POST.get('discount_amount') or '0').strip())
    except (InvalidOperation, TypeError, ValueError):
        messages.error(request, 'Enter a valid discount amount.')
        return redirect(redirect_url)
    if discount_amount <= 0:
        messages.error(request, 'Discount must be greater than zero.')
        return redirect(redirect_url)

    services_list, _total = _get_patient_pending_services_for_payment(patient)
    invoice_ids = []
    for svc in services_list:
        iid = svc.get('invoice_id')
        if iid and str(iid) not in invoice_ids:
            invoice_ids.append(str(iid))
    invoices = list(
        Invoice.all_objects.filter(pk__in=invoice_ids, patient=patient, is_deleted=False)
        if invoice_ids
        else []
    )
    if not invoices:
        messages.warning(request, 'No open invoices on this bill to discount.')
        return redirect(redirect_url)

    result = distribute_combined_bill_discount_across_invoices(
        invoices,
        discount_amount,
        patient=patient,
        user=request.user,
    )
    if result.applied > 0:
        msg = f'Applied GHS {result.applied:.2f} bill discount.'
        if result.gl_posted:
            msg += ' General ledger updated.'
        elif result.gl_error:
            msg += f' GL posting skipped: {result.gl_error}'
        messages.success(request, msg)
    else:
        messages.warning(request, 'No discount was applied (check outstanding balance).')
    return redirect(redirect_url)


@login_required
@user_passes_test(is_cashier)
@never_cache
def cashier_patient_deposit_usage_json(request, patient_id, deposit_id):
    """JSON list of invoices/amounts this deposit was applied to (for total-bill modal)."""
    from django.http import JsonResponse
    from django.urls import reverse
    from .models_patient_deposits import PatientDeposit, DepositApplication

    patient = get_object_or_404(Patient, pk=patient_id, is_deleted=False)
    dep = get_object_or_404(PatientDeposit, pk=deposit_id, patient=patient, is_deleted=False)
    applications = (
        DepositApplication.objects.filter(deposit=dep, is_deleted=False)
        .select_related('invoice')
        .order_by('-applied_date')
    )
    rows = []
    for app in applications:
        inv = app.invoice
        if not inv:
            continue
        line_count = 0
        try:
            line_count = inv.lines.filter(is_deleted=False).count()
        except Exception:
            pass
        rows.append(
            {
                'applied_amount': str(app.applied_amount),
                'applied_date': (
                    timezone.localtime(app.applied_date).strftime('%d %b %Y %H:%M')
                    if app.applied_date
                    else ''
                ),
                'invoice_number': getattr(inv, 'invoice_number', None) or str(inv.pk)[:8],
                'invoice_id': str(inv.pk),
                'invoice_status': getattr(inv, 'status', '') or '',
                'invoice_balance': str(getattr(inv, 'balance', '') or ''),
                'line_count': line_count,
                'invoice_url': reverse('hospital:invoice_detail', args=[inv.pk]),
            }
        )
    return JsonResponse(
        {
            'deposit_number': dep.deposit_number,
            'deposit_amount': str(dep.deposit_amount),
            'used_amount': str(dep.used_amount or Decimal('0.00')),
            'applications': rows,
        }
    )


@login_required
@user_passes_test(is_cashier)
def cashier_apply_deposit_to_bill(request, patient_id):
    """
    Apply patient's deposit balance to all unpaid invoices (bill). One-click – affects the bill as payment,
    then generates a receipt and redirects to receipt print.
    """
    from .services.deposit_payment_service import apply_deposit_to_all_patient_invoices

    if request.method != 'POST':
        return redirect('hospital:cashier_patient_total_bill', patient_id=patient_id)

    patient = get_object_or_404(Patient, pk=patient_id, is_deleted=False)
    try:
        # create_receipt=True: each invoice gets its own receipt so totals/outstanding are correct (plan §2)
        total_applied = apply_deposit_to_all_patient_invoices(patient, create_receipt=True)
    except Exception as e:
        logger.exception("Apply deposit to bill failed")
        messages.error(request, f'Could not apply deposit: {e}')
        return redirect('hospital:cashier_patient_total_bill', patient_id=patient_id)

    if total_applied > 0:
        messages.success(
            request,
            f'Deposit GHS {total_applied:.2f} applied to the total bill. A receipt was created for each invoice.'
        )
    else:
        messages.info(request, 'No deposit was applied (no deposit balance or no unpaid cash invoices).')
    return redirect('hospital:cashier_patient_total_bill', patient_id=patient_id)


@login_required
@user_passes_test(is_cashier)
def cashier_refund_credit(request, patient_id):
    """
    Refund patient credit (overpayment). Only when encounter is not yet discharged (plan §6).
    Creates refund_issued transaction(s) so invoice balance increases (credit reduces).
    """
    from .services.patient_outstanding_service import get_patient_outstanding
    from .models_accounting import Transaction

    patient = get_object_or_404(Patient, pk=patient_id, is_deleted=False)
    outstanding_data = get_patient_outstanding(patient)
    credit_balance = outstanding_data.get('credit_balance', Decimal('0.00'))
    if credit_balance <= 0:
        messages.info(request, 'No credit to refund.')
        return redirect('hospital:cashier_patient_total_bill', patient_id=patient_id)
    has_open_encounter = Encounter.objects.filter(
        patient=patient, is_deleted=False, billing_closed_at__isnull=True
    ).exists()
    if not has_open_encounter:
        messages.warning(request, 'Refund credit is only available before discharge.')
        return redirect('hospital:cashier_patient_total_bill', patient_id=patient_id)

    if request.method == 'POST':
        try:
            amount_str = (request.POST.get('amount') or '').strip()
            refund_method = request.POST.get('refund_method', 'cash')
            notes = (request.POST.get('notes') or '').strip() or 'Refund of credit (pre-discharge)'
            amount = Decimal(amount_str) if amount_str else credit_balance
            if amount <= 0 or amount > credit_balance:
                messages.error(request, f'Amount must be between GHS 0.01 and GHS {credit_balance:.2f}.')
                return redirect('hospital:cashier_refund_credit', patient_id=patient_id)
        except Exception as e:
            messages.error(request, f'Invalid amount: {e}')
            return redirect('hospital:cashier_refund_credit', patient_id=patient_id)

        invoices_with_credit = list(
            Invoice.objects.filter(patient=patient, is_deleted=False)
            .exclude(status='cancelled')
            .filter(balance__lt=0)
            .order_by('balance')
        )
        if not invoices_with_credit:
            messages.warning(request, 'No invoice with credit found. Totals may need recalc.')
            return redirect('hospital:cashier_patient_total_bill', patient_id=patient_id)

        remaining = amount
        created = []
        for inv in invoices_with_credit:
            if remaining <= 0:
                break
            inv.refresh_from_db()
            credit_on_inv = abs(inv.balance or Decimal('0.00'))
            if credit_on_inv <= 0:
                continue
            alloc = min(remaining, credit_on_inv)
            txn = Transaction.objects.create(
                transaction_type='refund_issued',
                invoice=inv,
                patient=patient,
                amount=alloc,
                payment_method=refund_method,
                processed_by=request.user,
                transaction_date=timezone.now(),
                notes=notes,
            )
            inv.update_totals()
            created.append(txn)
            remaining -= alloc
        if created:
            messages.success(
                request,
                f'Refund of GHS {amount:.2f} processed. Transaction(s): {", ".join(t.transaction_number for t in created)}.'
            )
        return redirect('hospital:cashier_patient_total_bill', patient_id=patient_id)

    context = {
        'patient': patient,
        'credit_balance': credit_balance,
        'title': f'Refund credit - {patient.full_name}',
    }
    return render(request, 'hospital/cashier_refund_credit.html', context)


@login_required
@user_passes_test(is_cashier)
def cashier_add_services_to_invoice(request, patient_id):
    """
    Automatically add all pending services to an invoice
    Creates invoice lines for services that aren't on invoices yet
    Can target a specific invoice if invoice_id is provided
    """
    from .models import Invoice, InvoiceLine, ServiceCode
    from .services.auto_billing_service import AutoBillingService
    
    patient = get_object_or_404(Patient, pk=patient_id, is_deleted=False)
    
    # Check if a specific invoice ID was provided (from invoice detail page)
    invoice_id = request.POST.get('invoice_id') or request.GET.get('invoice_id')
    target_invoice = None
    
    if invoice_id:
        try:
            target_invoice = Invoice.objects.get(
                pk=invoice_id,
                patient=patient,
                is_deleted=False
            )
        except Invoice.DoesNotExist:
            pass
    
    # Get or create invoice for this patient
    payer = patient.primary_insurance or None
    if not payer:
        from .models import Payer
        payer, _ = Payer.objects.get_or_create(
            name='Cash',
            payer_type='cash',
            defaults={'is_active': True}
        )
    
    # Get the most recent encounter
    from .models import Encounter
    encounter = Encounter.objects.filter(
        patient=patient,
        is_deleted=False
    ).order_by('-started_at').first()
    
    # Determine which invoice to use
    if target_invoice:
        # Use the specified invoice
        invoice = target_invoice
    else:
        # Get existing invoice or create new one
        # First try to get an existing issued invoice with no lines
        invoices_with_lines = InvoiceLine.objects.filter(
            invoice__patient=patient,
            invoice__is_deleted=False,
            is_deleted=False
        ).values_list('invoice_id', flat=True).distinct()
        
        invoice = Invoice.objects.filter(
            patient=patient,
            is_deleted=False,
            status__in=['draft', 'issued']
        ).exclude(id__in=invoices_with_lines).first()
        
        if not invoice and encounter:
            # Prefer invoice for this specific encounter (avoid duplicates)
            invoice = Invoice.objects.filter(
                patient=patient,
                encounter=encounter,
                is_deleted=False
            ).first()
        if not invoice:
            # Get most recent unpaid invoice
            invoice = Invoice.objects.filter(
                patient=patient,
                is_deleted=False
            ).exclude(status__in=['paid', 'cancelled']).order_by('-created').first()
        if not invoice:
            # Create new invoice
            invoice = Invoice.objects.create(
                patient=patient,
                encounter=encounter,
                payer=payer,
                status='issued',
                total_amount=Decimal('0.00'),
                balance=Decimal('0.00'),
            )
    if invoice and getattr(invoice, 'encounter', None) and getattr(invoice.encounter, 'billing_closed_at', None):
        messages.error(
            request,
            'Billing is closed for this encounter (discharged). No new charges can be added.',
        )
        return redirect('hospital:cashier_patient_total_bill', patient_id=patient_id)
    
    lines_created = 0
    errors = []
    
    # Add lab results
    labs = LabResult.objects.filter(
        order__encounter__patient=patient,
        is_deleted=False
    ).select_related('test', 'order__encounter')
    
    for lab in labs:
        # Check if already on ANY invoice for this patient (match by service_code + encounter)
        test_code = getattr(lab.test, 'code', None) or str(lab.test_id)
        lab_service_code = f"LAB-{test_code}"
        existing_qs = InvoiceLine.objects.filter(
            invoice__patient=patient,
            invoice__is_deleted=False,
            service_code__code=lab_service_code,
            description__icontains=lab.test.name if lab.test else '',
            is_deleted=False
        )
        if lab.order and lab.order.encounter_id:
            existing_qs = existing_qs.filter(invoice__encounter=lab.order.encounter)
        existing_line = existing_qs.exists()
        
        if not existing_line:
            try:
                if target_invoice:
                    # Add directly to the specified invoice (create or merge to avoid duplicates)
                    from .models import ServiceCode
                    from .services.pricing_engine_service import PricingEngineService
                    
                    # Get or create service code
                    test_code = getattr(lab.test, 'code', None) or str(lab.test.id)
                    service_code = ServiceCode.objects.filter(
                        code=f"LAB-{test_code}",
                        is_deleted=False
                    ).first()
                    
                    if not service_code:
                        service_code = ServiceCode.objects.create(
                            code=f"LAB-{test_code}",
                            description=lab.test.name,
                            category='Laboratory Services',
                            is_active=True,
                        )
                    
                    # Get price
                    test_price = getattr(lab.test, 'price', None) or Decimal('50.00')
                    pricing_service = PricingEngineService()
                    unit_price = pricing_service.get_price_for_service(
                        service_code=service_code,
                        service_name=lab.test.name,
                        payer=invoice.payer,
                        default_price=test_price
                    )
                    
                    _, created = create_or_merge_invoice_line(
                        invoice=invoice,
                        service_code=service_code,
                        quantity=Decimal('1'),
                        unit_price=unit_price,
                        description=lab.test.name,
                    )
                    if created:
                        lines_created += 1
                else:
                    # Create invoice line using auto billing service (creates its own invoice)
                    result = AutoBillingService.create_lab_bill(lab)
                    if result.get('success'):
                        lines_created += 1
            except Exception as e:
                errors.append(f"Lab {lab.test.name if lab.test else 'Unknown'}: {str(e)}")
                logger.error(f"Error adding lab to invoice: {str(e)}")
    
    # Do NOT add prescriptions here. Consultation prescriptions go to pharmacy first.
    # Pharmacy edits (drug/quantity), then sends to payer or cancels. Bill is created only
    # when pharmacy uses "Send to Cashier" / "Send to Insurance" (create_pharmacy_bill).
    
    # Add imaging studies
    from .models_advanced import ImagingStudy
    imaging_studies = ImagingStudy.objects.filter(
        Q(patient=patient) | Q(order__encounter__patient=patient),
        is_deleted=False
    ).select_related('order__encounter')
    
    for imaging in imaging_studies:
        # Use same canonical code as create_imaging_bill so we find/merge the same line (prevents duplicate scan lines)
        img_code = AutoBillingService.get_imaging_service_code_string(imaging)
        existing_qs = InvoiceLine.objects.filter(
            invoice__patient=patient,
            invoice__is_deleted=False,
            is_deleted=False
        )
        if img_code:
            existing_qs = existing_qs.filter(service_code__code=img_code)
        existing_line = existing_qs.exists()
        
        if not existing_line:
            try:
                if target_invoice:
                    # Add directly to the specified invoice (create or merge to avoid duplicates)
                    from .models import ServiceCode
                    from .services.pricing_engine_service import PricingEngineService
                    from .models_advanced import ImagingCatalog
                    
                    # Get price from ImagingCatalog
                    imaging_price = Decimal('50.00')  # Default
                    if hasattr(imaging, 'price') and imaging.price:
                        imaging_price = imaging.price
                    else:
                        # Try to get from ImagingCatalog
                        catalog_item = ImagingCatalog.objects.filter(
                            study_type__iexact=imaging.study_type,
                            body_part__iexact=imaging.body_part,
                            is_deleted=False
                        ).first()
                        if catalog_item:
                            # Get price based on payer
                            pricing_service = PricingEngineService()
                            imaging_price = pricing_service.get_price_for_service(
                                service_code=None,
                                service_name=f"{imaging.study_type} - {imaging.body_part}",
                                payer=invoice.payer,
                                default_price=Decimal('50.00')
                            )
                    
                    # Get or create service code (same code as create_imaging_bill for merge)
                    service_code = ServiceCode.objects.filter(
                        code=img_code,
                        is_deleted=False
                    ).first()
                    
                    if not service_code:
                        service_code = ServiceCode.objects.create(
                            code=img_code,
                            description=f"{imaging.study_type} - {imaging.body_part}",
                            category='Imaging Services',
                            is_active=True,
                        )
                    
                    desc = f"{imaging.study_type} - {imaging.body_part}"
                    _, created = create_or_merge_invoice_line(
                        invoice=invoice,
                        service_code=service_code,
                        quantity=Decimal('1'),
                        unit_price=imaging_price,
                        description=desc,
                        max_quantity=1,
                    )
                    if created:
                        lines_created += 1
                else:
                    result = AutoBillingService.create_imaging_bill(imaging)
                    if result.get('success'):
                        lines_created += 1
            except Exception as e:
                errors.append(f"Imaging {imaging.study_type}: {str(e)}")
                logger.error(f"Error adding imaging to invoice: {str(e)}")
    
    # Recalculate and persist invoice totals so added items (e.g. Service Charge) show on bill
    if hasattr(invoice, 'update_totals'):
        invoice.update_totals()
    elif hasattr(invoice, 'calculate_totals'):
        invoice.calculate_totals()
        invoice.save(update_fields=['total_amount', 'balance', 'status'])
    
    if lines_created > 0:
        messages.success(
            request,
            f"✅ Added {lines_created} service(s) to invoice {invoice.invoice_number}. "
            f"Total: GHS {invoice.total_amount:.2f}"
        )
        # Redirect to invoice detail if we were adding to a specific invoice
        if target_invoice:
            return redirect('hospital:cashier_invoice_detail', pk=invoice.id)
    else:
        messages.info(request, "No new services to add. All services are already on invoices.")
        # Still redirect to invoice detail if we were on that page
        if target_invoice:
            return redirect('hospital:cashier_invoice_detail', pk=invoice.id)
    
    if errors:
        messages.warning(request, f"Some services could not be added: {', '.join(errors[:5])}")
    
    return redirect('hospital:cashier_patient_total_bill', patient_id=patient_id)


# Addable services for cashier to select (code, label, cash_amount, insurance_amount)
# Order: common + dental (Scaling 460) + antenatal/gynae + rest
ADDABLE_SERVICES = [
    ('registration_fee', 'Registration Fee', Decimal('50.00'), Decimal('50.00')),
    ('service_charge', 'Service Charge', Decimal('25.00'), Decimal('25.00')),
    ('gp', 'General Consultation (GP)', Decimal('150.00'), Decimal('150.00')),
    ('scaling_polishing', 'Scaling and Polishing (Dental)', Decimal('460.00'), Decimal('460.00')),
    ('antenatal', 'Antenatal (Special Payment)', Decimal('235.00'), Decimal('235.00')),
    ('gynae_special', 'Gynae / Special (Special Payment)', Decimal('260.00'), Decimal('260.00')),
    ('admission', 'Admission', Decimal('150.00'), Decimal('150.00')),
    ('bed', 'Bed Fee', Decimal('150.00'), Decimal('140.00')),
    ('detainment', 'Detainment Fee', Decimal('150.00'), Decimal('140.00')),
    ('doctor_care', 'Doctor Care', Decimal('80.00'), Decimal('80.00')),
    ('nursing_care', 'Nursing Care', Decimal('70.00'), Decimal('70.00')),
    ('dressing', 'Dressing', Decimal('50.00'), Decimal('50.00')),
    ('injection', 'Injection', Decimal('20.00'), Decimal('20.00')),
    ('ecg', 'ECG', Decimal('80.00'), Decimal('80.00')),
    ('urinalysis', 'Urinalysis', Decimal('30.00'), Decimal('30.00')),
    ('xray', 'X-Ray', Decimal('60.00'), Decimal('60.00')),
    ('wound_care', 'Wound Care', Decimal('40.00'), Decimal('40.00')),
    ('delivery_fee', 'Delivery Fee', Decimal('2800.00'), Decimal('2800.00')),
    ('midwife_care', 'Midwife Care', Decimal('300.00'), Decimal('300.00')),
    ('physio', 'Physiotherapy', Decimal('250.00'), Decimal('250.00')),
    # Quick-add consumables and oxygen services (front desk standard amounts)
    ('consumables_50', 'Consumables (Package)', Decimal('50.00'), Decimal('50.00')),
    ('oxygen_60min', 'Oxygen (60 minutes)', Decimal('220.00'), Decimal('220.00')),
]

SERVICE_CODE_MAP = {
    'registration_fee': 'REG', 'service_charge': 'SVC-CHG', 'gp': 'CON001',
    'antenatal': 'MAT-ANC', 'gynae_special': 'CON002',
    'scaling_polishing': 'DENT-SCALE',
    'admission': 'ADM001', 'bed': 'BED001', 'detainment': 'DET001',
    'doctor_care': 'ADM-DOCTOR-CARE', 'nursing_care': 'ADM-NURSING-CARE',
    'dressing': 'DRS001', 'injection': 'INJ001', 'ecg': 'ECG001', 'urinalysis': 'URA001',
    'xray': 'XR001', 'wound_care': 'WND001',
    'delivery_fee': 'MAT-DELIVER', 'midwife_care': 'MAT-MIDWIFE',
    'physio': 'PHYSIO',
    'consumables_50': 'CONS-PACK',
    'oxygen_60min': 'OXY-60',
}


def _resolve_physio_charge_for_patient(patient):
    """
    First physio charge in system is 250; subsequent charges are 150.
    """
    had_prior_physio = InvoiceLine.objects.filter(
        invoice__patient=patient,
        invoice__is_deleted=False,
        is_deleted=False,
        waived_at__isnull=True,
        service_code__code__in=['PHYSIO', 'PHYSIO-SUB'],
    ).exclude(invoice__status='cancelled').exists()
    if had_prior_physio:
        return {
            'service_code': 'PHYSIO-SUB',
            'label': 'Physiotherapy (Subsequent Session)',
            'amount': Decimal('150.00'),
        }
    return {
        'service_code': 'PHYSIO',
        'label': 'Physiotherapy (First Session)',
        'amount': Decimal('250.00'),
    }


@login_required
@user_passes_test(can_add_manual_charges)
def cashier_search_billable_items(request):
    """
    Unified cashier search for manual services, labs, and imaging.
    """
    query = (request.GET.get('q') or '').strip()
    if len(query) < 2:
        return JsonResponse({'results': []})

    results = []

    # Manual cashier services (existing addable services catalog)
    q_lower = query.lower()
    for code, label, cash_amt, _ins_amt in ADDABLE_SERVICES:
        if q_lower not in label.lower() and q_lower not in code.lower():
            continue
        if code == 'physio':
            # Expose explicit options so cashier can choose first/subsequent directly.
            results.append({
                'item_type': 'manual',
                'item_key': 'physio_first',
                'display_name': 'Physiotherapy (First Session)',
                'service_code': 'PHYSIO',
                'unit_price': str(Decimal('250.00')),
                'source': 'service',
            })
            results.append({
                'item_type': 'manual',
                'item_key': 'physio_subsequent',
                'display_name': 'Physiotherapy (Subsequent Session)',
                'service_code': 'PHYSIO-SUB',
                'unit_price': str(Decimal('150.00')),
                'source': 'service',
            })
            continue
        results.append({
            'item_type': 'manual',
            'item_key': code,
            'display_name': label,
            'service_code': SERVICE_CODE_MAP.get(code, 'CASH-MISC'),
            'unit_price': str(cash_amt),
            'source': 'service',
        })

    # Lab test catalog
    lab_q = Q(name__icontains=query) | Q(code__icontains=query) | Q(specimen_type__icontains=query)
    lab_tests = LabTest.objects.filter(
        lab_q,
        is_active=True,
        is_deleted=False,
    ).exclude(name__iexact='')[:20]
    for lab in lab_tests:
        results.append({
            'item_type': 'lab',
            'item_key': str(lab.id),
            'display_name': f"Lab - {lab.name}",
            'service_code': f"LABTEST-{lab.id}",
            'unit_price': str(Decimal(str(lab.price or 0)).quantize(Decimal('0.01'))),
            'source': 'lab',
        })

    # Imaging catalog
    try:
        from .models_advanced import ImagingCatalog
        img_q = (
            Q(name__icontains=query)
            | Q(code__icontains=query)
            | Q(body_part__icontains=query)
            | Q(modality__icontains=query)
        )
        studies = ImagingCatalog.objects.filter(
            img_q,
            is_active=True,
            is_deleted=False,
        )[:20]
        for study in studies:
            display_name = study.name or study.description or 'Imaging Study'
            results.append({
                'item_type': 'imaging',
                'item_key': str(study.id),
                'display_name': f"Scan - {display_name}",
                'service_code': f"IMGCAT-{study.id}",
                'unit_price': str(Decimal(str(study.price or 0)).quantize(Decimal('0.01'))),
                'source': 'scan',
            })
    except Exception:
        pass

    return JsonResponse({'results': results[:40]})


@login_required
@user_passes_test(can_add_manual_charges)
def cashier_add_services_select(request, patient_id):
    """
    Add Services - cashier selects items to add (Consultation 150, Dressing 50, etc.)
    """
    from datetime import timedelta
    from .models import Invoice, InvoiceLine, ServiceCode

    patient = get_object_or_404(Patient, pk=patient_id, is_deleted=False)
    payer = patient.primary_insurance
    if not payer:
        payer, _ = Payer.objects.get_or_create(name='Cash', defaults={'payer_type': 'cash', 'is_active': True})
    is_insurance = payer and getattr(payer, 'payer_type', None) in ('insurance', 'private', 'nhis', 'corporate')

    if request.method == 'POST':
        selected = request.POST.getlist('service_codes')  # legacy checkbox support
        selected_items_json = (request.POST.get('selected_items_json') or '').strip()
        custom_name = (request.POST.get('custom_service_name') or '').strip()
        custom_amount_str = (request.POST.get('custom_service_amount') or '').strip()

        allow_amount_edit = user_can_edit_invoice_line_amounts(request.user)
        if not allow_amount_edit and (custom_name or custom_amount_str):
            messages.warning(
                request,
                'Custom item amounts can only be entered by accounting staff. Use search to add services at system prices.',
            )
            custom_name = ''
            custom_amount_str = ''

        selected_items = []
        if selected_items_json:
            try:
                parsed = json.loads(selected_items_json)
                if isinstance(parsed, list):
                    selected_items = parsed
            except Exception:
                selected_items = []

        if not selected and not selected_items and not (custom_name and custom_amount_str):
            messages.warning(request, 'Please select at least one service or enter a custom item with amount.')
            return redirect('hospital:cashier_add_services_select', patient_id=patient_id)

        # Get or create invoice (exclude cancelled - removed from bill)
        invoice = Invoice.objects.filter(
            patient=patient, is_deleted=False
        ).exclude(status__in=['paid', 'cancelled']).order_by('-created').first()
        if not invoice:
            invoice = Invoice.objects.create(
                patient=patient,
                encounter=None,
                payer=payer,
                status='issued',
                issued_at=timezone.now(),
                due_at=timezone.now() + timedelta(days=7),
            )
        if getattr(invoice, 'encounter', None) and getattr(invoice.encounter, 'billing_closed_at', None):
            messages.error(
                request,
                'Billing is closed for this encounter (discharged). No new charges can be added.',
            )
            return redirect('hospital:cashier_add_services_select', patient_id=patient_id)

        lines_created = 0
        added_items = []  # list of (label, amount) to show in success message

        # Add custom service if both name and amount provided (create or merge to avoid duplicates)
        if custom_name and custom_amount_str:
            try:
                custom_amount = Decimal(custom_amount_str)
                if custom_amount > 0:
                    service_code, _ = ServiceCode.objects.get_or_create(
                        code='CASH-MISC',
                        defaults={'description': 'Cashier-Added Service', 'category': 'Other', 'is_active': True}
                    )
                    desc = custom_name[:200]
                    _, created = create_or_merge_invoice_line(
                        invoice=invoice,
                        service_code=service_code,
                        quantity=Decimal('1'),
                        unit_price=custom_amount,
                        description=desc,
                    )
                    if created:
                        lines_created += 1
                    added_items.append((desc, custom_amount))
            except (ValueError, TypeError):
                pass

        addable_by_code = {svc[0]: svc for svc in ADDABLE_SERVICES}

        # Legacy checkbox selections
        for code in selected:
            if code not in [s[0] for s in ADDABLE_SERVICES]:
                continue
            svc = addable_by_code.get(code)
            if not svc:
                continue
            _, label, cash_amt, ins_amt = svc
            amount = ins_amt if is_insurance else cash_amt
            svc_code_str = SERVICE_CODE_MAP.get(code, 'CASH-MISC')

            if code == 'physio':
                physio_info = _resolve_physio_charge_for_patient(patient)
                amount = physio_info['amount']
                svc_code_str = physio_info['service_code']
                label = physio_info['label']

            # Avoid duplicate consultation (CON001) across invoices: if patient already has unpaid consultation, skip
            if code == 'gp' and svc_code_str == 'CON001':
                existing_con = InvoiceLine.objects.filter(
                    invoice__patient=patient,
                    invoice__is_deleted=False,
                    invoice__status__in=['issued', 'draft', 'partially_paid'],
                    invoice__balance__gt=0,
                    service_code__code='CON001',
                    is_deleted=False,
                ).exists()
                if existing_con:
                    continue  # already have unpaid consultation on another invoice
            # Avoid duplicate Antenatal (MAT-ANC) or Gynae/Special (CON002) when already on bill
            if code in ('antenatal', 'gynae_special'):
                existing_special = InvoiceLine.objects.filter(
                    invoice__patient=patient,
                    invoice__is_deleted=False,
                    invoice__status__in=['issued', 'draft', 'partially_paid'],
                    invoice__balance__gt=0,
                    service_code__code=svc_code_str,
                    is_deleted=False,
                ).exists()
                if existing_special:
                    continue

            service_code, _ = ServiceCode.objects.get_or_create(
                code=svc_code_str,
                defaults={'description': label, 'category': 'Clinical Services', 'is_active': True}
            )
            if not service_code.description or service_code.description == 'Cashier-Added Service':
                service_code.description = label
                service_code.save(update_fields=['description'])

            # Create or merge line (avoids duplicate ECG/dressing etc. on same invoice)
            _, created = create_or_merge_invoice_line(
                invoice=invoice,
                service_code=service_code,
                quantity=Decimal('1'),
                unit_price=amount,
                description=label,
            )
            if created:
                lines_created += 1
            added_items.append((label, amount))

        # New searchable selected items
        for selected_item in selected_items:
            if not isinstance(selected_item, dict):
                continue
            item_type = str(selected_item.get('item_type') or '').strip()
            item_key = str(selected_item.get('item_key') or '').strip()
            item_label = str(selected_item.get('display_name') or '').strip()[:200]
            qty_str = str(selected_item.get('quantity') or '1').strip()
            unit_price_str = str(selected_item.get('unit_price') or '0').strip()

            try:
                quantity = Decimal(qty_str)
                if quantity <= 0:
                    continue
            except Exception:
                continue

            # Never trust client-supplied unit_price for users who may not override amounts (e.g. cashier).
            try:
                client_amount = Decimal(unit_price_str)
            except Exception:
                client_amount = Decimal('0.00')

            service_code_obj = None
            line_label = item_label or 'Cashier Added Item'
            amount = client_amount if allow_amount_edit else Decimal('0.00')

            if item_type == 'manual':
                if item_key in ('physio_first', 'physio_subsequent'):
                    if item_key == 'physio_first':
                        amount = Decimal('250.00')
                        svc_code_str = 'PHYSIO'
                        line_label = 'Physiotherapy (First Session)'
                    else:
                        amount = Decimal('150.00')
                        svc_code_str = 'PHYSIO-SUB'
                        line_label = 'Physiotherapy (Subsequent Session)'
                    service_code_obj, _ = ServiceCode.objects.get_or_create(
                        code=svc_code_str,
                        defaults={'description': line_label, 'category': 'Clinical Services', 'is_active': True},
                    )
                    _, created = create_or_merge_invoice_line(
                        invoice=invoice,
                        service_code=service_code_obj,
                        quantity=quantity,
                        unit_price=amount,
                        description=line_label,
                    )
                    if created:
                        lines_created += 1
                    added_items.append((line_label, amount))
                    continue
                svc = addable_by_code.get(item_key)
                if not svc:
                    continue
                _, default_label, cash_amt, ins_amt = svc
                amount = ins_amt if is_insurance else cash_amt
                svc_code_str = SERVICE_CODE_MAP.get(item_key, 'CASH-MISC')
                line_label = default_label
                if item_key == 'physio':
                    physio_info = _resolve_physio_charge_for_patient(patient)
                    amount = physio_info['amount']
                    svc_code_str = physio_info['service_code']
                    line_label = physio_info['label']
                service_code_obj, _ = ServiceCode.objects.get_or_create(
                    code=svc_code_str,
                    defaults={'description': line_label, 'category': 'Clinical Services', 'is_active': True},
                )
            elif item_type == 'lab':
                try:
                    lab = LabTest.objects.get(pk=item_key, is_active=True, is_deleted=False)
                except LabTest.DoesNotExist:
                    continue
                amount = Decimal(str(lab.price or 0))
                line_label = f"Lab - {lab.name}"
                service_code_obj, _ = ServiceCode.objects.get_or_create(
                    code=f"LABTEST-{lab.id}",
                    defaults={'description': line_label, 'category': 'Laboratory', 'is_active': True},
                )
            elif item_type == 'imaging':
                try:
                    from .models_advanced import ImagingCatalog
                    imaging = ImagingCatalog.objects.get(pk=item_key, is_active=True, is_deleted=False)
                except Exception:
                    continue
                imaging_name = imaging.name or imaging.description or 'Imaging Study'
                amount = Decimal(str(imaging.price or 0))
                line_label = f"Scan - {imaging_name}"
                service_code_obj, _ = ServiceCode.objects.get_or_create(
                    code=f"IMGCAT-{imaging.id}",
                    defaults={'description': line_label, 'category': 'Imaging', 'is_active': True},
                )
            else:
                continue

            if amount <= 0:
                continue

            if not service_code_obj.description:
                service_code_obj.description = line_label
                service_code_obj.save(update_fields=['description'])

            _, created = create_or_merge_invoice_line(
                invoice=invoice,
                service_code=service_code_obj,
                quantity=quantity,
                unit_price=amount,
                description=line_label,
            )
            if created:
                lines_created += 1
            added_items.append((line_label, amount))

        # Safety net: merge any duplicate lines (same service_code) before recalculating totals
        from .utils_invoice_line import merge_duplicate_lines_on_invoice
        merge_duplicate_lines_on_invoice(invoice)
        invoice.update_totals()
        if lines_created > 0:
            item_list = ', '.join(f'{name} (GHS {amt:.2f})' for name, amt in added_items)
            messages.success(
                request,
                f'Added {lines_created} item(s) to bill: {item_list}. Invoice total: GHS {invoice.total_amount:.2f}'
            )
            request.session['cashier_added_items'] = [
                {'name': name, 'amount': str(amt)} for name, amt in added_items
            ]
        else:
            messages.info(request, 'Selected services already on invoice.')
        return redirect('hospital:cashier_patient_total_bill', patient_id=patient_id)

    # Build list with prices for display
    services_with_prices = []
    for code, label, cash_amt, ins_amt in ADDABLE_SERVICES:
        amt = ins_amt if is_insurance else cash_amt
        if cash_amt != ins_amt:
            price_display = f"GHS {int(cash_amt)} (Cash) / GHS {int(ins_amt)} (Insurance)"
        else:
            price_display = f"GHS {int(amt)}"
        services_with_prices.append({'code': code, 'label': label, 'price': amt, 'price_display': price_display})

    return render(request, 'hospital/cashier_add_services_select.html', {
        'patient': patient,
        'services': services_with_prices,
        'payer_type': 'insurance' if is_insurance else 'cash',
        'can_edit_invoice_amounts': user_can_edit_invoice_line_amounts(request.user),
    })


@login_required
@user_passes_test(is_cashier)
def cashier_patient_list(request):
    """
    Cashier/Accountant: Browse all patients by name/MRN/phone and create bill from here.
    Searchable, paginated list with primary action "Create bill" → add services.
    """
    from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
    from .utils_patient_validation import is_valid_patient_id

    query = request.GET.get('q', '').strip()
    page_number = request.GET.get('page', 1)
    per_page = 25

    qs = Patient.objects.filter(
        is_deleted=False
    ).exclude(
        id__isnull=True
    ).only(
        'id', 'first_name', 'last_name', 'middle_name', 'mrn', 'phone_number', 'created'
    ).order_by('last_name', 'first_name')

    if query:
        query_parts = query.strip().split()
        search_query = Q(
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(middle_name__icontains=query) |
            Q(mrn__icontains=query) |
            Q(phone_number__icontains=query)
        )
        if len(query_parts) >= 2:
            first_part = query_parts[0]
            last_parts = ' '.join(query_parts[1:])
            search_query |= Q(
                Q(first_name__icontains=first_part) & Q(last_name__icontains=last_parts)
            ) | Q(
                Q(first_name__icontains=last_parts) & Q(last_name__icontains=first_part)
            )
            for part in query_parts:
                search_query |= Q(first_name__icontains=part) | Q(last_name__icontains=part)
        qs = qs.filter(search_query).distinct()

    paginator = Paginator(qs, per_page)
    try:
        page_obj = paginator.page(page_number)
    except (PageNotAnInteger, EmptyPage):
        page_obj = paginator.page(1)

    patients = []
    for p in page_obj:
        if not is_valid_patient_id(p.id):
            continue
        patients.append({
            'id': p.id,
            'name': p.full_name,
            'mrn': p.mrn or '—',
            'phone': p.phone_number or '—',
        })

    return render(request, 'hospital/cashier_patient_list.html', {
        'patients': patients,
        'page_obj': page_obj,
        'query': query,
        'total_count': paginator.count,
    })


@login_required
@user_passes_test(can_add_manual_charges)
def cashier_create_billing(request):
    """
    Create Billing - Search for a patient, then add services to their bill.
    Landing page that redirects to Add Services for the selected patient.
    Cashier/Accountant can also create a bill for someone not yet registered (link to registration).
    """
    if request.method == 'POST':
        patient_id = request.POST.get('patient_id', '').strip()
        if patient_id:
            try:
                patient = Patient.objects.get(pk=patient_id, is_deleted=False)
                return redirect('hospital:cashier_add_services_select', patient_id=patient.pk)
            except Patient.DoesNotExist:
                messages.error(request, 'Patient not found.')
    return render(request, 'hospital/cashier_create_billing.html', {})


@login_required
@user_passes_test(is_cashier)
@never_cache
def cashier_patient_bills(request):
    """
    Patient-centric billing - Show all pending services grouped by patient
    Allows processing all services for a patient in one payment
    """
    from django.db.models import Q
    from .models_advanced import ImagingStudy
    from .models_accounting import PaymentReceipt
    from datetime import datetime, time, timedelta

    search = request.GET.get('search', '')
    today_pending = request.GET.get('today_pending') == '1'
    service_filter = request.GET.get('service_filter', '').strip().lower()  # all, lab, pharmacy, imaging, bed, consultation, invoice, pharmacy_walkin
    today_date = timezone.now().date()
    # Date filter: optional specific date to show pending services from
    filter_date = None
    filter_date_str = request.GET.get('filter_date', '').strip()
    if filter_date_str:
        try:
            filter_date = datetime.strptime(filter_date_str, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            pass
    if filter_date is None and today_pending:
        filter_date = today_date
    # Default to today when no search and no date so first load is fast
    if filter_date is None and not search:
        filter_date = today_date
    if filter_date is not None and not filter_date_str:
        filter_date_str = filter_date.isoformat()

    # When filtering by date, use DB-level date range (local timezone) for much faster queries
    date_range_start = None
    date_range_end = None
    if filter_date is not None:
        tz = timezone.get_current_timezone()
        # ZoneInfo has no localize(); use tzinfo= for timezone-aware datetime
        date_range_start = datetime.combine(filter_date, time.min, tzinfo=tz)
        date_range_end = date_range_start + timedelta(days=1)

    # Get all pending items grouped by patient
    patients_bills = {}  # {patient_id: {'patient': Patient, 'services': [], 'total': Decimal}}

    # Get all lab results (optionally filtered by date at DB level); prefetch release_record to avoid N+1
    # Include verified OR released (has release_record) so cashier sees labs as soon as they are ready for billing
    labs_query = LabResult.objects.filter(
        is_deleted=False
    ).filter(
        Q(verified_by__isnull=False) | Q(release_record__isnull=False)
    ).select_related('test', 'order__encounter__patient', 'release_record')

    if date_range_start is not None:
        # When viewing "today", include last 24h so labs from yesterday evening / timezone edge cases still show
        if filter_date == today_date:
            last_24h = timezone.now() - timedelta(hours=24)
            labs_query = labs_query.filter(created__gte=last_24h)
        else:
            labs_query = labs_query.filter(created__gte=date_range_start, created__lt=date_range_end)

    if search:
        labs_query = labs_query.filter(
            Q(order__encounter__patient__first_name__icontains=search) |
            Q(order__encounter__patient__last_name__icontains=search) |
            Q(order__encounter__patient__mrn__icontains=search)
        )
    
    for lab in labs_query:
        # Skip labs without order/encounter (data integrity)
        order = getattr(lab, 'order', None)
        if not order or not getattr(order, 'encounter', None):
            continue
        # Check if lab has been paid - improved check
        try:
            # Check if there's a release record with payment
            if hasattr(lab, 'release_record'):
                release = lab.release_record
                if release and release.payment_receipt_id is not None:
                    continue  # Already paid
        except LabResultRelease.DoesNotExist:
            pass  # No release record, need payment
        except AttributeError:
            pass  # No release record attribute, need payment
        
        patient = order.encounter.patient
        patient_id = str(patient.id)
        
        if patient_id not in patients_bills:
            patients_bills[patient_id] = {
                'patient': patient,
                'services': [],
                'total': Decimal('0.00')
            }
        
        price = lab.test.price if hasattr(lab.test, 'price') else Decimal('0.00')
        # Use invoice line amount when lab has been billed so list matches Pay page
        if order.encounter_id and lab.test:
            test_code = getattr(lab.test, 'code', None) or str(lab.test_id)
            lab_svc = f"LAB-{test_code}"
            lab_inv_line = InvoiceLine.objects.filter(
                service_code__code=lab_svc,
                invoice__patient=patient,
                invoice__encounter=order.encounter,
                invoice__is_deleted=False,
                is_deleted=False,
                description__icontains=lab.test.name
            ).first()
            if lab_inv_line and (lab_inv_line.line_total or lab_inv_line.unit_price):
                price = lab_inv_line.line_total or (lab_inv_line.unit_price * lab_inv_line.quantity)
        patients_bills[patient_id]['services'].append({
            'type': 'lab',
            'id': str(lab.id),
            'name': lab.test.name,
            'price': price,
            'date': lab.created,
            'encounter': order.encounter,
        })
        patients_bills[patient_id]['total'] += price

    # Get all prescriptions (optionally filtered by date at DB level); prefetch dispensing_record and invoice_lines for price
    rx_query = Prescription.objects.filter(
        is_deleted=False
    ).select_related('drug', 'order__encounter__patient', 'dispensing_record').prefetch_related(
        Prefetch('invoice_lines', queryset=InvoiceLine.objects.filter(is_deleted=False, waived_at__isnull=True))
    )

    if date_range_start is not None:
        if filter_date == today_date:
            last_24h = timezone.now() - timedelta(hours=24)
            rx_query = rx_query.filter(created__gte=last_24h)
        else:
            rx_query = rx_query.filter(created__gte=date_range_start, created__lt=date_range_end)

    if search:
        rx_query = rx_query.filter(
            Q(order__encounter__patient__first_name__icontains=search) |
            Q(order__encounter__patient__last_name__icontains=search) |
            Q(order__encounter__patient__mrn__icontains=search)
        )
    
    for rx in rx_query:
        if not getattr(rx, 'order', None) or not getattr(rx.order, 'encounter', None):
            continue
        # Check if prescription has been paid - improved check
        try:
            # Check if there's a dispensing record with payment
            if hasattr(rx, 'dispensing_record'):
                dispensing = rx.dispensing_record
                if dispensing and dispensing.payment_receipt_id is not None:
                    continue  # Already paid
                # Do not show if pharmacy removed or cancelled this item
                if dispensing and (
                    dispensing.dispensing_status == 'cancelled' or
                    (dispensing.quantity_ordered or 0) <= 0
                ):
                    continue
        except PharmacyDispensing.DoesNotExist:
            pass  # No dispensing record, need payment
        except AttributeError:
            pass  # No dispensing record attribute, need payment
        
        patient = rx.order.encounter.patient
        patient_id = str(patient.id)
        
        if patient_id not in patients_bills:
            patients_bills[patient_id] = {
                'patient': patient,
                'services': [],
                'total': Decimal('0.00')
            }
        
        # Only bill encounter drugs after pharmacy sends to cashier (invoice line exists)
        _rx_lines = getattr(rx, 'invoice_lines', None)
        _lines_list = _rx_lines.all() if _rx_lines else []
        inv_line = next((l for l in _lines_list if not getattr(l, 'waived_at', None)), None)
        if not inv_line:
            continue
        if inv_line.line_total or (inv_line.unit_price and inv_line.quantity):
            total = inv_line.line_total or (inv_line.unit_price * inv_line.quantity)
        else:
            continue

        patients_bills[patient_id]['services'].append({
            'type': 'pharmacy',
            'id': str(rx.id),
            'name': f"{rx.drug.name} {rx.drug.strength} x {rx.quantity}",
            'price': total,
            'date': rx.created,
            'encounter': rx.order.encounter,
        })
        patients_bills[patient_id]['total'] += total
    
    # Walk-in pharmacy sales (optionally filtered by date at DB level; exclude waived)
    walkin_query = WalkInPharmacySale.objects.filter(
        is_deleted=False,
        payment_status__in=['pending', 'partial'],
        waived_at__isnull=True
    ).select_related('patient')

    if date_range_start is not None:
        walkin_query = walkin_query.filter(sale_date=filter_date)

    if search:
        walkin_query = walkin_query.filter(
            Q(customer_name__icontains=search) |
            Q(sale_number__icontains=search) |
            Q(patient__mrn__icontains=search) |
            Q(patient__first_name__icontains=search) |
            Q(patient__last_name__icontains=search)
        )
    
    for sale in walkin_query:
        patient = WalkInPharmacyService.ensure_sale_patient(sale)
        patient_id = str(patient.id)
        
        if patient_id not in patients_bills:
            patients_bills[patient_id] = {
                'patient': patient,
                'services': [],
                'total': Decimal('0.00')
            }
        
        amount_due = sale.amount_due or (sale.total_amount - sale.amount_paid)
        if amount_due < 0:
            amount_due = Decimal('0.00')
        
        patients_bills[patient_id]['services'].append({
            'type': 'pharmacy_walkin',
            'id': str(sale.id),
            'name': f"Prescribe Sale {sale.sale_number}",
            'price': amount_due,
            'date': sale.sale_date,
            'obj': sale,
        })
        patients_bills[patient_id]['total'] += amount_due
    
    # Get all imaging studies (scan/imaging done – billable at cashier) (optionally filtered by date at DB level)
    imaging_query = ImagingStudy.objects.filter(
        is_deleted=False,
        status__in=IMAGING_BILLABLE_STATUSES
    ).select_related('order__encounter__patient', 'patient')

    if date_range_start is not None:
        if filter_date == today_date:
            last_24h = timezone.now() - timedelta(hours=24)
            imaging_query = imaging_query.filter(
                Q(performed_at__gte=last_24h) |
                Q(performed_at__isnull=True, created__gte=last_24h)
            )
        else:
            imaging_query = imaging_query.filter(
                Q(performed_at__gte=date_range_start, performed_at__lt=date_range_end) |
                Q(performed_at__isnull=True, created__gte=date_range_start, created__lt=date_range_end)
            )

    if search:
        imaging_query = imaging_query.filter(
            Q(patient__first_name__icontains=search) |
            Q(patient__last_name__icontains=search) |
            Q(patient__mrn__icontains=search)
        )
    # Batch "already paid" for imaging: one query instead of per-study (avoids N+1)
    imaging_list = list(imaging_query)
    imaging_paid_set = set()  # (patient_id, study_type) that have a payment receipt
    imaging_added_keys = set()  # (patient_id, imaging_id) already added to avoid duplicate rows
    encounter_ids_shown_as_imaging = set()  # so we can show invoice with adjusted amount (reception-added items)
    encounter_imaging_amount = {}  # encounter_id -> sum of imaging prices already shown (for adjusted invoice amount)
    if imaging_list:
        patient_ids_imaging = set()
        for im in imaging_list:
            p = im.patient if hasattr(im, 'patient') and getattr(im, 'patient_id', None) else (im.order.encounter.patient if getattr(im, 'order', None) else None)
            if p:
                patient_ids_imaging.add(p.id)
        if patient_ids_imaging:
            from django.db.models.functions import TruncDate
            receipts_qs = PaymentReceipt.objects.filter(
                is_deleted=False,
                patient_id__in=patient_ids_imaging,
                service_type='imaging_study'
            ).annotate(rd=TruncDate('receipt_date')).values('patient_id', 'rd', 'service_details')
            for r in receipts_qs:
                try:
                    sd = r.get('service_details')
                    if isinstance(sd, dict) and sd.get('study_type'):
                        imaging_paid_set.add((r['patient_id'], sd.get('study_type'), r['rd']))
                except (TypeError, AttributeError):
                    pass
    for imaging in imaging_list:
        patient_for_check = imaging.patient if hasattr(imaging, 'patient') and getattr(imaging, 'patient_id', None) else (imaging.order.encounter.patient if getattr(imaging, 'order', None) else None)
        if not patient_for_check:
            continue
        created_date = imaging.created.date() if hasattr(imaging.created, 'date') else imaging.created
        already_paid = any(
            pid == patient_for_check.id and stype == getattr(imaging, 'study_type', None) and rdate >= created_date
            for (pid, stype, rdate) in imaging_paid_set
        )
        if not already_paid:
            patient = patient_for_check
            patient_id = str(patient.id)
            # Dedupe: same study must not appear twice for same patient (e.g. query edge cases)
            img_key = (patient_id, str(imaging.id))
            if img_key in imaging_added_keys:
                continue
            imaging_added_keys.add(img_key)
            
            if patient_id not in patients_bills:
                patients_bills[patient_id] = {
                    'patient': patient,
                    'services': [],
                    'total': Decimal('0.00')
                }
            
            # Use same logic as Pay page: invoice line first, then catalog, then default
            imaging_price = Decimal('50.00')
            try:
                img_encounter = getattr(imaging, 'encounter', None) or (imaging.order.encounter if getattr(imaging, 'order', None) else None)
                if img_encounter:
                    img_inv_line = InvoiceLine.objects.filter(
                        invoice__encounter=img_encounter,
                        invoice__patient=patient,
                        is_deleted=False
                    ).filter(
                        Q(service_code__description__icontains=imaging.study_type or '') |
                        Q(description__icontains=imaging.study_type or '')
                    ).first()
                    if img_inv_line and (img_inv_line.unit_price or img_inv_line.line_total):
                        imaging_price = img_inv_line.unit_price or img_inv_line.line_total
                if imaging_price == Decimal('50.00'):
                    from .models_advanced import ImagingCatalog
                    catalog_item = ImagingCatalog.objects.filter(
                        Q(code=imaging.study_type) | Q(name__iexact=imaging.study_type),
                        modality=imaging.modality,
                        is_active=True,
                        is_deleted=False
                    ).first()
                    if catalog_item and catalog_item.price:
                        imaging_price = catalog_item.price
            except Exception:
                pass
            
            img_encounter = imaging.order.encounter if getattr(imaging, 'order', None) else getattr(imaging, 'encounter', None)
            if img_encounter:
                encounter_ids_shown_as_imaging.add(img_encounter.id)
                encounter_imaging_amount[img_encounter.id] = (
                    encounter_imaging_amount.get(img_encounter.id, Decimal('0.00')) + imaging_price
                )
            patients_bills[patient_id]['services'].append({
                'type': 'imaging',
                'id': str(imaging.id),
                'name': f"{imaging.study_type} - {imaging.body_part}",
                'price': imaging_price,
                'date': imaging.performed_at or imaging.created,
                'encounter': img_encounter,
            })
            patients_bills[patient_id]['total'] += imaging_price
    
    # Get consultations (if any pending) (optionally filtered by date at DB level)
    consultations_query = Encounter.objects.filter(
        is_deleted=False,
        status='active'
    ).select_related('patient')

    if date_range_start is not None:
        # When defaulting to "today", also include active encounters from last 24h so new visits show immediately
        if filter_date == today_date:
            last_24h = timezone.now() - timedelta(hours=24)
            consultations_query = consultations_query.filter(
                Q(started_at__gte=date_range_start, started_at__lt=date_range_end) |
                Q(started_at__gte=last_24h)
            )
        else:
            consultations_query = consultations_query.filter(
                started_at__gte=date_range_start, started_at__lt=date_range_end
            )

    if search:
        consultations_query = consultations_query.filter(
            Q(patient__first_name__icontains=search) |
            Q(patient__last_name__icontains=search) |
            Q(patient__mrn__icontains=search)
        )
    
    # Get active admissions (bed charges) (optionally filtered by date at DB level)
    admissions_query = Admission.objects.filter(
        is_deleted=False,
        status='admitted'
    ).select_related('encounter__patient', 'ward', 'bed')

    if date_range_start is not None:
        admissions_query = admissions_query.filter(admit_date=filter_date)

    if search:
        admissions_query = admissions_query.filter(
            Q(encounter__patient__first_name__icontains=search) |
            Q(encounter__patient__last_name__icontains=search) |
            Q(encounter__patient__mrn__icontains=search)
        )
    
    for admission in admissions_query:
        patient = admission.encounter.patient
        patient_id = str(patient.id)
        
        if patient_id not in patients_bills:
            patients_bills[patient_id] = {
                'patient': patient,
                'services': [],
                'total': Decimal('0.00')
            }
        
        # Calculate current bed charges
        try:
            from .services.bed_billing_service import bed_billing_service
            charges = bed_billing_service.get_bed_charges_summary(admission)
            bed_charge = charges['current_charges']
            days = charges['days_admitted']
        except:
            bed_charge = Decimal('120.00')  # Default 1 day
            days = 1
        
        patients_bills[patient_id]['services'].append({
            'type': 'bed',
            'id': str(admission.id),
            'name': f"Bed Charges - {admission.ward.name} - Bed {admission.bed.bed_number} ({days} night{'s' if days != 1 else ''})",
            'price': bed_charge,
            'date': admission.admit_date,
            'encounter': admission.encounter,
        })
        patients_bills[patient_id]['total'] += bed_charge
    
    # Precompute which encounters are paid / will be shown as consultation (avoid duplicate consultation + invoice row)
    consultations_list = list(consultations_query)
    consultation_paid_encounter_ids = set(
        PaymentReceipt.objects.filter(
            is_deleted=False,
            service_type='consultation',
            invoice__encounter_id__isnull=False
        ).values_list('invoice__encounter_id', flat=True).distinct()
    )
    from django.db.models.functions import TruncDate
    old_consultation_paid_set = set(
        PaymentReceipt.objects.filter(
            is_deleted=False,
            service_type='consultation',
            invoice__encounter_id__isnull=True
        ).annotate(rd=TruncDate('receipt_date')).values_list('patient_id', 'rd')
    )
    encounter_ids_shown_as_consultation = set()
    encounter_consultation_amount = {}  # encounter_id -> consultation price shown (for adjusted invoice amount)
    for e in consultations_list:
        paid = e.id in consultation_paid_encounter_ids
        if not paid and old_consultation_paid_set:
            sd = e.started_at.date() if hasattr(e.started_at, 'date') else e.started_at
            paid = any(pid == e.patient_id and rdate >= sd for (pid, rdate) in old_consultation_paid_set)
        if not paid:
            encounter_ids_shown_as_consultation.add(e.id)
            # Populate now so unpaid_inv loop can subtract it and show reception-added items
            cp = get_consultation_price_for_encounter(e)
            if cp == Decimal('30.00'):
                cp = Decimal('150.00')
            encounter_consultation_amount[e.id] = cp

    # Get patients with unpaid invoices (consumables, registration fee, manual charges, etc.)
    # Include invoices with balance>0 OR with billable lines (consumables) - refresh totals to fix stale balance
    # Include overdue so cashier can collect; use modified for date so recently-added consumables show in today filter
    # Skip invoices that are the encounter's bill (we show those as "Consultation" to avoid duplicate row)
    from .models import Invoice
    has_billable_lines = InvoiceLine.objects.filter(
        invoice_id=OuterRef('pk'),
        is_deleted=False,
        waived_at__isnull=True
    ).exclude(line_total__lte=0)
    unpaid_inv = Invoice.objects.filter(
        is_deleted=False,
        status__in=('draft', 'issued', 'partially_paid', 'overdue')
    ).filter(
        Q(balance__gt=0) | Q(Exists(has_billable_lines))
    ).distinct().select_related('patient').prefetch_related('lines')
    if date_range_start is not None:
        # When "today", include last 24h so reception-added items show immediately
        if filter_date == today_date:
            last_24h = timezone.now() - timedelta(hours=24)
            unpaid_inv = unpaid_inv.filter(
                Q(modified__gte=last_24h) | Q(issued_at__gte=last_24h)
            )
        else:
            unpaid_inv = unpaid_inv.filter(
                Q(modified__gte=date_range_start, modified__lt=date_range_end) |
                Q(issued_at__gte=date_range_start, issued_at__lt=date_range_end)
            )
    if search:
        unpaid_inv = unpaid_inv.filter(
            Q(patient__first_name__icontains=search) |
            Q(patient__last_name__icontains=search) |
            Q(patient__mrn__icontains=search)
        )
    for inv in unpaid_inv:
        if getattr(inv, 'balance', None) is None or inv.balance <= 0:
            inv.update_totals()
        balance = inv.balance or inv.total_amount or Decimal('0.00')
        if balance <= 0:
            continue
        enc_id = getattr(inv, 'encounter_id', None)
        # Show invoice with adjusted amount when we already show consultation/imaging for this encounter
        # so reception-added items (registration, manual charge, etc.) are visible at cashier
        amount_already_shown = Decimal('0.00')
        if enc_id in encounter_ids_shown_as_consultation:
            amount_already_shown += encounter_consultation_amount.get(enc_id, Decimal('0.00'))
        if enc_id in encounter_ids_shown_as_imaging:
            amount_already_shown += encounter_imaging_amount.get(enc_id, Decimal('0.00'))
        amount_to_show = balance - amount_already_shown
        if amount_to_show <= 0:
            continue  # nothing extra (reception-added) to show
        patient = inv.patient
        patient_id = str(patient.id)
        if patient_id not in patients_bills:
            patients_bills[patient_id] = {
                'patient': patient,
                'services': [],
                'total': Decimal('0.00')
            }
        patients_bills[patient_id]['services'].append({
            'type': 'invoice',
            'id': str(inv.id),
            'name': f"Invoice {inv.invoice_number}" + (" (other charges)" if amount_already_shown else ""),
            'price': amount_to_show,
            'date': getattr(inv, 'modified', None) or inv.issued_at,
            'invoice': inv,
        })
        patients_bills[patient_id]['total'] += amount_to_show

    # Registration fee is NOT automatic. Cashiers add it via "Add Services" when applicable.

    # Add consultation rows (paid sets already computed above)
    for encounter in consultations_list:
        already_paid = encounter.id in consultation_paid_encounter_ids
        if not already_paid and old_consultation_paid_set:
            started_date = encounter.started_at.date() if hasattr(encounter.started_at, 'date') else encounter.started_at
            already_paid = any(
                pid == encounter.patient_id and rdate >= started_date
                for (pid, rdate) in old_consultation_paid_set
            )
        if not already_paid:
            patient = encounter.patient
            patient_id = str(patient.id)
            
            if patient_id not in patients_bills:
                patients_bills[patient_id] = {
                    'patient': patient,
                    'services': [],
                    'total': Decimal('0.00')
                }
            
            consultation_price = get_consultation_price_for_encounter(encounter)  # 150 general / 300 specialist
            if consultation_price == Decimal('30.00'):
                consultation_price = Decimal('150.00')
            encounter_consultation_amount[encounter.id] = consultation_price
            # Label so specialist appears clearly under same structure as consultation, lab, scan
            enc_type_lower = (encounter.encounter_type or '').lower()
            if enc_type_lower == 'specialist':
                consultation_label = 'Specialist Consultation'
            else:
                consultation_label = f"{encounter.get_encounter_type_display()} Consultation"
            patients_bills[patient_id]['services'].append({
                'type': 'consultation',
                'id': str(encounter.id),
                'name': consultation_label,
                'price': consultation_price,
                'date': encounter.started_at,
                'encounter': encounter,
            })
            patients_bills[patient_id]['total'] += consultation_price

    # Include patients who have a deposit balance but no current services (so deposit shows when searching)
    from .models_patient_deposits import PatientDeposit
    from .models import Patient
    if search:
        deposit_only_patients = (
            PatientDeposit.objects.filter(
                status='active',
                is_deleted=False,
                available_balance__gt=0
            )
            .values_list('patient_id', flat=True)
            .distinct()
        )
        for pid in deposit_only_patients:
            if str(pid) in patients_bills:
                continue
            try:
                patient = Patient.objects.get(pk=pid, is_deleted=False)
            except Patient.DoesNotExist:
                continue
            s = search.strip().lower()
            fn = (getattr(patient, 'first_name', None) or '').lower()
            ln = (getattr(patient, 'last_name', None) or '').lower()
            mrn = (getattr(patient, 'mrn', None) or '').lower()
            full = f'{fn} {ln}'.strip()
            if s not in full and s not in fn and s not in ln and s not in mrn:
                continue
            patients_bills[str(patient.id)] = {
                'patient': patient,
                'services': [],
                'total': Decimal('0.00')
            }
    
    # Convert to list and sort by total amount (highest first) for pagination
    patients_list = list(patients_bills.values())

    # Add deposit balance and amount due after deposit for each patient (single batch query)
    if patients_list:
        patient_ids = [p['patient'].id for p in patients_list]
        deposit_totals = (
            PatientDeposit.objects.filter(
                patient_id__in=patient_ids,
                status='active',
                is_deleted=False,
                available_balance__gt=0
            )
            .values('patient_id')
            .annotate(total=Sum('available_balance'))
        )
        deposit_by_patient = {d['patient_id']: d['total'] for d in deposit_totals}
        # Deposit already applied to this patient's invoices (include payment_method='deposit' and "Apply deposit to bill" receipts)
        deposit_applied_totals = (
            PaymentReceipt.objects.filter(
                invoice__patient_id__in=patient_ids,
                is_deleted=False,
            )
            .filter(
                Q(payment_method='deposit') |
                Q(service_details__deposit_applied=True) |
                Q(notes__icontains='Deposit applied to bill')
            )
            .values('invoice__patient_id')
            .annotate(total=Sum('amount_paid'))
        )
        deposit_applied_by_patient = {d['invoice__patient_id']: d['total'] for d in deposit_applied_totals}
        # Total paid to date per patient (so outstanding = initial - total_paid - deposit, same as Total Bill page)
        total_paid_totals = (
            PaymentReceipt.objects.filter(patient_id__in=patient_ids, is_deleted=False)
            .values('patient_id')
            .annotate(total=Sum('amount_paid'))
        )
        total_paid_by_patient = {d['patient_id']: d['total'] for d in total_paid_totals}
        from .services.patient_outstanding_service import get_patient_outstanding_bulk
        outstanding_by_pid = get_patient_outstanding_bulk(patient_ids)
        for p in patients_list:
            pid = p['patient'].id
            deposit_sum = deposit_by_patient.get(pid) or Decimal('0.00')
            deposit_applied = deposit_applied_by_patient.get(pid) or Decimal('0.00')
            total_paid_val = total_paid_by_patient.get(pid) or Decimal('0.00')
            p['deposit_balance'] = deposit_sum
            p['deposit_applied_to_bill'] = deposit_applied
            p['total_paid'] = total_paid_val
            p['initial_total'] = p['total'] + deposit_applied
            o = outstanding_by_pid.get(pid) or {}
            p['total_outstanding'] = o.get('total_outstanding', p['total'])
            p['amount_due_after_deposit'] = o.get('amount_due_after_deposit', Decimal('0.00'))
    else:
        from .services.patient_outstanding_service import get_patient_outstanding_bulk
        patient_ids_else = [p['patient'].id for p in patients_list]
        outstanding_by_pid = get_patient_outstanding_bulk(patient_ids_else)
        for p in patients_list:
            p['deposit_balance'] = Decimal('0.00')
            p['deposit_applied_to_bill'] = Decimal('0.00')
            p['total_paid'] = Decimal('0.00')
            p['initial_total'] = p['total']
            o = outstanding_by_pid.get(p['patient'].id) or {}
            p['total_outstanding'] = o.get('total_outstanding', p['total'])
            p['amount_due_after_deposit'] = o.get('amount_due_after_deposit', p['total'])

    # Filter by date if requested (in-memory pass for timezone consistency; when date_range_start set we already filtered at DB)
    if filter_date is not None:
        def _svc_date(svc):
            d = svc.get('date')
            if d is None:
                return None
            if hasattr(d, 'date'):
                if hasattr(d, 'tzinfo') and getattr(d, 'tzinfo', None) is not None:
                    return timezone.localtime(d).date()
                return d.date()
            return d
        # When "today", keep services from today or yesterday so last-24h items (labs, imaging, etc.) still show
        allowed_dates = (filter_date,) if filter_date != today_date else (today_date, today_date - timedelta(days=1))
        filtered = []
        filter_patient_ids = [p['patient'].id for p in patients_list]
        from .services.patient_outstanding_service import get_patient_outstanding_bulk
        outstanding_map = get_patient_outstanding_bulk(filter_patient_ids)
        for p in patients_list:
            date_svcs = [s for s in p['services'] if _svc_date(s) in allowed_dates]
            if date_svcs:
                p_total = sum(s['price'] for s in date_svcs)
                deposit_bal = p.get('deposit_balance', Decimal('0.00'))
                dep_applied = p.get('deposit_applied_to_bill', Decimal('0.00'))
                total_paid_val = p.get('total_paid', Decimal('0.00'))
                initial = p_total + dep_applied
                o = outstanding_map.get(p['patient'].id) or {}
                filtered.append({
                    'patient': p['patient'],
                    'services': date_svcs,
                    'total': p_total,
                    'deposit_balance': deposit_bal,
                    'deposit_applied_to_bill': dep_applied,
                    'total_paid': total_paid_val,
                    'initial_total': initial,
                    'total_outstanding': o.get('total_outstanding', p_total),
                    'amount_due_after_deposit': o.get('amount_due_after_deposit', Decimal('0.00')),
                })
        patients_list = filtered

    # Filter by service type if requested (only accountant / cashier filter)
    if service_filter and service_filter != 'all':
        filtered = []
        filter_patient_ids = [p['patient'].id for p in patients_list]
        from .services.patient_outstanding_service import get_patient_outstanding_bulk
        outstanding_map = get_patient_outstanding_bulk(filter_patient_ids)
        for p in patients_list:
            matching = [s for s in p['services'] if s.get('type') == service_filter]
            if matching:
                p_total = sum(s['price'] for s in matching)
                deposit_bal = p.get('deposit_balance', Decimal('0.00'))
                dep_applied = p.get('deposit_applied_to_bill', Decimal('0.00'))
                total_paid_val = p.get('total_paid', Decimal('0.00'))
                initial = p_total + dep_applied
                o = outstanding_map.get(p['patient'].id) or {}
                filtered.append({
                    'patient': p['patient'],
                    'services': matching,
                    'total': p_total,
                    'deposit_balance': deposit_bal,
                    'deposit_applied_to_bill': dep_applied,
                    'total_paid': total_paid_val,
                    'initial_total': initial,
                    'amount_due_after_deposit': o.get('amount_due_after_deposit', Decimal('0.00')),
                })
        patients_list = filtered

    patients_list.sort(key=lambda x: x['total'], reverse=True)

    # Pagination: only run heavy _get_patient_pending_services_for_payment for the current page
    per_page = 30
    try:
        page_num = max(1, int(request.GET.get('page', 1)))
    except (ValueError, TypeError):
        page_num = 1
    total_patients = len(patients_list)
    start_idx = (page_num - 1) * per_page
    end_idx = start_idx + per_page
    page_patients = patients_list[start_idx:end_idx]

    def _service_date(s):
        obj = s.get('obj')
        if not obj:
            return None
        return (getattr(obj, 'created', None) or getattr(obj, 'sale_date', None) or getattr(obj, 'admit_date', None)
                or getattr(obj, 'issued_at', None) or getattr(obj, 'performed_at', None))
    # Single source of truth: same outstanding as /patients/<id>/outstanding/ and Total Bill
    from .services.patient_outstanding_service import get_patient_outstanding_bulk
    page_patient_ids = [p['patient'].id for p in page_patients]
    outstanding_by_patient = get_patient_outstanding_bulk(page_patient_ids)
    for p in page_patients:
        try:
            services_list, total = _get_patient_pending_services_for_payment(p['patient'])
            p['services'] = [
                {'type': s.get('type'), 'name': s.get('name'), 'price': s.get('price'), 'date': _service_date(s)}
                for s in services_list
            ]
            p['total'] = total
            dep_applied = p.get('deposit_applied_to_bill', Decimal('0.00'))
            p['initial_total'] = total + dep_applied
            o = outstanding_by_patient.get(p['patient'].id) or {}
            p['amount_due_after_deposit'] = o.get('amount_due_after_deposit', Decimal('0.00'))
        except Exception as e:
            logger.warning('cashier_patient_bills: could not get pending services for patient %s: %s', p['patient'].id, e)

    total_amount = sum(p['total'] for p in page_patients)
    total_services = sum(len(p['services']) for p in page_patients)
    num_pages = (total_patients + per_page - 1) // per_page if total_patients else 1
    has_prev = page_num > 1
    has_next = page_num < num_pages
    prev_page = page_num - 1 if has_prev else 1
    next_page = page_num + 1 if has_next else num_pages

    context = {
        'title': 'Patient Bills - Combined Billing' + (' (Today\'s Pending)' if today_pending else '') + (f' ({filter_date})' if filter_date and not today_pending else ''),
        'patients_bills': page_patients,
        'search': search,
        'today_pending': today_pending,
        'service_filter': service_filter,
        'filter_date': filter_date,
        'filter_date_str': filter_date_str,
        'total_patients': total_patients,
        'total_amount': total_amount,
        'total_services': total_services,
        'page': page_num,
        'num_pages': num_pages,
        'has_prev': has_prev,
        'has_next': has_next,
        'prev_page': prev_page,
        'next_page': next_page,
        'per_page': per_page,
    }
    return render(request, 'hospital/cashier_patient_bills.html', context)


@login_required
@user_passes_test(is_cashier)
def cashier_all_pending_bills(request):
    """
    Show ALL pending bills - comprehensive view
    Search by patient name, MRN, or service.
    Default to today's pending when no search so first load is fast.
    """
    search = request.GET.get('search', '')
    service_filter = request.GET.get('service_type', 'all')
    filter_today_pending = request.GET.get('today_pending') == '1'
    today = timezone.now().date()
    # Default to today's pending when no search so queries are date-bounded
    if not search and not filter_today_pending:
        filter_today_pending = True
    
    pending_items = []
    _date_range_start = None
    _date_range_end = None
    _use_last_24h = False
    if filter_today_pending:
        from datetime import datetime, time, timedelta
        tz = timezone.get_current_timezone()
        _date_range_start = datetime.combine(today, time.min, tzinfo=tz)
        _date_range_end = _date_range_start + timedelta(days=1)
        _use_last_24h = True  # When "today" pending, include last 24h so more items show
    
    # Get lab results; date filter at DB when today pending, prefetch release_record
    # Include verified OR released so cashier sees labs ready for billing (same as cashier_patient_bills)
    labs_query = LabResult.objects.filter(
        is_deleted=False
    ).filter(
        Q(verified_by__isnull=False) | Q(release_record__isnull=False)
    ).select_related('test', 'order__encounter__patient', 'release_record')
    if _date_range_start is not None:
        if _use_last_24h:
            last_24h = timezone.now() - timedelta(hours=24)
            labs_query = labs_query.filter(created__gte=last_24h)
        else:
            labs_query = labs_query.filter(created__gte=_date_range_start, created__lt=_date_range_end)
    
    if search:
        labs_query = labs_query.filter(
            Q(order__encounter__patient__first_name__icontains=search) |
            Q(order__encounter__patient__last_name__icontains=search) |
            Q(order__encounter__patient__mrn__icontains=search) |
            Q(test__name__icontains=search)
        )
    
    for lab in labs_query:
        order = getattr(lab, 'order', None)
        if not order or not getattr(order, 'encounter', None):
            continue
        try:
            if hasattr(lab, 'release_record') and lab.release_record.payment_receipt:
                continue  # Already paid
        except Exception:
            pass
        
        # Unpaid - add to list
        if service_filter == 'all' or service_filter == 'lab':
            pending_items.append({
                'type': 'lab',
                'id': str(lab.id),
                'patient': order.encounter.patient,
                'patient_name': order.encounter.patient.full_name,
                'patient_mrn': order.encounter.patient.mrn,
                'service': lab.test.name,
                'price': lab.test.price,
                'date': lab.created,
                'encounter': order.encounter,
            })
    
    # Get prescriptions; date filter at DB when today pending, prefetch dispensing_record and invoice_lines
    rx_query = Prescription.objects.filter(
        is_deleted=False
    ).select_related('drug', 'order__encounter__patient', 'dispensing_record').prefetch_related(
        Prefetch('invoice_lines', queryset=InvoiceLine.objects.filter(is_deleted=False))
    )
    if _date_range_start is not None:
        if _use_last_24h:
            last_24h = timezone.now() - timedelta(hours=24)
            rx_query = rx_query.filter(
                Q(created__gte=last_24h)
                | Q(
                    invoice_lines__is_deleted=False,
                    invoice_lines__waived_at__isnull=True,
                    invoice_lines__modified__gte=last_24h,
                )
                | Q(
                    invoice_lines__is_deleted=False,
                    invoice_lines__waived_at__isnull=True,
                    invoice_lines__created__gte=last_24h,
                )
                | Q(
                    dispensing_record__is_deleted=False,
                    dispensing_record__modified__gte=last_24h,
                )
            ).distinct()
        else:
            rx_query = rx_query.filter(
                Q(created__gte=_date_range_start, created__lt=_date_range_end)
                | Q(
                    invoice_lines__is_deleted=False,
                    invoice_lines__waived_at__isnull=True,
                    invoice_lines__modified__gte=_date_range_start,
                    invoice_lines__modified__lt=_date_range_end,
                )
                | Q(
                    invoice_lines__is_deleted=False,
                    invoice_lines__waived_at__isnull=True,
                    invoice_lines__created__gte=_date_range_start,
                    invoice_lines__created__lt=_date_range_end,
                )
                | Q(
                    dispensing_record__is_deleted=False,
                    dispensing_record__modified__gte=_date_range_start,
                    dispensing_record__modified__lt=_date_range_end,
                )
            ).distinct()
    if search:
        rx_query = rx_query.filter(
            Q(order__encounter__patient__first_name__icontains=search) |
            Q(order__encounter__patient__last_name__icontains=search) |
            Q(order__encounter__patient__mrn__icontains=search) |
            Q(drug__name__icontains=search)
        )
    
    # Collect unpaid pharmacy prescriptions and group by encounter (one row per patient per visit)
    pharmacy_rx_list = []
    for rx in rx_query:
        if not getattr(rx, 'order', None) or not getattr(rx.order, 'encounter', None):
            continue
        try:
            if hasattr(rx, 'dispensing_record') and rx.dispensing_record.payment_receipt_id:
                continue  # Already paid
            if hasattr(rx, 'dispensing_record') and rx.dispensing_record:
                d = rx.dispensing_record
                if d.dispensing_status == 'cancelled' or (d.quantity_ordered or 0) <= 0:
                    continue
                if (
                    d.dispensing_status == 'ready_to_dispense'
                    and getattr(d, 'payment_verified_at', None)
                    and not d.payment_receipt_id
                ):
                    continue
        except Exception:
            pass
        try:
            _lines = getattr(rx, 'invoice_lines', None)
            invoice_line = next(
                (l for l in (_lines.all() if _lines is not None else []) if not getattr(l, 'waived_at', None)),
                None
            )
            if not invoice_line or getattr(invoice_line, 'waived_at', None):
                continue
        except Exception:
            continue
        enc = rx.order.encounter
        payer = getattr(enc.patient, 'primary_insurance', None)
        drug_price = get_drug_price_for_prescription(rx.drug, payer=payer)
        total = drug_price * rx.quantity
        pharmacy_rx_list.append({
            'rx': rx,
            'enc': enc,
            'price': total,
            'date': rx.created,
        })
    # Group by encounter – one row per patient (one invoice per encounter)
    if service_filter == 'all' or service_filter == 'pharmacy':
        seen_enc = set()
        for item in pharmacy_rx_list:
            enc = item['enc']
            if enc.id in seen_enc:
                continue
            seen_enc.add(enc.id)
            encounter_items = [i for i in pharmacy_rx_list if i['enc'].id == enc.id]
            total_enc = sum(i['price'] for i in encounter_items)
            service_label = ", ".join(
                f"{i['rx'].drug.name} x{i['rx'].quantity}" for i in encounter_items[:3]
            )
            if len(encounter_items) > 3:
                service_label += f" (+{len(encounter_items) - 3} more)"
            pending_items.append({
                'type': 'pharmacy_encounter',
                'id': str(enc.id),
                'encounter_id': enc.id,
                'patient': enc.patient,
                'patient_name': enc.patient.full_name,
                'patient_mrn': enc.patient.mrn,
                'service': service_label,
                'price': total_enc,
                'date': encounter_items[0]['date'],
                'encounter': enc,
            })
    
    # Walk-in pharmacy sales (exclude waived)
    walkin_sales = WalkInPharmacySale.objects.filter(
        is_deleted=False,
        payment_status__in=['pending', 'partial'],
        waived_at__isnull=True
    ).select_related('patient')
    
    if search:
        walkin_sales = walkin_sales.filter(
            Q(customer_name__icontains=search) |
            Q(sale_number__icontains=search) |
            Q(patient__mrn__icontains=search) |
            Q(patient__first_name__icontains=search) |
            Q(patient__last_name__icontains=search)
        )
    
    if service_filter in ['all', 'pharmacy', 'pharmacy_walkin']:
        for sale in walkin_sales:
            patient = WalkInPharmacyService.ensure_sale_patient(sale)
            amount_due = sale.amount_due or (sale.total_amount - sale.amount_paid)
            if amount_due < 0:
                amount_due = Decimal('0.00')
            
            pending_items.append({
                'type': 'pharmacy_walkin',
                'id': str(sale.id),
                'patient': patient,
                'patient_name': patient.full_name,
                'patient_mrn': patient.mrn,
                'service': f"Prescribe Sale {sale.sale_number}",
                'price': amount_due,
                'date': sale.sale_date,
                'sale': sale,
            })
    
    # Get imaging studies; date filter at DB when today pending
    from .models_advanced import ImagingStudy
    imaging_query = ImagingStudy.objects.filter(
        is_deleted=False,
        status__in=IMAGING_BILLABLE_STATUSES
    ).select_related('order__encounter__patient', 'patient')
    if _date_range_start is not None:
        if _use_last_24h:
            last_24h = timezone.now() - timedelta(hours=24)
            imaging_query = imaging_query.filter(
                Q(performed_at__gte=last_24h) |
                Q(performed_at__isnull=True, created__gte=last_24h)
            )
        else:
            imaging_query = imaging_query.filter(
                Q(performed_at__gte=_date_range_start, performed_at__lt=_date_range_end) |
                Q(performed_at__isnull=True, created__gte=_date_range_start, created__lt=_date_range_end)
            )
    if search:
        imaging_query = imaging_query.filter(
            Q(patient__first_name__icontains=search) |
            Q(patient__last_name__icontains=search) |
            Q(patient__mrn__icontains=search) |
            Q(study_type__icontains=search) |
            Q(body_part__icontains=search)
        )
    
    # Batch "already paid" check: one query for imaging receipts for these patients, then set in Python
    imaging_list = list(imaging_query)
    imaging_paid_ids = set()  # imaging study ids that have a payment receipt
    if imaging_list:
        patient_ids_imaging = set()
        for im in imaging_list:
            p = im.patient if (getattr(im, 'patient_id', None)) else (im.order.encounter.patient if getattr(im, 'order', None) else None)
            if p:
                patient_ids_imaging.add(p.id)
        if patient_ids_imaging:
            from django.db.models.functions import TruncDate
            for r in PaymentReceipt.objects.filter(
                is_deleted=False,
                patient_id__in=patient_ids_imaging,
                service_type='imaging_study'
            ).annotate(rd=TruncDate('receipt_date')).values('patient_id', 'rd', 'service_details'):
                try:
                    sd = r.get('service_details')
                    if isinstance(sd, dict):
                        study_id = sd.get('study_id')
                        if study_id:
                            imaging_paid_ids.add(int(study_id) if isinstance(study_id, str) and study_id.isdigit() else study_id)
                except (TypeError, AttributeError, ValueError):
                    pass
    
    for imaging in imaging_list:
        if imaging.id in imaging_paid_ids:
            continue
        patient_for_list = imaging.patient if (getattr(imaging, 'patient_id', None)) else (imaging.order.encounter.patient if getattr(imaging, 'order', None) else None)
        if not patient_for_list:
            continue
        if service_filter == 'all' or service_filter == 'imaging':
            imaging_price = Decimal('50.00')  # Default - can be made configurable
            pending_items.append({
                'type': 'imaging',
                'id': str(imaging.id),
                'patient': patient_for_list,
                'patient_name': patient_for_list.full_name,
                'patient_mrn': patient_for_list.mrn,
                'service': f"{imaging.study_type} - {imaging.body_part}",
                'price': imaging_price,
                'date': imaging.performed_at or imaging.created,
                'encounter': imaging.order.encounter if hasattr(imaging, 'order') else None,
            })
    
    # Get unpaid invoices (consumables, manual charges, consultation, etc.)
    # Include invoices with balance>0 OR with billable lines - refresh totals to fix stale balance
    if service_filter == 'all' or service_filter == 'invoice':
        has_billable_lines_all = InvoiceLine.objects.filter(
            invoice_id=OuterRef('pk'),
            is_deleted=False,
            waived_at__isnull=True
        ).exclude(line_total__lte=0)
        unpaid_invoices = Invoice.objects.filter(
            is_deleted=False,
            status__in=('issued', 'draft', 'partially_paid')
        ).filter(
            Q(balance__gt=0) | Q(Exists(has_billable_lines_all))
        ).distinct().select_related('patient', 'payer').prefetch_related('lines').order_by('-created')
        if _date_range_start is not None:
            unpaid_invoices = unpaid_invoices.filter(
                Q(modified__gte=_date_range_start, modified__lt=_date_range_end) |
                Q(issued_at__gte=_date_range_start, issued_at__lt=_date_range_end)
            )
        if search:
            unpaid_invoices = unpaid_invoices.filter(
                Q(patient__first_name__icontains=search) |
                Q(patient__last_name__icontains=search) |
                Q(patient__mrn__icontains=search) |
                Q(invoice_number__icontains=search)
            )
        
        for inv in unpaid_invoices:
            # Avoid update_totals() for every invoice; use stored balance, refresh only when likely stale
            if getattr(inv, 'balance', None) is None or inv.balance <= 0:
                inv.update_totals()
            if (inv.balance or 0) <= 0:
                continue
            patient = inv.patient
            pending_items.append({
                'type': 'invoice',
                'id': str(inv.id),
                'patient': patient,
                'patient_name': patient.full_name,
                'patient_mrn': patient.mrn,
                'service': f"Invoice {inv.invoice_number} ({inv.lines.filter(is_deleted=False).count()} items)",
                'price': inv.balance,
                'date': inv.issued_at or inv.created,
                'invoice': inv,
            })
    
    # Get active admissions (bed charges); limit to recent when today pending to avoid N+1 on large sets
    if service_filter == 'all' or service_filter == 'bed':
        from datetime import timedelta
        admissions_query = Admission.objects.filter(
            is_deleted=False,
            status='admitted'
        ).select_related('encounter__patient', 'ward', 'bed')
        if _date_range_start is not None:
            admissions_query = admissions_query.filter(admit_date=_date_range_start.date())
        else:
            ninety_days_ago = today - timedelta(days=90)
            admissions_query = admissions_query.filter(admit_date__gte=ninety_days_ago)[:500]
        if search:
            admissions_query = admissions_query.filter(
                Q(encounter__patient__first_name__icontains=search) |
                Q(encounter__patient__last_name__icontains=search) |
                Q(encounter__patient__mrn__icontains=search)
            )
        
        for admission in admissions_query:
            try:
                from .services.bed_billing_service import bed_billing_service
                charges = bed_billing_service.get_bed_charges_summary(admission)
                bed_charge = charges['current_charges']
                days = charges['days_admitted']
                
                patient = admission.encounter.patient
                
                pending_items.append({
                    'type': 'bed',
                    'id': str(admission.id),
                    'patient': patient,
                    'patient_name': patient.full_name,
                    'patient_mrn': patient.mrn,
                    'service': f"Bed Charges - {admission.ward.name} - Bed {admission.bed.bed_number} ({days} night{'s' if days != 1 else ''})",
                    'price': bed_charge,
                    'date': admission.admit_date,
                    'encounter': admission.encounter,
                })
            except Exception as e:
                logger.error(f"Error adding bed charges to pending: {str(e)}")

    # Unpaid consultation encounters (Outpatient + Special Consultation) so they appear in All Pending with patient name
    if service_filter == 'all' or service_filter == 'consultation':
        consultation_paid_ids = set(
            PaymentReceipt.objects.filter(
                is_deleted=False,
                service_type='consultation',
                invoice__encounter_id__isnull=False
            ).values_list('invoice__encounter_id', flat=True).distinct()
        )
        from django.db.models.functions import TruncDate
        old_consultation_paid = set(
            PaymentReceipt.objects.filter(
                is_deleted=False,
                service_type='consultation',
                invoice__encounter_id__isnull=True
            ).annotate(rd=TruncDate('receipt_date')).values_list('patient_id', 'rd')
        )
        consultations_qs = Encounter.objects.filter(
            is_deleted=False,
            status='active'
        ).select_related('patient').order_by('-started_at')
        if _date_range_start is not None:
            if _use_last_24h:
                last_24h = timezone.now() - timedelta(hours=24)
                d0, d1 = local_datetime_bounds_for_date(today)
                consultations_qs = consultations_qs.filter(
                    Q(started_at__gte=d0, started_at__lt=d1) | Q(started_at__gte=last_24h)
                )
            else:
                consultations_qs = consultations_qs.filter(
                    started_at__gte=_date_range_start,
                    started_at__lt=_date_range_end
                )
        if search:
            consultations_qs = consultations_qs.filter(
                Q(patient__first_name__icontains=search) |
                Q(patient__last_name__icontains=search) |
                Q(patient__mrn__icontains=search)
            )
        for enc in consultations_qs[:500]:
            if enc.id in consultation_paid_ids:
                continue
            _sa = enc.started_at
            if _sa and getattr(_sa, 'tzinfo', None):
                started_date = timezone.localtime(_sa).date()
            else:
                started_date = _sa.date() if hasattr(_sa, 'date') else _sa
            if old_consultation_paid and any(pid == enc.patient_id and rdate >= started_date for (pid, rdate) in old_consultation_paid):
                continue
            price = get_consultation_price_for_encounter(enc)
            if price == Decimal('30.00'):
                price = Decimal('150.00')
            enc_type_lower = (enc.encounter_type or '').lower()
            service_label = 'Specialist Consultation' if enc_type_lower == 'specialist' else f"{enc.get_encounter_type_display()} Consultation"
            pending_items.append({
                'type': 'consultation',
                'id': str(enc.id),
                'patient': enc.patient,
                'patient_name': enc.patient.full_name,
                'patient_mrn': enc.patient.mrn,
                'service': service_label,
                'price': price,
                'date': enc.started_at,
                'encounter': enc,
            })
    
    # Filter to today's pending only when requested
    if filter_today_pending:
        def _item_date(d):
            if d is None:
                return None
            if hasattr(d, 'date') and callable(getattr(d, 'date')):
                dt = d
                if getattr(dt, 'tzinfo', None) is not None:
                    return timezone.localtime(dt).date()
                return dt.date()
            return d
        pending_items = [i for i in pending_items if _item_date(i.get('date')) == today]
    
    # Sort by date
    pending_items.sort(key=lambda x: x['date'], reverse=True)
    
    context = {
        'title': 'All Pending Bills',
        'pending_items': pending_items,
        'search': search,
        'service_filter': service_filter,
        'filter_today_pending': filter_today_pending,
        'total_pending': len(pending_items),
        'total_amount': sum(item['price'] for item in pending_items),
    }
    return render(request, 'hospital/cashier_all_pending_bills.html', context)


@login_required
@user_passes_test(is_cashier)
def cashier_process_pharmacy_encounter(request, encounter_id):
    """
    Process payment for all pharmacy (prescriptions) for one encounter.
    One invoice per encounter – patient pays all drugs at once.
    """
    from hospital import models as _hospital_models
    enc = get_object_or_404(Encounter, id=encounter_id, is_deleted=False)
    patient = enc.patient
    # Pending prescriptions: sent to cashier, not paid, not cancelled
    rx_list = list(
        Prescription.objects.filter(
            order__encounter=enc,
            is_deleted=False
        ).select_related('drug', 'order', 'dispensing_record').prefetch_related(
            Prefetch('invoice_lines', queryset=InvoiceLine.objects.filter(is_deleted=False))
        )
    )
    pending_rx = []
    total = Decimal('0.00')
    for rx in rx_list:
        disp = getattr(rx, 'dispensing_record', None)
        if disp and disp.payment_receipt_id:
            continue
        if disp and (disp.dispensing_status == 'cancelled' or (disp.quantity_ordered or 0) <= 0):
            continue
        _lines = getattr(rx, 'invoice_lines', None)
        inv_line = next(
            (l for l in (_lines.all() if _lines is not None else [])
             if not getattr(l, 'waived_at', None)),
            None
        )
        if not inv_line:
            continue
        if getattr(inv_line, 'waived_at', None):
            continue
        line_total = (inv_line.unit_price or Decimal('0')) * (inv_line.quantity or 0)
        rx.line_total = line_total  # template-safe (no leading underscore)
        pending_rx.append(rx)
        total += line_total
    if not pending_rx:
        messages.warning(request, 'No pending pharmacy for this encounter, or already paid.')
        return redirect('hospital:centralized_cashier_dashboard')
    invoice = get_invoice_for_prescription(pending_rx[0])
    if not invoice:
        messages.error(request, 'No invoice found for this pharmacy order. Ask pharmacy to Send to Cashier first.')
        return redirect('hospital:centralized_cashier_dashboard')
    if request.method == 'POST':
        amount = Decimal(request.POST.get('amount', total))
        payment_method = request.POST.get('payment_method', 'cash')
        notes = request.POST.get('notes', '')
        invoice.refresh_from_db()
        try:
            invoice.update_totals()
        except Exception:
            pass
        amount_to_collect = invoice.balance or Decimal('0')
        if amount_to_collect <= 0:
            from .models_accounting import PaymentReceipt
            receipt = PaymentReceipt.objects.filter(
                invoice=invoice, is_deleted=False
            ).order_by('-receipt_date').first()
            if receipt:
                prescription_ids = [rx.id for rx in pending_rx]
                PharmacyDispensing.objects.filter(
                    prescription_id__in=prescription_ids,
                    payment_receipt_id__isnull=True,
                ).exclude(dispensing_status='cancelled').update(
                    payment_receipt_id=receipt.id,
                    payment_verified_at=timezone.now(),
                    payment_verified_by_id=request.user.id,
                    dispensing_status='ready_to_dispense',
                )
            messages.success(request, 'Invoice already fully paid.')
            return redirect('hospital:centralized_cashier_dashboard')
        amount_to_pay = min(max(Decimal('0'), amount), amount_to_collect)
        if amount_to_pay <= 0:
            messages.warning(request, 'Enter an amount to collect.')
            return redirect(request.path)
        service_details = {
            'pharmacy_encounter': True,
            'encounter_id': str(enc.id),
            'prescriptions': [
                {'prescription_id': str(rx.id), 'drug_name': rx.drug.name, 'quantity': rx.quantity}
                for rx in pending_rx
            ],
        }
        result = UnifiedReceiptService.create_receipt_with_qr(
            patient=patient,
            amount=amount_to_pay,
            payment_method=payment_method,
            received_by_user=request.user,
            invoice=invoice,
            service_type='pharmacy_prescription',
            service_details=service_details,
            notes=notes or f"Pharmacy – {len(pending_rx)} item(s)",
        )
        if result and result.get('success'):
            receipt = result['receipt']
            # Mark ALL dispensing records for this encounter as paid so they leave every queue
            prescription_ids = [rx.id for rx in pending_rx]
            updated = PharmacyDispensing.objects.filter(
                prescription_id__in=prescription_ids,
                payment_receipt_id__isnull=True,
            ).exclude(dispensing_status='cancelled').update(
                payment_receipt_id=receipt.id,
                payment_verified_at=timezone.now(),
                payment_verified_by_id=request.user.id,
                dispensing_status='ready_to_dispense',
            )
            logger.info(f"Pharmacy encounter payment: receipt {receipt.receipt_number}, updated {updated} dispensing record(s).")
            messages.success(request, f"Payment recorded. Receipt {receipt.receipt_number}.")
            from django.urls import reverse
            return redirect(reverse('hospital:receipt_pos_print', args=[receipt.id]) + '?auto_print=1')
        messages.error(request, result.get('message', 'Payment failed.'))
        return redirect(request.path)
    amount_due_after_deposit = estimate_amount_after_deposit(invoice, total)
    service_name = "Pharmacy – " + ", ".join(
        f"{rx.drug.name} × {getattr(rx, 'display_quantity', None) or rx.quantity}"
        for rx in pending_rx[:5]
    )
    if len(pending_rx) > 5:
        service_name += f" (+{len(pending_rx) - 5} more)"
    patient_deposit_balance = Decimal('0.00')
    try:
        from .models_patient_deposits import PatientDeposit
        deposit_sum = PatientDeposit.objects.filter(
            patient=patient, status='active', is_deleted=False
        ).aggregate(total=Sum('available_balance'))['total']
        patient_deposit_balance = deposit_sum or Decimal('0.00')
    except Exception:
        pass
    context = {
        'title': f'Pay pharmacy – {patient.full_name}',
        'service_type': 'pharmacy_encounter',
        'service_obj': enc,
        'patient': patient,
        'service_name': service_name,
        'service_price': total,
        'amount_due_after_deposit': amount_due_after_deposit,
        'unit_price': total,
        'payment_methods': Transaction.PAYMENT_METHODS,
        'patient_deposit_balance': patient_deposit_balance,
        'pharmacy_items': pending_rx,
    }
    return render(request, 'hospital/cashier_process_payment.html', context)


@login_required
@user_passes_test(is_cashier)
def cashier_process_service_payment(request, service_type, service_id):
    """
    Process payment for any service
    Universal payment processor
    """
    # Use module refs so no local name can be shadowed by later imports (avoids UnboundLocalError)
    from hospital import models as _hospital_models
    from hospital.services import auto_billing_service as _auto_billing_module

    # Get service details
    service_obj = None
    patient = None
    service_name = ""
    service_price = Decimal('0.00')

    if service_type == 'lab':
        service_obj = get_object_or_404(LabResult, id=service_id, is_deleted=False)
        patient = service_obj.order.encounter.patient
        service_name = service_obj.test.name
        payer = getattr(patient, 'primary_insurance', None)
        unit_price = service_obj.test.price if hasattr(service_obj.test, 'price') else Decimal('0.00')
        try:
            test_code = getattr(service_obj.test, 'code', None) or str(service_obj.test_id)
            svc = ServiceCode.objects.filter(code=f'LAB-{test_code}', is_deleted=False).first()
            if svc:
                unit_price = Decimal(str(pricing_engine.get_service_price(svc, patient, payer=payer) or unit_price))
        except Exception:
            pass
        service_price = unit_price
        # Use invoice line amount when lab has been billed so Pay page matches list
        if service_obj.order and service_obj.order.encounter_id:
            test_code = getattr(service_obj.test, 'code', None) or str(service_obj.test_id)
            lab_svc = f"LAB-{test_code}"
            lab_inv_line = _hospital_models.InvoiceLine.objects.filter(
                service_code__code=lab_svc,
                invoice__patient=patient,
                invoice__encounter=service_obj.order.encounter,
                invoice__is_deleted=False,
                is_deleted=False
            )
            if service_obj.test and service_obj.test.name:
                lab_inv_line = lab_inv_line.filter(description__icontains=service_obj.test.name)
            lab_inv_line = lab_inv_line.first()
            if lab_inv_line and (lab_inv_line.line_total or lab_inv_line.unit_price):
                service_price = lab_inv_line.line_total or (lab_inv_line.unit_price * lab_inv_line.quantity)
                unit_price = lab_inv_line.unit_price
        
    elif service_type == 'pharmacy':
        service_obj = get_object_or_404(Prescription, id=service_id, is_deleted=False)
        patient = service_obj.order.encounter.patient
        service_name = f"{service_obj.drug.name} x {service_obj.quantity}"
        # Use invoice line amount when available so Pay page matches list/billed amount
        inv_line = _hospital_models.InvoiceLine.objects.filter(
            prescription=service_obj, is_deleted=False, waived_at__isnull=True
        ).first()
        if inv_line and (inv_line.line_total or (inv_line.unit_price * inv_line.quantity)):
            service_price = inv_line.line_total or (inv_line.unit_price * inv_line.quantity)
        else:
            payer = getattr(patient, 'primary_insurance', None)
            drug_price = get_drug_price_for_prescription(service_obj.drug, payer=payer)
            service_price = drug_price * service_obj.quantity
        
        dispensing_record = getattr(service_obj, 'dispensing_record', None)
        if not dispensing_record:
            # Do NOT create bill from cashier. Only create dispensing record so pharmacy can see it.
            _auto_billing_module.AutoBillingService.create_pharmacy_dispensing_record_only(service_obj)
            dispensing_record = getattr(service_obj, 'dispensing_record', None)
        # Prescription only gets on invoice when pharmacy sends to cashier/payer
        has_invoice_line = _hospital_models.InvoiceLine.objects.filter(
            prescription=service_obj, is_deleted=False, waived_at__isnull=True
        ).exists()
        if not dispensing_record or not has_invoice_line:
            messages.error(request, '❌ Pharmacy has not sent this medication to the cashier yet. Ask pharmacy to verify and Send to Cashier/Payer first.')
            return redirect('hospital:centralized_cashier_dashboard')
        if dispensing_record.dispensing_status == 'cancelled' or (dispensing_record.quantity_ordered or 0) <= 0:
            messages.warning(request, 'This medication was removed or changed by pharmacy and is no longer pending payment.')
            return redirect('hospital:centralized_cashier_dashboard')
        if dispensing_record.payment_receipt_id:
            messages.error(request, '✅ Payment for this medication has already been recorded.')
            return redirect('hospital:centralized_cashier_dashboard')
    elif service_type == 'pharmacy_walkin':
        service_obj = get_object_or_404(WalkInPharmacySale, id=service_id, is_deleted=False)
        if service_obj.payment_status == 'paid':
            messages.error(request, '✅ Payment for this prescribe sale has already been recorded.')
            return redirect('hospital:centralized_cashier_dashboard')
        patient = WalkInPharmacyService.ensure_sale_patient(service_obj)
        service_name = f"Prescribe Sale {service_obj.sale_number}"
        service_price = service_obj.amount_due or (service_obj.total_amount - service_obj.amount_paid)
        if service_price < 0:
            service_price = Decimal('0.00')
        
    elif service_type == 'imaging':
        from .models_advanced import ImagingStudy
        service_obj = get_object_or_404(ImagingStudy, id=service_id, is_deleted=False)
        patient = service_obj.order.encounter.patient if hasattr(service_obj, 'order') else service_obj.patient
        service_name = service_obj.study_type or f"{service_obj.get_modality_display()} - {service_obj.body_part}"
        
        # Get price from invoice line if exists
        service_price = Decimal('50.00')  # Default
        try:
            invoice_line = _hospital_models.InvoiceLine.objects.filter(
                invoice__encounter=service_obj.encounter,
                invoice__patient=patient,
                service_code__description__icontains=service_obj.study_type or '',
                is_deleted=False
            ).first()
            
            if invoice_line:
                service_price = invoice_line.unit_price or invoice_line.line_total
            else:
                # Try to get from ImagingCatalog
                from .models_advanced import ImagingCatalog
                catalog_item = ImagingCatalog.objects.filter(
                    Q(code=service_obj.study_type) | Q(name__iexact=service_obj.study_type),
                    modality=service_obj.modality,
                    is_active=True,
                    is_deleted=False
                ).first()
                
                if catalog_item and catalog_item.price:
                    service_price = catalog_item.price
        except Exception as e:
            logger.warning(f"Error getting imaging price: {str(e)}")
            service_price = Decimal('50.00')  # Fallback to default
        
    elif service_type == 'consultation':
        service_obj = get_object_or_404(Encounter, id=service_id, is_deleted=False)
        patient = service_obj.patient
        service_name = f"{service_obj.get_encounter_type_display()} Consultation"
        # Use invoice line amount when present so Pay page matches list/billed amount
        consultation_line = get_consultation_line_for_encounter(service_obj)
        line_amt = consultation_line_display_amount(consultation_line)
        if line_amt is not None:
            service_price = line_amt
        else:
            service_price = get_consultation_price_for_encounter(service_obj)
        if service_price == Decimal('30.00'):
            service_price = Decimal('150.00')
        
    elif service_type == 'invoice':
        service_obj = get_object_or_404(Invoice, id=service_id, is_deleted=False)
        if service_obj.status == 'paid' or service_obj.balance <= 0:
            messages.error(request, '✅ This invoice has already been paid.')
            return redirect('hospital:centralized_cashier_dashboard')
        patient = service_obj.patient
        service_name = f"Invoice {service_obj.invoice_number}"
        service_price = service_obj.balance
        
    elif service_type == 'bed':
        service_obj = get_object_or_404(Admission, id=service_id, is_deleted=False)
        patient = service_obj.encounter.patient
        # Calculate current bed charges
        try:
            from .services.bed_billing_service import bed_billing_service
            charges = bed_billing_service.get_bed_charges_summary(service_obj)
            service_price = charges['current_charges']
            days = charges['days_admitted']
            service_name = f"Bed Charges - {service_obj.ward.name} - Bed {service_obj.bed.bed_number} ({days} nights)"
        except:
            service_price = Decimal('120.00')
            service_name = f"Bed Charges - {service_obj.ward.name} - Bed {service_obj.bed.bed_number}"
    
    lab_bill_result = pharm_bill_result = None
    if service_type == 'lab':
        release_record = getattr(service_obj, 'release_record', None)
        if not release_record:
            lab_bill_result = _auto_billing_module.AutoBillingService.create_lab_bill(service_obj)
            release_record = getattr(service_obj, 'release_record', None)
        if not release_record:
            messages.error(request, '❌ Lab result has not been sent to the cashier yet.')
            return redirect('hospital:centralized_cashier_dashboard')
        if release_record.payment_receipt_id:
            messages.error(request, '✅ Payment for this lab test has already been recorded.')
            return redirect('hospital:centralized_cashier_dashboard')

    if request.method == 'POST':
        # Lab tests always billed at quantity 1 (no multiple billing)
        if service_type == 'lab':
            try:
                _inv = get_invoice_for_lab(service_obj)
                payer = _resolve_invoice_payer(_inv, patient)
                test_code = getattr(service_obj.test, 'code', None) or str(service_obj.test_id)
                svc = ServiceCode.objects.filter(code=f'LAB-{test_code}', is_deleted=False).first()
                if svc:
                    service_price = Decimal(str(pricing_engine.get_service_price(svc, patient, payer=payer) or 0))
                else:
                    service_price = service_obj.test.price or Decimal('0')
            except Exception:
                service_price = service_obj.test.price or Decimal('0')
        amount = Decimal(request.POST.get('amount', service_price))
        payment_method = request.POST.get('payment_method', 'cash')
        reference_number = request.POST.get('reference_number', '')
        notes = request.POST.get('notes', '')
        
        # Process payment based on service type
        result = None
        
        if service_type == 'lab':
            invoice = None
            if lab_bill_result and lab_bill_result.get('success'):
                invoice = lab_bill_result.get('invoice')
            if not invoice:
                invoice = get_invoice_for_lab(service_obj)
            if invoice:
                invoice.refresh_from_db()
                try:
                    invoice.update_totals()
                except Exception:
                    pass
                amount_to_collect = invoice.balance or Decimal('0')
            else:
                amount_to_collect = amount
            if invoice and amount_to_collect <= 0:
                receipt = link_deposit_receipt_to_release(None, release_record, invoice, request.user)
                if receipt:
                    from django.urls import reverse
                    messages.success(request, f"✅ Already paid. Receipt {receipt.receipt_number}.")
                    pos_url = reverse('hospital:receipt_pos_print', args=[receipt.id]) + '?auto_print=1'
                    return redirect(pos_url)
                messages.success(request, "✅ Invoice already fully paid.")
                return redirect('hospital:centralized_cashier_dashboard')
            # Allow part payment: collect up to amount_to_collect
            amount_to_pay = min(max(Decimal('0'), amount), amount_to_collect) if (invoice and amount_to_collect > 0) else amount
            if amount_to_pay > 0:
                result = LabPaymentService.create_lab_payment_receipt(
                    lab_result=service_obj,
                    amount=amount_to_pay,
                    payment_method=payment_method,
                    received_by_user=request.user,
                    notes=notes,
                    invoice=invoice
                )
        elif service_type == 'pharmacy':
            invoice = (pharm_bill_result.get('invoice') if pharm_bill_result and pharm_bill_result.get('success') else None) or get_invoice_for_prescription(service_obj)
            amount_to_collect = amount
            if invoice:
                invoice.refresh_from_db()
                try:
                    invoice.update_totals()
                except Exception:
                    pass
                amount_to_collect = invoice.balance or Decimal('0')
            if invoice and amount_to_collect <= 0:
                receipt = link_deposit_receipt_to_release(None, dispensing_record, invoice, request.user)
                if receipt:
                    from django.urls import reverse
                    messages.success(request, f"✅ Already paid. Receipt {receipt.receipt_number}.")
                    pos_url = reverse('hospital:receipt_pos_print', args=[receipt.id]) + '?auto_print=1'
                    return redirect(pos_url)
                messages.success(request, "✅ Invoice already fully paid.")
                return redirect('hospital:centralized_cashier_dashboard')
            # Allow part payment
            amount_to_pay = min(max(Decimal('0'), amount), amount_to_collect) if amount_to_collect > 0 else amount
            if amount_to_pay > 0:
                result = PharmacyPaymentService.create_pharmacy_payment_receipt(
                    prescription=service_obj,
                    amount=amount_to_pay,
                    payment_method=payment_method,
                    received_by_user=request.user,
                    notes=notes,
                    invoice=invoice
                )
        elif service_type == 'pharmacy_walkin':
            result = WalkInPharmacyService.create_payment_receipt(
                sale=service_obj,
                amount=amount,
                payment_method=payment_method,
                received_by_user=request.user,
                notes=notes or f"Prescribe sale {service_obj.sale_number}"
            )
        elif service_type == 'imaging':
            invoice = get_invoice_for_imaging(service_obj)
            amount_to_collect = amount
            imaging_release = getattr(service_obj, 'release_record', None)
            if invoice:
                invoice.refresh_from_db()
                try:
                    invoice.update_totals()
                except Exception:
                    pass
                amount_to_collect = invoice.balance or Decimal('0')
            if invoice and amount_to_collect <= 0 and imaging_release:
                receipt = link_deposit_receipt_to_release(None, imaging_release, invoice, request.user)
                if receipt:
                    from django.urls import reverse
                    messages.success(request, f"✅ Already paid. Receipt {receipt.receipt_number}.")
                    pos_url = reverse('hospital:receipt_pos_print', args=[receipt.id]) + '?auto_print=1'
                    return redirect(pos_url)
                messages.success(request, "✅ Invoice already fully paid.")
                return redirect('hospital:centralized_cashier_dashboard')
            # Allow part payment
            amount_to_pay = min(max(Decimal('0'), amount), amount_to_collect) if amount_to_collect > 0 else amount
            if amount_to_pay > 0:
                result = ImagingPaymentService.create_imaging_payment_receipt(
                    imaging_study=service_obj,
                    amount=amount_to_pay,
                    payment_method=payment_method,
                    received_by_user=request.user,
                    notes=notes,
                    invoice=invoice
                )
        elif service_type == 'consultation':
            result = ConsultationPaymentService.create_consultation_payment_receipt(
                encounter=service_obj,
                amount=amount,
                payment_method=payment_method,
                received_by_user=request.user,
                notes=notes
            )
        elif service_type == 'bed':
            result = BedPaymentService.create_bed_payment_receipt(
                admission=service_obj,
                amount=amount,
                payment_method=payment_method,
                received_by_user=request.user,
                notes=notes
            )
        elif service_type == 'invoice':
            from .services.unified_receipt_service import UnifiedReceiptService
            service_obj.refresh_from_db()
            service_obj.update_totals()
            amount_to_collect_inv = service_obj.balance or Decimal('0')
            if amount_to_collect_inv <= 0:
                messages.success(request, "✅ This invoice is already fully paid.")
                return redirect('hospital:centralized_cashier_dashboard')
            # Allow part payment
            amount_to_pay = min(max(Decimal('0'), amount), amount_to_collect_inv)
            if amount_to_pay <= 0:
                messages.warning(request, "Enter an amount to collect (partial or full).")
                return redirect(request.path)
            else:
                result = UnifiedReceiptService.create_receipt_with_qr(
                    patient=service_obj.patient,
                    amount=amount_to_pay,
                    payment_method=payment_method,
                    received_by_user=request.user,
                    invoice=service_obj,
                    service_type='other',
                    service_details={'invoice_number': service_obj.invoice_number, 'invoice_id': str(service_obj.id)},
                    notes=notes
                )
                if result and result.get('success'):
                    service_obj.update_totals()
                    try:
                        from .services.pharmacy_invoice_payment_link import (
                            link_pharmacy_dispensing_when_invoice_paid,
                        )
                        if (service_obj.balance or Decimal('0')) <= 0:
                            link_pharmacy_dispensing_when_invoice_paid(
                                service_obj,
                                receipt=result.get('receipt'),
                                verified_by_user=request.user,
                                refresh_invoice=False,
                            )
                    except Exception:
                        pass
        
        if result and result.get('success'):
            # Show digital receipt info
            digital = result.get('digital_receipt', {})
            accounting = result.get('accounting_sync', {})
            
            msg = f"✅ Payment processed! Receipt {result['receipt'].receipt_number} generated."
            if digital.get('email', {}).get('sent'):
                msg += " 📧 Email sent."
            if digital.get('sms', {}).get('sent'):
                msg += " 📱 SMS sent."
            if accounting.get('success'):
                msg += " 💰 Accounting synced."
            
            messages.success(request, msg)
            # Redirect to POS receipt with auto-print option
            from django.urls import reverse
            pos_url = reverse('hospital:receipt_pos_print', args=[result['receipt'].id]) + '?auto_print=1'
            return redirect(pos_url)
        elif result:
            error_msg = result.get('message', result.get('error', 'Unknown error'))
            messages.error(request, f"❌ Payment failed: {error_msg}")
            logger.error(f"Payment failed for {service_type} {service_id}: {error_msg}")
        else:
            messages.error(request, "❌ Payment processing failed - no result returned")
            logger.error(f"Payment processing returned None for {service_type} {service_id}")
    
    # Get patient deposit balance if available
    patient_deposit_balance = Decimal('0.00')
    try:
        from .models_patient_deposits import PatientDeposit
        deposit_sum = PatientDeposit.objects.filter(
            patient=patient,
            status='active',
            is_deleted=False
        ).aggregate(total=Sum('available_balance'))['total']
        patient_deposit_balance = deposit_sum if deposit_sum else Decimal('0.00')
    except Exception as e:
        logger.warning(f"Error calculating deposit balance for patient {patient.id}: {e}")
        patient_deposit_balance = Decimal('0.00')
    
    unit_price = service_price
    if service_type == 'lab':
        try:
            _inv = get_invoice_for_lab(service_obj)
            payer = _resolve_invoice_payer(_inv, patient)
            test_code = getattr(service_obj.test, 'code', None) or str(service_obj.test_id)
            svc = ServiceCode.objects.filter(code=f'LAB-{test_code}', is_deleted=False).first()
            if svc:
                unit_price = Decimal(str(pricing_engine.get_service_price(svc, patient, payer=payer) or 0))
            else:
                unit_price = service_obj.test.price if hasattr(service_obj.test, 'price') else Decimal('0.00')
        except Exception:
            unit_price = service_obj.test.price if hasattr(service_obj.test, 'price') else Decimal('0.00')
    # Amount to collect after deposit (for form default value)
    amount_due_after_deposit = service_price
    if service_type == 'lab':
        inv = get_invoice_for_lab(service_obj)
        amount_due_after_deposit = estimate_amount_after_deposit(inv, service_price)
    elif service_type == 'pharmacy':
        # Use this prescription's amount so "Amount to collect" matches "Price" (single-item payment)
        amount_due_after_deposit = service_price
    elif service_type == 'imaging':
        inv = get_invoice_for_imaging(service_obj)
        amount_due_after_deposit = estimate_amount_after_deposit(inv, service_price)
    context = {
        'title': f'Process Payment - {service_name}',
        'service_type': service_type,
        'service_obj': service_obj,
        'patient': patient,
        'service_name': service_name,
        'service_price': service_price,
        'amount_due_after_deposit': amount_due_after_deposit,
        'unit_price': unit_price,
        'payment_methods': Transaction.PAYMENT_METHODS,
        'patient_deposit_balance': patient_deposit_balance,
    }
    # Itemized list for pharmacy (encounter uses pending_rx with .line_total; walk-in uses sale items with .line_total)
    if service_type == 'pharmacy_walkin' and hasattr(service_obj, 'items'):
        context['pharmacy_items'] = list(service_obj.items.select_related('drug').all())
    return render(request, 'hospital/cashier_process_payment.html', context)


def _get_patient_pending_services_for_payment(patient):
    """
    Get pending services - SAME logic as cashier_patient_total_bill.
    Returns (services_list, total) so process-combined matches total-bill exactly.
    """
    from .models_advanced import ImagingStudy
    from .models_accounting import PaymentReceipt
    from .models_payment_verification import LabResultRelease, PharmacyDispensing, ImagingRelease
    from .models_pharmacy_walkin import WalkInPharmacySale
    from .models import Admission, Invoice, InvoiceLine
    from django.db.models import Q

    services = []
    total = Decimal('0.00')

    # Labs: SAME as total-bill (no verified_by filter)
    labs_query = LabResult.objects.filter(
        order__encounter__patient=patient,
        is_deleted=False
    ).select_related('test', 'order__encounter', 'order__encounter__patient').distinct()
    
    for lab in labs_query:
        # Check if lab has been paid - multiple methods (same as cashier_patient_total_bill)
        lab_paid = False
        try:
            if hasattr(lab, 'release_record'):
                release = lab.release_record
                if release and release.payment_receipt_id is not None:
                    lab_paid = True
        except (LabResultRelease.DoesNotExist, AttributeError):
            pass
        if not lab_paid:
            for receipt in PaymentReceipt.objects.filter(patient=patient, is_deleted=False, service_type__in=('lab_test', 'lab_result', 'lab'))[:20]:
                try:
                    d = receipt.service_details or {}
                    if isinstance(d, dict) and (d.get('order_id') == str(lab.order_id) or d.get('lab_result_id') == str(lab.id)):
                        lab_paid = True
                        break
                except (TypeError, AttributeError):
                    pass
        if not lab_paid and lab.test and lab.test.name:
            from .models import InvoiceLine
            if InvoiceLine.objects.filter(invoice__patient=patient, invoice__status='paid', invoice__is_deleted=False, description__icontains=lab.test.name[:50], is_deleted=False).exists():
                lab_paid = True
        # Skip if lab is on unpaid invoice (same as total-bill)
        on_unpaid_invoice = False
        if not lab_paid and lab.order and lab.order.encounter_id:
            test_code = getattr(lab.test, 'code', None) or str(lab.test_id)
            lab_svc = f"LAB-{test_code}"
            on_unpaid_invoice = InvoiceLine.objects.filter(
                service_code__code=lab_svc,
                invoice__patient=patient,
                invoice__encounter=lab.order.encounter,
                invoice__is_deleted=False,
                invoice__status__in=('issued', 'draft', 'partially_paid'),
                invoice__balance__gt=0,
                is_deleted=False
            ).exists()
        if lab_paid or on_unpaid_invoice:
            continue
        
        unit_price = lab.test.price if hasattr(lab.test, 'price') else Decimal('0.00')
        try:
            encounter = getattr(lab.order, 'encounter', None)
            patient_for_price = encounter.patient if encounter else patient
            payer = getattr(patient_for_price, 'primary_insurance', None)
            test_code = getattr(lab.test, 'code', None) or str(lab.test_id)
            svc = ServiceCode.objects.filter(code=f"LAB-{test_code}", is_deleted=False).first()
            if svc:
                unit_price = Decimal(str(pricing_engine.get_service_price(svc, patient_for_price, payer=payer) or unit_price))
        except Exception:
            pass
        if unit_price == 0 and lab.order and lab.order.encounter_id:
            test_code = getattr(lab.test, 'code', None) or str(lab.test_id)
            lab_svc = f"LAB-{test_code}"
            inv_line = InvoiceLine.objects.filter(
                service_code__code=lab_svc,
                description__icontains=lab.test.name if lab.test else '',
                invoice__patient=patient,
                invoice__encounter=lab.order.encounter,
                invoice__is_deleted=False,
                is_deleted=False
            ).first()
            if inv_line:
                unit_price = inv_line.line_total
        quantity = Decimal('1.00')
        price = unit_price * quantity
        services.append({
            'type': 'lab', 'id': str(lab.id), 'obj': lab, 'name': lab.test.name if lab.test else 'Lab Test',
            'quantity': quantity, 'unit_price': unit_price, 'price': price,
        })
        total += price
    
    # Prescriptions: do NOT add as standalone items. They only appear when on an invoice
    # (pharmacy has sent to cashier/payer), and are then counted in the invoice block below.
    
    # Imaging - same as total-bill (Q for patient, skip if on unpaid invoice) – only billable statuses
    imaging_query = ImagingStudy.objects.filter(
        Q(patient=patient) | Q(order__encounter__patient=patient),
        is_deleted=False,
        status__in=IMAGING_BILLABLE_STATUSES
    ).select_related('order__encounter', 'order__encounter__patient').distinct()
    
    for imaging in imaging_query:
        already_paid = False
        try:
            release = imaging.release_record
            if release and release.payment_receipt_id is not None:
                already_paid = True
        except Exception:
            pass
        if not already_paid:
            for receipt in PaymentReceipt.objects.filter(patient=patient, is_deleted=False, service_type__in=('imaging_study', 'imaging'))[:20]:
                try:
                    d = receipt.service_details or {}
                    if isinstance(d, dict):
                        if d.get('study_id') == str(imaging.id):
                            already_paid = True
                            break
                        if d.get('study_type') == getattr(imaging, 'study_type', None) and d.get('body_part') == getattr(imaging, 'body_part', None):
                            already_paid = True
                            break
                except (TypeError, AttributeError):
                    pass
        if not already_paid and getattr(imaging, 'study_type', None):
            st = (imaging.study_type or '')[:50]
            if st and InvoiceLine.objects.filter(invoice__patient=patient, invoice__status='paid', invoice__is_deleted=False, description__icontains=st, is_deleted=False).exists():
                already_paid = True
        img_on_unpaid_invoice = False
        if not already_paid and getattr(imaging, 'study_type', None):
            st = (imaging.study_type or '')[:50]
            if st:
                qs = InvoiceLine.objects.filter(description__icontains=st, invoice__patient=patient, invoice__is_deleted=False,
                    invoice__status__in=('issued', 'draft', 'partially_paid'), invoice__balance__gt=0, is_deleted=False)
                if getattr(imaging, 'encounter_id', None):
                    qs = qs.filter(invoice__encounter=imaging.encounter)
                img_on_unpaid_invoice = qs.exists()
        if not already_paid and not img_on_unpaid_invoice:
            imaging_price = Decimal('50.00')
            if hasattr(imaging, 'price') and imaging.price:
                imaging_price = imaging.price
            else:
                inv_line = InvoiceLine.objects.filter(description__icontains=imaging.study_type, invoice__patient=patient, invoice__is_deleted=False, is_deleted=False).first()
                if inv_line:
                    imaging_price = inv_line.line_total
            services.append({
                'type': 'imaging', 'id': str(imaging.id), 'obj': imaging,
                'name': f"{imaging.study_type} - {imaging.body_part}",
                'quantity': Decimal('1.00'), 'unit_price': imaging_price, 'price': imaging_price,
            })
            total += imaging_price
    
    # Walk-in pharmacy sales (exclude waived). Skip sales already on an unpaid invoice (same as total-bill).
    walkin_sales = WalkInPharmacySale.objects.filter(
        patient=patient,
        is_deleted=False,
        payment_status__in=['pending', 'partial'],
        waived_at__isnull=True
    ).select_related('patient')
    # Include paid invoices so prescribe lines already settled on an invoice do not reappear as walk-in due.
    _unpaid_inv_line_descriptions = list(
        InvoiceLine.objects.filter(
            invoice__patient=patient,
            invoice__is_deleted=False,
            invoice__status__in=('issued', 'draft', 'partially_paid', 'overdue', 'paid'),
            waived_at__isnull=True,
            is_deleted=False,
        )
        .exclude(invoice__status='cancelled')
        .values_list('description', flat=True)
    )
    sale_numbers_covered_by_invoice = set()
    for sale in walkin_sales:
        for desc in _unpaid_inv_line_descriptions:
            if desc and sale.sale_number in desc:
                sale_numbers_covered_by_invoice.add(sale.sale_number)
                break
    for sale in walkin_sales:
        if sale.sale_number in sale_numbers_covered_by_invoice:
            continue
        amount_due = getattr(sale, 'amount_due', None)
        if amount_due is None:
            amount_due = (sale.total_amount or Decimal('0.00')) - (sale.amount_paid or Decimal('0.00'))
        if amount_due > 0:
            services.append({
                'type': 'pharmacy_walkin', 'id': str(sale.id), 'obj': sale,
                'name': f"Prescribe Sale {sale.sale_number}",
                'quantity': Decimal('1.00'), 'unit_price': amount_due, 'price': amount_due,
            })
            total += amount_due
    
    # Active admissions (bed charges)
    try:
        from .services.bed_billing_service import bed_billing_service
        admissions = Admission.objects.filter(
            encounter__patient=patient,
            is_deleted=False,
            status='admitted'
        ).select_related('encounter', 'ward', 'bed')
        for admission in admissions:
            try:
                charges = bed_billing_service.get_bed_charges_summary(admission)
                bed_charge = charges.get('current_charges', Decimal('0.00'))
                if bed_charge > 0:
                    days = charges.get('days_admitted', 0)
                    services.append({
                        'type': 'bed', 'id': str(admission.id), 'obj': admission,
                        'name': f"Bed Charges - {admission.ward.name} - Bed {admission.bed.bed_number} ({days} night{'s' if days != 1 else ''})",
                        'quantity': Decimal('1.00'), 'unit_price': bed_charge, 'price': bed_charge,
                    })
                    total += bed_charge
            except Exception as e:
                logger.warning(f"Error calculating bed charges for admission {admission.id}: {e}")
    except Exception as e:
        logger.warning(f"Error loading admissions for combined payment: {e}")
    
    # Unpaid invoices: all_objects so draft/zero-total-then-updated bills stay visible (default manager hides total_amount=0)
    from .models import Invoice
    invoices = (
        Invoice.all_objects.filter(patient=patient, is_deleted=False)
        .exclude(status__in=['paid', 'cancelled'])
        .exclude(
            issued_at__date__gte=Invoice.WRITE_OFF_START,
            issued_at__date__lte=Invoice.WRITE_OFF_END,
        )
        .select_related('encounter', 'payer')
        .prefetch_related('lines')
        .order_by('issued_at', 'created')
    )
    # Only invoices with money still owed (paid / fully settled must not appear or spawn line rows).
    invoices_with_balance = []
    walkin_groups = {}
    skipped_duplicate_invoice_ids = set()
    all_open_invoice_ids = []
    for invoice in invoices:
        invoice.update_totals()
        inv_balance = invoice.balance if getattr(invoice, 'balance', None) is not None else Decimal('0.00')
        if inv_balance <= 0:
            continue
        invoices_with_balance.append(invoice)
        fp = _walkin_invoice_dedupe_fingerprint(invoice)
        if fp:
            walkin_groups.setdefault(fp, []).append(invoice)

    for grouped in walkin_groups.values():
        if len(grouped) <= 1:
            continue
        # Keep the row with the smallest remaining balance (most paid), then oldest.
        keep = min(
            grouped,
            key=lambda inv: (
                inv.balance if getattr(inv, 'balance', None) is not None else Decimal('0.00'),
                getattr(inv, 'issued_at', None) or getattr(inv, 'created', None) or timezone.now(),
            ),
        )
        for inv in grouped:
            if inv.pk == keep.pk:
                continue
            skipped_duplicate_invoice_ids.add(inv.pk)
            logger.info(
                "Total bill dedupe: skipping duplicate walk-in invoice %s for patient %s; keeping %s",
                inv.invoice_number,
                patient.id,
                keep.invoice_number,
            )

    for invoice in invoices_with_balance:
        if invoice.pk in skipped_duplicate_invoice_ids:
            continue
        all_open_invoice_ids.append(invoice.pk)
        lines_count = invoice.lines.filter(is_deleted=False).count()
        inv_balance = invoice.balance if getattr(invoice, 'balance', None) is not None else Decimal('0.00')
        if lines_count == 0:
            # Empty shell invoices (e.g. draft never filled) clutter Total Bill and show "No services added".
            # Still surface if money is somehow owed on a line-less invoice.
            services.append({
                'type': 'invoice', 'id': str(invoice.id), 'obj': invoice,
                'name': f"Invoice {invoice.invoice_number} (no line items — balance due)",
                'quantity': Decimal('1.00'), 'unit_price': inv_balance, 'price': inv_balance,
            })
            total += inv_balance
        else:
            services.append({
                'type': 'invoice', 'id': str(invoice.id), 'obj': invoice,
                'name': f"Invoice {invoice.invoice_number}",
                'quantity': Decimal('1.00'), 'unit_price': inv_balance, 'price': inv_balance,
            })
            total += inv_balance
    
    # Do not add per-invoice-line rows here. Each open invoice is already one row with its
    # full balance due; adding lines would double-count (invoice total + sum of lines) when
    # the "already on invoice" guard fails, or when the invoice row is the correct source.
    # Line detail is shown from Invoice.lines in _total_bill_services_to_display for type invoice.

    return (services, total)


def _total_bill_services_to_display(services_list):
    """
    Convert _get_patient_pending_services_for_payment output to Total Bill template format
    (name, price, date, encounter, breakdown, invoice_id where applicable).
    """
    from .models import Invoice, InvoiceLine
    from .models_pharmacy_walkin import WalkInPharmacySaleItem
    from .utils_invoice_line import (
        heal_invoice_zero_line_prices,
        invoice_line_display_unit_and_total,
        walkin_sale_item_display_unit_and_total,
    )
    display = []
    for s in services_list:
        stype = s.get('type', '')
        obj = s.get('obj')
        if stype == 'invoice' and obj:
            fr = Invoice.all_objects.filter(pk=obj.pk).first()
            if (
                not fr
                or getattr(fr, 'is_deleted', False)
                or fr.status in ('paid', 'cancelled')
                or (fr.balance or Decimal('0')) <= 0
            ):
                continue
            obj = fr
        elif stype == 'invoice_line' and obj:
            fr = Invoice.all_objects.filter(pk=getattr(obj, 'pk', None)).first()
            if (
                not fr
                or getattr(fr, 'is_deleted', False)
                or fr.status in ('paid', 'cancelled')
                or (fr.balance or Decimal('0')) <= 0
            ):
                continue
            obj = fr
        elif stype == 'pharmacy_walkin' and obj:
            try:
                obj.refresh_from_db()
            except Exception:
                pass
            if getattr(obj, 'payment_status', None) == 'paid':
                continue
            due = getattr(obj, 'amount_due', None)
            if due is None:
                due = (obj.total_amount or Decimal('0')) - (obj.amount_paid or Decimal('0'))
            if due <= 0 and (obj.total_amount or Decimal('0')) > 0:
                continue
        name = s.get('name', '')
        price = s.get('price', Decimal('0.00'))
        date = None
        encounter = None
        breakdown = []
        invoice_id = None
        if stype == 'lab' and obj:
            date = getattr(obj, 'created', None)
            encounter = obj.order.encounter if getattr(obj, 'order', None) else None
            unit = s.get('unit_price', price)
            breakdown = [{'description': name, 'quantity': 1, 'unit_price': unit, 'amount': price}]
        elif stype == 'imaging' and obj:
            date = getattr(obj, 'performed_at', None) or getattr(obj, 'created', None)
            encounter = obj.order.encounter if getattr(obj, 'order', None) else None
            unit = s.get('unit_price', price)
            breakdown = [{'description': name, 'quantity': 1, 'unit_price': unit, 'amount': price}]
        elif stype == 'pharmacy_walkin' and obj:
            date = getattr(obj, 'sale_date', None)
            sale_items = WalkInPharmacySaleItem.objects.filter(
                sale=obj, is_deleted=False, waived_at__isnull=True
            ).select_related('drug').order_by('created')
            for item in sale_items:
                drug_display = item.drug.name if item.drug else ''
                if getattr(item.drug, 'strength', None):
                    drug_display = f"{item.drug.name} {item.drug.strength}"
                _up, _amt = walkin_sale_item_display_unit_and_total(item)
                breakdown.append({
                    'description': drug_display,
                    'quantity': item.quantity,
                    'unit_price': _up,
                    'amount': _amt,
                    'sale_item_id': str(item.id),
                    'is_waived': False,
                })
            if not breakdown:
                breakdown = [{'description': f"Prescribe Sale {getattr(obj, 'sale_number', '')}", 'quantity': 1, 'unit_price': price, 'amount': price}]
        elif stype == 'bed' and obj:
            date = getattr(obj, 'admit_date', None)
            encounter = getattr(obj, 'encounter', None)
            try:
                from .services.bed_billing_service import bed_billing_service, BedBillingService
                charges = bed_billing_service.get_bed_charges_summary(obj)
                charge_breakdown = BedBillingService.calculate_admission_charges(obj)
                line_items = charge_breakdown.get('line_items', [])
                breakdown = [{'description': item.get('description', ''), 'quantity': item.get('quantity', 1), 'unit_price': item.get('unit_price', 0), 'amount': item.get('line_total', 0)} for item in line_items]
            except Exception:
                breakdown = [{'description': name, 'quantity': 1, 'unit_price': price, 'amount': price}]
        elif stype == 'invoice' and obj:
            date = getattr(obj, 'issued_at', None) or getattr(obj, 'created', None)
            encounter = getattr(obj, 'encounter', None)
            invoice_id = str(obj.id)
            inv_balance = getattr(obj, 'balance', None) or Decimal('0.00')
            is_paid = inv_balance <= 0
            try:
                heal_invoice_zero_line_prices(obj)
            except Exception:
                pass
            inv_lines = InvoiceLine.objects.filter(invoice=obj, is_deleted=False, waived_at__isnull=True).select_related('service_code')
            breakdown = []
            for l in inv_lines:
                desc = (getattr(l.service_code, 'description', None) or l.description) if l.service_code else l.description
                _up, _amt = invoice_line_display_unit_and_total(l)
                breakdown.append({
                    'description': desc,
                    'quantity': l.quantity,
                    'unit_price': _up,
                    'amount': _amt,
                    'line_id': str(l.id),
                    'is_waived': False,
                    'is_paid': is_paid,
                })
            if not breakdown:
                breakdown = [{'description': 'No line items yet', 'quantity': 0, 'unit_price': 0, 'amount': Decimal('0.00'), 'is_paid': is_paid}]
        elif stype == 'invoice_line' and obj:
            line_id = s.get('id')
            line = InvoiceLine.objects.filter(id=line_id).select_related('service_code', 'invoice').first() if line_id else None
            if line:
                if line.waived_at:
                    breakdown = []
                    price = Decimal('0.00')
                    date = getattr(line.invoice, 'issued_at', None) or getattr(line.invoice, 'created', None)
                    encounter = getattr(line.invoice, 'encounter', None)
                    invoice_id = str(line.invoice_id)
                else:
                    date = getattr(line.invoice, 'issued_at', None) or getattr(line.invoice, 'created', None)
                    encounter = getattr(line.invoice, 'encounter', None)
                    invoice_id = str(line.invoice_id)
                    desc = (getattr(line.service_code, 'description', None) or line.description) if line.service_code else line.description
                    line_inv_balance = getattr(line.invoice, 'balance', None) or Decimal('0.00')
                    try:
                        heal_invoice_zero_line_prices(line.invoice)
                        line.refresh_from_db()
                    except Exception:
                        pass
                    _up, _amt = invoice_line_display_unit_and_total(line)
                    breakdown = [{'description': desc, 'quantity': line.quantity, 'unit_price': _up, 'amount': _amt, 'line_id': str(line.id), 'is_waived': False, 'is_paid': line_inv_balance <= 0}]
            else:
                date = getattr(obj, 'issued_at', None) or getattr(obj, 'created', None)
                encounter = getattr(obj, 'encounter', None)
                invoice_id = str(obj.id)
                breakdown = [{'description': name, 'quantity': 1, 'unit_price': price, 'amount': price}]
        else:
            date = timezone.now()
        # Set is_paid for invoice/invoice_line so itemized bill can show "Paid"
        is_paid = False
        if stype == 'invoice' and obj:
            is_paid = (getattr(obj, 'balance', None) or Decimal('0.00')) <= 0
        elif stype == 'invoice_line' and obj:
            line = InvoiceLine.objects.filter(id=s.get('id')).select_related('invoice').first() if s.get('id') else None
            if line and line.invoice:
                is_paid = (getattr(line.invoice, 'balance', None) or Decimal('0.00')) <= 0
        display.append({
            'type': stype,
            'id': s.get('id', ''),
            'name': name,
            'price': price,
            'date': date,
            'encounter': encounter,
            'breakdown': breakdown,
            'invoice_id': invoice_id,
            'is_paid': is_paid,
        })
    return display


@login_required
@user_passes_test(is_cashier)
def cashier_process_patient_combined_payment(request, patient_id):
    """Process combined payment - uses same service logic as total-bill."""
    patient = get_object_or_404(Patient, id=patient_id, is_deleted=False)
    services_list, total_amount = _get_patient_pending_services_for_payment(patient)
    
    if request.method == 'POST':
        # Read cashier-edited quantities and amounts from form (empty or 0 = zero the line)
        for idx, service in enumerate(services_list):
            qty_val = request.POST.get(f'service_{idx}_qty')
            amt_val = request.POST.get(f'service_{idx}_amount')
            if qty_val is not None:
                try:
                    service['quantity'] = Decimal(str(qty_val).strip() or '1')
                    if service['quantity'] < 0:
                        service['quantity'] = Decimal('1')
                except Exception:
                    pass
            if amt_val is not None:
                raw = str(amt_val).strip()
                if raw == '' or raw.lower() == '0' or raw == '0.00':
                    service['price'] = Decimal('0.00')
                else:
                    try:
                        service['price'] = Decimal(raw)
                        if service['price'] < 0:
                            service['price'] = Decimal('0.00')
                    except Exception:
                        service['price'] = service.get('quantity', Decimal('1')) * service.get('unit_price', Decimal('0'))
            else:
                service['price'] = service.get('quantity', Decimal('1')) * service.get('unit_price', Decimal('0'))
        total_amount = sum(s['price'] for s in services_list)
        
        # Keep row prices aligned with current invoice balances (deposits are applied only via cashier action)
        from .services.deposit_payment_service import refresh_combined_service_prices_after_deposit

        total_amount = refresh_combined_service_prices_after_deposit(services_list)
        total_deposit_applied = Decimal('0.00')
        
        service_invoices = {}  # service_idx -> (invoice, release_record or None)
        for idx, service in enumerate(services_list):
            inv = None
            release_rec = None
            if service['type'] == 'lab':
                inv = get_invoice_for_lab(service['obj'])
                release_rec = getattr(service['obj'], 'release_record', None)
            elif service['type'] == 'pharmacy':
                inv = get_invoice_for_prescription(service['obj'])
                release_rec = getattr(service['obj'], 'dispensing_record', None)
            elif service['type'] == 'imaging':
                inv = get_invoice_for_imaging(service['obj'])
                release_rec = getattr(service['obj'], 'release_record', None)
            elif service['type'] == 'invoice':
                inv = service['obj']
            elif service['type'] == 'invoice_line':
                inv = service['obj']
            elif service['type'] == 'pharmacy_walkin' and service.get('obj'):
                sale = service['obj']
                sale_patient = sale.patient or WalkInPharmacyService.ensure_sale_patient(sale)
                inv = WalkInPharmacyService.ensure_sale_invoice(sale, sale_patient)
            service_invoices[idx] = (inv, release_rec)
        
        amount_to_collect = max(Decimal('0.00'), total_amount)
        # Receipt amount = recalculated from edited/zeroed items; allow partial payment if cashier enters less
        amount = amount_to_collect
        try:
            posted = request.POST.get('amount')
            if posted is not None and str(posted).strip() != '':
                parsed = Decimal(str(posted).strip())
                if Decimal('0') <= parsed <= amount_to_collect:
                    amount = parsed
        except Exception:
            pass
        if total_amount <= 0:
            messages.warning(request, 'No chargeable amount. All items are zero or already paid.')
            return redirect('hospital:cashier_patient_total_bill', patient_id=patient.id)
        payment_method = request.POST.get('payment_method', 'cash')
        reference_number = request.POST.get('reference_number', '')
        notes = request.POST.get('notes', '')
        
        # Build service details list for combined receipt (include Prescribe Sale line-item breakdown for invoice/receipt)
        service_details_list = []
        for service in services_list:
            entry = {
                'type': service['type'],
                'name': service['name'],
                'price': str(service['price']),
                'service_id': service['id']
            }
            if service['type'] == 'pharmacy_walkin' and service.get('obj'):
                sale = service['obj']
                breakdown = []
                for item in sale.items.filter(is_deleted=False, waived_at__isnull=True).select_related('drug'):
                    drug_display = item.drug.name
                    if getattr(item.drug, 'strength', None):
                        drug_display = f"{item.drug.name} {item.drug.strength}"
                    breakdown.append({
                        'description': drug_display,
                        'quantity': item.quantity,
                        'unit_price': str(item.unit_price),
                        'amount': str(item.line_total),
                    })
                if breakdown:
                    entry['breakdown'] = breakdown
            service_details_list.append(entry)
        
        # Build allocation list for PaymentAllocation (one receipt per transaction; no extra receipts)
        from .services.unified_receipt_service import UnifiedReceiptService
        from .models_accounting import PaymentAllocation, PaymentReceipt

        to_allocate = []
        remaining = amount
        for idx in range(len(services_list)):
            inv, _ = service_invoices.get(idx, (None, None))
            if not inv or remaining <= 0:
                continue
            inv.refresh_from_db()
            if (inv.balance or Decimal('0')) <= 0:
                continue
            alloc = min(remaining, inv.balance)
            if alloc > 0:
                to_allocate.append((inv, alloc))
                remaining -= alloc

        combined_service_details = {
            'services': service_details_list,
            'total_services': len(services_list),
            'combined_bill': True,
            'reference_number': reference_number,
            'deposit_applied': str(total_deposit_applied),
        }
        first_invoice = to_allocate[0][0] if to_allocate else None
        base_notes = notes or f"Combined payment for {len(services_list)} service(s)"
        summary_notes = base_notes + (" Combined payment (summary)." if to_allocate else "")

        result = UnifiedReceiptService.create_receipt_with_qr(
            patient=patient,
            amount=amount,
            payment_method=payment_method,
            received_by_user=request.user,
            invoice=first_invoice,
            service_type='combined',
            service_details=combined_service_details,
            notes=summary_notes,
        )

        if result and result.get('success'):
            receipt = result['receipt']
            trans = result.get('transaction')

            if reference_number and trans:
                trans.reference_number = reference_number
                trans.save()

            # Single receipt per transaction (PaymentReceipt.transaction is OneToOne). Allocations
            # record the split; Invoice.calculate_totals() includes PaymentAllocation in total_paid.
            if to_allocate:
                try:
                    PaymentAllocation.allocate_payment(trans, to_allocate)
                except Exception as e:
                    logger.warning(f"Combined payment allocation (part payment): {e}")
            
            # Link the single combined receipt to each service (no extra receipts - one receipt only)
            failed_services = []
            for idx, service in enumerate(services_list):
                inv, release_rec = service_invoices.get(idx, (None, None))
                if inv and inv.balance <= 0 and release_rec:
                    link_deposit_receipt_to_release(None, release_rec, inv, request.user)
                    continue
                if not release_rec:
                    continue
                try:
                    # Link combined receipt to this service's release/dispensing record (one receipt for all)
                    release_rec.payment_receipt = receipt
                    release_rec.payment_verified_at = timezone.now()
                    release_rec.payment_verified_by = request.user
                    if hasattr(release_rec, 'release_status'):
                        release_rec.release_status = 'ready_for_release'
                    if hasattr(release_rec, 'dispensing_status'):
                        release_rec.dispensing_status = 'ready_to_dispense'
                    release_rec.save()
                    if service['type'] == 'imaging' and hasattr(service['obj'], 'mark_as_paid'):
                        try:
                            service['obj'].mark_as_paid(
                                service['price'],
                                receipt_number=receipt.receipt_number
                            )
                        except Exception:
                            pass
                    logger.info(f"✅ Linked combined receipt to {service['type']}: {service['name']}")
                except Exception as e:
                    failed_services.append({'type': service['type'], 'name': service['name'], 'error': str(e)})
                    logger.error(f"❌ Failed to link receipt to {service['type']} {service['name']}: {e}", exc_info=True)

            if failed_services:
                messages.warning(
                    request,
                    f"✅ One receipt issued: {receipt.receipt_number}. Amount paid: GHS {amount:.2f}. "
                    f"⚠️ {len(failed_services)} service(s) could not be linked (see logs)."
                )
            else:
                messages.success(
                    request,
                    f"✅ One receipt issued: {receipt.receipt_number}. Amount paid: GHS {amount:.2f} ({len(services_list)} service(s))."
                )

            # Prescriptions paid as part of encounter invoice: attach receipt to PharmacyDispensing
            try:
                from .services.pharmacy_invoice_payment_link import (
                    link_pharmacy_dispensing_when_invoice_paid,
                    link_walkin_sales_when_invoice_paid,
                )

                seen_pi = set()
                for idx, service in enumerate(services_list):
                    inv, _ = service_invoices.get(idx, (None, None))
                    if not inv or inv.pk in seen_pi:
                        continue
                    seen_pi.add(inv.pk)
                    inv.update_totals()
                    link_pharmacy_dispensing_when_invoice_paid(
                        inv,
                        receipt=receipt,
                        verified_by_user=request.user,
                        refresh_invoice=False,
                    )
                    link_walkin_sales_when_invoice_paid(inv, receipt=receipt, refresh_invoice=False)
            except Exception as e:
                logger.warning(f"Link pharmacy dispensing / walk-in sales after combined payment: {e}")

            return redirect('hospital:cashier_combined_bill_print', receipt_id=receipt.id)
        else:
            error_msg = result.get('message', result.get('error', 'Unknown error')) if result else 'No result returned'
            messages.error(request, f"❌ Payment failed: {error_msg}")
            logger.error(f"Combined payment failed for patient {patient.id}: {error_msg}")
    
    # Deposit balance for form display (use display helper so legacy 0/0 deposits count)
    patient_deposit_balance = Decimal('0.00')
    deposit_applied_to_bill = Decimal('0.00')
    try:
        from .services.deposit_payment_service import get_patient_deposit_balance_display
        patient_deposit_balance = get_patient_deposit_balance_display(patient)
        if services_list:
            _inv_ids = []
            for s in services_list:
                t, o = s.get('type'), s.get('obj')
                if t == 'invoice' and o:
                    _inv_ids.append(o.id)
                elif t == 'invoice_line' and o and getattr(o, 'invoice_id', None):
                    _inv_ids.append(o.invoice_id)
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
    # Single source of truth for outstanding (same as /patients/<id>/outstanding/)
    from .services.patient_outstanding_service import get_patient_outstanding
    outstanding_data = get_patient_outstanding(patient)
    patient_deposit_balance = outstanding_data['deposit_balance']
    total_outstanding = outstanding_data['total_outstanding']
    amount_due_after_deposit = outstanding_data['amount_due_after_deposit']
    initial_total = total_amount + deposit_applied_to_bill

    context = {
        'title': f'Process Combined Payment - {patient.full_name}',
        'patient': patient,
        'services': services_list,
        'total_amount': total_amount,
        'total_outstanding': total_outstanding,
        'amount_due_after_deposit': amount_due_after_deposit,
        'patient_deposit_balance': patient_deposit_balance,
        'service_count': len(services_list),
        'payment_methods': Transaction.PAYMENT_METHODS,
    }
    return render(request, 'hospital/cashier_combined_payment.html', context)


@login_required
@user_passes_test(is_cashier)
def cashier_combined_bill_print(request, receipt_id):
    """Print/view combined bill receipt - shows items paid for from receipt or QR. Prescribe Sale shows line-item breakdown."""
    import json
    from .models_payment_verification import ReceiptQRCode
    from .views_unified_payments import _receipt_items_paid_for
    receipt = get_object_or_404(PaymentReceipt, id=receipt_id, is_deleted=False)
    receipt_items = _receipt_items_paid_for(receipt)
    qr_code = None
    services = []
    # Prefer receipt.service_details so we get breakdown (e.g. Prescribe Sale line items) when stored
    details = getattr(receipt, 'service_details', None) or {}
    if isinstance(details, dict) and isinstance(details.get('services'), list):
        services = details['services']
    if not services:
        try:
            qr_code = ReceiptQRCode.objects.filter(receipt=receipt).first()
            if qr_code and qr_code.qr_code_data:
                service_details = json.loads(qr_code.qr_code_data) if isinstance(qr_code.qr_code_data, str) else (qr_code.qr_code_data or {})
                inner = service_details.get('service_details') if isinstance(service_details.get('service_details'), dict) else None
                if inner and isinstance(inner.get('services'), list):
                    services = inner['services']
                elif isinstance(service_details.get('services'), list):
                    services = service_details['services']
        except Exception:
            pass
    if not services and receipt_items:
        services = [{'name': it['description'], 'price': str(it['amount']), 'type': 'other'} for it in receipt_items]
    # All deposits on the patient's account for the invoice
    from .models_patient_deposits import PatientDeposit
    patient_deposits = list(
        PatientDeposit.objects.filter(
            patient=receipt.patient,
            is_deleted=False
        ).order_by('-deposit_date').select_related('received_by')
    )
    context = {
        'receipt': receipt,
        'patient': receipt.patient,
        'services': services,
        'receipt_items': receipt_items,
        'qr_code': qr_code,
        'patient_deposits': patient_deposits,
    }
    return render(request, 'hospital/cashier_combined_bill_print.html', context)


@login_required
@user_passes_test(can_add_manual_charges)
def cashier_add_manual_payment(request):
    """
    Add manual charges - reception adds for cashier to collect, or cashier adds & collects.
    Preset services: GP, Admission, Bed, Detainment, Dressing, Injection, ECG, etc.
    """
    from datetime import timedelta

    # Preset services. (label, cash_amount, insurance_amount, receipt_service_type)
    OTHER_SERVICES = {
        'registration_fee': ('Registration Fee', Decimal('50.00'), Decimal('50.00'), 'other'),
        'gp': ('General Consultation (GP)', Decimal('150.00'), Decimal('150.00'), 'consultation'),
        'admission': ('Admission', Decimal('150.00'), Decimal('150.00'), 'admission'),
        'bed': ('Bed Fee', Decimal('150.00'), Decimal('140.00'), 'bed'),
        'detainment': ('Detainment Fee', Decimal('150.00'), Decimal('140.00'), 'detainment'),
        'doctor_care': ('Doctor Care', Decimal('80.00'), Decimal('80.00'), 'other'),
        'nursing_care': ('Nursing Care', Decimal('70.00'), Decimal('70.00'), 'other'),
        'dressing': ('Dressing', Decimal('50.00'), Decimal('50.00'), 'other'),
        'injection': ('Injection', Decimal('20.00'), Decimal('20.00'), 'other'),
        'ecg': ('ECG', Decimal('80.00'), Decimal('80.00'), 'other'),
        'urinalysis': ('Urinalysis', Decimal('30.00'), Decimal('30.00'), 'other'),
        'xray': ('X-Ray', Decimal('60.00'), Decimal('60.00'), 'other'),
        'wound_care': ('Wound Care', Decimal('40.00'), Decimal('40.00'), 'other'),
        'delivery_fee': ('Delivery Fee', Decimal('2800.00'), Decimal('2800.00'), 'other'),
        'midwife_care': ('Midwife Care', Decimal('300.00'), Decimal('300.00'), 'other'),
    }
    
    if request.method == 'POST':
        patient_id = request.POST.get('patient_id', '').strip()
        service_type = request.POST.get('service_type', 'custom').strip()
        custom_service_name = (request.POST.get('custom_service_name', '') or '').strip()
        amount_str = request.POST.get('amount', '0').strip()
        payment_method = request.POST.get('payment_method', 'cash')
        notes = (request.POST.get('notes', '') or '').strip()
        charge_only = request.POST.get('charge_only') == '1'  # Add charge only, no payment (for reception)
        
        if not patient_id:
            messages.error(request, 'Please select a patient.')
            return redirect('hospital:cashier_add_manual_payment')
        
        try:
            patient = Patient.objects.get(pk=patient_id, is_deleted=False)
        except Patient.DoesNotExist:
            messages.error(request, 'Patient not found.')
            return redirect('hospital:cashier_add_manual_payment')
        
        try:
            amount = Decimal(amount_str)
        except (ValueError, TypeError):
            messages.error(request, 'Invalid amount.')
            return redirect('hospital:cashier_add_manual_payment')
        
        if amount <= 0:
            messages.error(request, 'Amount must be greater than zero.')
            return redirect('hospital:cashier_add_manual_payment')
        
        payer = patient.primary_insurance
        if not payer:
            payer, _ = Payer.objects.get_or_create(name='Cash', defaults={'payer_type': 'cash', 'is_active': True})
        
        if service_type in OTHER_SERVICES:
            label, cash_amt, ins_amt, receipt_service_type = OTHER_SERVICES[service_type]
            is_insurance = payer and getattr(payer, 'payer_type', None) in ('insurance', 'private', 'nhis', 'corporate')
            amount = ins_amt if is_insurance else cash_amt
            description = label
            service_code, _ = ServiceCode.objects.get_or_create(
                code={
                    'registration_fee': 'REG', 'gp': 'CON001', 'admission': 'ADM001', 'bed': 'BED001', 'detainment': 'DET001',
                    'doctor_care': 'ADM-DOCTOR-CARE', 'nursing_care': 'ADM-NURSING-CARE',
                    'dressing': 'DRS001', 'injection': 'INJ001', 'ecg': 'ECG001', 'urinalysis': 'URA001',
                    'xray': 'XR001', 'wound_care': 'WND001',
                    'delivery_fee': 'MAT-DELIVER', 'midwife_care': 'MAT-MIDWIFE',
                }.get(service_type, 'CASH-MISC'),
                defaults={
                    'description': description,
                    'category': 'Other' if service_type == 'custom' else 'Clinical Services',
                    'is_active': True,
                }
            )
            if not service_code.description or service_code.description == 'Cashier-Added Service':
                service_code.description = description
                service_code.save(update_fields=['description'])
        else:
            # custom
            if not custom_service_name:
                messages.error(request, 'Please enter the service name for custom service.')
                return redirect('hospital:cashier_add_manual_payment')
            service_code, _ = ServiceCode.objects.get_or_create(
                code='CASH-MISC',
                defaults={
                    'description': 'Cashier-Added Service',
                    'category': 'Other',
                    'is_active': True,
                }
            )
            description = custom_service_name[:200]
            receipt_service_type = 'other'
        
        try:
            from django.db import transaction
            with transaction.atomic():
                invoice = Invoice.objects.create(
                    patient=patient,
                    encounter=None,
                    payer=payer,
                    status='issued',
                    issued_at=timezone.now(),
                    due_at=timezone.now() + timedelta(days=7),
                )
                create_or_merge_invoice_line(
                    invoice=invoice,
                    service_code=service_code,
                    quantity=Decimal('1'),
                    unit_price=amount,
                    description=description,
                )
                invoice.update_totals()
                
                if charge_only:
                    messages.success(
                        request,
                        f'✅ Charge of GHS {amount} added for {patient.full_name} ({description}). '
                        f'Cashier will collect payment. Invoice #{invoice.invoice_number}'
                    )
                    return redirect('hospital:cashier_add_manual_payment')
                
                result = UnifiedReceiptService.create_receipt_with_qr(
                    patient=patient,
                    amount=amount,
                    payment_method=payment_method,
                    received_by_user=request.user,
                    invoice=invoice,
                    service_type=receipt_service_type,
                    service_details={'description': description, 'manual_add': True},
                    notes=notes or f'Manual payment - {description}',
                )
                
                receipt = result.get('receipt')
                if receipt:
                    messages.success(
                        request,
                        f'✅ Payment of GHS {amount} recorded for {description}. '
                        f'Receipt #{receipt.receipt_number}'
                    )
                    from django.urls import reverse
                    pos_url = reverse('hospital:receipt_pos_print', args=[receipt.id]) + '?auto_print=1'
                    return redirect(pos_url)
                else:
                    messages.success(request, f'✅ Payment of GHS {amount} recorded for {description}.')
        except Exception as e:
            logger.exception(f'Error in cashier_add_manual_payment: {e}')
            messages.error(request, f'Error recording payment: {str(e)}')
        
        return redirect('hospital:centralized_cashier_dashboard')
    
    return render(request, 'hospital/cashier_add_manual_payment.html', {
        'gp_price': Decimal('150.00'),
        'admission_price': Decimal('150.00'),
        'bed_price_cash': Decimal('150.00'),
        'bed_price_insurance': Decimal('140.00'),
        'detainment_price_cash': Decimal('150.00'),
        'detainment_price_insurance': Decimal('140.00'),
        'dressing_price': Decimal('50.00'),
        'injection_price': Decimal('20.00'),
        'ecg_price': Decimal('80.00'),
        'urinalysis_price': Decimal('30.00'),
        'xray_price': Decimal('60.00'),
        'wound_care_price': Decimal('40.00'),
        'registration_fee_price': Decimal('50.00'),
        'doctor_care_price': Decimal('80.00'),
        'nursing_care_price': Decimal('70.00'),
        'delivery_fee_price': Decimal('2800.00'),
        'midwife_care_price': Decimal('300.00'),
    })


@login_required
@user_passes_test(can_add_manual_charges)
def cashier_non_patient_charge(request):
    """Invoice and collect fees not tied to a patient chart (e.g. supplier registration)."""
    from datetime import timedelta
    import uuid
    from django.db import transaction

    NON_PATIENT_SERVICES = {
        'supplier_registration': ('Supplier registration', 'SUP-REG'),
        'supplier_annual_fee': ('Supplier annual / listing fee', 'SUP-ANNUAL'),
        'misc_admin': ('Administrative / filing fee', 'ADMIN-FEE'),
    }

    if request.method == 'POST':
        counterparty_name = (request.POST.get('counterparty_name') or '').strip()
        service_type = (request.POST.get('service_type') or 'custom').strip()
        custom_description = (request.POST.get('custom_description') or '').strip()
        amount_str = (request.POST.get('amount') or '0').strip()
        payment_method = request.POST.get('payment_method', 'cash')
        notes = (request.POST.get('notes') or '').strip()
        charge_only = request.POST.get('charge_only') == '1'
        idempotency_token = (request.POST.get('payment_idempotency_token') or '').strip()

        if not counterparty_name:
            messages.error(request, 'Payer name is required.')
            return redirect('hospital:cashier_non_patient_charge')

        try:
            amount = Decimal(amount_str)
        except (ValueError, TypeError):
            messages.error(request, 'Invalid amount.')
            return redirect('hospital:cashier_non_patient_charge')

        if amount <= 0:
            messages.error(request, 'Amount must be greater than zero.')
            return redirect('hospital:cashier_non_patient_charge')

        if service_type in NON_PATIENT_SERVICES:
            description, code = NON_PATIENT_SERVICES[service_type]
        elif service_type == 'custom':
            if not custom_description:
                messages.error(request, 'Please enter a description for custom charges.')
                return redirect('hospital:cashier_non_patient_charge')
            description = custom_description[:200]
            code = 'CASH-MISC'
        else:
            messages.error(request, 'Invalid charge type.')
            return redirect('hospital:cashier_non_patient_charge')

        payer, _ = Payer.objects.get_or_create(
            name='Cash',
            defaults={'payer_type': 'cash', 'is_active': True},
        )

        try:
            with transaction.atomic():
                invoice = Invoice.objects.create(
                    patient=None,
                    counterparty_name=counterparty_name,
                    encounter=None,
                    payer=payer,
                    status='issued',
                    issued_at=timezone.now(),
                    due_at=timezone.now() + timedelta(days=7),
                )
                service_code, _ = ServiceCode.objects.get_or_create(
                    code=code,
                    defaults={
                        'description': description,
                        'category': 'Administrative',
                        'is_active': True,
                    },
                )
                create_or_merge_invoice_line(
                    invoice=invoice,
                    service_code=service_code,
                    quantity=Decimal('1'),
                    unit_price=amount,
                    description=description,
                )
                invoice.update_totals()

                if charge_only:
                    messages.success(
                        request,
                        f'Charge of GHS {amount:,.2f} added for {counterparty_name} ({description}). '
                        f'Invoice #{invoice.invoice_number}',
                    )
                    return redirect('hospital:cashier_invoices')

                result = UnifiedReceiptService.create_receipt_with_qr(
                    patient=None,
                    amount=amount,
                    payment_method=payment_method,
                    received_by_user=request.user,
                    invoice=invoice,
                    service_type='other',
                    service_details={
                        'description': description,
                        'non_patient': True,
                        'counterparty_name': counterparty_name,
                    },
                    notes=notes or f'Non-patient charge - {description} - {counterparty_name}',
                    idempotency_token=idempotency_token or None,
                )

                if result.get('success') is False and result.get('error') == 'busy':
                    messages.warning(
                        request,
                        result.get(
                            'message',
                            'Payment is still processing. Check receipts before paying again.',
                        ),
                    )
                    return redirect('hospital:cashier_non_patient_charge')

                receipt = result.get('receipt')
                if receipt:
                    messages.success(
                        request,
                        f'Payment of GHS {amount:,.2f} recorded for {counterparty_name} ({description}). '
                        f'Receipt #{receipt.receipt_number}',
                    )
                    from django.urls import reverse
                    pos_url = reverse('hospital:receipt_pos_print', args=[receipt.id]) + '?auto_print=1'
                    return redirect(pos_url)

                messages.success(
                    request,
                    f'Payment of GHS {amount:,.2f} recorded for {counterparty_name}.',
                )
        except Exception as e:
            logger.exception('Error in cashier_non_patient_charge: %s', e)
            messages.error(request, f'Error recording charge: {e!s}')
            return redirect('hospital:cashier_non_patient_charge')

        return redirect('hospital:cashier_invoices')

    return render(
        request,
        'hospital/cashier_non_patient_charge.html',
        {'payment_idempotency_token': str(uuid.uuid4())},
    )


@login_required
def cashier_revenue_report(request):
    """Revenue report with accounting breakdown"""
    from .services.accounting_sync_service import AccountingSyncService
    
    date_str = request.GET.get('date', timezone.now().date().isoformat())
    try:
        report_date = timezone.datetime.strptime(date_str, '%Y-%m-%d').date()
    except:
        report_date = timezone.now().date()
    
    summary = AccountingSyncService.get_daily_revenue_summary(report_date)
    
    context = {
        'title': 'Revenue Report',
        'date': report_date,
        'today': timezone.now().date(),
        'summary': summary,
    }
    return render(request, 'hospital/cashier_revenue_report.html', context)

