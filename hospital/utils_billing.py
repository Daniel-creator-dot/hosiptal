"""
Utility functions for automatic billing and charge capture
"""
import logging
import re
from decimal import Decimal
from django.utils import timezone
from datetime import date, datetime, time, timedelta

from .models import Encounter, Invoice, InvoiceLine, ServiceCode, Payer, Patient
from .models_pricing import DefaultPrice, PayerPrice
from .services.pricing_engine_service import pricing_engine
from hospital.models_enterprise_billing import ServicePricing


logger = logging.getLogger(__name__)

# Corporate bill pack: sync encounter/claim charges onto invoices issued on or after this date
CORPORATE_PACK_VISIT_CHARGE_SYNC_FROM = date(2026, 3, 10)

# General (non-specialist) OPD consultation — flat rates; only specialist uses doctor/tier pricing.
GENERAL_CONSULTATION_CASH = Decimal('150.00')
GENERAL_CONSULTATION_CORPORATE = Decimal('160.00')


def is_gp_general_medicine_department(department):
    """
    True when staff belongs to General Medicine / GP OPD — use flat CON001 (150 cash / 160 corporate),
    not CON002 specialist baseline (300). Department titles that include the word 'specialist'
    (for example, 'General Medicine & Specialist OPD') still count as GP here.
    """
    if not department:
        return False
    name = (getattr(department, 'name', None) or '').strip().lower()
    code = (getattr(department, 'code', None) or '').strip().upper()
    if code in ('GEN', 'GM', 'GP', 'GPMED', 'GPM'):
        return True
    if 'general medicine' in name or 'general practice' in name or 'family medicine' in name:
        return True
    if name in ('gp', 'g.p.', 'internal medicine opd'):
        return True
    return False


def should_use_gp_flat_consultation_fee(encounter, doctor_staff):
    """
    When True, bill CON001 / flat GP rates. Excludes ER, gynae, and antenatal (those use other paths).
    """
    if not encounter or not doctor_staff:
        return False
    if not is_gp_general_medicine_department(getattr(doctor_staff, 'department', None)):
        return False
    et = (encounter.encounter_type or '').lower()
    if et in ('er', 'emergency', 'gynae'):
        return False
    if 'antenatal' in et:
        return False
    return True


def normalize_consultation_type_for_gp_department(encounter, consultation_type, doctor_staff):
    """Coerce mistaken 'specialist' to 'general' for General Medicine OPD."""
    if consultation_type != 'specialist':
        return consultation_type
    if should_use_gp_flat_consultation_fee(encounter, doctor_staff):
        return 'general'
    return consultation_type


def get_general_consultation_price_for_patient_and_payer(patient, payer=None):
    """
    General OPD (CON001): fixed cash walk-in rate (GENERAL_CONSULTATION_CASH); corporate
    prefers flexible PricingCategory corporate ServicePrice then GENERAL_CONSULTATION_CORPORATE.
    Returns None for insurance/NHIS/private so tiered pricing can use the engine.
    """
    if payer is None and patient is not None:
        payer = getattr(patient, 'primary_insurance', None)
    pt = getattr(payer, 'payer_type', None) if payer else None
    if pt in ('insurance', 'private', 'nhis'):
        return None

    use_corporate_rate = pt == 'corporate'
    if not use_corporate_rate and patient is not None:
        try:
            from hospital.models_enterprise_billing import CorporateEmployee

            if CorporateEmployee.objects.filter(patient=patient, is_active=True).exists():
                use_corporate_rate = True
        except Exception:
            pass

    if not use_corporate_rate:
        return GENERAL_CONSULTATION_CASH

    from hospital.models_flexible_pricing import ServicePrice, PricingCategory

    today = timezone.now().date()
    service_code = ServiceCode.objects.filter(code='CON001', is_deleted=False).first()
    if service_code:
        cat = PricingCategory.objects.filter(
            category_type='corporate', is_active=True, is_deleted=False
        ).order_by('priority').first()
        if cat:
            p = ServicePrice.get_price(service_code, cat, today)
            if p is not None and p > 0:
                return p

    return GENERAL_CONSULTATION_CORPORATE


def get_general_consultation_price_for_payer(payer):
    """Payer-only helper (no corporate-employee record check)."""
    from hospital.models_flexible_pricing import ServicePrice, PricingCategory

    if not payer:
        return GENERAL_CONSULTATION_CASH
    pt = getattr(payer, 'payer_type', None)
    if pt in ('insurance', 'private', 'nhis'):
        return None

    if pt != 'corporate':
        return GENERAL_CONSULTATION_CASH

    today = timezone.now().date()
    service_code = ServiceCode.objects.filter(code='CON001', is_deleted=False).first()

    if service_code:
        cat = PricingCategory.objects.filter(
            category_type='corporate', is_active=True, is_deleted=False
        ).order_by('priority').first()
        if cat:
            p = ServicePrice.get_price(service_code, cat, today)
            if p is not None and p > 0:
                return p

    return GENERAL_CONSULTATION_CORPORATE

# Strip trailing legal forms so "Acme Ltd" and "Acme Limited" share one company-bills group (all companies).
_LEGAL_SUFFIX_CHUNK_RE = re.compile(
    r'\s*,?\s*'
    r'(?:ltd\.?|limited|plc\.?|inc\.?|incorporated|corp\.?|corporation|llc\.?|g\.?\s*i\.?\s*e\.?)\s*$',
    re.IGNORECASE,
)


def _strip_trailing_legal_suffixes(s):
    s = (s or '').strip().rstrip(',').strip()
    while s:
        new_s = _LEGAL_SUFFIX_CHUNK_RE.sub('', s).strip().rstrip(',').strip()
        if new_s == s:
            break
        s = new_s
    return s


def _normalize_company_name_for_consolidation(name):
    if not name:
        return ''
    s = str(name).strip()
    s = s.replace('\u00a0', ' ').replace('\u2013', '-').replace('\u2014', '-')
    s = s.lower()
    s = re.sub(r"['’]", '', s)
    s = re.sub(r'\s+', ' ', s)
    s = _strip_trailing_legal_suffixes(s)
    s = re.sub(r'\s+', ' ', s)
    return s.strip()


# Merge duplicate corporate payer spellings into one row on company bill lists.
# Variants are plain names; _company_consolidation_match_key() normalizes them consistently
# (legal suffixes, "the ", &, /, *, trailing "(ECG)"-style acronyms, etc.).
_CORPORATE_COMPANY_ALIAS_RAW = (
    (
        'Electricity Company of Ghana',
        (
            'Electricity Company of Ghana',
            'ECG Electricity Company of Ghana',
            'ECG / Power Distribution Service',
            'ECG/Power Distribution Service',
            'ECG Power Distribution Service',
            'ECG*electricity company of ghana',
            'ECG*Electricity Company of Ghana',
            'Electricity Company of Ghana (ECG)',
            'ECG',
        ),
    ),
    (
        'Anointed Electrical Company',
        (
            'Anointed Electrical',
            'Anointed Electrical Company',
            'Anointed Electricals',
            'Anointed Electricals Limited',
            'ANOINTED ELECTRICALS',
        ),
    ),
    (
        'Ghana Commercial Bank',
        (
            'Ghana Commercial Bank',
            'Ghana Commercial Bank GCB',
            'GCB Ghana Commercial Bank',
            'GCB',
            'GCB Bank',
            'The Ghana Commercial Bank',
            'Ghana Commercial Bank (GCB)',
        ),
    ),
    (
        'Volta River Authority',
        (
            'Volta River Authority',
            'VRA',
            'V.R.A.',
            'The Volta River Authority',
        ),
    ),
    (
        'Ghana Grid Company',
        (
            'Ghana Grid Company',
            'Ghana Grid Company Limited',
            'GRIDCo',
            'GRIDCO',
        ),
    ),
    (
        'Ghana Water Company',
        (
            'Ghana Water Company',
            'Ghana Water Company Limited',
            'Ghana Water',
            'GWCL',
            'GWC',
        ),
    ),
    (
        'Ghana National Petroleum Corporation',
        (
            'Ghana National Petroleum Corporation',
            'GNPC',
            'Ghana National Petroleum',
        ),
    ),
    (
        'Social Security and National Insurance Trust',
        (
            'Social Security and National Insurance Trust',
            'SSNIT',
            'S.S.N.I.T.',
        ),
    ),
    (
        'Ghana Cocoa Board',
        (
            'Ghana Cocoa Board',
            'COCOBOD',
            'Cocoa Board',
        ),
    ),
    (
        'Ghana Ports and Harbours Authority',
        (
            'Ghana Ports and Harbours Authority',
            'GPHA',
            'Ghana Ports & Harbours Authority',
        ),
    ),
    (
        'Bulk Oil Storage and Transportation Company',
        (
            'Bulk Oil Storage and Transportation Company',
            'Bulk Oil Storage and Transportation',
            'BOST',
        ),
    ),
    (
        'Tema Oil Refinery',
        (
            'Tema Oil Refinery',
            'TOR',
        ),
    ),
    (
        'Agricultural Development Bank',
        (
            'Agricultural Development Bank',
            'Agricultural Development Bank Limited',
            'ADB',
            'ADB Bank',
        ),
    ),
    (
        'National Service Scheme',
        (
            'National Service Scheme',
            'National Service Secretariat',
            'NSS',
        ),
    ),
    (
        'Primecare Medical Center',
        (
            'Primecare Medical Center',
            'Primecare Medical Centre',
            'Primecare',
            'Prime Care',
        ),
    ),
)


def _company_consolidation_match_key(name):
    """
    Normalized key for alias matching and default grouping.
    Collapses common duplicate forms: the/, *, &, slashes, trailing (ABC) acronyms.
    """
    raw = (name or '').strip()
    n = _normalize_company_name_for_consolidation(raw)
    if not n:
        return ''
    t = re.sub(r'^\s*the\s+', '', n)
    t = t.replace('&', ' and ')
    t = t.replace('*', ' ')
    t = re.sub(r'[/\\]+', ' ', t)
    t = re.sub(r'\s+', ' ', t).strip()
    # Trailing parenthetical acronym e.g. "Electricity Company of Ghana (ECG)"
    t = re.sub(r'\s*\(([a-z]{2,12})\)\s*$', '', t, flags=re.IGNORECASE)
    t = re.sub(r'\s+', ' ', t).strip()
    # Dotted acronyms: V.R.A., S.S.N.I.T. → vra, ssnit
    if len(t) <= 32 and re.match(r'^([a-z]\.)+[a-z]\.?$', t):
        t = t.replace('.', '')
    t = re.sub(r'\s+', ' ', t).strip()
    return t


def _build_corporate_alias_groups():
    out = []
    for display, variants in _CORPORATE_COMPANY_ALIAS_RAW:
        keys = frozenset(_company_consolidation_match_key(v) for v in variants if v)
        keys = frozenset(k for k in keys if k)
        out.append((display, keys))
    return tuple(out)


