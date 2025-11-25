"""
Django management command to send birthday reminders
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import date, timedelta
from hospital.models import Staff, Patient
from hospital.models_reminders import BirthdayReminder, SMSNotification
import requests
from django.conf import settings


class Command(BaseCommand):
    help = 'Send birthday reminders via SMS'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days-ahead',
            type=int,
            default=3,
            help='Number of days ahead to send reminders (default: 3)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Do not send SMS, just show what would be sent',
        )

    def handle(self, *args, **options):
        days_ahead = options['days_ahead']
        dry_run = options['dry_run']
        today = date.today()
        reminder_date = today + timedelta(days=days_ahead)
        
        self.stdout.write(f'Checking for birthdays on {reminder_date}...')
        
        # Check staff birthdays
        staff_birthdays = self.get_staff_birthdays_on_date(reminder_date)
        patient_birthdays = self.get_patient_birthdays_on_date(reminder_date)
        
        total_sent = 0
        
        # Process staff birthdays
        for staff in staff_birthdays:
            if dry_run:
                self.stdout.write(
                    f'[DRY RUN] Would send birthday reminder for {staff.user.get_full_name()} '
                    f'({staff.date_of_birth}) to {staff.phone_number}'
                )
            else:
                sent = self.send_staff_birthday_reminder(staff, reminder_date)
                if sent:
                    total_sent += 1
        
        # Process patient birthdays (optional - might want to notify their assigned doctor)
        for patient in patient_birthdays:
            if dry_run:
                self.stdout.write(
                    f'[DRY RUN] Would send birthday reminder for {patient.full_name} '
                    f'({patient.date_of_birth})'
                )
            else:
                # Could send to patient or their doctor
                # For now, just create a reminder record
                BirthdayReminder.objects.get_or_create(
                    reminder_type='patient',
                    patient=patient,
                    birthday_date=patient.date_of_birth,
                    defaults={'reminder_date': reminder_date}
                )
        
        if not dry_run:
            self.stdout.write(self.style.SUCCESS(f'Successfully sent {total_sent} birthday reminders'))
        else:
            self.stdout.write(self.style.WARNING('DRY RUN - No messages sent'))

    def get_staff_birthdays_on_date(self, target_date):
        """Get staff whose birthdays fall on target_date (ignoring year)"""
        staff_list = []
        for staff in Staff.objects.filter(
            date_of_birth__isnull=False,
            is_active=True,
            is_deleted=False,
            phone_number__isnull=False
        ).exclude(phone_number=''):
            if staff.date_of_birth.month == target_date.month and \
               staff.date_of_birth.day == target_date.day:
                staff_list.append(staff)
        return staff_list

    def get_patient_birthdays_on_date(self, target_date):
        """Get patients whose birthdays fall on target_date"""
        patients = []
        for patient in Patient.objects.filter(
            date_of_birth__isnull=False,
            is_deleted=False
        ):
            if patient.date_of_birth.month == target_date.month and \
               patient.date_of_birth.day == target_date.day:
                patients.append(patient)
        return patients

    def send_staff_birthday_reminder(self, staff, birthday_date):
        """Send SMS reminder to staff about upcoming birthday"""
        try:
            phone = staff.phone_number
            if not phone:
                return False
            
            # Create or update reminder record
            reminder, created = BirthdayReminder.objects.get_or_create(
                reminder_type='staff',
                staff=staff,
                birthday_date=birthday_date,
                defaults={'reminder_date': birthday_date}
            )
            
            # Don't send if already notified
            if reminder.notified:
                return False
            
            message = f"Happy Birthday! Your birthday is coming up on {birthday_date.strftime('%B %d')}. We wish you a wonderful year ahead!"
            
            # Send SMS
            success = self.send_sms(phone, message, recipient_name=staff.user.get_full_name())
            
            if success:
                reminder.notified = True
                reminder.notified_at = timezone.now()
                reminder.notification_sent_to = phone
                reminder.save()
                
                # Log SMS notification
                SMSNotification.objects.create(
                    notification_type='birthday',
                    recipient_number=phone,
                    recipient_name=staff.user.get_full_name(),
                    message=message,
                    status='sent',
                    sent_at=timezone.now(),
                    staff=staff,
                )
                
                return True
            else:
                SMSNotification.objects.create(
                    notification_type='birthday',
                    recipient_number=phone,
                    recipient_name=staff.user.get_full_name(),
                    message=message,
                    status='failed',
                    staff=staff,
                )
                return False
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error sending reminder to {staff.user.get_full_name()}: {str(e)}'))
            return False

    def send_sms(self, phone_number, message, recipient_name=''):
        """Send SMS using the centralized SMS service"""
        try:
            from hospital.services.sms_service import sms_service
            
            sms_log = sms_service.send_sms(
                phone_number=phone_number,
                message=message,
                message_type='birthday_reminder',
                recipient_name=recipient_name
            )
            
            return sms_log.status == 'sent'
            
            response = requests.post(
                api_url,
                json=data,
                auth=(api_key, api_secret),
                headers={'Content-Type': 'application/json'},
                timeout=10
            )
            
            if response.status_code == 200:
                return True
            else:
                self.stdout.write(self.style.ERROR(f'SMS API Error: {response.status_code} - {response.text}'))
                return False
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error sending SMS: {str(e)}'))
            return False

