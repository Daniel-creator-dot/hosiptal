"""
WhatsApp Service Integration
Sends WhatsApp messages via Twilio WhatsApp API or Meta WhatsApp Business API
"""
import requests
import json
from django.conf import settings
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


class WhatsAppService:
    """WhatsApp sending service via Twilio"""
    
    def __init__(self):
        # Twilio WhatsApp API configuration
        self.account_sid = getattr(settings, 'TWILIO_ACCOUNT_SID', '')
        self.auth_token = getattr(settings, 'TWILIO_AUTH_TOKEN', '')
        self.whatsapp_from = getattr(settings, 'TWILIO_WHATSAPP_FROM', 'whatsapp:+14155238886')  # Twilio Sandbox
        self.api_url = f'https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}/Messages.json'
        
        # Alternatively, use Meta WhatsApp Business API
        self.use_meta_api = getattr(settings, 'USE_META_WHATSAPP_API', False)
        self.meta_access_token = getattr(settings, 'META_WHATSAPP_ACCESS_TOKEN', '')
        self.meta_phone_number_id = getattr(settings, 'META_WHATSAPP_PHONE_NUMBER_ID', '')
        self.meta_api_url = f'https://graph.facebook.com/v18.0/{self.meta_phone_number_id}/messages'
    
    def send_whatsapp(self, phone_number, message, message_type='general', 
                      recipient_name='', include_media=False, media_url=''):
        """
        Send WhatsApp message
        
        Args:
            phone_number: Recipient WhatsApp number (format: +233XXXXXXXXX)
            message: Message text
            message_type: Type of message
            recipient_name: Name of recipient
            include_media: Whether to include media attachment
            media_url: URL of media file (PDF, image, etc.)
            
        Returns:
            dict with status and details
        """
        result = {
            'success': False,
            'status': 'failed',
            'message': '',
            'provider_response': {},
            'sent_at': None,
            'recipient_phone': phone_number,
            'recipient_name': recipient_name
        }
        
        try:
            # Validate phone number
            if not phone_number or not phone_number.strip():
                result['message'] = "Phone number is required"
                return result
            
            # Format phone number
            phone = self._format_phone_number(phone_number)
            if not phone:
                result['message'] = f"Invalid phone number format: {phone_number}"
                return result
            
            # Choose API based on configuration
            if self.use_meta_api and self.meta_access_token:
                return self._send_via_meta_api(phone, message, media_url if include_media else None)
            elif self.account_sid and self.auth_token:
                return self._send_via_twilio(phone, message, media_url if include_media else None)
            else:
                result['message'] = "WhatsApp API not configured. Set TWILIO_ACCOUNT_SID or META_WHATSAPP_ACCESS_TOKEN"
                return result
                
        except Exception as e:
            logger.error(f"WhatsApp send error: {str(e)}")
            result['message'] = f"Unexpected error: {str(e)}"
            return result
    
    def _send_via_twilio(self, phone, message, media_url=None):
        """Send via Twilio WhatsApp API"""
        result = {
            'success': False,
            'status': 'failed',
            'message': '',
            'provider': 'twilio',
            'provider_response': {},
            'sent_at': None,
            'recipient_phone': phone
        }
        
        try:
            # Prepare WhatsApp number format (whatsapp:+233...)
            to_number = f"whatsapp:{phone}" if not phone.startswith('whatsapp:') else phone
            
            # Prepare payload
            payload = {
                'From': self.whatsapp_from,
                'To': to_number,
                'Body': message
            }
            
            # Add media if provided
            if media_url:
                payload['MediaUrl'] = media_url
            
            # Send via Twilio API
            response = requests.post(
                self.api_url,
                auth=(self.account_sid, self.auth_token),
                data=payload,
                timeout=30
            )
            
            # Parse response
            if response.status_code in [200, 201]:
                response_data = response.json()
                result['success'] = True
                result['status'] = 'sent'
                result['sent_at'] = timezone.now()
                result['message'] = 'WhatsApp message sent successfully via Twilio'
                result['provider_response'] = {
                    'sid': response_data.get('sid'),
                    'status': response_data.get('status'),
                    'to': response_data.get('to'),
                    'from': response_data.get('from'),
                    'date_created': response_data.get('date_created')
                }
            else:
                error_data = response.json() if response.text else {}
                result['message'] = f"Twilio API error: {error_data.get('message', response.text)}"
                result['provider_response'] = {
                    'status_code': response.status_code,
                    'error': error_data
                }
            
        except requests.exceptions.Timeout:
            result['message'] = "Request timeout - Twilio API did not respond"
        except requests.exceptions.ConnectionError:
            result['message'] = "Connection error: Unable to reach Twilio API"
        except Exception as e:
            result['message'] = f"Twilio error: {str(e)}"
            logger.error(f"Twilio WhatsApp error: {str(e)}", exc_info=True)
        
        return result
    
    def _send_via_meta_api(self, phone, message, media_url=None):
        """Send via Meta WhatsApp Business API"""
        result = {
            'success': False,
            'status': 'failed',
            'message': '',
            'provider': 'meta',
            'provider_response': {},
            'sent_at': None,
            'recipient_phone': phone
        }
        
        try:
            # Remove + from phone number for Meta API
            phone_number = phone.replace('+', '')
            
            # Prepare headers
            headers = {
                'Authorization': f'Bearer {self.meta_access_token}',
                'Content-Type': 'application/json'
            }
            
            # Prepare payload - text message
            payload = {
                'messaging_product': 'whatsapp',
                'to': phone_number,
                'type': 'text',
                'text': {
                    'body': message
                }
            }
            
            # If media provided, use media message type
            if media_url:
                # Determine media type from URL
                if media_url.lower().endswith('.pdf'):
                    media_type = 'document'
                elif media_url.lower().endswith(('.jpg', '.jpeg', '.png', '.gif')):
                    media_type = 'image'
                else:
                    media_type = 'document'
                
                payload = {
                    'messaging_product': 'whatsapp',
                    'to': phone_number,
                    'type': media_type,
                    media_type: {
                        'link': media_url,
                        'caption': message
                    }
                }
            
            # Send via Meta API
            response = requests.post(
                self.meta_api_url,
                headers=headers,
                json=payload,
                timeout=30
            )
            
            # Parse response
            if response.status_code == 200:
                response_data = response.json()
                result['success'] = True
                result['status'] = 'sent'
                result['sent_at'] = timezone.now()
                result['message'] = 'WhatsApp message sent successfully via Meta API'
                result['provider_response'] = {
                    'message_id': response_data.get('messages', [{}])[0].get('id'),
                    'contacts': response_data.get('contacts', []),
                }
            else:
                error_data = response.json() if response.text else {}
                result['message'] = f"Meta API error: {error_data.get('error', {}).get('message', response.text)}"
                result['provider_response'] = {
                    'status_code': response.status_code,
                    'error': error_data
                }
            
        except requests.exceptions.Timeout:
            result['message'] = "Request timeout - Meta WhatsApp API did not respond"
        except requests.exceptions.ConnectionError:
            result['message'] = "Connection error: Unable to reach Meta WhatsApp API"
        except Exception as e:
            result['message'] = f"Meta API error: {str(e)}"
            logger.error(f"Meta WhatsApp error: {str(e)}", exc_info=True)
        
        return result
    
    def _format_phone_number(self, phone_number):
        """Format phone number for WhatsApp (international format with +)"""
        # Remove all non-numeric characters except +
        phone = ''.join(c for c in phone_number if c.isdigit() or c == '+')
        
        # Ensure it starts with +
        if not phone.startswith('+'):
            # Assume Ghana country code if not provided
            if phone.startswith('0'):
                phone = '+233' + phone[1:]
            elif phone.startswith('233'):
                phone = '+' + phone
            else:
                phone = '+233' + phone
        
        # Validate format (must be +233XXXXXXXXX - 13 characters)
        if len(phone) == 13 and phone.startswith('+233'):
            return phone
        
        return None
    
    def send_lab_result_whatsapp(self, lab_result, patient, include_pdf=False, pdf_url=''):
        """Send lab result ready notification via WhatsApp"""
        try:
            # Build WhatsApp message (no specific test name)
            message = f"🏥 *PrimeCare Hospital*\n\n"
            message += f"Dear {patient.first_name},\n\n"
            message += "Your lab test results are ready.\n\n"
            
            # Add result summary if completed
            if lab_result.status == 'completed' and lab_result.value:
                message += f"*Result:* {lab_result.value}"
                if lab_result.units:
                    message += f" {lab_result.units}"
                message += "\n"
                
                if lab_result.range_low and lab_result.range_high:
                    message += f"*Normal Range:* {lab_result.range_low}-{lab_result.range_high}\n"
                
                if lab_result.is_abnormal:
                    message += f"⚠️ *Status:* ABNORMAL - Please consult your doctor\n"
                
                message += "\n"
            
            # Add verification info
            if lab_result.verified_by:
                verifier = lab_result.verified_by.user.get_full_name() or lab_result.verified_by.user.username
                message += f"*Verified by:* Dr. {verifier}\n"
            
            if lab_result.verified_at:
                message += f"*Verified on:* {lab_result.verified_at.strftime('%B %d, %Y at %I:%M %p')}\n"
            
            # Add reference
            message += f"\n*Patient MRN:* {patient.mrn}\n"
            
            if include_pdf and pdf_url:
                message += f"\n📄 Full report attached"
            else:
                message += f"\n💡 Visit the hospital or check your patient portal for full details."
            
            message += f"\n\nThank you,\n*PrimeCare Hospital*"
            
            # Get patient's WhatsApp number
            whatsapp_number = patient.phone_number
            if hasattr(patient, 'notification_preference'):
                pref = patient.notification_preference
                whatsapp_number = pref.get_whatsapp_number()
            
            if not whatsapp_number:
                return {
                    'success': False,
                    'message': f"Patient {patient.full_name} does not have a WhatsApp number",
                    'status': 'failed'
                }
            
            # Send WhatsApp message
            return self.send_whatsapp(
                phone_number=whatsapp_number,
                message=message,
                message_type='lab_result_ready',
                recipient_name=patient.full_name,
                include_media=include_pdf,
                media_url=pdf_url
            )
            
        except Exception as e:
            logger.error(f"Error sending WhatsApp lab result: {str(e)}", exc_info=True)
            return {
                'success': False,
                'message': f"Error: {str(e)}",
                'status': 'failed'
            }


# Singleton instance
whatsapp_service = WhatsAppService()
























