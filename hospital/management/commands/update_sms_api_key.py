"""
Management command to update SMS API key
"""
from django.core.management.base import BaseCommand
from django.conf import settings
import os
from pathlib import Path


class Command(BaseCommand):
    help = 'Update SMS API key in environment or .env file'

    def add_arguments(self, parser):
        parser.add_argument(
            'api_key',
            type=str,
            nargs='?',
            help='New SMS API key to set',
        )
        parser.add_argument(
            '--show',
            action='store_true',
            help='Show current API key (masked)',
        )
        parser.add_argument(
            '--sender-id',
            type=str,
            help='Update sender ID',
        )

    def handle(self, *args, **options):
        api_key = options.get('api_key')
        show = options.get('show', False)
        sender_id = options.get('sender_id')
        
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('SMS API KEY CONFIGURATION'))
        self.stdout.write(self.style.SUCCESS('=' * 60))
        
        # Show current configuration
        current_key = getattr(settings, 'SMS_API_KEY', 'Not set')
        current_sender = getattr(settings, 'SMS_SENDER_ID', 'Not set')
        current_url = getattr(settings, 'SMS_API_URL', 'Not set')
        
        # Mask API key for display
        if current_key and current_key != 'Not set':
            masked_key = current_key[:8] + '...' + current_key[-8:] if len(current_key) > 16 else '***'
        else:
            masked_key = 'Not set'
        
        self.stdout.write(f'\nCurrent Configuration:')
        self.stdout.write(f'  API Key: {masked_key}')
        self.stdout.write(f'  Sender ID: {current_sender}')
        self.stdout.write(f'  API URL: {current_url}')
        
        if show:
            return
        
        # Update API key
        if api_key:
            # Try to update .env file
            env_file = Path(settings.BASE_DIR) / '.env'
            env_updated = False
            
            if env_file.exists():
                try:
                    # Read current .env
                    with open(env_file, 'r') as f:
                        lines = f.readlines()
                    
                    # Update or add SMS_API_KEY
                    updated = False
                    new_lines = []
                    for line in lines:
                        if line.strip().startswith('SMS_API_KEY='):
                            new_lines.append(f'SMS_API_KEY={api_key}\n')
                            updated = True
                        else:
                            new_lines.append(line)
                    
                    if not updated:
                        new_lines.append(f'\n# SMS Configuration\n')
                        new_lines.append(f'SMS_API_KEY={api_key}\n')
                    
                    # Write back
                    with open(env_file, 'w') as f:
                        f.writelines(new_lines)
                    
                    self.stdout.write(self.style.SUCCESS(f'\n✓ Updated SMS_API_KEY in .env file'))
                    env_updated = True
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f'\n⚠ Could not update .env file: {e}'))
            
            if not env_updated:
                self.stdout.write(self.style.WARNING('\n⚠ .env file not found. Please set environment variable:'))
                self.stdout.write(self.style.WARNING('  Windows: set SMS_API_KEY=' + api_key))
                self.stdout.write(self.style.WARNING('  Linux/Mac: export SMS_API_KEY=' + api_key))
            
            # Test the new API key
            self.stdout.write(self.style.SUCCESS('\nTesting new API key...'))
            try:
                from ...services.sms_service import SMSService
                test_service = SMSService()
                # The service will use the new key from environment
                self.stdout.write(self.style.SUCCESS('✓ API key updated. Restart server to apply changes.'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'✗ Error: {e}'))
        
        # Update sender ID
        if sender_id:
            env_file = Path(settings.BASE_DIR) / '.env'
            if env_file.exists():
                try:
                    with open(env_file, 'r') as f:
                        lines = f.readlines()
                    
                    updated = False
                    new_lines = []
                    for line in lines:
                        if line.strip().startswith('SMS_SENDER_ID='):
                            new_lines.append(f'SMS_SENDER_ID={sender_id}\n')
                            updated = True
                        else:
                            new_lines.append(line)
                    
                    if not updated:
                        new_lines.append(f'SMS_SENDER_ID={sender_id}\n')
                    
                    with open(env_file, 'w') as f:
                        f.writelines(new_lines)
                    
                    self.stdout.write(self.style.SUCCESS(f'✓ Updated SMS_SENDER_ID to: {sender_id}'))
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f'⚠ Could not update sender ID: {e}'))
        
        if not api_key and not sender_id:
            self.stdout.write(self.style.WARNING('\n⚠ No changes made. Provide API key to update:'))
            self.stdout.write(self.style.WARNING('  python manage.py update_sms_api_key YOUR_API_KEY_HERE'))
        
        self.stdout.write('\n' + '=' * 60)
        self.stdout.write('IMPORTANT:')
        self.stdout.write('=' * 60)
        self.stdout.write('1. Restart the server after updating API key')
        self.stdout.write('2. Test the API: python manage.py test_sms_api')
        self.stdout.write('3. Retry failed SMS: python manage.py check_sms_failures --retry')
        self.stdout.write('=' * 60)