_CORPORATE_COMPANY_ALIAS_GROUPS = _build_corporate_alias_groups()


def consolidated_corporate_company_group(name):
    """
    Map a raw company / payer label to (group_key, display_name) for grouping list rows.
    group_key is stable lowercase; display_name is the preferred label shown in the UI.
    """
    raw = (name or '').strip()
    k = _company_consolidation_match_key(raw)
    if not k:
        return 'n/a', 'N/A'
    for display, alias_keys in _CORPORATE_COMPANY_ALIAS_GROUPS:
        if k in alias_keys:
            return display.lower(), display
    if k.startswith('ghana commercial bank'):
        return 'ghana commercial bank', 'Ghana Commercial Bank'
    if k == 'gcb' or re.match(r'^gcb([\s\-/]|$)', k):
        return 'ghana commercial bank', 'Ghana Commercial Bank'
    if len(k) <= 32 and re.sub(r'[\s.\-/]+', '', k) == 'gcb':
        return 'ghana commercial bank', 'Ghana Commercial Bank'
    if k == 'ecg' or re.match(r'^ecg([\s\-/]|$)', k):
        return 'electricity company of ghana', 'Electricity Company of Ghana'
    if re.match(r'^anointed electric', k):
        return 'anointed electrical company', 'Anointed Electrical Company'
    for token in ('assougyaman', 'assuogyaman', 'asuogyaman', 'assougyman'):
        if token in k:
            return 'assougyaman', 'Assougyaman'
    if (
        re.match(r'^prime[\s\-]?care(\s|$)', k)
        or k == 'primecare'
        or re.match(r'^primecare medical', k)
    ):
        return 'primecare medical center', 'Primecare Medical Center'
    return k, raw


def all_corporate_payer_ids_for_consolidation_group_key(group_key):
    """
    All corporate Payer PKs whose name maps to the same consolidation key as company bills.
    Used to open one Detail/Excel pack covering every merged alias payer (server-side, reliable).
    """
    gk = (group_key or '').strip().lower()
    if not gk:
        return []
    found = set()
    for p in Payer.objects.filter(payer_type='corporate', is_deleted=False).only('id', 'name'):
        k, _ = consolidated_corporate_company_group(p.name)
        if k == gk:
            found.add(p.pk)
    return sorted(found, key=lambda u: str(u))


def local_datetime_bounds_for_date(d):
    """
    Inclusive start and exclusive end (timezone-aware) for the hospital's current timezone calendar day.
    Use instead of __date lookups on UTC-stored datetimes so "today" matches staff expectations.
    """
    tz = timezone.get_current_timezone()
    start = timezone.make_aware(datetime.combine(d, time.min), tz)
    return start, start + timedelta(days=1)


def infer_encounter_for_invoice_visit_day(invoice):
    """
    Resolve the visit encounter for an invoice: prefer invoice.encounter, else same local calendar
    day as issued_at (OPD/corporate pharmacy bills often need this for pack sync).
    """
    if not invoice or not invoice.patient_id or not getattr(invoice, 'issued_at', None):
        return None
    enc = getattr(invoice, 'encounter', None)
    if enc and not getattr(enc, 'is_deleted', False) and getattr(enc, 'status', None) != 'cancelled':
        return enc
    ld = timezone.localtime(invoice.issued_at).date()
    start, end = local_datetime_bounds_for_date(ld)
    return (
        Encounter.objects.filter(
            patient_id=invoice.patient_id,
            is_deleted=False,
        )
        .exclude(status='cancelled')
        .filter(started_at__gte=start, started_at__lt=end)
        .order_by('-started_at')
        .first()
    )


def try_link_invoice_to_encounter(invoice, encounter):
    """
    Set invoice.encounter when it is empty and no other non-deleted invoice already uses encounter.
    """
    if not invoice or not encounter or getattr(invoice, 'is_deleted', False):
        return False
    if getattr(encounter, 'is_deleted', False):
        return False
    if invoice.encounter_id:
        return str(invoice.encounter_id) == str(encounter.id)
    conflict = (
        Invoice.all_objects.filter(encounter_id=encounter.id, is_deleted=False)
        .exclude(pk=invoice.pk)
        .exists()
    )
    if conflict:
        return False
    invoice.encounter = encounter
    invoice.save(update_fields=['encounter', 'modified'])
    return True


# Consultation-like invoice lines (OPD + antenatal + legacy/import codes). Cashier and payer sync must use the same set.
CONSULTATION_LINE_SERVICE_CODES = ('CON001', 'CON002', 'MAT-ANC', 'S00023', 'CONS-GEN')

# Lines billed at general OPD policy (150/160 cash/corp when encounter is general OPD); includes legacy S00023.
GENERAL_OPD_LINE_SERVICE_CODES = frozenset(
    c.upper() for c in ('CON001', 'CONS-GEN', 'CONSULTATION_GENERAL', 'S00023')
)

_CONSULTATION_LINE_CODES_UPPER = frozenset(c.strip().upper() for c in CONSULTATION_LINE_SERVICE_CODES if c)


def invoice_line_display_category(line):
    """
    Section title when grouping invoice lines (corporate bill pack, invoice detail, exports).

    CON001/CON002 are created with ServiceCode.category 'Clinical Services' in add_consultation_charge;
    without normalization, accountants look for 'Consultation' and think the fee is missing.
    """
    sc = getattr(line, 'service_code', None)
    if not sc:
        return 'Other'
    code = (sc.code or '').strip().upper()
    if code in _CONSULTATION_LINE_CODES_UPPER:
        return 'Consultation'
    if code.startswith(('LAB-', 'LABTEST-')) or code == 'URA001':
        return 'Laboratory'
    cat = (sc.category or '').strip()
    cat_cf = cat.casefold()
    if 'laborat' in cat_cf or cat_cf in (
        'pathology',
        'microbiology',
        'histology',
        'biochemistry',
        'hematology',
        'immunology',
        'serology',
    ):
        return 'Laboratory'
    if 'consult' in cat_cf:
        return 'Consultation'
    # Non-pharmacy lines whose description is clearly a consultation fee
    if not getattr(line, 'prescription_id', None):
        desc = (getattr(line, 'description', None) or '').casefold()
        if 'consultation' in desc:
            return 'Consultation'
    return cat if cat else 'Other'


def consultation_line_display_amount(line):
    """
    Amount for cashier display: matches Invoice.calculate_totals per line (qty×unit − discount + tax).
    Prefer over line.line_total when line_total is stale or zero but unit_price is set.
    """
    if not line or getattr(line, 'waived_at', None):
        return None
    qty = Decimal(str(line.quantity or 1))
    unit = Decimal(str(line.unit_price or 0))
    return qty * unit - Decimal(str(line.discount_amount or 0)) + Decimal(str(line.tax_amount or 0))


def get_mat_anc_consultation_price(patient, payer):
    """
    Antenatal MAT-ANC price for display or payer change. Matches add_consultation_charge (default 235 GHC).
    """
    try:
        antenatal_code = ServiceCode.objects.filter(code='MAT-ANC', is_active=True).first()
        if antenatal_code:
            p = pricing_engine.get_service_price(
                service_code=antenatal_code,
                patient=patient,
                payer=payer,
            )
            if p and p > 0:
                return p
    except Exception:
        pass
    return Decimal('235.00')


def _active_patient_insurances_for_badges(patient, limit=5):
    """Active PatientInsurance rows for payer badges; uses prefetch cache when present."""
    cache = getattr(patient, '_prefetched_objects_cache', None)
    if cache and 'insurances' in cache:
        rows = [
            x
            for x in patient.insurances.all()
            if getattr(x, 'status', None) == 'active' and not getattr(x, 'is_deleted', False)
        ]
        rows.sort(
            key=lambda x: (not getattr(x, 'is_primary', False), getattr(x, 'created', None) or ''),
            reverse=True,
        )
        return rows[:limit]
    try:
        from .models_insurance_companies import PatientInsurance

        return list(
            PatientInsurance.objects.filter(
                patient=patient,
                status='active',
                is_deleted=False,
            )
            .select_related('insurance_company')
            .order_by('-is_primary', '-created')[:limit]
        )
    except Exception:
        return []


def _corporate_employee_for_enrollment_name(patient):
    """Same selection as corporate_enrollment_company_name ORM path; prefetch-aware."""
    cache = getattr(patient, '_prefetched_objects_cache', None)
    if cache and 'corporate_enrollments' in cache:
        rows = [
            x
            for x in patient.corporate_enrollments.all()
            if not x.is_deleted and x.corporate_account_id
        ]
        if not rows:
            return None
        active = [x for x in rows if x.is_active]
        pool = active if active else rows
        pool.sort(
            key=lambda x: (x.is_active, x.enrollment_date or date.min),
            reverse=True,
        )
        return pool[0]
    try:
        from .models_enterprise_billing import CorporateEmployee

        emp = (
            CorporateEmployee.objects.filter(
                patient=patient,
                is_active=True,
                is_deleted=False,
                corporate_account__isnull=False,
            )
            .select_related('corporate_account')
            .first()
        )
        if not emp:
            emp = (
                CorporateEmployee.objects.filter(
                    patient=patient,
                    is_deleted=False,
                    corporate_account__isnull=False,
                )
                .select_related('corporate_account')
                .order_by('-is_active', '-enrollment_date')
                .first()
            )
        return emp
    except Exception:
        return None


def _corporate_employee_for_billing_ref(patient):
    """order_by('-is_active', '-enrollment_date').first() — prefetch-aware."""
    cache = getattr(patient, '_prefetched_objects_cache', None)
    if cache and 'corporate_enrollments' in cache:
        rows = [x for x in patient.corporate_enrollments.all() if not x.is_deleted]
        if not rows:
            return None
        rows.sort(
            key=lambda x: (x.is_active, x.enrollment_date or date.min),
            reverse=True,
        )
        return rows[0]
    try:
        from .models_enterprise_billing import CorporateEmployee

        return (
            CorporateEmployee.objects.filter(patient=patient, is_deleted=False)
            .select_related('corporate_account')
            .order_by('-is_active', '-enrollment_date')
            .first()
        )
    except Exception:
        return None


