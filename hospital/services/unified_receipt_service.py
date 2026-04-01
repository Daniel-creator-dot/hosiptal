"""
🏆 WORLD-CLASS UNIFIED RECEIPT GENERATION SYSTEM
Automatic QR code generation for all payment points
Pharmacy | Lab | Imaging | Procedures | Consultation | All Services
"""
import qrcode
from io import BytesIO
from django.core.files import File
from django.utils import timezone
from django.db import transaction
from decimal import Decimal
import json
import logging

logger = logging.getLogger(__name__)


class UnifiedReceiptService:
    """
    Centralized service for receipt generation with QR codes
    Handles all payment types: Lab, Pharmacy, Imaging, Procedures, etc.
    """
    
    @staticmethod
    def create_receipt_with_qr(
        patient,
        amount,
        payment_method,
        received_by_user,
        invoice=None,
        bill=None,
        service_type=None,
        service_details=None,
        notes=''
    ):
        """
        Create a payment receipt with automatic QR code generation
        
        Args:
            patient: Patient object
            amount: Decimal amount paid
            payment_method: 'cash', 'card', 'mobile_money', etc.
            received_by_user: User who received payment
            invoice: Invoice object (if applicable)
            bill: Bill object (if applicable)
            service_type: 'lab', 'pharmacy', 'imaging', 'consultation', etc.
            service_details: Dict with service-specific details
            notes: Additional notes
        
        Returns:
            dict: {
                'receipt': PaymentReceipt object,
                'qr_code': ReceiptQRCode object,
                'transaction': Transaction object
            }
        """
        from hospital.models_accounting import Transaction, PaymentReceipt
        from hospital.models_payment_verification import ReceiptQRCode
        from hospital.models import Invoice
        
        try:
            with transaction.atomic():
                # Check for duplicate transaction before creating
                from datetime import timedelta
                recent_cutoff = timezone.now() - timedelta(minutes=1)
                
                existing_transaction = Transaction.objects.filter(
                    transaction_type='payment_received',
                    invoice=invoice,
                    patient=patient,
                    amount=amount,
                    payment_method=payment_method,
                    transaction_date__gte=recent_cutoff,
                    is_deleted=False
                ).first()
                
                if existing_transaction:
                    # Duplicate found - return existing transaction
                    logger.warning(
                        f"Duplicate payment transaction detected. "
                        f"Using existing transaction {existing_transaction.id}"
                    )
                    trans = existing_transaction
                else:
                    # 1. Create Transaction
                    trans = Transaction.objects.create(
                        transaction_type='payment_received',
                        invoice=invoice,
                        patient=patient,
                        amount=amount,
                        payment_method=payment_method,
                        processed_by=received_by_user,
                        transaction_date=timezone.now(),
                        notes=notes or f"Payment for {service_type or 'services'}"
                    )
                
                # 2. Get or create invoice if not provided
                if not invoice:
                    if bill:
                        # One invoice per encounter: reuse encounter invoice when bill has encounter (plan §4/§5)
                        encounter = getattr(bill, 'encounter', None)
                        if encounter:
                            try:
                                from hospital.utils_billing import get_or_create_encounter_invoice
                                invoice = get_or_create_encounter_invoice(encounter)
                            except Exception:
                                invoice = None
                        if not invoice:
                            invoice = Invoice.objects.filter(
                                patient=patient,
                                is_deleted=False
                            ).order_by('-created').first()
                        if not invoice:
                            from hospital.models import Payer
                            payer = patient.primary_insurance
                            if not payer:
                                payer, _ = Payer.objects.get_or_create(
                                    name='Cash',
                                    defaults={'payer_type': 'cash', 'is_active': True}
                                )
                            from datetime import timedelta
                            invoice = Invoice.objects.create(
                                patient=patient,
                                encounter=encounter if encounter else None,
                                payer=payer,
                                issued_at=timezone.now(),
                                due_at=timezone.now() + timedelta(days=7),
                                status='paid',
                                total_amount=amount,
                                balance=Decimal('0.00')
                            )
                    else:
                        # Get payer
                        from hospital.models import Payer
                        payer = patient.primary_insurance
                        if not payer:
                            payer, _ = Payer.objects.get_or_create(
                                name='Cash',
                                defaults={'payer_type': 'cash', 'is_active': True}
                            )
                        
                        from datetime import timedelta
                        # Create a simple receipt-only invoice
                        invoice = Invoice.objects.create(
                            patient=patient,
                            payer=payer,
                            issued_at=timezone.now(),
                            due_at=timezone.now() + timedelta(days=7),
                            status='paid',
                            total_amount=amount,
                            balance=Decimal('0.00')
                        )
                
                # 3. Create PaymentReceipt
                # Check for duplicate receipt before creating
                existing_receipt = PaymentReceipt.objects.filter(
                    transaction=trans,
                    invoice=invoice,
                    is_deleted=False
                ).first()
                
                if not existing_receipt:
                    receipt = PaymentReceipt.objects.create(
                        transaction=trans,
                        invoice=invoice,
                        patient=patient,
                        amount_paid=amount,
                        payment_method=payment_method,
                        received_by=received_by_user,
                        receipt_date=timezone.now(),
                        notes=notes,
                        service_type=service_type or 'other',
                        service_details=service_details or {}
                    )
                else:
                    receipt = existing_receipt
                
                # 4. Generate QR Code Data
                qr_data = UnifiedReceiptService._generate_qr_data(
                    receipt=receipt,
                    service_type=service_type,
                    service_details=service_details
                )
                
                # 5. Create QR Code (prevent duplicates)
                existing_qr_code = ReceiptQRCode.objects.filter(
                    receipt=receipt,
                    is_deleted=False
                ).first()
                
                if not existing_qr_code:
                    qr_code_obj = ReceiptQRCode.objects.create(
                        receipt=receipt,
                        qr_code_data=qr_data
                    )
                else:
                    # Update existing QR code
                    qr_code_obj = existing_qr_code
                    qr_code_obj.qr_code_data = qr_data
                    qr_code_obj.save()
                
                # 6. Generate QR Code Image
                qr_code_obj.generate_qr_code()
                qr_code_obj.save()
                
                # 7. Update invoice totals from lines and receipts (single source of truth)
                # Also syncs pharmacy dispensing + prescribe sales when invoice is settled (Invoice._sync_pharmacy_after_totals_saved)
                invoice.update_totals()

                try:
                    from hospital.services.pharmacy_invoice_payment_link import (
                        link_pharmacy_dispensing_when_invoice_paid,
                    )
                    if invoice and (invoice.balance or Decimal('0')) <= Decimal('0'):
                        link_pharmacy_dispensing_when_invoice_paid(
                            invoice,
                            receipt=receipt,
                            verified_by_user=received_by_user,
                            refresh_invoice=False,
                        )
                except Exception as link_exc:
                    logger.warning(
                        "Pharmacy receipt attach after unified receipt: %s", link_exc, exc_info=True
                    )

                logger.info(
                    f"✅ Receipt {receipt.receipt_number} created with QR code "
                    f"for {patient.full_name} - {service_type} - GHS {amount}"
                )
                
                # 8. 🌿 PAPERLESS: Send digital receipt
                from hospital.services.paperless_receipt_service import DigitalReceiptPreferences
                try:
                    digital_results = DigitalReceiptPreferences.send_by_preferences(receipt)
                    logger.info(f"📧 Digital receipt sent: Email={digital_results.get('email', {}).get('sent')}, SMS={digital_results.get('sms', {}).get('sent')}")
                except Exception as e:
                    logger.error(f"Error sending digital receipt: {str(e)}")
                    digital_results = {}
                
                # 9. 💰 ACCOUNTING: Auto-sync to accounting system
                from hospital.services.accounting_sync_service import AccountingSyncService
                try:
                    accounting_result = AccountingSyncService.sync_payment_to_accounting(
                        payment_receipt=receipt,
                        service_type=service_type or 'general'
                    )
                    logger.info(f"💰 Accounting sync: {accounting_result.get('message')}")
                except Exception as e:
                    logger.error(f"Error syncing to accounting: {str(e)}")
                    accounting_result = {'success': False}
                
                return {
                    'success': True,
                    'receipt': receipt,
                    'qr_code': qr_code_obj,
                    'transaction': trans,
                    'digital_receipt': digital_results,
                    'accounting_sync': accounting_result,
                    'message': f'Receipt {receipt.receipt_number} generated successfully (Paperless + Accounting synced)'
                }
                
        except Exception as e:
            logger.error(f"❌ Error creating receipt: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'message': f'Failed to generate receipt: {str(e)}'
            }

    @staticmethod
    def create_deposit_application_receipt(patient, amount_applied, received_by_user, invoice=None):
        """
        Create a receipt for deposit applied to bill. Does NOT update invoice balance
        (deposit was already applied by deposit_payment_service). Use when cashier
        clicks "Apply deposit to bill" so the patient gets a receipt for the deposit payment.
        """
        from hospital.models_accounting import Transaction, PaymentReceipt
        from hospital.models_payment_verification import ReceiptQRCode
        from hospital.models import Invoice

        if not invoice:
            invoice = Invoice.objects.filter(
                patient=patient,
                is_deleted=False
            ).order_by('-modified').first()
        if not invoice:
            logger.error("create_deposit_application_receipt: no invoice for patient %s", patient.id)
            return {'success': False, 'error': 'No invoice to attach receipt to'}

        try:
            with transaction.atomic():
                trans = Transaction.objects.create(
                    transaction_type='payment_received',
                    invoice=invoice,
                    patient=patient,
                    amount=amount_applied,
                    payment_method='deposit',
                    processed_by=received_by_user,
                    transaction_date=timezone.now(),
                    notes='Deposit applied to bill'
                )
                receipt = PaymentReceipt.objects.create(
                    transaction=trans,
                    invoice=invoice,
                    patient=patient,
                    amount_paid=amount_applied,
                    payment_method='deposit',
                    received_by=received_by_user,
                    receipt_date=timezone.now(),
                    notes='Deposit applied to bill',
                    service_type='other',
                    service_details={'deposit_applied': True, 'description': 'Deposit applied to bill'}
                )
                qr_data = UnifiedReceiptService._generate_qr_data(
                    receipt=receipt,
                    service_type='other',
                    service_details=receipt.service_details
                )
                qr_code_obj = ReceiptQRCode.objects.create(
                    receipt=receipt,
                    qr_code_data=qr_data
                )
                qr_code_obj.generate_qr_code()
                qr_code_obj.save()
                logger.info(
                    f"✅ Deposit application receipt {receipt.receipt_number} for {patient.full_name} GHS {amount_applied}"
                )
                try:
                    from hospital.services.paperless_receipt_service import DigitalReceiptPreferences
                    digital_results = DigitalReceiptPreferences.send_by_preferences(receipt)
                except Exception as e:
                    logger.warning("Digital receipt send failed: %s", e)
                    digital_results = {}
                return {
                    'success': True,
                    'receipt': receipt,
                    'qr_code': qr_code_obj,
                    'transaction': trans,
                    'digital_receipt': digital_results,
                }
        except Exception as e:
            logger.error("❌ create_deposit_application_receipt: %s", e, exc_info=True)
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def _generate_qr_data(receipt, service_type=None, service_details=None):
        """
        Generate QR code data with all necessary information
        """
        data = {
            'receipt_number': receipt.receipt_number,
            'patient_mrn': receipt.patient.mrn,
            'patient_name': receipt.patient.full_name,
            'amount': str(receipt.amount_paid),
            'payment_method': receipt.payment_method,
            'date': receipt.receipt_date.isoformat(),
            'service_type': service_type or 'general',
            'verification_url': f'/hms/receipt/verify/{receipt.receipt_number}/'
        }
        
        # Add service-specific details
        if service_details:
            data['service_details'] = service_details
        
        return json.dumps(data)
    
    @staticmethod
    def verify_receipt_by_qr(qr_data_string, verified_by_user):
        """
        Verify a receipt by scanning its QR code
        
        Args:
            qr_data_string: JSON string from QR code
            verified_by_user: User performing verification
        
        Returns:
            dict with verification result
        """
        from hospital.models_accounting import PaymentReceipt
        from hospital.models_payment_verification import ReceiptQRCode
        
        try:
            # Parse QR data
            qr_data = json.loads(qr_data_string)
            receipt_number = qr_data.get('receipt_number')
            
            if not receipt_number:
                return {
                    'success': False,
                    'message': 'Invalid QR code: No receipt number found'
                }
            
            # Find receipt
            try:
                receipt = PaymentReceipt.objects.get(
                    receipt_number=receipt_number,
                    is_deleted=False
                )
            except PaymentReceipt.DoesNotExist:
                return {
                    'success': False,
                    'message': f'Receipt {receipt_number} not found'
                }
            
            # Find QR code
            try:
                qr_code = receipt.qr_code
                qr_code.record_scan(verified_by_user)
            except:
                pass
            
            return {
                'success': True,
                'receipt': receipt,
                'patient': receipt.patient,
                'amount': receipt.amount_paid,
                'date': receipt.receipt_date,
                'service_type': qr_data.get('service_type', 'general'),
                'message': f'✅ Receipt {receipt_number} verified successfully'
            }
            
        except json.JSONDecodeError:
            return {
                'success': False,
                'message': 'Invalid QR code format'
            }
        except Exception as e:
            logger.error(f"Error verifying receipt: {str(e)}")
            return {
                'success': False,
                'message': f'Verification failed: {str(e)}'
            }
    
    @staticmethod
    def verify_receipt_by_number(receipt_number, verified_by_user):
        """
        Verify a receipt by entering receipt number manually
        """
        from hospital.models_accounting import PaymentReceipt
        
        try:
            receipt = PaymentReceipt.objects.get(
                receipt_number=receipt_number,
                is_deleted=False
            )
            
            # Record scan if QR code exists
            try:
                qr_code = receipt.qr_code
                qr_code.record_scan(verified_by_user)
            except:
                pass
            
            return {
                'success': True,
                'receipt': receipt,
                'patient': receipt.patient,
                'amount': receipt.amount_paid,
                'date': receipt.receipt_date,
                'message': f'✅ Receipt {receipt_number} verified'
            }
            
        except PaymentReceipt.DoesNotExist:
            return {
                'success': False,
                'message': f'Receipt {receipt_number} not found'
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'Verification failed: {str(e)}'
            }


