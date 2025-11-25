"""
Automatic Bed Billing Service
Charges patients for bed occupancy at GHS 120 per day
"""
from django.db import transaction
from django.utils import timezone
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


class BedBillingService:
    """Service for automatic bed billing and charges"""
    
    # Bed pricing configuration
    DAILY_BED_RATE = Decimal('120.00')  # GHS 120 per day
    VIP_BED_RATE = Decimal('300.00')    # VIP ward rate per day
    
    @staticmethod
    def _get_daily_rate(admission):
        """Return appropriate daily rate based on ward."""
        if admission and admission.ward:
            ward_name = (admission.ward.name or '').lower()
            if 'vip' in ward_name:
                return BedBillingService.VIP_BED_RATE
        return BedBillingService.DAILY_BED_RATE
    
    @staticmethod
    def create_admission_bill(admission, days=1):
        """
        Create bill/invoice for bed admission
        
        Args:
            admission: Admission object
            days: Number of days to bill (default: 1 for initial admission)
            
        Returns:
            dict with bill/invoice details
        """
        from hospital.models import Invoice, InvoiceLine
        from hospital.models_accounting import PaymentReceipt
        
        try:
            with transaction.atomic():
                patient = admission.encounter.patient
                encounter = admission.encounter
                
                # Calculate charge based on days
                daily_rate = BedBillingService._get_daily_rate(admission)
                total_charge = daily_rate * days
                
                # Get or create invoice for this encounter
                invoice, created = Invoice.objects.get_or_create(
                    patient=patient,
                    encounter=encounter,
                    status='draft',
                    defaults={
                        'invoice_date': timezone.now(),
                        'payer': patient.primary_insurance,
                        'subtotal': Decimal('0.00'),
                        'total_amount': Decimal('0.00'),
                        'balance': Decimal('0.00')
                    }
                )
                
                # Get or create ServiceCode for bed charges
                from hospital.models import ServiceCode
                bed_service_code_str = f"BED-{admission.bed.bed_number}"
                
                service_code, sc_created = ServiceCode.objects.get_or_create(
                    code=bed_service_code_str,
                    defaults={
                        'description': f'Bed {admission.bed.bed_number} - {admission.ward.name}',
                        'category': 'accommodation',
                        'default_price': daily_rate,
                        'is_active': True
                    }
                )
                
                # Add invoice line for bed charges
                bed_description = (
                    f"Bed Charges - {admission.ward.name} - Bed {admission.bed.bed_number} "
                    f"({days} day{'s' if days != 1 else ''} @ GHS {daily_rate}/day)"
                )
                
                invoice_line, line_created = InvoiceLine.objects.get_or_create(
                    invoice=invoice,
                    service_code=service_code,
                    defaults={
                        'description': bed_description,
                        'quantity': days,
                        'unit_price': daily_rate,
                        'line_total': total_charge
                    }
                )
                
                if line_created:
                    # Update invoice totals
                    invoice.total_amount += total_charge
                    invoice.balance += total_charge
                    invoice.status = 'issued'  # Ready for payment
                    invoice.save()
                    
                    logger.info(
                        f"✅ Bed billing created: {patient.full_name} - "
                        f"{days} day(s) @ GHS {daily_rate} = GHS {total_charge}"
                    )
                else:
                    logger.info(f"Bed charges already exist for admission {admission.pk}")
                
                return {
                    'success': True,
                    'invoice': invoice,
                    'invoice_line': invoice_line,
                    'days': days,
                    'daily_rate': daily_rate,
                    'total_charge': total_charge,
                    'message': f'Bed charges added: {days} day(s) @ GHS {daily_rate} = GHS {total_charge}'
                }
                
        except Exception as e:
            logger.error(f"Error creating bed billing: {str(e)}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'message': f'Failed to create bed billing: {str(e)}'
            }
    
    @staticmethod
    def calculate_admission_charges(admission, include_partial_days=True):
        """
        Calculate total bed charges for an admission
        
        Args:
            admission: Admission object
            include_partial_days: If True, charge for partial days (e.g., 2.5 days)
            
        Returns:
            dict with charge breakdown
        """
        days = admission.get_duration_days()
        
        # If include_partial_days, calculate hours and round up
        if include_partial_days:
            if admission.discharge_date:
                delta = admission.discharge_date - admission.admit_date
            else:
                delta = timezone.now() - admission.admit_date
            
            total_hours = delta.total_seconds() / 3600
            # Round up partial days (e.g., 1.5 days = 2 days charged)
            days = int(total_hours / 24) + (1 if total_hours % 24 > 0 else 0)
        
        # Ensure at least 1 day is charged
        if days < 1:
            days = 1
        
        daily_rate = BedBillingService._get_daily_rate(admission)
        total_charge = daily_rate * days
        
        return {
            'days': days,
            'daily_rate': daily_rate,
            'total_charge': total_charge,
            'admission_date': admission.admit_date,
            'discharge_date': admission.discharge_date or timezone.now(),
            'bed': admission.bed.bed_number if admission.bed else 'N/A',
            'ward': admission.ward.name if admission.ward else 'N/A'
        }
    
    @staticmethod
    def update_bed_charges_on_discharge(admission):
        """
        Update bed charges when patient is discharged
        Calculates final charges based on actual stay duration
        
        Args:
            admission: Admission object
            
        Returns:
            dict with updated charges
        """
        from hospital.models import Invoice, InvoiceLine
        
        try:
            with transaction.atomic():
                patient = admission.encounter.patient
                encounter = admission.encounter
                
                # Calculate actual days stayed
                charge_breakdown = BedBillingService.calculate_admission_charges(
                    admission,
                    include_partial_days=True
                )
                
                days = charge_breakdown['days']
                daily_rate = charge_breakdown['daily_rate']
                total_charge = charge_breakdown['total_charge']
                
                # Get existing invoice
                try:
                    invoice = Invoice.objects.get(
                        patient=patient,
                        encounter=encounter,
                        is_deleted=False
                    )
                except Invoice.DoesNotExist:
                    # Create new invoice if doesn't exist
                    invoice = Invoice.objects.create(
                        patient=patient,
                        encounter=encounter,
                        invoice_date=timezone.now(),
                        payer=patient.primary_insurance,
                        subtotal=Decimal('0.00'),
                        total_amount=Decimal('0.00'),
                        balance=Decimal('0.00'),
                        status='draft'
                    )
                
                # Find existing bed charge line
                from hospital.models import ServiceCode
                bed_service_codes = ServiceCode.objects.filter(
                    code__startswith='BED-',
                    is_deleted=False
                )
                
                bed_line = InvoiceLine.objects.filter(
                    invoice=invoice,
                    service_code__in=bed_service_codes,
                    is_deleted=False
                ).first()
                
                if bed_line:
                    # Update existing line with final charges
                    old_amount = bed_line.line_total
                    bed_line.quantity = days
                    bed_line.line_total = total_charge
                    bed_line.description = (
                        f"Bed Charges - {admission.ward.name} - Bed {admission.bed.bed_number} "
                        f"({days} day{'s' if days != 1 else ''} @ GHS {daily_rate}/day)"
                    )
                    bed_line.save()
                    
                    # Update invoice totals
                    invoice.total_amount = invoice.total_amount - old_amount + total_charge
                    invoice.balance = invoice.balance - old_amount + total_charge
                else:
                    # Create new line - need to get/create ServiceCode first
                    bed_service_code_str = f"BED-{admission.bed.bed_number}"
                    service_code_obj, sc_created = ServiceCode.objects.get_or_create(
                        code=bed_service_code_str,
                        defaults={
                            'description': f'Bed {admission.bed.bed_number} - {admission.ward.name}',
                            'category': 'accommodation',
                            'default_price': daily_rate,
                            'is_active': True
                        }
                    )
                    
                    bed_line = InvoiceLine.objects.create(
                        invoice=invoice,
                        service_code=service_code_obj,
                        description=f"Bed Charges - {admission.ward.name} - Bed {admission.bed.bed_number} ({days} days @ GHS {daily_rate}/day)",
                        quantity=days,
                        unit_price=daily_rate,
                        line_total=total_charge
                    )
                    
                    # Update invoice totals
                    invoice.total_amount += total_charge
                    invoice.balance += total_charge
                
                if invoice.balance > 0:
                    invoice.status = 'issued'
                invoice.save()
                
                logger.info(
                    f"✅ Bed charges updated on discharge: {patient.full_name} - "
                    f"{days} days @ GHS {daily_rate} = GHS {total_charge}"
                )
                
                return {
                    'success': True,
                    'invoice': invoice,
                    'invoice_line': bed_line,
                    'charge_breakdown': charge_breakdown,
                    'message': f'Bed charges updated: {days} days @ GHS {daily_rate} = GHS {total_charge}'
                }
                
        except Exception as e:
            logger.error(f"Error updating bed charges on discharge: {str(e)}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'message': f'Failed to update bed charges: {str(e)}'
            }
    
    @staticmethod
    def get_bed_charges_summary(admission):
        """
        Get summary of bed charges for an admission
        
        Returns:
            dict with current charges
        """
        charge_breakdown = BedBillingService.calculate_admission_charges(admission)
        
        return {
            'days_admitted': charge_breakdown['days'],
            'daily_rate': charge_breakdown['daily_rate'],
            'current_charges': charge_breakdown['total_charge'],
            'bed_number': charge_breakdown['bed'],
            'ward_name': charge_breakdown['ward'],
            'admission_date': charge_breakdown['admission_date'],
            'discharge_date': charge_breakdown['discharge_date'],
            'is_discharged': admission.status == 'discharged'
        }


# Singleton instance
bed_billing_service = BedBillingService()

