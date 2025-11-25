"""
Management command to test SMS API configuration
"""
from django.core.management.base import BaseCommand
from django.conf import settings
import requests
import json


class Command(BaseCommand):
    help = 'Test SMS API configuration and connection'

    def add_arguments(self, parser):
        parser.add_argument(
            '--test-send',
            type=str,
            help='Test sending SMS to a phone number (format: +233XXXXXXXXX)',
        )

    def handle(self, *args, **options):
        test_phone = options.get('test_send')
        
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('SMS API CONFIGURATION TEST'))
        self.stdout.write(self.style.SUCCESS('=' * 60))
        
        # Check configuration
        self.stdout.write('\n[1] Checking Configuration...')
        api_key = getattr(settings, 'SMS_API_KEY', '84c879bb-f9f9-4666-84a8-9f70a9b238cc')
        sender_id = getattr(settings, 'SMS_SENDER_ID', 'PrimeCare')
        base_url = getattr(settings, 'SMS_API_URL', 'https://sms.smsnotifygh.com/smsapi')
        
        self.stdout.write(f'  API Key: {api_key[:20]}...{api_key[-10:] if len(api_key) > 30 else ""}')
        self.stdout.write(f'  Sender ID: {sender_id}')
        self.stdout.write(f'  API URL: {base_url}')
        
        # Test API connection
        self.stdout.write('\n[2] Testing API Connection...')
        try:
            # Test with a simple request (check balance or status endpoint if available)
            test_payload = {
                'key': api_key,
                'to': '233247904675',  # Test number
                'msg': 'TEST',
                'sender_id': sender_id
            }
            
            response = requests.get(
                base_url,
                params=test_payload,
                timeout=10
            )
            
            self.stdout.write(f'  HTTP Status: {response.status_code}')
            self.stdout.write(f'  Response: {response.text[:200]}')
            
            # Parse response
            try:
                response_json = json.loads(response.text)
                if response_json.get('success') == True or response_json.get('code') == 1000:
                    self.stdout.write(self.style.SUCCESS('  ✓ API connection successful'))
                else:
                    error_code = response_json.get('code', 'unknown')
                    error_msg = response_json.get('message', 'Unknown error')
                    
                    if error_code == 1004:
                        self.stdout.write(self.style.ERROR(f'  ✗ INVALID API KEY (Code {error_code})'))
                        self.stdout.write(self.style.ERROR(f'     Error: {error_msg}'))
                        self.stdout.write(self.style.WARNING('\n  SOLUTION:'))
                        self.stdout.write(self.style.WARNING('    1. Check your SMS provider account'))
                        self.stdout.write(self.style.WARNING('    2. Get a valid API key from your SMS provider'))
                        self.stdout.write(self.style.WARNING('    3. Update SMS_API_KEY in settings or environment'))
                        self.stdout.write(self.style.WARNING('    4. Example: export SMS_API_KEY="your-valid-key"'))
                    elif error_code == 1707:
                        self.stdout.write(self.style.ERROR(f'  ✗ INSUFFICIENT BALANCE (Code {error_code})'))
                        self.stdout.write(self.style.WARNING('     Top up your SMS account'))
                    else:
                        self.stdout.write(self.style.ERROR(f'  ✗ API Error (Code {error_code}): {error_msg}'))
            except json.JSONDecodeError:
                # Plain text response
                if '1701' in response.text or 'success' in response.text.lower():
                    self.stdout.write(self.style.SUCCESS('  ✓ API connection successful'))
                else:
                    self.stdout.write(self.style.ERROR(f'  ✗ API Error: {response.text[:100]}'))
                    
        except requests.exceptions.Timeout:
            self.stdout.write(self.style.ERROR('  ✗ Connection timeout - API server not responding'))
        except requests.exceptions.ConnectionError:
            self.stdout.write(self.style.ERROR('  ✗ Connection error - Cannot reach API server'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'  ✗ Error: {str(e)}'))
        
        # Test sending if phone provided
        if test_phone:
            self.stdout.write(f'\n[3] Testing SMS Send to {test_phone}...')
            try:
                from ...services.sms_service import sms_service
                sms_log = sms_service.send_sms(
                    phone_number=test_phone,
                    message='Test SMS from HMS system. If you receive this, SMS is working correctly.',
                    message_type='test',
                    recipient_name='Test Recipient'
                )
                
                if sms_log.status == 'sent':
                    self.stdout.write(self.style.SUCCESS(f'  ✓ Test SMS sent successfully!'))
                    self.stdout.write(f'     Log ID: {sms_log.id}')
                    self.stdout.write(f'     Sent at: {sms_log.sent_at}')
                else:
                    self.stdout.write(self.style.ERROR(f'  ✗ Test SMS failed: {sms_log.error_message}'))
                    if sms_log.provider_response:
                        self.stdout.write(f'     Response: {sms_log.provider_response}')
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  ✗ Error sending test SMS: {str(e)}'))
        
        # Summary
        self.stdout.write('\n' + '=' * 60)
        self.stdout.write('RECOMMENDATIONS:')
        self.stdout.write('=' * 60)
        self.stdout.write('\n1. If API key is invalid:')
        self.stdout.write('   - Get valid API key from SMS provider')
        self.stdout.write('   - Set in environment: export SMS_API_KEY="your-key"')
        self.stdout.write('   - Or update in settings.py')
        self.stdout.write('\n2. To test sending:')
        self.stdout.write('   python manage.py test_sms_api --test-send "+233247904675"')
        self.stdout.write('\n3. To check failed SMS:')
        self.stdout.write('   python manage.py check_sms_failures')
        self.stdout.write('=' * 60)