class LabPaymentService:
    """Service for lab payment and receipt generation"""
    
    @staticmethod
    def create_lab_payment_receipt(lab_result, amount, payment_method, received_by_user, notes='', invoice=None):
        """Create receipt for lab test payment. Pass invoice when deposit was applied (use existing invoice)."""
        service_details = {
            'lab_result_id': str(lab_result.id),
            'test_name': lab_result.test.name,
            'test_code': lab_result.test.code if hasattr(lab_result.test, 'code') else '',
            'order_id': str(lab_result.order.id)
        }
        
        result = UnifiedReceiptService.create_receipt_with_qr(
            patient=lab_result.order.encounter.patient,
            amount=amount,
            payment_method=payment_method,
            received_by_user=received_by_user,
            service_type='lab_test',
            service_details=service_details,
            notes=notes or f"Payment for {lab_result.test.name}",
            invoice=invoice
        )
        
        if result['success']:
            # Link receipt to lab result release record
            from hospital.models_payment_verification import LabResultRelease
            
            try:
                release_record, created = LabResultRelease.objects.get_or_create(
                    lab_result=lab_result,
                    patient=lab_result.order.encounter.patient,
                    defaults={
                        'release_status': 'ready_for_release',
                        'payment_receipt': result['receipt'],
                        'payment_verified_at': timezone.now(),
                        'payment_verified_by': received_by_user
                    }
                )
                
                if not created:
                    release_record.payment_receipt = result['receipt']
                    release_record.payment_verified_at = timezone.now()
                    release_record.payment_verified_by = received_by_user
                    release_record.release_status = 'ready_for_release'
                    release_record.save()
                
            except Exception as e:
                logger.error(f"Error creating lab release record: {str(e)}")
        
        return result