def patient_payer_display_labels(patient, encounter=None):
    """
    All distinct non-cash payer / company names for UI badges (any department).
    Merges visit invoice, patient primary payer, corporate enrollment, and primary PatientInsurance
    so corporate is not dropped when the encounter invoice is insurance-only.
    """
    if not patient:
        return []
    seen = set()
    out = []

    def push(text):
        t = (text or '').strip()
        if not t or t.lower() == 'cash':
            return
        key = t.lower()
        if key in seen:
            return
        seen.add(key)
        out.append(t)

    if encounter:
        inv = None
        try:
            for c in getattr(encounter, '_prefetched_objects_cache', {}).get('invoices', ()):
                if c and not getattr(c, 'is_deleted', False):
                    inv = c
                    break
        except Exception:
            inv = None
        if inv is None:
            inv = (
                Invoice.all_objects.filter(encounter=encounter, is_deleted=False)
                .select_related('payer')
                .order_by('-created')
                .first()
            )
        if inv and inv.payer and not getattr(inv.payer, 'is_deleted', False):
            pt = (getattr(inv.payer, 'payer_type', '') or '').strip().lower()
            nm = (getattr(inv.payer, 'name', '') or '').strip()
            if pt != 'cash':
                push(nm)
            elif nm and nm.lower() != 'cash':
                # Invoice billed to a payer row stored as cash but named (e.g. corporate / scheme)
                push(nm)

    pi = getattr(patient, 'primary_insurance', None)
    if pi and not getattr(pi, 'is_deleted', False):
        pt = (getattr(pi, 'payer_type', '') or '').strip().lower()
        nm = (getattr(pi, 'name', '') or '').strip()
        if pt != 'cash':
            push(nm)
        elif nm and nm.lower() != 'cash':
            # Payer row mis-typed as cash but name is a company / insurer
            push(nm)

    push(corporate_enrollment_company_name(patient))

    try:
        for pip in _active_patient_insurances_for_badges(patient, 5):
            if pip.insurance_company:
                push(getattr(pip.insurance_company, 'name', None))
    except Exception:
        pass

    if not out:
        legacy = (getattr(patient, 'insurance_company', '') or '').strip()
        if legacy and legacy.lower() not in ('cash', 'none', 'n/a', '-', ''):
            push(legacy)

    return out


def patient_non_cash_billing_context(patient, encounter=None):
    """True if patient or this visit bills to a non-cash payer (for showing policy/member badges)."""
    if not patient:
        return False
    pi = getattr(patient, 'primary_insurance', None)
    if pi and not getattr(pi, 'is_deleted', False):
        if (getattr(pi, 'payer_type', '') or '').strip().lower() != 'cash':
            return True
    if encounter:
        inv = (
            Invoice.all_objects.filter(encounter=encounter, is_deleted=False)
            .select_related('payer')
            .order_by('-created')
            .first()
        )
        if (
            inv
            and inv.payer
            and not getattr(inv.payer, 'is_deleted', False)
            and (getattr(inv.payer, 'payer_type', '') or '').strip().lower() != 'cash'
        ):
            return True
    return False


def patient_billing_member_id_display(patient, payer=None):
    """
    Single ID string for bills/claims tables: insurance member/policy ID, or corporate employee ID.
    """
    if not patient:
        return ''
    payer_type = ''
    if payer is not None:
        payer_type = (getattr(payer, 'payer_type', None) or '').strip().lower()
    ins_id = (
        (getattr(patient, 'insurance_id', None) or '').strip()
        or (getattr(patient, 'insurance_member_id', None) or '').strip()
        or (getattr(patient, 'insurance_policy_number', None) or '').strip()
    )
    if payer_type == 'corporate':
        try:
            emp = _corporate_employee_for_billing_ref(patient)
            if emp:
                eid = (getattr(emp, 'employee_id', None) or '').strip()
                if eid:
                    return eid
        except Exception:
            pass
    if ins_id:
        return ins_id
    if payer_type != 'corporate':
        try:
            emp = _corporate_employee_for_billing_ref(patient)
            if emp:
                eid = (getattr(emp, 'employee_id', None) or '').strip()
                if eid:
                    return eid
        except Exception:
            pass
    return ''


def patient_bill_payer_details(patient, payer=None):
    """
    Company, plan, and member/corporate ID for combined bills and print statements.
    payer: optional invoice payer; falls back to get_patient_payer_info when omitted.
    """
    if not patient:
        return {
            'company_name': 'Cash',
            'plan_name': '',
            'member_or_policy_number': '',
            'payer_type': 'cash',
            'is_cash': True,
            'is_corporate': False,
        }

    payer_info = get_patient_payer_info(patient)
    if payer is None:
        payer = payer_info.get('payer')

    payer_type = ''
    if payer and not getattr(payer, 'is_deleted', False):
        payer_type = (getattr(payer, 'payer_type', '') or '').strip().lower()
    if not payer_type:
        payer_type = (payer_info.get('type') or '').strip().lower()
    if payer_type == 'insurance':
        payer_type = 'private'

    company = ''
    if payer and not getattr(payer, 'is_deleted', False):
        company = (getattr(payer, 'name', '') or '').strip()
    if not company:
        pn = (payer_info.get('name') or '').strip()
        if pn and pn.lower() != 'cash':
            company = pn
    legacy_co = (getattr(patient, 'insurance_company', '') or '').strip()
    if not company and legacy_co and legacy_co.lower() not in ('cash', 'n/a', 'na', 'none'):
        company = legacy_co

    plan_name = ''
    member_number = ''

    if payer_type == 'corporate':
        emp = _corporate_employee_for_billing_ref(patient)
        if emp:
            member_number = (getattr(emp, 'employee_id', '') or '').strip()
            dept = (getattr(emp, 'department', '') or '').strip()
            if dept:
                plan_name = dept
        if not member_number:
            member_number = patient_billing_member_id_display(patient, payer)
        if not plan_name:
            plan_name = (getattr(patient, 'insurance_group_number', '') or '').strip()
    elif payer_type in ('nhis', 'private'):
        try:
            from .models_insurance_companies import PatientInsurance

            pi = (
                PatientInsurance.objects.filter(
                    patient=patient, status='active', is_deleted=False
                )
                .select_related('insurance_plan', 'insurance_company')
                .order_by('-is_primary', '-created')
                .first()
            )
            if pi:
                if pi.insurance_plan:
                    plan_name = (getattr(pi.insurance_plan, 'plan_name', '') or '').strip()
                if not company and pi.insurance_company:
                    company = (pi.insurance_company.name or '').strip()
                member_number = (
                    (pi.member_id or '').strip()
                    or (pi.policy_number or '').strip()
                    or (pi.group_number or '').strip()
                )
        except Exception:
            pass
        if not member_number:
            member_number = (
                (getattr(patient, 'insurance_id', '') or '').strip()
                or (getattr(patient, 'insurance_member_id', '') or '').strip()
                or (getattr(patient, 'insurance_policy_number', '') or '').strip()
            )
        if not plan_name:
            plan_name = (getattr(patient, 'insurance_group_number', '') or '').strip()

    is_cash = payer_type == 'cash' or (
        not company and not member_number and payer_type not in ('nhis', 'private', 'corporate')
    )
    if is_cash and not company:
        company = 'Cash'

    is_insurance_or_corporate = payer_type in ('nhis', 'private', 'corporate')
    return {
        'company_name': company,
        'plan_name': plan_name,
        'member_or_policy_number': member_number,
        'payer_type': payer_type,
        'is_cash': is_cash,
        'is_corporate': payer_type == 'corporate',
        'is_insurance_or_corporate': is_insurance_or_corporate,
    }


def _format_bill_diagnosis_entry(text, code=''):
    text = (text or '').strip()
    code = (code or '').strip()
    if text and code:
        return f'{text} ({code})'
    return text or code


def patient_bill_diagnoses_for_display(patient, invoices=None):
    """
    Diagnosis lines for insurance/corporate combined bills (encounters on unpaid invoices).
    Returns {'items': [...], 'display_text': '...'}.
    """
    if not patient:
        return {'items': [], 'display_text': ''}

    encounter_ids = set()
    if invoices:
        for inv in invoices:
            eid = getattr(inv, 'encounter_id', None)
            if eid:
                encounter_ids.add(eid)

    seen = set()
    items = []
    type_rank = {'primary': 0, 'secondary': 1, 'differential': 2}

    try:
        from .models_advanced import Diagnosis

        dx_qs = Diagnosis.objects.filter(patient=patient, is_deleted=False).select_related(
            'diagnosis_code', 'encounter'
        )
        if encounter_ids:
            dx_qs = dx_qs.filter(encounter_id__in=encounter_ids)
        else:
            dx_qs = dx_qs.order_by('-diagnosis_date')[:15]

        dx_rows = list(dx_qs)
        dx_rows.sort(
            key=lambda d: (
                type_rank.get((d.diagnosis_type or '').strip().lower(), 9),
                -(d.diagnosis_date.timestamp() if d.diagnosis_date else 0),
            )
        )
        for dx in dx_rows:
            text = (getattr(dx, 'diagnosis_name', None) or dx.diagnosis or '').strip()
            code = (getattr(dx, 'display_code', None) or '').strip()
            if not text and not code:
                continue
            key = (code.lower(), text.lower())
            if key in seen:
                continue
            seen.add(key)
            items.append(
                {
                    'text': text,
                    'code': code,
                    'display': _format_bill_diagnosis_entry(text, code),
                }
            )
    except Exception:
        pass

    if encounter_ids:
        try:
            from .models import Encounter

            for enc in Encounter.objects.filter(
                pk__in=encounter_ids, is_deleted=False
            ).only('pk', 'diagnosis'):
                raw = (enc.diagnosis or '').strip()
                if not raw:
                    continue
                for chunk in raw.split('\n'):
                    line = chunk.strip()
                    if not line or len(line) < 2:
                        continue
                    key = ('', line.lower())
                    if key in seen:
                        continue
                    seen.add(key)
                    items.append({'text': line, 'code': '', 'display': line})
        except Exception:
            pass

    display_text = '; '.join(i['display'] for i in items if i.get('display'))
    return {'items': items, 'display_text': display_text}


def batch_patient_billing_member_ids(patients_by_id, payer_by_patient_id=None):
    """patient_id -> insurance or corporate ID for list tables."""
    payer_by_patient_id = payer_by_patient_id or {}
    out = {}
    for pid, patient in patients_by_id.items():
        if not patient:
            continue
        payer = payer_by_patient_id.get(pid)
        out[pid] = patient_billing_member_id_display(patient, payer)
    return out


def _short_payer_uuid_ref(value):
    if not value:
        return ''
    return str(value).replace('-', '')[:8].upper()


def _names_match_for_corporate_link(payer_name, company_name):
    if not payer_name or not company_name:
        return False
    pn, cn = payer_name.strip().lower(), company_name.strip().lower()
    return pn == cn or pn in cn or cn in pn


