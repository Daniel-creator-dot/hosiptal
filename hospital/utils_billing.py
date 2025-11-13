"""
Utility functions for automatic billing and charge capture
"""
from decimal import Decimal
from django.utils import timezone
from datetime import timedelta


def add_consultation_charge(encounter, consultation_type='general'):
    """
    Add consultation charge to encounter's invoice
    Uses intelligent pricing engine for multi-tier pricing
    consultation_type: 'general' or 'specialist'
    """
    from .models import Invoice, InvoiceLine, ServiceCode, Payer, Patient
    from .models_pricing import DefaultPrice, PayerPrice
    from .services.pricing_engine_service import pricing_engine
    
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
    
    # 💰 USE NEW PRICING ENGINE: Get intelligent price based on patient type
    try:
        consultation_price = pricing_engine.get_service_price(
            service_code=service_code,
            patient=patient,
            payer=payer
        )
        
        # Log which price tier was used
        import logging
        logger = logging.getLogger(__name__)
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
    
    if not existing_line:
        # Add consultation fee line
        InvoiceLine.objects.create(
            invoice=invoice,
            service_code=service_code,
            description=description,
            quantity=1,
            unit_price=consultation_price,
            line_total=consultation_price
        )
        
        # Update invoice totals
        invoice.update_totals()
        return invoice
    
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

