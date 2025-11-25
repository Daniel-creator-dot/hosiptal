"""
Management command to check SMS failures and provide diagnostics
"""
from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone
from datetime import timedelta
from ...models_advanced import SMSLog


class Command(BaseCommand):
    help = 'Check SMS failures and provide diagnostics'

    def add_arguments(self, parser):
        parser.add_argument(
            '--recipient',
            type=str,
            help='Check failures for specific recipient name',
        )
        parser.add_argument(
            '--phone',
            type=str,
            help='Check failures for specific phone number',
        )
        parser.add_argument(
            '--last-hours',
            type=int,
            default=24,
            help='Check failures in last N hours (default: 24)',
        )
        parser.add_argument(
            '--retry',
            action='store_true',
            help='Retry failed SMS messages',
        )

    def handle(self, *args, **options):
        recipient_name = options.get('recipient')
        phone_number = options.get('phone')
        last_hours = options.get('last_hours', 24)
        retry = options.get('retry', False)
        
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('SMS FAILURE DIAGNOSTICS'))
        self.stdout.write(self.style.SUCCESS('=' * 60))
        
        # Build query
        since = timezone.now() - timedelta(hours=last_hours)
        query = Q(status='failed', created__gte=since)
        
        if recipient_name:
            query &= Q(recipient_name__icontains=recipient_name)
            self.stdout.write(f'\nSearching for: {recipient_name}')
        
        if phone_number:
            query &= Q(recipient_phone__icontains=phone_number)
            self.stdout.write(f'\nSearching for phone: {phone_number}')
        
        failed_sms = SMSLog.objects.filter(query).order_by('-created')
        total_failed = failed_sms.count()
        
        self.stdout.write(f'\nFound {total_failed} failed SMS in last {last_hours} hours\n')
        
        if total_failed == 0:
            self.stdout.write(self.style.SUCCESS('✓ No failed SMS found!'))
            return
        
        # Group by error type
        error_types = {}
        for sms in failed_sms[:50]:  # Limit to first 50 for display
            error = sms.error_message or 'Unknown error'
            error_key = error[:50]  # First 50 chars
            if error_key not in error_types:
                error_types[error_key] = []
            error_types[error_key].append(sms)
        
        # Display failures
        for error_type, sms_list in error_types.items():
            self.stdout.write(self.style.ERROR(f'\nError: {error_type}'))
            self.stdout.write(f'  Count: {len(sms_list)}')
            self.stdout.write(f'  Examples:')
            for sms in sms_list[:5]:
                phone_display = sms.recipient_phone[:15] + '...' if len(sms.recipient_phone) > 15 else sms.recipient_phone
                self.stdout.write(f'    - {sms.recipient_name} ({phone_display}) at {sms.created.strftime("%Y-%m-%d %H:%M")}')
                if sms.provider_response:
                    self.stdout.write(f'      Response: {str(sms.provider_response)[:100]}')
        
        # Specific check for Anthony Amissah
        if not recipient_name and not phone_number:
            anthony_failures = SMSLog.objects.filter(
                Q(recipient_name__icontains='Anthony') | Q(recipient_name__icontains='Amissah'),
                status='failed',
                created__gte=since
            ).order_by('-created')
            
            if anthony_failures.exists():
                self.stdout.write(self.style.WARNING('\n' + '=' * 60))
                self.stdout.write(self.style.WARNING('ANTHONY AMISSAH SMS FAILURES:'))
                self.stdout.write(self.style.WARNING('=' * 60))
                for sms in anthony_failures[:10]:
                    self.stdout.write(f'\n  Name: {sms.recipient_name}')
                    self.stdout.write(f'  Phone: {sms.recipient_phone}')
                    self.stdout.write(f'  Status: {sms.status}')
                    self.stdout.write(f'  Error: {sms.error_message}')
                    self.stdout.write(f'  Time: {sms.created.strftime("%Y-%m-%d %H:%M:%S")}')
                    if sms.provider_response:
                        self.stdout.write(f'  Provider Response: {sms.provider_response}')
                    
                    # Check phone number format
                    phone = sms.recipient_phone.replace('+', '').replace(' ', '').replace('-', '').strip()
                    if phone.startswith('0'):
                        phone = '233' + phone[1:]
                    elif not phone.startswith('233'):
                        if len(phone) == 9:
                            phone = '233' + phone
                    
                    if not phone.startswith('233') or len(phone) != 12:
                        self.stdout.write(self.style.ERROR(f'  ⚠ INVALID PHONE FORMAT: {sms.recipient_phone} -> {phone}'))
                    else:
                        self.stdout.write(self.style.SUCCESS(f'  ✓ Phone format OK: {phone}'))
        
        # Retry option
        if retry:
            self.stdout.write(self.style.SUCCESS('\n' + '=' * 60))
            self.stdout.write(self.style.SUCCESS('RETRYING FAILED SMS'))
            self.stdout.write(self.style.SUCCESS('=' * 60))
            
            from ...services.sms_service import sms_service
            retry_count = 0
            success_count = 0
            
            for sms in failed_sms[:20]:  # Limit retries to 20
                if not sms.recipient_phone or not sms.message:
                    continue
                
                self.stdout.write(f'\nRetrying: {sms.recipient_name} ({sms.recipient_phone})')
                retry_count += 1
                
                try:
                    new_sms_log = sms_service.send_sms(
                        phone_number=sms.recipient_phone,
                        message=sms.message,
                        message_type=sms.message_type,
                        recipient_name=sms.recipient_name,
                        related_object_id=sms.related_object_id,
                        related_object_type=sms.related_object_type
                    )
                    
                    if new_sms_log.status == 'sent':
                        success_count += 1
                        self.stdout.write(self.style.SUCCESS(f'  ✓ Retry successful'))
                    else:
                        self.stdout.write(self.style.ERROR(f'  ✗ Retry failed: {new_sms_log.error_message}'))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'  ✗ Retry error: {str(e)}'))
            
            self.stdout.write(self.style.SUCCESS(f'\nRetry Summary: {success_count}/{retry_count} successful'))
        
        # Recommendations
        self.stdout.write(self.style.SUCCESS('\n' + '=' * 60))
        self.stdout.write('RECOMMENDATIONS:')
        self.stdout.write('=' * 60)
        
        common_errors = {}
        for sms in failed_sms:
            error = sms.error_message or 'Unknown'
            if error not in common_errors:
                common_errors[error] = 0
            common_errors[error] += 1
        
        if 'Invalid phone number format' in str(common_errors):
            self.stdout.write('\n1. Phone number format issues detected:')
            self.stdout.write('   - Ensure phone numbers are in format: +233XXXXXXXXX or 0XXXXXXXXX')
            self.stdout.write('   - Check for missing or invalid phone numbers in patient/staff records')
        
        if 'Connection error' in str(common_errors) or 'timeout' in str(common_errors).lower():
            self.stdout.write('\n2. Network/API connection issues:')
            self.stdout.write('   - Check SMS API service is accessible')
            self.stdout.write('   - Verify SMS_API_KEY and SMS_API_URL in settings')
            self.stdout.write('   - Check internet connectivity')
        
        if 'Insufficient balance' in str(common_errors):
            self.stdout.write('\n3. SMS account balance issues:')
            self.stdout.write('   - Top up your SMS provider account')
            self.stdout.write('   - Check SMS_API_KEY is valid and account is active')
        
        self.stdout.write('\nTo retry failed SMS:')
        self.stdout.write('  python manage.py check_sms_failures --retry')
        self.stdout.write('\nTo check specific recipient:')
        self.stdout.write('  python manage.py check_sms_failures --recipient "Anthony Amissah"')
        
        self.stdout.write('=' * 60)