def corporate_payer_reference_lookup(payer_ids):
    """Map payer UUID -> company_code, accounting account #, short payer ref."""
    from hospital.models_enterprise_billing import CorporateAccount, MonthlyStatement

    payer_ids = [p for p in payer_ids if p]
    if not payer_ids:
        return {}
    lookup = {
        pid: {'company_code': '', 'account_number': '', 'payer_ref': _short_payer_uuid_ref(pid)}
        for pid in payer_ids
    }
    for row in (
        MonthlyStatement.objects.filter(
            payer_id__in=payer_ids,
            corporate_account__isnull=False,
            is_deleted=False,
        )
        .values('payer_id', 'corporate_account__company_code')
        .distinct()
    ):
        code = (row.get('corporate_account__company_code') or '').strip()
        if code and row['payer_id']:
            lookup[row['payer_id']]['company_code'] = code

    payer_names = dict(Payer.objects.filter(pk__in=payer_ids).values_list('id', 'name'))
    corp_by_name = list(
        CorporateAccount.objects.filter(is_deleted=False).values('company_name', 'company_code')
    )
    acct_by_name = []
    try:
        from hospital.models_accounting_advanced import AccountingCorporateAccount

        acct_by_name = list(
            AccountingCorporateAccount.objects.filter(is_active=True).values(
                'company_name', 'account_number'
            )
        )
    except Exception:
        pass

    for pid, pname in payer_names.items():
        if not lookup[pid]['company_code']:
            for acc in corp_by_name:
                if _names_match_for_corporate_link(pname, acc['company_name']):
                    lookup[pid]['company_code'] = (acc['company_code'] or '').strip()
                    break
        if not lookup[pid]['account_number']:
            for acc in acct_by_name:
                if _names_match_for_corporate_link(pname, acc['company_name']):
                    lookup[pid]['account_number'] = (acc['account_number'] or '').strip()
                    break
    return lookup


def format_corporate_reference_label(ref):
    ref = ref or {}
    parts = []
    code = (ref.get('company_code') or '').strip()
    acct = (ref.get('account_number') or '').strip()
    pref = (ref.get('payer_ref') or '').strip()
    if code:
        parts.append(code)
    if acct and acct != code:
        parts.append(f'Acct {acct}')
    if pref and not code:
        parts.append(f'Payer {pref}')
    return ' · '.join(parts)


def patient_payer_billing_ref_parts(patient, encounter=None):
    """
    Short strings for policy / member / employee references shown next to payer name badges
    (corporate and insurance) on dashboards.
    """
    if not patient or not patient_non_cash_billing_context(patient, encounter):
        return []

    parts = []
    oid = (getattr(patient, 'insurance_id', None) or '').strip()
    if oid:
        parts.append(f'Policy/ID: {oid}')
    mid = (getattr(patient, 'insurance_member_id', None) or '').strip()
    if mid:
        parts.append(f'Member: {mid}')
    pol2 = (getattr(patient, 'insurance_policy_number', None) or '').strip()
    if pol2 and pol2 != oid:
        parts.append(f'Policy#: {pol2}')
    grp = (getattr(patient, 'insurance_group_number', None) or '').strip()
    if grp:
        parts.append(f'Group: {grp}')

    # Insurance plan (from PatientInsurance enrollment, if set)
    try:
        from .models_insurance_companies import PatientInsurance

        scope_ids = _patient_billing_scope_ids(patient)
        pi = (
            PatientInsurance.objects.filter(
                patient_id__in=scope_ids,
                status='active',
                is_deleted=False,
            )
            .select_related('insurance_plan')
            .order_by('-is_primary', '-effective_date', '-created')
            .first()
        )
        plan_name = (getattr(getattr(pi, 'insurance_plan', None), 'plan_name', None) or '').strip()
        if plan_name:
            parts.append(f'Plan: {plan_name}')
    except Exception:
        pass

    pi = getattr(patient, 'primary_insurance', None)
    if pi and (getattr(pi, 'payer_type', '') or '').strip().lower() == 'corporate':
        try:
            emp = _corporate_employee_for_billing_ref(patient)
            if emp:
                eid = (getattr(emp, 'employee_id', None) or '').strip()
                if eid and eid != mid and eid != oid:
                    parts.append(f'Emp ID: {eid}')
        except Exception:
            pass

    return parts


# Backward-compatible alias (pharmacy dashboard and older imports)
pharmacy_payer_display_labels = patient_payer_display_labels


def corporate_enrollment_company_name(patient):
    """
    Active corporate employer name from CorporateEmployee, if any.
    Used for pharmacy badges and as a fallback when primary payer is still cash.
    """
    if not patient:
        return None
    try:
        emp = _corporate_employee_for_enrollment_name(patient)
        if emp and emp.corporate_account:
            name = (emp.corporate_account.company_name or '').strip()
            return name or None
    except Exception:
        pass
    return None


def _patient_billing_scope_ids(patient):
    """All active Patient PKs sharing this MRN (merged clinical/billing identity)."""
    if not patient:
        return []
    ids = [patient.pk]
    mrn = (getattr(patient, 'mrn', None) or '').strip()
    if not mrn:
        return ids
    try:
        found = list(Patient.objects.filter(mrn=mrn, is_deleted=False).values_list('pk', flat=True))
        return found or ids
    except Exception:
        return ids


def _corporate_enrollment_company_name_for_patient_ids(patient_pks):
    """Corporate employer name from any enrollment row tied to these patient IDs."""
    if not patient_pks:
        return None
    try:
        from .models_enterprise_billing import CorporateEmployee

        emp = (
            CorporateEmployee.objects.filter(
                patient_id__in=patient_pks,
                is_active=True,
                is_deleted=False,
                corporate_account__isnull=False,
            )
            .select_related('corporate_account')
            .order_by('-enrollment_date', '-id')
            .first()
        )
        if not emp:
            emp = (
                CorporateEmployee.objects.filter(
                    patient_id__in=patient_pks,
                    is_deleted=False,
                    corporate_account__isnull=False,
                )
                .select_related('corporate_account')
                .order_by('-is_active', '-enrollment_date', '-id')
                .first()
            )
        if emp and emp.corporate_account:
            return (emp.corporate_account.company_name or '').strip() or None
    except Exception:
        pass
    return None


def get_patient_payer_info(patient, encounter=None):
    """
    Determine payer for a patient. Checks encounter invoice, primary_insurance,
    CorporateEmployee, and PatientInsurance. Returns dict with type, name, is_insurance_or_corporate, payer.
    When the bill-to payer is insurance but the patient also has a corporate employer enrollment,
    corporate_badge_name is set so UIs can show both tags.
    Used by pharmacy payment verification and AutoBillingService so invoice gets the correct payer.
    """
    payer = None
    payer_type = 'cash'
    payer_name = 'Cash'

    if not patient:
        return {'type': payer_type, 'name': payer_name, 'is_insurance_or_corporate': False, 'payer': None}

    scope_ids = _patient_billing_scope_ids(patient)

    # 1. Encounter invoice (most specific for this visit)
    if encounter:
        inv = Invoice.all_objects.filter(
            encounter=encounter, is_deleted=False
        ).exclude(status__iexact='cancelled').select_related('payer').order_by('-created').first()
        if (
            inv
            and inv.payer
            and not getattr(inv.payer, 'is_deleted', False)
            and getattr(inv.payer, 'payer_type', '') != 'cash'
        ):
            payer = inv.payer
            payer_type = getattr(payer, 'payer_type', 'cash')
            payer_name = getattr(payer, 'name', '')

    # 2. Patient primary_insurance (this profile row first, then same-MRN duplicates)
    if not payer or payer_type == 'cash':
        seen_payer_pk = set()
        cand_patients = [patient]
        try:
            cand_patients.extend(
                list(
                    Patient.objects.filter(pk__in=scope_ids, is_deleted=False)
                    .exclude(pk=patient.pk)
                    .select_related('primary_insurance')
                )
            )
        except Exception:
            pass
        for p_cand in cand_patients:
            pi_obj = getattr(p_cand, 'primary_insurance', None)
            if not pi_obj or pi_obj.pk in seen_payer_pk:
                continue
            seen_payer_pk.add(pi_obj.pk)
            if getattr(pi_obj, 'is_deleted', False):
                continue
            pt = (getattr(pi_obj, 'payer_type', '') or '').strip().lower()
            if pt == 'cash':
                continue
            payer = pi_obj
            payer_type = getattr(pi_obj, 'payer_type', 'cash')
            payer_name = getattr(pi_obj, 'name', '') or payer_name
            break

    # 3. Corporate: check CorporateEmployee (patient may be corporate without primary_insurance set)
    if not payer or payer_type == 'cash':
        corp_name = _corporate_enrollment_company_name_for_patient_ids(scope_ids)
        if corp_name:
            payer_name = corp_name
            payer_type = 'corporate'
            payer = Payer.objects.filter(name=payer_name, is_deleted=False).first()
            if not payer:
                try:
                    payer, _ = Payer.objects.get_or_create(
                        name=payer_name,
                        defaults={'payer_type': 'corporate', 'is_active': True},
                    )
                except Exception:
                    payer = None

    # 4. Insurance: check PatientInsurance (models_insurance_companies)
    if not payer or payer_type == 'cash':
        try:
            from .models_insurance_companies import PatientInsurance
            pi = (
                PatientInsurance.objects.filter(
                    patient_id__in=scope_ids, status='active', is_deleted=False
                )
                .select_related('insurance_company')
                .order_by('-is_primary', '-created')
                .first()
            )
            if pi and pi.insurance_company:
                payer_name = pi.insurance_company.name
                payer_type = 'private'
                if 'nhis' in (pi.insurance_company.name or '').lower():
                    payer_type = 'nhis'
                payer = Payer.objects.filter(name=payer_name, is_deleted=False).first()
                if not payer:
                    payer, _ = Payer.objects.get_or_create(
                        name=payer_name,
                        defaults={'payer_type': payer_type, 'is_active': True}
                    )
        except Exception:
            pass

    # Still cash but has corporate enrollment (safety net if earlier steps did not resolve payer)
    corp_company = _corporate_enrollment_company_name_for_patient_ids(scope_ids)
    corporate_badge_name = None
    if corp_company and payer_type == 'cash':
        payer_name = corp_company
        payer_type = 'corporate'
        payer = Payer.objects.filter(name=payer_name, is_deleted=False).first()
        if not payer:
            try:
                payer, _ = Payer.objects.get_or_create(
                    name=payer_name,
                    defaults={'payer_type': 'corporate', 'is_active': True},
                )
            except Exception:
                pass
    elif corp_company:
        pt = (payer_type or '').strip().lower()
        if pt == 'insurance':
            pt = 'private'
        if pt in ('nhis', 'private') and (payer_name or '').strip().lower() != corp_company.strip().lower():
            corporate_badge_name = corp_company

    # Visit invoice often bills to insurance while patient.primary_insurance is still corporate (no CorporateEmployee row)
    if not corporate_badge_name:
        badge_candidates = [patient]
        try:
            badge_candidates.extend(
                list(
                    Patient.objects.filter(pk__in=scope_ids, is_deleted=False)
                    .exclude(pk=patient.pk)
                    .select_related('primary_insurance')
                )
            )
        except Exception:
            pass
        for p_cand in badge_candidates:
            pi_direct = getattr(p_cand, 'primary_insurance', None)
            if (
                pi_direct
                and not getattr(pi_direct, 'is_deleted', False)
                and getattr(pi_direct, 'payer_type', '') == 'corporate'
            ):
                cn = (getattr(pi_direct, 'name', '') or '').strip()
                if cn and cn.lower() != 'cash':
                    pt = (payer_type or '').strip().lower()
                    if pt == 'insurance':
                        pt = 'private'
                    if pt in ('nhis', 'private'):
                        corporate_badge_name = cn
                        break
                    if pt == 'corporate' and (payer_name or '').strip().lower() != cn.lower():
                        corporate_badge_name = cn
                        break

    # 5. insurance_company text on file (any same-MRN row) when payer FK was never switched off Cash
    if (payer_type or '').strip().lower() == 'cash':
        try:
            for row in Patient.objects.filter(pk__in=scope_ids, is_deleted=False).only(
                'insurance_company',
            ):
                t = (getattr(row, 'insurance_company', None) or '').strip()
                if t and t.lower() not in ('cash', 'n/a', 'na', 'none'):
                    payer_name = t
                    payer_type = 'private'
                    payer = Payer.objects.filter(name__iexact=t, is_deleted=False).first()
                    break
        except Exception:
            pass

    pt_flag = (payer_type or '').strip().lower()
    if pt_flag == 'insurance':
        pt_flag = 'private'
    is_ins = pt_flag in ('nhis', 'private', 'corporate')
    if corporate_badge_name and not is_ins:
        is_ins = True
        if (payer_name or '').strip().lower() in ('cash', ''):
            payer_name = corporate_badge_name
            payer_type = 'corporate'
    out = {
        'type': payer_type,
        'name': payer_name or 'Cash',
        'is_insurance_or_corporate': is_ins,
        'payer': payer,
    }
    if corporate_badge_name:
        out['corporate_badge_name'] = corporate_badge_name
    return out


