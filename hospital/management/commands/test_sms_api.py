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
        api_key = getattr(settings, 'SMS_API_KEY', '')
        sender_id = getattr(settings, 'SMS_SENDER_ID', 'Primecare')
        base_url = getattr(settings, 'SMS_API_URL', 'https://www.inteksms.top/api/v1/messages/send')
        wallet_url = getattr(settings, 'SMS_WALLET_URL', 'https://www.inteksms.top/api/v1/balance')
        
        self.stdout.write(f'  API Key: {api_key[:20]}...{api_key[-10:] if len(api_key) > 30 else ""}')
        self.stdout.write(f'  Sender ID: {sender_id}')
        self.stdout.write(f'  Send URL: {base_url}')
        self.stdout.write(f'  Balance URL: {wallet_url}')
        
        # Test API connection (Intek SMS balance endpoint)
        self.stdout.write('\n[2] Testing API Connection (balance)...')
        try:
            response = requests.get(
                wallet_url,
                headers={'Authorization': f'Bearer {api_key}', 'Accept': 'application/json'},
                timeout=10,
            )
            
            self.stdout.write(f'  HTTP Status: {response.status_code}')
            self.stdout.write(f'  Response: {response.text[:200]}')
            
            try:
                response_json = json.loads(response.text)
                if response_json.get('ok') is True:
                    units = (response_json.get('data') or {}).get('balance_units')
                    self.stdout.write(self.style.SUCCESS(f'  ✓ API connection successful (balance: {units} units)'))
                else:
                    error_msg = response_json.get('error') or response_json.get('message', 'Unknown error')
                    if response.status_code == 401:
                        self.stdout.write(self.style.ERROR('  ✗ INVALID API KEY'))
                        self.stdout.write(self.style.ERROR(f'     Error: {error_msg}'))
                        self.stdout.write(self.style.WARNING('\n  SOLUTION:'))
                        self.stdout.write(self.style.WARNING('    1. Check your Intek SMS account at https://www.inteksms.top'))
                        self.stdout.write(self.style.WARNING('    2. Update SMS_API_KEY in settings or environment'))
                        self.stdout.write(self.style.WARNING('    3. Example: export SMS_API_KEY="your-valid-key"'))
                    else:
                        self.stdout.write(self.style.ERROR(f'  ✗ API Error: {error_msg}'))
            except json.JSONDecodeError:
                self.stdout.write(self.style.ERROR(f'  ✗ Non-JSON response: {response.text[:100]}'))
                    
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




