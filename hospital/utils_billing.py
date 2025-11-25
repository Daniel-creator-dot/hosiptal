"""
Utility functions for automatic billing and charge capture
"""
import logging
from decimal import Decimal
from django.utils import timezone
from datetime import timedelta

from .models import Invoice, InvoiceLine, ServiceCode, Payer, Patient
from .models_pricing import DefaultPrice, PayerPrice
from .services.pricing_engine_service import pricing_engine
from hospital.models_enterprise_billing import ServicePricing


logger = logging.getLogger(__name__)


def _ensure_consultation_pricing(service_code):
    """
    Ensure the standard pricing tiers for consultations are enforced:
    Cash = 120, Insurance = 150. Corporate defaults to cash.
    """
    today = timezone.now().date()
    desired_cash = Decimal('120.00')
    desired_insurance = Decimal('150.00')
    
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


def add_consultation_charge(encounter, consultation_type='general'):
    """
    Add consultation charge to encounter's invoice
    Uses intelligent pricing engine for multi-tier pricing
    consultation_type: 'general' or 'specialist'
    """
    
    # Get patient's payer - ensure payer is not None
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
    
    # Determine service code
    service_code_key = 'consultation_general' if consultation_type == 'general' else 'consultation_specialist'
    
    # Get or create consultation service code
    service_code_str = 'CON001' if consultation_type == 'general' else 'CON002'
    description = 'General Consultation' if consultation_type == 'general' else 'Specialist Consultation'
    
    service_code, _ = ServiceCode.objects.get_or_create(
        code=service_code_str,
        defaults={
            'description': description,
            'category': 'Clinical Services',
            'is_active': True,
            'default_price': Decimal('100.00') if consultation_type == 'general' else Decimal('150.00')
        }
    )
    
    if consultation_type == 'general':
        _ensure_consultation_pricing(service_code)
    
    # 💰 USE NEW PRICING ENGINE: Get intelligent price based on patient type
    try:
        consultation_price = pricing_engine.get_service_price(
            service_code=service_code,
            patient=patient,
            payer=payer
        )
        
        # Log which price tier was used
        logger.info(
            f"💰 Consultation price for {patient.full_name}: "
            f"GHS {consultation_price} (Payer: {payer.name})"
        )
        
    except Exception as e:
        # Fallback to old pricing if new engine fails
        consultation_price = PayerPrice.get_price(payer, service_code_key)
        if consultation_price is None:
            if consultation_type == 'general':
                consultation_price = DefaultPrice.get_price('consultation_general', Decimal('100.00'))
            else:
                consultation_price = DefaultPrice.get_price('consultation_specialist', Decimal('150.00'))
    
    # Get or create invoice for this encounter
    invoice = Invoice.objects.filter(
        encounter=encounter,
        is_deleted=False
    ).first()
    
    if not invoice:
        # Create new invoice
        due_date = timezone.now() + timedelta(days=30)
        invoice = Invoice.objects.create(
            patient=patient,
            encounter=encounter,
            payer=payer,
            status='draft',
            due_at=due_date,
            notes='Auto-generated invoice'
        )
    
    # Check if consultation charge already exists for this encounter
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
    
    _record_locum_consultation_service(encounter, consultation_price, consultation_type, invoice_line)
    return invoice


def get_or_create_encounter_invoice(encounter):
    """Get or create invoice for an encounter"""
    from .models import Invoice, Payer
    from datetime import timedelta
    
    # Check if invoice already exists
    invoice = Invoice.objects.filter(
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
    invoice = Invoice.objects.create(
        patient=patient,
        encounter=encounter,
        payer=payer,
        status='draft',
        due_at=due_date,
        notes='Auto-generated invoice'
    )
    
    return invoice