def _ensure_consultation_pricing(service_code):
    """
    Ensure the standard pricing tiers for consultations are enforced:
    - General Consultation: Cash = 150, Corporate = 160, Insurance from PricingCategory (seed_general_prices)
    - Specialist Consultation: Cash = 300, Corporate/Insurance from PricingCategory
    """
    today = timezone.now().date()
    is_general = (service_code.code or '').strip().upper() in ('CON001', 'CONS-GEN', 'CONSULTATION_GENERAL')
    desired_cash = GENERAL_CONSULTATION_CASH if is_general else Decimal('300.00')
    desired_corporate = GENERAL_CONSULTATION_CORPORATE if is_general else Decimal('300.00')
    desired_insurance = GENERAL_CONSULTATION_CASH if is_general else Decimal('300.00')
    
    pricing, created = ServicePricing.objects.get_or_create(
        service_code=service_code,
        payer__isnull=True,
        defaults={
            'is_active': True,
            'effective_from': today,
            'cash_price': desired_cash,
            'corporate_price': desired_corporate,
            'insurance_price': desired_insurance,
        }
    )
    
    updated = False
    if pricing.cash_price != desired_cash:
        pricing.cash_price = desired_cash
        updated = True
    if pricing.corporate_price != desired_corporate:
        pricing.corporate_price = desired_corporate
        updated = True
    if pricing.insurance_price != desired_insurance:
        pricing.insurance_price = desired_insurance
        updated = True
    if pricing.effective_from > today:
        pricing.effective_from = today
        updated = True
    if not pricing.is_active:
        pricing.is_active = True
        updated = True
    
    if updated:
        pricing.save()


# Drug markup by payer: insurance 30%, corporate 50%
DRUG_INSURANCE_MARKUP = Decimal('0.30')
DRUG_CORPORATE_MARKUP = Decimal('0.50')
# Deprecated alias kept for apply_drug_markup_pending (historical 50% upgrade command)
DRUG_INSURANCE_CORPORATE_MARKUP = DRUG_CORPORATE_MARKUP


def get_drug_markup_for_payer(payer):
    """Return drug markup fraction for payer type (0 for cash / unknown)."""
    payer_type = getattr(payer, 'payer_type', None)
    if payer_type == 'corporate':
        return DRUG_CORPORATE_MARKUP
    if payer_type in ('insurance', 'private', 'nhis'):
        return DRUG_INSURANCE_MARKUP
    return Decimal('0')


def get_drug_price_for_prescription(drug, payer=None):
    """
    Get stable drug selling price for prescriptions.
    Prefers Drug.unit_price (selling price) when set and > 0, so pharmacy price does not
    change with every stock receipt or inventory sync. Falls back to pharmacy store
    InventoryItem.unit_cost only when Drug.unit_price is 0 or unset.
    Insurance payers get 30% markup; corporate payers get 50% markup on base price.

    Set Drug.unit_price in the Drug master for stable selling prices; inventory unit_cost
    is used only for costing/valuation and as fallback when no selling price is set.
    """
    drug_price = Decimal(str(getattr(drug, 'unit_price', 0) or 0))
    if drug_price and drug_price > 0:
        base = drug_price
    else:
        try:
            from .models_procurement import Store, InventoryItem
            pharmacy_store = Store.get_main_pharmacy_store()
            if pharmacy_store and drug:
                item = InventoryItem.objects.filter(
                    store=pharmacy_store,
                    drug=drug,
                    is_deleted=False,
                    is_active=True,
                    unit_cost__gt=0
                ).order_by('-quantity_on_hand').first()
                if item and item.unit_cost is not None:
                    base = Decimal(str(item.unit_cost))
                else:
                    base = Decimal('0.00')
            else:
                base = Decimal('0.00')
        except Exception:
            base = Decimal('0.00')
    if payer:
        markup = get_drug_markup_for_payer(payer)
        if markup > 0:
            base = base * (1 + markup)
    return base


def _record_locum_consultation_service(encounter, service_amount, consultation_type, invoice_line):
    """Automatically create locum service entry when a locum doctor consults."""
    provider = getattr(encounter, 'provider', None)
    patient = getattr(encounter, 'patient', None)
    if not provider or not patient or not getattr(provider, 'is_locum', False):
        return
    
    try:
        from .models_locum_doctors import LocumDoctorService
    except ImportError:
        logger.warning("Locum module not available; skipping locum consultation tracking.")
        return
    
    service_label = f"{consultation_type.title()} Consultation"
    existing = LocumDoctorService.objects.filter(
        encounter=encounter,
        service_type=service_label,
        is_deleted=False
    ).first()
    
    description = (
        f"{service_label} automatically captured from consultation billing. "
        f"Invoice #{getattr(invoice_line.invoice, 'invoice_number', '') or invoice_line.invoice.pk}"
    )
    
    service_date = encounter.started_at.date() if getattr(encounter, 'started_at', None) else timezone.now().date()
    
    if existing:
        if existing.service_charge != service_amount:
            existing.service_charge = service_amount
            existing.service_description = description
            existing.save()
        return existing
    
    locum_service = LocumDoctorService.objects.create(
        doctor=provider,
        patient=patient,
        encounter=encounter,
        service_date=service_date,
        service_type=service_label,
        service_description=description,
        service_charge=service_amount,
        payment_method='bank_transfer',
        notes='Auto-generated from consultation billing.'
    )
    logger.info(
        "Locum consultation recorded: %s -> %s (%s, GHS %s)",
        provider.user.get_full_name(),
        patient.full_name,
        service_label,
        service_amount
    )
    return locum_service


def is_review_visit(encounter):
    """
    True when this encounter is a follow-up/review visit — no consultation / visit fee.

    Uses explicit markers from front desk (patient_quick_visit / frontdesk_visit) so random
    words like "review" in clinical notes do not zero billing.
    """
    if not encounter:
        return False
    notes_lower = (encounter.notes or '').lower()
    if '[review_visit]' in notes_lower:
        return True
    complaint = (encounter.chief_complaint or '').strip().lower()
    if complaint.startswith('review:') or complaint.startswith('review '):
        return True
    if complaint.startswith('follow-up:') or complaint.startswith('followup:'):
        return True
    if complaint.startswith('follow up:'):
        return True
    return False


def waive_encounter_consultation_fees_for_review(encounter):
    """
    Waive CON001/CON002/MAT-ANC/S00023 lines on non-paid invoices for this encounter.
    Paid invoices are left unchanged (accounting already settled).
    """
    if not encounter:
        return
    now = timezone.now()
    for inv in (
        Invoice.all_objects.filter(encounter=encounter, is_deleted=False)
        .exclude(status__in=('paid', 'cancelled'))
    ):
        qs = InvoiceLine.objects.filter(
            invoice=inv,
            service_code__code__in=CONSULTATION_LINE_SERVICE_CODES,
            is_deleted=False,
            waived_at__isnull=True,
        )
        touched = False
        for line in qs:
            line.waived_at = now
            line.save(update_fields=['waived_at', 'modified'])
            touched = True
        if touched:
            inv.update_totals()


