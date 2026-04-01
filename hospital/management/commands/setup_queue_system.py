"""
Management command to set up queue system with default configurations
"""
from django.core.management.base import BaseCommand
from hospital.models import Department
from hospital.models_queue import QueueConfiguration


class Command(BaseCommand):
    help = 'Set up queue system with default configurations for all departments'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS('\n🎫 Setting up Queue Management System...\n'))
        
        departments = Department.objects.filter(is_deleted=False)
        
        if not departments.exists():
            self.stdout.write(self.style.WARNING('⚠️  No departments found. Please create departments first.'))
            return
        
        created_count = 0
        updated_count = 0
        
        for department in departments:
            dept_name = department.name.upper()
            
            # Determine queue prefix based on department name
            if 'EMERGENCY' in dept_name or 'EMG' in dept_name:
                prefix = 'EMG'
                avg_time = 10
                buffer = 3
            elif 'OUTPATIENT' in dept_name or 'OPD' in dept_name:
                prefix = 'OPD'
                avg_time = 15
                buffer = 5
            elif 'INPATIENT' in dept_name or 'IPD' in dept_name:
                prefix = 'IPD'
                avg_time = 20
                buffer = 5
            elif 'SPECIALIST' in dept_name or 'SPL' in dept_name:
                prefix = 'SPL'
                avg_time = 20
                buffer = 5
            elif 'PEDIATRIC' in dept_name or 'PEDS' in dept_name:
                prefix = 'PED'
                avg_time = 15
                buffer = 5
            else:
                # Use first 3 letters of department name (avoid confusing SMS prefixes like ACC-)
                prefix = dept_name.replace(' ', '')[:3]
                blocked = {'ACC', 'XXX', 'ASS'}
                if prefix in blocked:
                    code = (department.code or '').strip().upper().replace(' ', '')
                    code = ''.join(c for c in code if c.isalnum())[:5]
                    prefix = code if code and code not in blocked else 'VIS'
                avg_time = 15
                buffer = 5
            
            # Create or update configuration
            config, created = QueueConfiguration.objects.get_or_create(
                department=department,
                defaults={
                    'queue_prefix': prefix,
                    'enable_queue': True,
                    'average_consultation_minutes': avg_time,
                    'buffer_time_minutes': buffer,
                    'send_check_in_sms': True,
                    'send_progress_updates': True,
                    'send_ready_notification': True,
                    'notification_interval_patients': 5,
                    'show_on_public_display': True,
                    'display_upcoming_count': 5,
                }
            )
            
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f'✅ Created queue config for {department.name} '
                        f'(Prefix: {prefix}, Avg time: {avg_time} mins)'
                    )
                )
            else:
                updated_count += 1
                self.stdout.write(
                    self.style.WARNING(
                        f'⚠️  Queue config already exists for {department.name} (Prefix: {config.queue_prefix})'
                    )
                )
        
        self.stdout.write(self.style.SUCCESS(f'\n📊 Summary:'))
        self.stdout.write(f'   - Created: {created_count} configurations')
        self.stdout.write(f'   - Existing: {updated_count} configurations')
        self.stdout.write(f'   - Total departments: {departments.count()}')
        
        self.stdout.write(self.style.SUCCESS('\n✅ Queue system setup complete!\n'))
        self.stdout.write('Next steps:')
        self.stdout.write('   1. Create a visit/encounter to test')
        self.stdout.write('   2. Check admin: /admin/hospital/queueentry/')
        self.stdout.write('   3. Verify SMS sent to patient')
        self.stdout.write('')
























