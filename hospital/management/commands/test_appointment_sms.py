"""
Management command to test appointment booking SMS
"""
from django.core.management.base import BaseCommand
from hospital.services.sms_service import sms_service
from hospital.models import Patient, Appointment, Staff, Department
from django.utils import timezone
from datetime import timedelta


class Command(BaseCommand):
    help = 'Test appointment booking SMS with a phone number'

    def add_arguments(self, parser):
        parser.add_argument(
            '--phone',
            type=str,
            required=True,
            help='Phone number to test (e.g., 0247904675)',
        )

    def handle(self, *args, **options):
        phone = options['phone']
        
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS('APPOINTMENT BOOKING SMS TEST'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        
        # Format phone number
        if phone.startswith('0'):
            phone_formatted = '233' + phone[1:]
        elif phone.startswith('+233'):
            phone_formatted = phone[1:]
        elif phone.startswith('233'):
            phone_formatted = phone
        else:
            phone_formatted = '233' + phone
        
        self.stdout.write(f'\n[1] Testing SMS to: {phone} (formatted: {phone_formatted})')
        
        # Create test message similar to appointment booking
        message = (
            f"Appointment Booking\n\n"
            f"Dear Test,\n\n"
            f"Your appointment is scheduled:\n"
            f"Date: {timezone.now().strftime('%d/%m/%Y')}\n"
            f"Time: {timezone.now().strftime('%I:%M %p')}\n"
            f"Doctor: Dr. Test Doctor\n"
            f"Dept: General Medicine\n\n"
            f"Please arrive 15 minutes early.\n"
            f"- PrimeCare Medical Center"
        )
        
        self.stdout.write(f'\n[2] Sending test appointment booking SMS...')
        self.stdout.write(f'Message preview:\n{message[:200]}...\n')
        
        try:
            result = sms_service.send_sms(
                phone_number=phone,
                message=message,
                message_type='appointment_booking_test',
                recipient_name='Test Patient',
                related_object_id=None,
                related_object_type='Appointment'
            )
            
            if result.status == 'sent':
                self.stdout.write(self.style.SUCCESS(f'\n✅ SMS sent successfully!'))
                self.stdout.write(f'   Log ID: {result.id}')
                self.stdout.write(f'   Sent at: {result.sent_at}')
                self.stdout.write(f'   Phone: {result.recipient_phone}')
            else:
                self.stdout.write(self.style.ERROR(f'\n❌ SMS failed to send'))
                self.stdout.write(f'   Status: {result.status}')
                self.stdout.write(f'   Error: {result.error_message}')
                if result.provider_response:
                    self.stdout.write(f'   Response: {result.provider_response}')
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'\n❌ Error: {str(e)}'))
            import traceback
            self.stdout.write(traceback.format_exc())
        
        self.stdout.write('\n' + '=' * 70)
