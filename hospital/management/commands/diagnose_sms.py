"""
Management command to diagnose SMS issues across the application
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import models
from datetime import timedelta
from hospital.models_advanced import SMSLog
from hospital.models import Patient
from hospital.services.sms_service import sms_service


class Command(BaseCommand):
    help = 'Diagnose SMS issues - check configuration, recent logs, and test sending'

    def add_arguments(self, parser):
        parser.add_argument(
            '--test-phone',
            type=str,
            help='Test sending SMS to a specific phone number',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS('SMS SYSTEM DIAGNOSTICS'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        
        # 1. Check SMS Configuration
        self.stdout.write('\n[1] SMS Configuration:')
        from django.conf import settings
        api_key = getattr(settings, 'SMS_API_KEY', 'Not set')
        sender_id = getattr(settings, 'SMS_SENDER_ID', 'Not set')
        api_url = getattr(settings, 'SMS_API_URL', 'Not set')
        
        self.stdout.write(f'  API Key: {api_key[:20]}...{api_key[-10:] if len(str(api_key)) > 30 else ""}')
        self.stdout.write(f'  Sender ID: {sender_id}')
        self.stdout.write(f'  API URL: {api_url}')
        
        # 2. Check recent SMS logs (last 48 hours)
        self.stdout.write('\n[2] Recent SMS Activity (Last 48 hours):')
        since = timezone.now() - timedelta(hours=48)
        recent_logs = SMSLog.objects.filter(created__gte=since).order_by('-created')
        total = recent_logs.count()
        
        if total == 0:
            self.stdout.write(self.style.WARNING('  ⚠️  No SMS activity in last 48 hours'))
        else:
            status_counts = {}
            for log in recent_logs:
                status_counts[log.status] = status_counts.get(log.status, 0) + 1
            
            self.stdout.write(f'  Total SMS attempts: {total}')
            for status, count in status_counts.items():
                if status == 'sent':
                    self.stdout.write(self.style.SUCCESS(f'    ✅ Sent: {count}'))
                elif status == 'failed':
                    self.stdout.write(self.style.ERROR(f'    ❌ Failed: {count}'))
                elif status == 'pending':
                    self.stdout.write(self.style.WARNING(f'    ⏳ Pending: {count}'))
            
            # Show recent failures
            failed = recent_logs.filter(status='failed')[:5]
            if failed.exists():
                self.stdout.write('\n  Recent Failures:')
                for log in failed:
                    error = log.error_message[:80] if log.error_message else 'No error message'
                    self.stdout.write(f'    - {log.recipient_phone or "NO PHONE"}: {error}')
        
        # 3. Check patients without phone numbers
        self.stdout.write('\n[3] Patient Phone Number Status:')
        patients_with_phone = Patient.objects.filter(
            phone_number__isnull=False
        ).exclude(phone_number='').count()
        
        patients_without_phone = Patient.objects.filter(
            models.Q(phone_number__isnull=True) | models.Q(phone_number='')
        ).count()
        
        total_patients = Patient.objects.filter(is_deleted=False).count()
        
        self.stdout.write(f'  Total patients: {total_patients}')
        self.stdout.write(self.style.SUCCESS(f'  ✅ Patients WITH phone: {patients_with_phone}'))
        self.stdout.write(self.style.ERROR(f'  ❌ Patients WITHOUT phone: {patients_without_phone}'))
        
        if patients_without_phone > 0:
            percentage = (patients_without_phone / total_patients * 100) if total_patients > 0 else 0
            self.stdout.write(self.style.WARNING(
                f'  ⚠️  {percentage:.1f}% of patients are missing phone numbers'
            ))
        
        # 4. Test SMS sending if phone provided
        if options.get('test_phone'):
            self.stdout.write(f'\n[4] Testing SMS Send to {options["test_phone"]}:')
            try:
                result = sms_service.send_sms(
                    phone_number=options['test_phone'],
                    message='Test SMS from HMS diagnostics. If you receive this, SMS is working correctly.',
                    message_type='diagnostic_test',
                    recipient_name='Test Recipient'
                )
                
                if result.status == 'sent':
                    self.stdout.write(self.style.SUCCESS('  ✅ Test SMS sent successfully!'))
                    self.stdout.write(f'     Log ID: {result.id}')
                    self.stdout.write(f'     Sent at: {result.sent_at}')
                else:
                    self.stdout.write(self.style.ERROR(f'  ❌ Test SMS failed: {result.error_message}'))
                    if result.provider_response:
                        self.stdout.write(f'     Response: {result.provider_response}')
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  ❌ Error sending test SMS: {str(e)}'))
        
        # 5. Recommendations
        self.stdout.write('\n' + '=' * 70)
        self.stdout.write('RECOMMENDATIONS:')
        self.stdout.write('=' * 70)
        
        if patients_without_phone > total_patients * 0.5:
            self.stdout.write(self.style.WARNING(
                '\n⚠️  MOST PATIENTS ARE MISSING PHONE NUMBERS'
            ))
            self.stdout.write('  Action: Update patient records with phone numbers')
            self.stdout.write('  Go to: Admin → Patients → Edit Patient → Add phone_number')
        
        if recent_logs.filter(status='failed').exists():
            failed_recent = recent_logs.filter(status='failed', created__gte=timezone.now() - timedelta(hours=24))
            if failed_recent.exists():
                self.stdout.write(self.style.WARNING(
                    '\n⚠️  RECENT SMS FAILURES DETECTED'
                ))
                self.stdout.write('  Run: python manage.py check_sms_failures --last-hours 24')
                self.stdout.write('  To see detailed error messages')
        
        self.stdout.write('\n✓ Diagnostic complete')
        self.stdout.write('=' * 70)
