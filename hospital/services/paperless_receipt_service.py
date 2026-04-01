"""
🌿 PAPERLESS RECEIPT SYSTEM - GO GREEN!
Digital receipts via Email, SMS, Patient Portal
Zero paper waste, instant delivery, eco-friendly
"""
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


class PaperlessReceiptService:
    """
    Digital receipt delivery service
    Sends receipts via email, SMS, patient portal
    """
    
    @staticmethod
    def send_digital_receipt(receipt, methods=['email', 'sms', 'portal']):
        """
        Send receipt through multiple digital channels
        
        Args:
            receipt: PaymentReceipt object
            methods: List of delivery methods ['email', 'sms', 'portal']
        
        Returns:
            dict with delivery status for each method
        """
        results = {
            'email': {'sent': False, 'message': ''},
            'sms': {'sent': False, 'message': ''},
            'portal': {'sent': False, 'message': ''},
        }
        
        patient = receipt.patient
        
        # 1. EMAIL RECEIPT
        if 'email' in methods and patient.email:
            email_result = PaperlessReceiptService._send_email_receipt(receipt)
            results['email'] = email_result
        
        # 2. SMS RECEIPT
        if 'sms' in methods and patient.phone_number:
            sms_result = PaperlessReceiptService._send_sms_receipt(receipt)
            results['sms'] = sms_result
        
        # 3. PATIENT PORTAL
        if 'portal' in methods:
            portal_result = PaperlessReceiptService._save_to_portal(receipt)
            results['portal'] = portal_result
        
        return results
    
    @staticmethod
    def _send_email_receipt(receipt):
        """Send receipt via email with QR code"""
        try:
            patient = receipt.patient
            
            # Get QR code
            qr_code = None
            qr_url = None
            try:
                qr_code = receipt.qr_code
                if qr_code.qr_code_image:
                    qr_url = qr_code.qr_code_image.url
            except:
                pass
            
            # Prepare context
            context = {
                'receipt': receipt,
                'patient': patient,
                'qr_code': qr_code,
                'qr_url': qr_url,
                'verification_url': f"{settings.SITE_URL}/hms/receipt/verify/number/",
            }
            
            # Render HTML email
            html_message = render_to_string('hospital/email_receipt.html', context)
            plain_message = strip_tags(html_message)
            
            # Send email
            send_mail(
                subject=f'Payment Receipt {receipt.receipt_number} - PrimeCare Medical',
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[patient.email],
                html_message=html_message,
                fail_silently=False,
            )
            
            logger.info(f"✅ Email receipt sent to {patient.email}")
            
            return {
                'sent': True,
                'message': f'Receipt emailed to {patient.email}'
            }
            
        except Exception as e:
            logger.error(f"❌ Error sending email receipt: {str(e)}")
            return {
                'sent': False,
                'message': f'Email failed: {str(e)}'
            }
    
    @staticmethod
    def _send_sms_receipt(receipt):
        """Send receipt via SMS with download link"""
        try:
            from hospital.services.sms_service import sms_service
            
            patient = receipt.patient
            
            # Create SMS message with receipt link
            message = (
                f"💳 Payment Receipt\n"
                f"Receipt: {receipt.receipt_number}\n"
                f"Amount Paid: GHS {receipt.amount_paid}\n"
                f"Date: {receipt.receipt_date.strftime('%b %d, %Y')}\n"
                f"\n"
                f"View details: {settings.SITE_URL}/hms/receipt/{receipt.id}/\n"
                f"\n"
                f"PrimeCare Medical Center"
            )
            
            # Send SMS
            sms_log = sms_service.send_sms(
                phone_number=patient.phone_number,
                message=message,
                message_type='payment_receipt',
                recipient_name=patient.full_name,
                related_object_id=receipt.id if hasattr(receipt, 'id') else None,
                related_object_type='PaymentReceipt'
            )
            
            if sms_log.status == 'sent':
                logger.info(f"✅ SMS receipt sent to {patient.phone_number}")
                return {
                    'sent': True,
                    'message': f'Receipt sent via SMS to {patient.phone_number}'
                }
            else:
                error_msg = sms_log.error_message or 'Unknown error'
                logger.warning(f"⚠️ SMS receipt failed: {error_msg}")
                return {
                    'sent': False,
                    'message': f'SMS send failed: {error_msg}'
                }
                
        except Exception as e:
            logger.error(f"❌ Error sending SMS receipt: {str(e)}")
            return {
                'sent': False,
                'message': f'SMS failed: {str(e)}'
            }
    
    @staticmethod
    def _save_to_portal(receipt):
        """Save receipt to patient portal for online access"""
        try:
            # Receipt already in database, just mark as available in portal
            # Patient can access via: /hms/patient-portal/receipts/
            
            logger.info(f"✅ Receipt {receipt.receipt_number} available in patient portal")
            
            return {
                'sent': True,
                'message': 'Receipt available in patient portal'
            }
            
        except Exception as e:
            logger.error(f"❌ Error saving to portal: {str(e)}")
            return {
                'sent': False,
                'message': f'Portal save failed: {str(e)}'
            }
    
    @staticmethod
    def get_digital_receipt_summary(receipt):
        """
        Get summary of digital receipt delivery status
        """
        summary = {
            'receipt_number': receipt.receipt_number,
            'patient': receipt.patient.full_name,
            'amount': receipt.amount_paid,
            'channels': []
        }
        
        # Check email
        if receipt.patient.email:
            summary['channels'].append({
                'type': 'email',
                'destination': receipt.patient.email,
                'status': 'available'
            })
        
        # Check SMS
        if receipt.patient.phone_number:
            summary['channels'].append({
                'type': 'sms',
                'destination': receipt.patient.phone_number,
                'status': 'available'
            })
        
        # Portal always available
        summary['channels'].append({
            'type': 'portal',
            'destination': 'Patient Portal',
            'status': 'available'
        })
        
        return summary


class DigitalReceiptPreferences:
    """
    Manage patient preferences for receipt delivery
    """
    
    @staticmethod
    def get_patient_preferences(patient):
        """
        Get patient's preferred receipt delivery methods
        """
        # Default preferences
        preferences = {
            'email': bool(patient.email),
            'sms': bool(patient.phone_number),
            'portal': True,
            'print': False,  # Only on request
        }
        
        # TODO: Load from patient preferences table if exists
        
        return preferences
    
    @staticmethod
    def send_by_preferences(receipt):
        """
        Send receipt according to patient preferences
        """
        patient = receipt.patient
        preferences = DigitalReceiptPreferences.get_patient_preferences(patient)
        
        methods = []
        if preferences.get('email'):
            methods.append('email')
        if preferences.get('sms'):
            methods.append('sms')
        if preferences.get('portal'):
            methods.append('portal')
        
        return PaperlessReceiptService.send_digital_receipt(receipt, methods)


# Export
__all__ = [
    'PaperlessReceiptService',
    'DigitalReceiptPreferences',
]






