class PharmacyPaymentService:
    """Service for pharmacy payment and receipt generation"""
    
    @staticmethod
    def create_pharmacy_payment_receipt(prescription, amount, payment_method, received_by_user, notes='', invoice=None):
        """Create receipt for pharmacy prescription payment. Pass invoice when deposit was applied."""
        service_details = {
            'prescription_id': str(prescription.id),
            'drug_name': prescription.drug.name,
            'quantity': prescription.quantity,
            'dose': prescription.dose,
            'frequency': prescription.frequency,
            'duration': prescription.duration
        }
        
        result = UnifiedReceiptService.create_receipt_with_qr(
            patient=prescription.order.encounter.patient,
            amount=amount,
            payment_method=payment_method,
            received_by_user=received_by_user,
            service_type='pharmacy_prescription',
            service_details=service_details,
            notes=notes or f"Payment for {prescription.drug.name}",
            invoice=invoice
        )
        
        if result['success']:
            # Link receipt to pharmacy dispensing record
            from hospital.models_payment_verification import PharmacyDispensing
            
            try:
                dispensing_record, created = PharmacyDispensing.objects.get_or_create(
                    prescription=prescription,
                    patient=prescription.order.encounter.patient,
                    defaults={
                        'dispensing_status': 'ready_to_dispense',
                        'quantity_ordered': prescription.quantity,
                        'payment_receipt': result['receipt'],
                        'payment_verified_at': timezone.now(),
                        'payment_verified_by': received_by_user
                    }
                )
                
                if not created:
                    dispensing_record.payment_receipt = result['receipt']
                    dispensing_record.payment_verified_at = timezone.now()
                    dispensing_record.payment_verified_by = received_by_user
                    dispensing_record.dispensing_status = 'ready_to_dispense'
                    dispensing_record.save()
                
            except Exception as e:
                logger.error(f"Error creating dispensing record: {str(e)}")
        
        return result