def add_consultation_charge(
    encounter,
    consultation_type='general',
    doctor_staff=None,
    billing_payer=None,
    pricing_patient=None,
    *,
    ignore_billing_closed=False,
):
    """
    Add consultation charge to encounter's invoice
    Uses intelligent pricing engine for multi-tier pricing
    consultation_type: 'general' or 'specialist'
    doctor_staff: Optional Staff object for doctor-specific pricing
    billing_payer: If set (e.g. corporate invoice payer), use for pricing instead of patient.primary_insurance.
    pricing_patient: If set (e.g. Patient loaded by invoice.patient_id UUID), use for all price resolution
    (corporate enrollment, insurance tiers, doctor pricing) while invoice rows still use encounter.patient.
    ignore_billing_closed: If True (corporate pack repair only), allow adding/updating the consultation line
    even when encounter.billing_closed_at is set.
    
    Review/follow-up encounters (see is_review_visit): no consultation or MAT-ANC visit fee; existing
    unpaid consultation lines on the encounter invoice are waived.
    
    Special handling:
    - Antenatal visits use MAT-ANC service code with existing pricing
    - Doctor-specific pricing takes precedence over general pricing
    - Specialist visits: doctor/tier or engine (e.g. 300 cash baseline); insurance uses tiers
    - General visits: always 150 (cash) / 160 (corporate); insurance uses tiers (no doctor-specific GP fees)
    """
    if is_review_visit(encounter):
        waive_encounter_consultation_fees_for_review(encounter)
        existing_inv = Invoice.all_objects.filter(encounter=encounter, is_deleted=False).first()
        if existing_inv is not None:
            return existing_inv
        return get_or_create_encounter_invoice(encounter)

    encounter_patient = encounter.patient
    price_patient = pricing_patient if pricing_patient is not None else encounter_patient
    patient = encounter_patient
    payer = billing_payer if billing_payer is not None else price_patient.primary_insurance
    
    # 🏥 HANDLE ANTENATAL VISITS - Use existing MAT-ANC pricing
    encounter_type_lower = (encounter.encounter_type or '').lower()
    is_antenatal = 'antenatal' in encounter_type_lower
    
    if is_antenatal:
        # Use MAT-ANC service code for antenatal visits
        antenatal_service_code, _ = ServiceCode.objects.get_or_create(
            code='MAT-ANC',
            defaults={
                'description': 'Antenatal Care Visit',
                'category': 'Maternity',
                'is_active': True,
            }
        )
        
        # Get price using pricing engine (respects insurance/cash pricing)
        # Default antenatal price: 235 GHC (front desk / cashier standard)
        try:
            consultation_price = pricing_engine.get_service_price(
                service_code=antenatal_service_code,
                patient=price_patient,
                payer=payer
            )
            if consultation_price is None or consultation_price == Decimal('0.00'):
                consultation_price = Decimal('235.00')
        except Exception as e:
            logger.warning(f"Error getting antenatal price: {e}, using default")
            consultation_price = Decimal('235.00')
        
        service_code = antenatal_service_code
        description = 'Antenatal Care Visit'
        
        # Get or create invoice (use all_objects so new invoice with total_amount=0 is findable)
        invoice = Invoice.all_objects.filter(
            encounter=encounter,
            is_deleted=False
        ).first()
        
        if not invoice:
            # Ensure payer exists for invoice
            if not payer:
                payer = Payer.objects.filter(payer_type='cash', is_active=True, is_deleted=False).first()
                if not payer:
                    payer = Payer.objects.create(name='Cash', payer_type='cash', is_active=True)
            
            due_date = timezone.now() + timedelta(days=30)
            invoice = Invoice.all_objects.create(
                patient=patient,
                encounter=encounter,
                payer=payer,
                status='draft',
                due_at=due_date,
            )
        
        if getattr(encounter, 'billing_closed_at', None) and not ignore_billing_closed:
            logger.warning(f"Antenatal billing skipped: encounter {encounter.id} billing closed")
            return invoice

        # Check if antenatal charge already exists
        existing_line = InvoiceLine.objects.filter(
            invoice=invoice,
            service_code=antenatal_service_code,
            is_deleted=False
        ).first()
        
        if not existing_line:
            InvoiceLine.objects.create(
                invoice=invoice,
                service_code=antenatal_service_code,
                description=description,
                quantity=1,
                unit_price=consultation_price,
                line_total=consultation_price
            )
            invoice.update_totals()
        
        logger.info(
            f"💰 Antenatal visit charge for {patient.full_name}: "
            f"GHS {consultation_price} (Payer: {payer.name if payer else 'Cash'}, Type: {payer.payer_type if payer else 'cash'})"
        )
        return invoice
    
    # Regular consultation handling
    if not payer:
        # Try to get Cash payer (only for non-insurance patients)
        payer = Payer.objects.filter(payer_type='cash', is_active=True, is_deleted=False).first()
        if not payer:
            # Try any active payer
            payer = Payer.objects.filter(is_active=True, is_deleted=False).first()
            if not payer:
                # Create a default Cash payer if none exists
                payer = Payer.objects.create(
                    name='Cash',
                    payer_type='cash',
                    is_active=True
                )
    
    if not payer:
        return None  # This should never happen after auto-creation, but keep as safety check

    consultation_type = normalize_consultation_type_for_gp_department(
        encounter, consultation_type, doctor_staff
    )
    
    # Determine service code
    service_code_key = 'consultation_general' if consultation_type == 'general' else 'consultation_specialist'
    
    # Get or create consultation service code
    service_code_str = 'CON001' if consultation_type == 'general' else 'CON002'
    description = 'General Consultation' if consultation_type == 'general' else 'Specialist Consultation'
    
    service_code, _ = ServiceCode.objects.get_or_create(
        code=service_code_str,
        defaults={
            'description': description,
            'category': 'Consultation',
            'is_active': True,
        }
    )
    # Legacy rows used category "Clinical Services"; normalize so lists/exports match staff wording.
    if service_code_str in ('CON001', 'CON002') and (service_code.category or '').strip().lower() in (
        'clinical services',
        'clinical',
    ):
        service_code.category = 'Consultation'
        service_code.save(update_fields=['category'])

    if consultation_type == 'general':
        _ensure_consultation_pricing(service_code)
    
    # 💰 DOCTOR-SPECIFIC PRICING: specialist consultations only (GP uses flat 150/160 + insurance tiers)
    consultation_price = None
    if doctor_staff and consultation_type == 'specialist':
        try:
            from .utils_doctor_pricing import DoctorPricingService
            consultation_price = DoctorPricingService.get_consultation_fee(
                patient=price_patient,
                doctor_staff=doctor_staff,
                encounter_type=encounter_type_lower,
                is_review_visit=False  # Already checked above
            )
            logger.info(
                f"💰 Doctor-specific pricing for {doctor_staff.user.get_full_name()}: "
                f"GHS {consultation_price} (Patient: {price_patient.full_name})"
            )
        except Exception as e:
            logger.warning(f"Error getting doctor-specific pricing: {e}")
            consultation_price = None
    
    # Gynae / Special: default 260 GHC when no doctor-specific price (front desk / cashier special payment)
    if consultation_price is None and encounter_type_lower == 'gynae':
        consultation_price = Decimal('260.00')

    # 💰 USE PRICING ENGINE: Pick from general system (ServicePrice + PricingCategory: cash, corporate, insurance)
    # Only if doctor-specific pricing wasn't found
    if consultation_price is None:
        fallback_cash = GENERAL_CONSULTATION_CASH if consultation_type == 'general' else Decimal('300.00')
        fallback_corp = GENERAL_CONSULTATION_CORPORATE if consultation_type == 'general' else Decimal('300.00')
        try:
            consultation_price = pricing_engine.get_service_price(
                service_code=service_code,
                patient=price_patient,
                payer=payer
            )
            if consultation_price is None:
                consultation_price = Decimal('0.00')
            
            # Use engine result when > 0; otherwise try category lookup or fallback
            if consultation_price <= 0:
                from hospital.models_flexible_pricing import ServicePrice, PricingCategory
                today = timezone.now().date()
                cat = None
                if payer and payer.payer_type == 'cash':
                    consultation_price = fallback_cash
                elif payer and payer.payer_type == 'corporate':
                    cat = PricingCategory.objects.filter(
                        category_type='corporate', is_active=True, is_deleted=False
                    ).order_by('priority').first()
                    if cat:
                        p = ServicePrice.get_price(service_code, cat, today)
                        if p and p > 0:
                            consultation_price = p
                    if consultation_price <= 0:
                        consultation_price = fallback_corp
                elif payer and payer.payer_type in ('insurance', 'nhis', 'private'):
                    cat = PricingCategory.objects.filter(
                        category_type='insurance', is_active=True, is_deleted=False
                    ).exclude(name__icontains='cash').order_by('priority').first()
                    if cat:
                        p = ServicePrice.get_price(service_code, cat, today)
                        if p and p > 0:
                            consultation_price = p
                    if consultation_price <= 0:
                        logger.warning(
                            f"⚠️ No insurance price for {service_code.description}; "
                            f"run seed_general_prices. Patient: {price_patient.full_name}"
                        )
                else:
                    consultation_price = fallback_cash
            
            logger.info(
                f"💰 Consultation price for {price_patient.full_name}: "
                f"GHS {consultation_price} (Payer: {payer.name}, Type: {payer.payer_type}, "
                f"Consultation: {consultation_type})"
            )
            
        except Exception as e:
            logger.error(f"Error in pricing engine: {e}", exc_info=True)
            consultation_price = PayerPrice.get_price(payer, service_code_key)
        if consultation_price is None:
            if payer and payer.payer_type == 'cash':
                consultation_price = GENERAL_CONSULTATION_CASH if consultation_type == 'general' else Decimal('300.00')
            elif payer and payer.payer_type == 'corporate':
                consultation_price = fallback_corp if consultation_type == 'general' else Decimal('300.00')
            else:
                consultation_price = DefaultPrice.get_price(
                    'consultation_general' if consultation_type == 'general' else 'consultation_specialist',
                    GENERAL_CONSULTATION_CASH if consultation_type == 'general' else Decimal('300.00'),
                )

    # GP flat rates: enforce when not insurance (flat helper returns None for insurance — keep engine)
    if consultation_type == 'general' and encounter_type_lower != 'gynae':
        flat = get_general_consultation_price_for_patient_and_payer(price_patient, payer)
        if flat is not None:
            consultation_price = flat
    
    # Get or create invoice for this encounter (all_objects so new/zero-amount invoices are findable)
    invoice = Invoice.all_objects.filter(
        encounter=encounter,
        is_deleted=False
    ).first()
    
    if not invoice:
        # Create new invoice
        due_date = timezone.now() + timedelta(days=30)
        invoice = Invoice.all_objects.create(
            patient=patient,
            encounter=encounter,
            payer=payer,
            status='draft',
            due_at=due_date,
        )
    
    if getattr(encounter, 'billing_closed_at', None) and not ignore_billing_closed:
        logger.warning(f"Consultation billing skipped: encounter {encounter.id} billing closed")
        return invoice

    # Check if consultation charge already exists for this encounter (CON001/CON002 only; antenatal uses MAT-ANC above)
    existing_line = InvoiceLine.objects.filter(
        invoice=invoice,
        service_code__code__in=['CON001', 'CON002'],
        is_deleted=False
    ).first()
    
    invoice_line = existing_line
    if not existing_line:
        # Add consultation fee line
        invoice_line = InvoiceLine.objects.create(
            invoice=invoice,
            service_code=service_code,
            description=description,
            quantity=1,
            unit_price=consultation_price,
            line_total=consultation_price
        )
        
        # Update invoice totals
        invoice.update_totals()
    else:
        # Same-day reuse or visit type/doctor changed: sync line so cashier matches reception / doctor pricing
        qty = existing_line.quantity or Decimal('1')
        needs_sync = (
            existing_line.service_code_id != service_code.id
            or existing_line.unit_price != consultation_price
            or (existing_line.description or '') != description
        )
        if needs_sync:
            existing_line.service_code = service_code
            existing_line.description = description
            existing_line.unit_price = consultation_price
            existing_line.line_total = consultation_price * qty
            existing_line.save(
                update_fields=[
                    'service_code', 'description', 'unit_price', 'line_total', 'modified',
                ]
            )
            invoice_line = existing_line
            invoice.update_totals()
    
    _record_locum_consultation_service(encounter, consultation_price, consultation_type, invoice_line)
    return invoice


