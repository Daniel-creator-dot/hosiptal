"""
Check staff SMS configuration and test send
"""
from django.core.management.base import BaseCommand
from hospital.models import Staff
from hospital.models_advanced import SMSLog
from hospital.services.sms_service import sms_service


class Command(BaseCommand):
    help = 'Check staff phone numbers and SMS logs'

    def add_arguments(self, parser):
        parser.add_argument('--staff_id', type=str, help='Staff ID to check')
        parser.add_argument('--send_test', action='store_true', help='Send test SMS')
        parser.add_argument('--show_recent', action='store_true', help='Show recent SMS logs')

    def handle(self, *args, **options):
        if options['show_recent']:
            self.stdout.write(self.style.SUCCESS('\n=== RECENT SMS LOGS ==='))
            logs = SMSLog.objects.all().order_by('-created')[:10]
            for log in logs:
                status_color = self.style.SUCCESS if log.status == 'sent' else self.style.ERROR
                self.stdout.write(
                    f"\n[{log.created.strftime('%Y-%m-%d %H:%M:%S')}] "
                    f"{status_color(log.status.upper())}\n"
                    f"  To: {log.recipient_phone or 'NO PHONE'}\n"
                    f"  Name: {log.recipient_name}\n"
                    f"  Type: {log.message_type}\n"
                )
                if log.status == 'failed':
                    self.stdout.write(self.style.ERROR(f"  Error: {log.error_message}"))
                if log.message:
                    self.stdout.write(f"  Message: {log.message[:100]}...")
            return

        if options['staff_id']:
            try:
                staff = Staff.objects.get(id=options['staff_id'])
            except Staff.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"Staff with ID {options['staff_id']} not found"))
                return
        else:
            # Show all staff with their phone status
            self.stdout.write(self.style.SUCCESS('\n=== ALL STAFF PHONE NUMBERS ==='))
            staff_list = Staff.objects.filter(is_deleted=False).select_related('user')
            
            for staff in staff_list:
                phone = getattr(staff, 'phone_number', None) or getattr(staff, 'phone', None)
                username = staff.user.username
                
                if phone:
                    self.stdout.write(
                        self.style.SUCCESS(f"✓ {staff.user.get_full_name()} ({staff.id}): {phone}")
                    )
                elif username and username.replace('+', '').replace(' ', '').isdigit():
                    self.stdout.write(
                        self.style.WARNING(f"⚠ {staff.user.get_full_name()} ({staff.id}): Using username as phone: {username}")
                    )
                else:
                    self.stdout.write(
                        self.style.ERROR(f"✗ {staff.user.get_full_name()} ({staff.id}): NO PHONE NUMBER")
                    )
            return

        # Check specific staff
        self.stdout.write(self.style.SUCCESS(f'\n=== CHECKING STAFF: {staff.user.get_full_name()} ==='))
        self.stdout.write(f"Staff ID: {staff.id}")
        self.stdout.write(f"Username: {staff.user.username}")
        self.stdout.write(f"Email: {staff.user.email}")
        
        phone = getattr(staff, 'phone_number', None)
        self.stdout.write(f"Phone Number field: {phone or 'NOT SET'}")
        
        phone_alt = getattr(staff, 'phone', None)
        self.stdout.write(f"Phone field: {phone_alt or 'NOT SET'}")
        
        # Check username as phone
        username_is_phone = staff.user.username and staff.user.username.replace('+', '').replace(' ', '').isdigit()
        if username_is_phone:
            self.stdout.write(self.style.WARNING(f"Username can be used as phone: {staff.user.username}"))
        
        # Determine what will be used
        final_phone = phone or phone_alt or (staff.user.username if username_is_phone else None)
        
        if final_phone:
            self.stdout.write(self.style.SUCCESS(f"\n✓ Phone to use: {final_phone}"))
        else:
            self.stdout.write(self.style.ERROR("\n✗ NO PHONE NUMBER AVAILABLE"))
            self.stdout.write(self.style.WARNING("\nTo fix: Go to Admin → Staff → Edit this staff → Add phone_number"))
            return
        
        # Send test SMS if requested
        if options['send_test']:
            self.stdout.write(self.style.WARNING(f"\nSending test SMS to {final_phone}..."))
            result = sms_service.send_sms(
                phone_number=final_phone,
                message=f"Test SMS for {staff.user.get_full_name()}. Your leave approval system is working!",
                message_type='test',
                recipient_name=staff.user.get_full_name()
            )
            
            if result.status == 'sent':
                self.stdout.write(self.style.SUCCESS("✓ SMS SENT SUCCESSFULLY!"))
            else:
                self.stdout.write(self.style.ERROR(f"✗ SMS FAILED: {result.error_message}"))
                if result.provider_response:
                    self.stdout.write(f"Provider response: {result.provider_response}")