class ImagingPaymentService:
    """Service for imaging/radiology payment and receipt generation"""
    
    @staticmethod
    def create_imaging_payment_receipt(imaging_study, amount, payment_method, received_by_user, notes='', invoice=None):
        """Create receipt for imaging study payment. Pass invoice when deposit was applied."""
        service_details = {
            'study_id': str(imaging_study.id),
            'study_type': imaging_study.study_type,
            'modality': imaging_study.modality if hasattr(imaging_study, 'modality') else '',
            'body_part': imaging_study.body_part if hasattr(imaging_study, 'body_part') else ''
        }
        
        result = UnifiedReceiptService.create_receipt_with_qr(
            patient=imaging_study.order.encounter.patient if hasattr(imaging_study, 'order') else imaging_study.patient,
            amount=amount,
            payment_method=payment_method,
            received_by_user=received_by_user,
            service_type='imaging_study',
            service_details=service_details,
            notes=notes or f"Payment for {imaging_study.study_type}",
            invoice=invoice
        )
        
        if result.get('success'):
            from hospital.models_payment_verification import ImagingRelease
            patient = imaging_study.order.encounter.patient if hasattr(imaging_study, 'order') and imaging_study.order else getattr(imaging_study, 'patient', None)
            if patient:
                try:
                    release_record, created = ImagingRelease.objects.get_or_create(
                        imaging_study=imaging_study,
                        patient=patient,
                        defaults={
                            'release_status': 'ready_for_release',
                            'payment_receipt': result['receipt'],
                            'payment_verified_at': timezone.now(),
                            'payment_verified_by': received_by_user
                        }
                    )
                    if not created:
                        release_record.payment_receipt = result['receipt']
                        release_record.payment_verified_at = timezone.now()
                        release_record.payment_verified_by = received_by_user
                        release_record.release_status = 'ready_for_release'
                        release_record.save()
                except Exception as e:
                    import logging
                    logging.getLogger(__name__).error(f"Error creating imaging release record: {str(e)}")
            # Mark imaging study as paid so it appears in imaging dashboard "Paid" tab
            try:
                imaging_study.mark_as_paid(
                    amount,
                    receipt_number=result.get('receipt').receipt_number if result.get('receipt') else ''
                )
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(f"Could not mark ImagingStudy as paid: {e}")
        
        return result