def get_consultation_line_for_encounter(encounter):
    """
    Return the encounter's consultation InvoiceLine (CON001/CON002/MAT-ANC) if it exists and is not waived.
    Used by cashier to display and collect the invoiced consultation amount.
    Invoice lookup uses all_objects so draft/zero-total encounter invoices are visible (VisibleManager hides total_amount=0).
    """
    if not encounter:
        return None
    invoice = Invoice.all_objects.filter(
        encounter=encounter,
        is_deleted=False
    ).first()
    if not invoice:
        return None
    line = (
        InvoiceLine.objects.filter(
            invoice=invoice,
            service_code__code__in=CONSULTATION_LINE_SERVICE_CODES,
            is_deleted=False,
            waived_at__isnull=True,
        )
        .select_related('service_code')
        .order_by('-modified', '-created')
        .first()
    )
    return line


def bulk_consultation_lines_for_encounters(encounter_ids):
    """
    Map encounter_id -> consultation InvoiceLine or None (same rules as get_consultation_line_for_encounter).
    Avoids N+1 when scanning many encounters (e.g. cashier dashboard).
    """
    if not encounter_ids:
        return {}
    ids = []
    for x in encounter_ids:
        if x is not None:
            try:
                ids.append(int(x))
            except (TypeError, ValueError):
                continue
    ids = list(dict.fromkeys(ids))
    if not ids:
        return {}
    invoices = (
        Invoice.all_objects.filter(encounter_id__in=ids, is_deleted=False)
        .order_by('encounter_id', '-modified', '-id')
    )
    inv_by_enc = {}
    for inv in invoices:
        if inv.encounter_id not in inv_by_enc:
            inv_by_enc[inv.encounter_id] = inv
    result = {eid: None for eid in ids}
    if not inv_by_enc:
        return result
    invoice_ids = [i.id for i in inv_by_enc.values()]
    lines = (
        InvoiceLine.objects.filter(
            invoice_id__in=invoice_ids,
            service_code__code__in=CONSULTATION_LINE_SERVICE_CODES,
            is_deleted=False,
            waived_at__isnull=True,
        )
        .select_related('service_code', 'invoice')
        .order_by('invoice_id', '-modified', '-created')
    )
    line_by_invoice = {}
    for line in lines:
        if line.invoice_id not in line_by_invoice:
            line_by_invoice[line.invoice_id] = line
    for eid, inv in inv_by_enc.items():
        if eid in result:
            result[eid] = line_by_invoice.get(inv.id)
    return result


def ensure_consultation_line_on_invoice(invoice, *, ignore_billing_closed=False):
    """
    If this invoice is linked to an encounter and has no consultation line (CON001/CON002/MAT-ANC/etc.),
    add the appropriate consultation charge using invoice.payer for pricing (important for corporate bills).

    Returns (added: bool, reason_code: str) e.g. (True, 'added'), (False, 'already_billed').
    """
    if not invoice or getattr(invoice, 'is_deleted', False) or getattr(invoice, 'status', None) == 'cancelled':
        return False, 'invalid_invoice'
    enc = getattr(invoice, 'encounter', None)
    if not enc or getattr(enc, 'is_deleted', False):
        return False, 'no_encounter'
    if getattr(enc, 'status', None) == 'cancelled':
        return False, 'enc_cancelled'
    if getattr(enc, 'billing_closed_at', None) and not ignore_billing_closed:
        return False, 'billing_closed'
    if is_review_visit(enc):
        return False, 'review_visit'
    if get_consultation_line_for_encounter(enc):
        return False, 'already_billed'
    doc = getattr(enc, 'provider', None)
    et = (enc.encounter_type or '').lower()
    # Treat gynae as specialist-tier for consultation billing (CON002),
    # matching cashier display and add_consultation_charge pricing rules.
    if et in ('specialist', 'gynae'):
        consultation_type = 'specialist'
    else:
        consultation_type = 'general'
    try:
        pricing_patient = Patient.objects.select_related('primary_insurance').get(
            pk=invoice.patient_id,
            is_deleted=False,
        )
    except Patient.DoesNotExist:
        pricing_patient = None
    try:
        add_consultation_charge(
            enc,
            consultation_type=consultation_type,
            doctor_staff=doc,
            billing_payer=invoice.payer,
            pricing_patient=pricing_patient,
            ignore_billing_closed=ignore_billing_closed,
        )
    except Exception:
        logger.exception(
            'ensure_consultation_line_on_invoice failed invoice=%s encounter=%s',
            getattr(invoice, 'pk', None),
            getattr(enc, 'pk', None),
        )
        return False, 'error'
    if get_consultation_line_for_encounter(enc):
        return True, 'added'
    return False, 'not_added'


_CONSULTATION_LINE_PRELOAD = object()


def get_consultation_price_for_encounter(encounter, preloaded_consultation_line=_CONSULTATION_LINE_PRELOAD):
    """
    Return the consultation price for an encounter (for display/cashier).
    Uses the same logic as add_consultation_charge: doctor-specific pricing for
    specialist encounters only; general OPD 150/160 (cash/corporate) or insurance from engine.
    Never returns the wrong legacy 30.
    When an invoice line exists, prefer that line's amount.
    If preloaded_consultation_line is passed (including None from a bulk lookup), skip fetching the line again.
    """
    if not encounter:
        return None
    if is_review_visit(encounter):
        return Decimal('0.00')
    if preloaded_consultation_line is _CONSULTATION_LINE_PRELOAD:
        line = get_consultation_line_for_encounter(encounter)
    else:
        line = preloaded_consultation_line
    if line:
        from_line = consultation_line_display_amount(line)
        # Trust line only when amount > 0; zero can be stale/wrong and would hide gynae from cashier
        if from_line is not None and from_line > 0:
            return from_line
    patient = encounter.patient
    encounter_type_lower = (encounter.encounter_type or '').lower()
    if 'antenatal' in encounter_type_lower:
        return get_mat_anc_consultation_price(patient, patient.primary_insurance)
    doctor_staff = getattr(encounter, 'provider', None) or getattr(encounter, 'assigned_doctor', None)
    if doctor_staff and encounter_type_lower == 'specialist':
        try:
            from .utils_doctor_pricing import DoctorPricingService
            fee = DoctorPricingService.get_consultation_fee(
                patient=patient,
                doctor_staff=doctor_staff,
                encounter_type=encounter_type_lower or None,
                is_review_visit=False,
            )
            if fee is not None and fee >= 0 and fee > 0:
                return fee
        except Exception:
            pass
    if encounter_type_lower == 'gynae':
        return Decimal('260.00')
    # Use encounter_type so Special Consultation shows correct price at cashier even without assigned doctor
    if encounter_type_lower == 'specialist':
        if should_use_gp_flat_consultation_fee(encounter, doctor_staff):
            flat = get_general_consultation_price_for_patient_and_payer(
                patient, patient.primary_insurance
            )
            if flat is not None:
                return flat
            return GENERAL_CONSULTATION_CASH
        return Decimal('300.00')
    flat = get_general_consultation_price_for_patient_and_payer(patient, patient.primary_insurance)
    if flat is not None:
        return flat
    try:
        sc = ServiceCode.objects.filter(code='CON001', is_active=True).first()
        if sc:
            p = pricing_engine.get_service_price(sc, patient, patient.primary_insurance)
            if p and p > 0:
                return p
    except Exception:
        pass
    return GENERAL_CONSULTATION_CASH


def get_consultation_price_for_encounter_and_payer(encounter, payer, consultation_type=None):
    """
    Compute consultation price for an encounter with a given payer.
    Same logic as add_consultation_charge (doctor-specific or pricing engine).
    Used when payer changes to update the consultation line amount.
    """
    if not encounter:
        return None
    if is_review_visit(encounter):
        return Decimal('0.00')
    patient = encounter.patient
    encounter_type_lower = (encounter.encounter_type or '').lower()
    doctor_staff = getattr(encounter, 'provider', None) or getattr(encounter, 'assigned_doctor', None)
    if consultation_type is None:
        consultation_type = (
            'specialist'
            if encounter_type_lower in ('specialist', 'gynae')
            else 'general'
        )
    consultation_type = normalize_consultation_type_for_gp_department(
        encounter, consultation_type, doctor_staff
    )
    service_code_str = 'CON001' if consultation_type == 'general' else 'CON002'
    service_code = ServiceCode.objects.filter(
        code=service_code_str, is_active=True
    ).first()
    if not service_code:
        return GENERAL_CONSULTATION_CASH if consultation_type == 'general' else Decimal('300.00')
    consultation_price = None
    if doctor_staff and consultation_type == 'specialist':
        try:
            from .utils_doctor_pricing import DoctorPricingService
            consultation_price = DoctorPricingService.get_consultation_fee(
                patient=patient,
                doctor_staff=doctor_staff,
                encounter_type=encounter_type_lower or None,
                is_review_visit=False,
            )
        except Exception:
            pass
    if consultation_price is None and encounter_type_lower == 'gynae':
        consultation_price = Decimal('260.00')
    if consultation_price is None and payer:
        fallback_cash = GENERAL_CONSULTATION_CASH if consultation_type == 'general' else Decimal('300.00')
        fallback_corp = GENERAL_CONSULTATION_CORPORATE if consultation_type == 'general' else Decimal('300.00')
        try:
            consultation_price = pricing_engine.get_service_price(
                service_code=service_code,
                patient=patient,
                payer=payer
            )
            if consultation_price is None:
                consultation_price = Decimal('0.00')
            if consultation_price <= 0:
                from hospital.models_flexible_pricing import ServicePrice, PricingCategory
                today = timezone.now().date()
                if payer.payer_type == 'cash':
                    consultation_price = fallback_cash
                elif payer.payer_type == 'corporate':
                    cat = PricingCategory.objects.filter(
                        category_type='corporate', is_active=True, is_deleted=False
                    ).order_by('priority').first()
                    if cat:
                        p = ServicePrice.get_price(service_code, cat, today)
                        if p and p > 0:
                            consultation_price = p
                    if consultation_price <= 0:
                        consultation_price = fallback_corp
                elif payer.payer_type in ('insurance', 'nhis', 'private'):
                    cat = PricingCategory.objects.filter(
                        category_type='insurance', is_active=True, is_deleted=False
                    ).exclude(name__icontains='cash').order_by('priority').first()
                    if cat:
                        p = ServicePrice.get_price(service_code, cat, today)
                        if p and p > 0:
                            consultation_price = p
                    if consultation_price <= 0:
                        consultation_price = fallback_cash
                else:
                    consultation_price = fallback_cash
        except Exception:
            consultation_price = fallback_cash
    if consultation_type == 'general' and encounter_type_lower != 'gynae':
        flat = get_general_consultation_price_for_patient_and_payer(patient, payer)
        if flat is not None:
            consultation_price = flat
    if consultation_price is None:
        return GENERAL_CONSULTATION_CASH if consultation_type == 'general' else Decimal('300.00')
    return consultation_price


