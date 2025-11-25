"""
Management command to send birthday wishes to staff
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from hospital.models import Staff
from hospital.services.sms_service import sms_service


class Command(BaseCommand):
    help = 'Send birthday wishes to staff with birthdays today'

    def add_arguments(self, parser):
        parser.add_argument(
            '--upcoming',
            action='store_true',
            help='Show upcoming birthdays in next 7 days',
        )
        parser.add_argument(
            '--days',
            type=int,
            default=7,
            help='Number of days to look ahead for upcoming birthdays',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be sent without actually sending',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('='*70))
        self.stdout.write(self.style.SUCCESS('Staff Birthday Wishes'))
        self.stdout.write(self.style.SUCCESS(f'Run at: {timezone.now()}'))
        self.stdout.write(self.style.SUCCESS('='*70))
        self.stdout.write('')

        # Show upcoming birthdays
        if options['upcoming']:
            days = options['days']
            self.stdout.write(self.style.WARNING(f'\n[UPCOMING] Birthdays in next {days} days:'))
            self.stdout.write('-' * 70)
            
            upcoming = Staff.get_upcoming_birthdays(days)
            
            if upcoming:
                for staff in upcoming:
                    days_until = staff.days_until_birthday()
                    age_text = f" (Will be {staff.age + 1} years old)" if staff.age else ""
                    
                    self.stdout.write(
                        f"  {staff.user.get_full_name():<30} | "
                        f"{staff.date_of_birth.strftime('%b %d'):<10} | "
                        f"In {days_until} day(s){age_text}"
                    )
                self.stdout.write(f'\nTotal: {len(upcoming)} upcoming birthdays')
            else:
                self.stdout.write(self.style.SUCCESS('  No upcoming birthdays'))
        
        # Send birthday wishes to today's birthdays
        else:
            self.stdout.write(self.style.WARNING('\n[TODAY] Sending birthday wishes...'))
            self.stdout.write('-' * 70)
            
            birthday_staff = Staff.get_birthdays_today()
            
            if not birthday_staff:
                self.stdout.write(self.style.SUCCESS('  No birthdays today'))
            else:
                self.stdout.write(f'  Found {birthday_staff.count()} staff with birthdays today:\n')
                
                sent_count = 0
                failed_count = 0
                
                for staff in birthday_staff:
                    age_text = f" (Turning {staff.age})" if staff.age else ""
                    self.stdout.write(f'  - {staff.user.get_full_name()}{age_text}')
                    
                    if options['dry_run']:
                        self.stdout.write(f'    [DRY RUN] Would send SMS to: {staff.phone_number or "NO PHONE"}')
                    else:
                        # Send birthday wish
                        result = sms_service.send_birthday_wish(staff)
                        
                        if result.status == 'sent':
                            self.stdout.write(self.style.SUCCESS(f'    [OK] SMS sent to {staff.phone_number}'))
                            sent_count += 1
                        else:
                            self.stdout.write(self.style.ERROR(f'    [FAILED] {result.error_message}'))
                            failed_count += 1
                        
                        # Notify department head
                        try:
                            dept_result = sms_service.send_birthday_reminder_to_department(staff)
                            if dept_result:
                                self.stdout.write(f'    [INFO] Department notified')
                        except Exception as e:
                            pass
                
                if not options['dry_run']:
                    self.stdout.write('')
                    self.stdout.write(self.style.SUCCESS(f'  Summary: {sent_count} sent, {failed_count} failed'))
        
        # Summary
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('='*70))
        self.stdout.write(self.style.SUCCESS('Birthday Wishes Complete!'))
        self.stdout.write(self.style.SUCCESS('='*70))
        self.stdout.write('')
