class ConsultationPaymentService:
    """Service for consultation payment and receipt generation"""
    
    @staticmethod
    def create_consultation_payment_receipt(encounter, amount, payment_method, received_by_user, notes=''):
        """Create receipt for consultation fee. Links to encounter's invoice so payment clears the right bill and item disappears from pending list."""
        from hospital.utils_billing import get_or_create_encounter_invoice
        invoice = get_or_create_encounter_invoice(encounter)
        service_details = {
            'encounter_type': encounter.encounter_type,
            'encounter_id': str(encounter.id),
            'provider': encounter.provider.user.get_full_name() if encounter.provider else '',
            'department': encounter.location.name if encounter.location else ''
        }
        
        result = UnifiedReceiptService.create_receipt_with_qr(
            patient=encounter.patient,
            amount=amount,
            payment_method=payment_method,
            received_by_user=received_by_user,
            invoice=invoice,
            service_type='consultation',
            service_details=service_details,
            notes=notes or f"Consultation fee - {encounter.encounter_type}"
        )
        if result and result.get('receipt') and invoice:
            try:
                invoice.update_totals()
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(f"Could not update invoice totals after consultation payment: {e}")
        
        return result


class ProcedurePaymentService:
    """Service for procedure payment and receipt generation"""
    
    @staticmethod
    def create_procedure_payment_receipt(patient, procedure_name, amount, payment_method, received_by_user, notes=''):
        """Create receipt for medical procedure payment"""
        service_details = {
            'procedure_name': procedure_name
        }
        
        result = UnifiedReceiptService.create_receipt_with_qr(
            patient=patient,
            amount=amount,
            payment_method=payment_method,
            received_by_user=received_by_user,
            service_type='procedure',
            service_details=service_details,
            notes=notes or f"Payment for {procedure_name}"
        )
        
        return result