def get_corrected_general_opd_line_unit_price(invoice, line):
    """
    Target unit price for an existing general-OPD-style consultation line (CON001 family, S00023).
    Uses encounter when linked: antenatal → MAT-ANC pricing; gynae/specialist → specialist rules;
    otherwise enforced general OPD (150/160 + insurance). Encounter-less invoices use patient + payer only.
    """
    enc = getattr(invoice, 'encounter', None)
    if enc and is_review_visit(enc):
        return Decimal('0.00')
    patient = getattr(invoice, 'patient', None)
    payer = getattr(invoice, 'payer', None)
    if patient is None:
        return None
    if enc and not getattr(enc, 'is_deleted', False):
        et = (enc.encounter_type or '').lower()
        if 'antenatal' in et:
            return get_mat_anc_consultation_price(patient, payer)
        if et in ('gynae', 'specialist'):
            return get_consultation_price_for_encounter_and_payer(
                enc, payer, consultation_type='specialist'
            )
        return get_consultation_price_for_encounter_and_payer(
            enc, payer, consultation_type='general'
        )
    flat = get_general_consultation_price_for_patient_and_payer(patient, payer)
    if flat is not None:
        return flat
    sc = getattr(line, 'service_code', None)
    if sc:
        try:
            p = pricing_engine.get_service_price(sc, patient, payer)
            if p and p > 0:
                return p
        except Exception:
            pass
    return GENERAL_CONSULTATION_CASH


def get_or_create_encounter_invoice(encounter):
    """Get or create invoice for an encounter"""
    from django.db import IntegrityError
    from .models import Invoice, Payer
    from datetime import timedelta

    # Use all_objects so we find any non-deleted invoice for this encounter,
    # including newly created ones with total_amount=0 (default manager excludes those).
    invoice = Invoice.all_objects.filter(
        encounter=encounter,
        is_deleted=False
    ).first()

    if invoice:
        return invoice

    # Create new invoice
    patient = encounter.patient
    payer = patient.primary_insurance
    if not payer:
        # Try to get Cash payer
        payer = Payer.objects.filter(payer_type='cash', is_active=True, is_deleted=False).first()
        if not payer:
            # Try any active payer
            payer = Payer.objects.filter(is_active=True, is_deleted=False).first()
            if not payer:
                # Create a default Cash payer if none exists
                payer = Payer.objects.create(
                    name='Cash',
                    payer_type='cash',
                    is_active=True
                )

    if not payer:
        return None  # This should never happen after auto-creation, but keep as safety check

    due_date = timezone.now() + timedelta(days=30)
    try:
        invoice = Invoice.all_objects.create(
            patient=patient,
            encounter=encounter,
            payer=payer,
            status='draft',
            due_at=due_date,
        )
        return invoice
    except IntegrityError:
        # Race: another request created the invoice; fetch and return it
        existing = Invoice.all_objects.filter(
            encounter=encounter,
            is_deleted=False
        ).first()
        if existing is not None:
            return existing
        raise  # constraint violation but no row found; re-raise


def ensure_consultation_on_corporate_pack_invoice(invoice, visit_enc, *, ignore_billing_closed=False):
    """
    When the corporate invoice has no encounter FK but we inferred visit_enc (same visit day),
    add a consultation line directly onto this invoice so the pack is not pharmacy-only.
    """
    if not invoice or not visit_enc or getattr(invoice, 'encounter_id', None):
        return
    if getattr(visit_enc, 'is_deleted', False) or getattr(visit_enc, 'status', None) == 'cancelled':
        return
    if str(visit_enc.patient_id) != str(invoice.patient_id):
        return
    if getattr(visit_enc, 'billing_closed_at', None) and not ignore_billing_closed:
        return
    if is_review_visit(visit_enc):
        return
    if InvoiceLine.objects.filter(
        invoice=invoice,
        service_code__code__in=CONSULTATION_LINE_SERVICE_CODES,
        is_deleted=False,
        waived_at__isnull=True,
    ).exists():
        return

    payer = getattr(invoice, 'payer', None)
    et = (visit_enc.encounter_type or '').lower()
    if 'antenatal' in et:
        sc, _ = ServiceCode.objects.get_or_create(
            code='MAT-ANC',
            defaults={
                'description': 'Antenatal Care Visit',
                'category': 'Maternity',
                'is_active': True,
            },
        )
        price = get_mat_anc_consultation_price(visit_enc.patient, payer)
        desc = 'Antenatal Care Visit'
    else:
        consultation_type = 'specialist' if et == 'specialist' else 'general'
        desc = 'Specialist Consultation' if consultation_type == 'specialist' else 'General Consultation'
        service_code_str = 'CON002' if consultation_type == 'specialist' else 'CON001'
        sc, _ = ServiceCode.objects.get_or_create(
            code=service_code_str,
            defaults={
                'description': desc,
                'category': 'Consultation',
                'is_active': True,
            },
        )
        price = get_consultation_price_for_encounter_and_payer(
            visit_enc, payer, consultation_type=consultation_type
        )

    InvoiceLine.objects.create(
        invoice=invoice,
        service_code=sc,
        description=desc,
        quantity=Decimal('1'),
        unit_price=price,
        line_total=price,
    )
    try:
        invoice.update_totals()
    except Exception:
        logger.exception('ensure_consultation_on_corporate_pack_invoice update_totals invoice=%s', invoice.pk)


def sync_corporate_invoice_visit_charges(invoice, *, min_invoice_issue_date=None):
    """
    For corporate invoices, backfill consultation, lab, imaging, and orphan insurance-claim lines
    onto the same invoice row shown in the corporate pack (fixes pharmacy-only bills).

    min_invoice_issue_date: only sync when invoice issued date (local) is on or after this date;
    defaults to CORPORATE_PACK_VISIT_CHARGE_SYNC_FROM (2026-03-10).
    """
    from decimal import Decimal

    from django.db.models import Q

    from hospital.models import InvoiceLine, LabResult, Patient
    from hospital.models_advanced import ImagingStudy
    from hospital.services.auto_billing_service import AutoBillingService

    min_d = min_invoice_issue_date if min_invoice_issue_date is not None else CORPORATE_PACK_VISIT_CHARGE_SYNC_FROM

    if not invoice or getattr(invoice, 'is_deleted', False) or getattr(invoice, 'status', None) == 'cancelled':
        return
    payer = getattr(invoice, 'payer', None)
    if not payer or (getattr(payer, 'payer_type', None) or '').lower() != 'corporate' or getattr(payer, 'is_deleted', False):
        return

    ia = getattr(invoice, 'issued_at', None)
    if not ia:
        return
    if timezone.localtime(ia).date() < min_d:
        return

    try:
        bill_patient = Patient.objects.select_related('primary_insurance').get(
            pk=invoice.patient_id,
            is_deleted=False,
        )
    except Patient.DoesNotExist:
        bill_patient = None

    visit_enc = infer_encounter_for_invoice_visit_day(invoice)
    if visit_enc:
        try_link_invoice_to_encounter(invoice, visit_enc)

    enc = None
    eid = getattr(invoice, 'encounter_id', None)
    if eid:
        enc = (
            Encounter.objects.filter(pk=eid, is_deleted=False)
            .exclude(status='cancelled')
            .first()
        )
    if enc is None and visit_enc and not getattr(visit_enc, 'is_deleted', False):
        if getattr(visit_enc, 'status', None) != 'cancelled':
            enc = visit_enc

    pricing_patient = bill_patient or (getattr(enc, 'patient', None) if enc else None)

    try:
        if getattr(invoice, 'encounter_id', None):
            ensure_consultation_line_on_invoice(invoice, ignore_billing_closed=True)
        elif visit_enc:
            ensure_consultation_on_corporate_pack_invoice(
                invoice, visit_enc, ignore_billing_closed=True
            )
    except Exception:
        logger.exception('sync_corporate_invoice_visit_charges: consultation invoice=%s', invoice.pk)

    if not enc:
        try:
            invoice.update_totals()
        except Exception:
            logger.exception('sync_corporate_invoice_visit_charges: update_totals invoice=%s', invoice.pk)
        return

    lab_qs = (
        LabResult.objects.filter(
            order__encounter_id=enc.id,
            is_deleted=False,
        )
        .exclude(status='cancelled')
        .select_related('order', 'test')
    )
    relax = not bool(getattr(invoice, 'encounter_id', None))
    for lr in lab_qs:
        try:
            AutoBillingService.create_lab_bill(
                lr,
                notify_patient=False,
                billing_payer=payer,
                pricing_patient=pricing_patient,
                invoice_target=invoice,
                allow_on_closed_encounter=True,
                relax_encounter_match=relax,
            )
        except Exception:
            logger.exception('sync_corporate_invoice_visit_charges: lab result=%s', lr.pk)

    img_qs = (
        ImagingStudy.objects.filter(
            Q(order__encounter_id=enc.id) | Q(encounter_id=enc.id),
            patient_id=enc.patient_id,
            is_deleted=False,
        )
        .exclude(status='cancelled')
    )
    for study in img_qs.distinct():
        try:
            AutoBillingService.create_imaging_bill(
                study,
                billing_payer=payer,
                notify_patient=False,
                pricing_patient=pricing_patient,
                invoice_target=invoice,
                allow_on_closed_encounter=True,
                relax_encounter_match=relax,
            )
        except Exception:
            logger.exception('sync_corporate_invoice_visit_charges: imaging study=%s', study.pk)

    try:
        from hospital.models_insurance import InsuranceClaimItem

        claim_qs = InsuranceClaimItem.objects.filter(
            patient_id=invoice.patient_id,
            encounter_id=enc.id,
            invoice_line__isnull=True,
            is_deleted=False,
            payer__payer_type__in=['nhis', 'private', 'insurance', 'corporate'],
            service_date__gte=min_d,
        ).select_related('service_code')
        for claim in claim_qs:
            if not claim.service_code_id:
                continue
            if InvoiceLine.objects.filter(
                invoice=invoice,
                service_code_id=claim.service_code_id,
                is_deleted=False,
                waived_at__isnull=True,
            ).exists():
                continue
            amt = claim.billed_amount or Decimal('0')
            if amt < Decimal('0.01'):
                continue
            desc = (claim.service_description or (claim.service_code.description if claim.service_code else '') or '')[:500]
            try:
                from django.db import transaction as db_transaction

                with db_transaction.atomic():
                    line = InvoiceLine.objects.create(
                        invoice=invoice,
                        service_code=claim.service_code,
                        description=desc,
                        quantity=Decimal('1'),
                        unit_price=amt,
                        line_total=amt,
                        patient_pay_cash=False,
                    )
                    claim.invoice_line = line
                    claim.invoice = invoice
                    claim.save(update_fields=['invoice_line', 'invoice', 'modified'])
            except Exception:
                logger.exception('sync_corporate_invoice_visit_charges: claim pk=%s', claim.pk)
    except Exception:
        logger.exception('sync_corporate_invoice_visit_charges: claim items invoice=%s', invoice.pk)

    try:
        invoice.update_totals()
    except Exception:
        logger.exception('sync_corporate_invoice_visit_charges: update_totals invoice=%s', invoice.pk)

