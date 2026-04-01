"""
Utility functions for automatic billing and charge capture
"""
import logging
from decimal import Decimal
from django.utils import timezone
from datetime import datetime, time, timedelta

from .models import Invoice, InvoiceLine, ServiceCode, Payer, Patient
from .models_pricing import DefaultPrice, PayerPrice
from .services.pricing_engine_service import pricing_engine
from hospital.models_enterprise_billing import ServicePricing


logger = logging.getLogger(__name__)


def local_datetime_bounds_for_date(d):
    """
    Inclusive start and exclusive end (timezone-aware) for the hospital's current timezone calendar day.
    Use instead of __date lookups on UTC-stored datetimes so "today" matches staff expectations.
    """
    tz = timezone.get_current_timezone()
    start = timezone.make_aware(datetime.combine(d, time.min), tz)
    return start, start + timedelta(days=1)


# Consultation-like invoice lines (OPD + antenatal + legacy/import codes). Cashier and payer sync must use the same set.
CONSULTATION_LINE_SERVICE_CODES = ('CON001', 'CON002', 'MAT-ANC', 'S00023', 'CONS-GEN')

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
    cat = (sc.category or '').strip()
    if 'consult' in cat.casefold():
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
        from .models_insurance_companies import PatientInsurance

        # Any active enrollment (not only is_primary — data often has primary flag unset)
        pip_qs = (
            PatientInsurance.objects.filter(
                patient=patient,
                status='active',
                is_deleted=False,
            )
            .select_related('insurance_company')
            .order_by('-is_primary', '-created')
        )
        for pip in pip_qs[:5]:
            if pip.insurance_company:
                push(getattr(pip.insurance_company, 'name', None))
    except Exception:
        pass

    if not out:
        legacy = (getattr(patient, 'insurance_company', '') or '').strip()
        if legacy and legacy.lower() not in ('cash', 'none', 'n/a', '-', ''):
            push(legacy)

    return out


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
        if emp and emp.corporate_account:
            name = (emp.corporate_account.company_name or '').strip()
            return name or None
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

    # 1. Encounter invoice (most specific for this visit)
    if encounter:
        inv = Invoice.all_objects.filter(
            encounter=encounter, is_deleted=False
        ).select_related('payer').order_by('-created').first()
        if (
            inv
            and inv.payer
            and not getattr(inv.payer, 'is_deleted', False)
            and getattr(inv.payer, 'payer_type', '') != 'cash'
        ):
            payer = inv.payer
            payer_type = getattr(payer, 'payer_type', 'cash')
            payer_name = getattr(payer, 'name', '')

    # 2. Patient primary_insurance
    if not payer or payer_type == 'cash':
        payer = getattr(patient, 'primary_insurance', None)
        if payer and not getattr(payer, 'is_deleted', False):
            payer_type = getattr(payer, 'payer_type', 'cash')
            payer_name = getattr(payer, 'name', '')

    # 3. Corporate: check CorporateEmployee (patient may be corporate without primary_insurance set)
    if not payer or payer_type == 'cash':
        corp_name = corporate_enrollment_company_name(patient)
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
                    patient=patient, status='active', is_deleted=False
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
    corp_company = corporate_enrollment_company_name(patient)
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
        pi_direct = getattr(patient, 'primary_insurance', None)
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
                elif pt == 'corporate' and (payer_name or '').strip().lower() != cn.lower():
                    corporate_badge_name = cn

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
    - General Consultation: Cash = 150, Corporate/Insurance from PricingCategory (run seed_general_prices)
    - Specialist Consultation: Cash = 300, Corporate/Insurance from PricingCategory
    """
    today = timezone.now().date()
    is_general = (service_code.code or '').strip().upper() in ('CON001', 'CONS-GEN', 'CONSULTATION_GENERAL')
    desired_cash = Decimal('150.00') if is_general else Decimal('300.00')
    desired_insurance = Decimal('150.00') if is_general else Decimal('300.00')
    
    pricing, created = ServicePricing.objects.get_or_create(
        service_code=service_code,
        payer__isnull=True,
        defaults={
            'is_active': True,
            'effective_from': today,
            'cash_price': desired_cash,
            'corporate_price': desired_cash,
            'insurance_price': desired_insurance,
        }
    )
    
    updated = False
    if pricing.cash_price != desired_cash:
        pricing.cash_price = desired_cash
        updated = True
    if pricing.corporate_price != desired_cash:
        pricing.corporate_price = desired_cash
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


# 50% markup for drugs billed to insurance and corporate payers
DRUG_INSURANCE_CORPORATE_MARKUP = Decimal('0.50')


def get_drug_price_for_prescription(drug, payer=None):
    """
    Get stable drug selling price for prescriptions.
    Prefers Drug.unit_price (selling price) when set and > 0, so pharmacy price does not
    change with every stock receipt or inventory sync. Falls back to pharmacy store
    InventoryItem.unit_cost only when Drug.unit_price is 0 or unset.
    For insurance and corporate payers, adds 50% markup to base price.

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
    # Add 15% for insurance and corporate
    if payer and getattr(payer, 'payer_type', None) in ('insurance', 'private', 'nhis', 'corporate'):
        base = base * (1 + DRUG_INSURANCE_CORPORATE_MARKUP)
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
    Check if this is a review visit (no charges should be applied)
    Checks encounter notes and chief_complaint for review indicators
    """
    if not encounter:
        return False
    
    # Check notes for review markers
    notes_lower = (encounter.notes or '').lower()
    complaint_lower = (encounter.chief_complaint or '').lower()
    
    review_keywords = ['review', 'follow-up', 'followup', 'revisit', 're-check', 'recheck']
    
    # Check if notes contain review markers
    if any(keyword in notes_lower for keyword in review_keywords):
        return True
    
    # Check if chief_complaint contains review keywords
    if any(keyword in complaint_lower for keyword in review_keywords):
        return True
    
    # Check for explicit [REVIEW_VISIT] marker in notes
    if '[review_visit]' in notes_lower or '[review]' in notes_lower:
        return True
    
    return False


def add_consultation_charge(encounter, consultation_type='general', doctor_staff=None):
    """
    Add consultation charge to encounter's invoice
    Uses intelligent pricing engine for multi-tier pricing
    consultation_type: 'general' or 'specialist'
    doctor_staff: Optional Staff object for doctor-specific pricing
    
    ⚠️ POLICY: Anyone who goes through consultation MUST be billed with the price.
    
    Special handling:
    - Antenatal visits use MAT-ANC service code with existing pricing
    - Doctor-specific pricing takes precedence over general pricing
    - Specialist visits: 300 for cash, insurance pricing for insurance clients
    - Insurance clients always use insurance price category (never cash fallback)
    """
    
    # Get patient's payer - ensure payer is not None
    patient = encounter.patient
    payer = patient.primary_insurance
    
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
                patient=patient,
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
        
        if getattr(encounter, 'billing_closed_at', None):
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
    
    # 💰 DOCTOR-SPECIFIC PRICING: Check if doctor has custom pricing
    consultation_price = None
    if doctor_staff:
        try:
            from .utils_doctor_pricing import DoctorPricingService
            consultation_price = DoctorPricingService.get_consultation_fee(
                patient=patient,
                doctor_staff=doctor_staff,
                encounter_type=encounter_type_lower,
                is_review_visit=False  # Already checked above
            )
            logger.info(
                f"💰 Doctor-specific pricing for {doctor_staff.user.get_full_name()}: "
                f"GHS {consultation_price} (Patient: {patient.full_name})"
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
        fallback_cash = Decimal('150.00') if consultation_type == 'general' else Decimal('300.00')
        try:
            consultation_price = pricing_engine.get_service_price(
                service_code=service_code,
                patient=patient,
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
                        consultation_price = fallback_cash
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
                            f"run seed_general_prices. Patient: {patient.full_name}"
                        )
                else:
                    consultation_price = fallback_cash
            
            logger.info(
                f"💰 Consultation price for {patient.full_name}: "
                f"GHS {consultation_price} (Payer: {payer.name}, Type: {payer.payer_type}, "
                f"Consultation: {consultation_type})"
            )
            
        except Exception as e:
            logger.error(f"Error in pricing engine: {e}", exc_info=True)
            consultation_price = PayerPrice.get_price(payer, service_code_key)
        if consultation_price is None:
            if payer and payer.payer_type == 'cash':
                consultation_price = Decimal('150.00') if consultation_type == 'general' else Decimal('300.00')
            else:
                consultation_price = DefaultPrice.get_price(
                    'consultation_general' if consultation_type == 'general' else 'consultation_specialist',
                    Decimal('150.00') if consultation_type == 'general' else Decimal('300.00'),
                )
    
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
    
    if getattr(encounter, 'billing_closed_at', None):
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


_CONSULTATION_LINE_PRELOAD = object()


def get_consultation_price_for_encounter(encounter, preloaded_consultation_line=_CONSULTATION_LINE_PRELOAD):
    """
    Return the consultation price for an encounter (for display/cashier).
    Uses the same logic as add_consultation_charge: doctor-specific pricing or
    general 150 / specialist 300. Never returns the wrong legacy 30.
    When an invoice line exists, prefer that line's amount.
    If preloaded_consultation_line is passed (including None from a bulk lookup), skip fetching the line again.
    """
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
    if doctor_staff:
        try:
            from .utils_doctor_pricing import DoctorPricingService
            fee = DoctorPricingService.get_consultation_fee(
                patient=patient,
                doctor_staff=doctor_staff,
                encounter_type=encounter_type_lower or None,
                is_review_visit=False,
            )
            if fee is not None and fee >= 0:
                # Legacy fix: general OPD is 150, never show old wrong 30
                if fee == Decimal('30.00'):
                    fee = Decimal('150.00')
                # Doctor tier 0 must not block gynae 260 / specialist fallbacks below
                if fee > 0:
                    return fee
        except Exception:
            pass
    if encounter_type_lower == 'gynae':
        return Decimal('260.00')
    # General OPD = 150, specialist = 300 (match add_consultation_charge fallback)
    # Use encounter_type so Special Consultation shows correct price at cashier even without assigned doctor
    if encounter_type_lower == 'specialist':
        return Decimal('300.00')
    return Decimal('150.00')


def get_consultation_price_for_encounter_and_payer(encounter, payer, consultation_type=None):
    """
    Compute consultation price for an encounter with a given payer.
    Same logic as add_consultation_charge (doctor-specific or pricing engine).
    Used when payer changes to update the consultation line amount.
    """
    patient = encounter.patient
    encounter_type_lower = (encounter.encounter_type or '').lower()
    if consultation_type is None:
        consultation_type = (
            'specialist'
            if encounter_type_lower in ('specialist', 'gynae')
            else 'general'
        )
    service_code_str = 'CON001' if consultation_type == 'general' else 'CON002'
    service_code = ServiceCode.objects.filter(
        code=service_code_str, is_active=True
    ).first()
    if not service_code:
        return Decimal('150.00') if consultation_type == 'general' else Decimal('300.00')
    doctor_staff = getattr(encounter, 'provider', None) or getattr(encounter, 'assigned_doctor', None)
    consultation_price = None
    if doctor_staff:
        try:
            from .utils_doctor_pricing import DoctorPricingService
            consultation_price = DoctorPricingService.get_consultation_fee(
                patient=patient,
                doctor_staff=doctor_staff,
                encounter_type=encounter_type_lower or None,
                is_review_visit=False,
            )
            if consultation_price is not None and consultation_price == Decimal('30.00'):
                consultation_price = Decimal('150.00')
        except Exception:
            pass
    if consultation_price is None and encounter_type_lower == 'gynae':
        consultation_price = Decimal('260.00')
    if consultation_price is None and payer:
        fallback_cash = Decimal('150.00') if consultation_type == 'general' else Decimal('300.00')
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
                        consultation_price = fallback_cash
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
    if consultation_price is None:
        return Decimal('150.00') if consultation_type == 'general' else Decimal('300.00')
    return consultation_price


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