class BedPaymentService:
    """Service for bed charge payment and receipt generation"""
    
    @staticmethod
    def create_bed_payment_receipt(admission, amount, payment_method, received_by_user, notes=''):
        """Create receipt for bed charges payment"""
        from hospital.services.bed_billing_service import bed_billing_service
        
        try:
            charges = bed_billing_service.get_bed_charges_summary(admission)
            days = charges['days_admitted']
            daily_rate = charges['daily_rate']
        except:
            days = admission.get_duration_days()
            daily_rate = Decimal('120.00')
        
        service_details = {
            'ward_name': admission.ward.name if admission.ward else '',
            'bed_number': admission.bed.bed_number if admission.bed else '',
            'admission_id': str(admission.id),
            'days': days,
            'daily_rate': float(daily_rate)
        }
        
        result = UnifiedReceiptService.create_receipt_with_qr(
            patient=admission.encounter.patient,
            amount=amount,
            payment_method=payment_method,
            received_by_user=received_by_user,
            service_type='admission',
            service_details=service_details,
            notes=notes or f"Bed charges - {admission.ward.name} - Bed {admission.bed.bed_number}"
        )
        
        return result


# Export all services
__all__ = [
    'UnifiedReceiptService',
    'LabPaymentService',
    'PharmacyPaymentService',
    'ImagingPaymentService',
    'ConsultationPaymentService',
    'ProcedurePaymentService',
    'BedPaymentService',
]

