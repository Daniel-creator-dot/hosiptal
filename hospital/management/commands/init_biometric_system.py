"""
Management command to initialize biometric authentication system
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from hospital.models_biometric import (
    BiometricType,
    BiometricSystemSettings,
    BiometricDevice,
)
from decimal import Decimal


class Command(BaseCommand):
    help = 'Initialize biometric authentication system with default data'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Initializing Biometric Authentication System...'))
        
        with transaction.atomic():
            # Create BiometricTypes
            self.stdout.write('Creating biometric types...')
            
            face_type, created = BiometricType.objects.get_or_create(
                name='face',
                defaults={
                    'display_name': 'Face Recognition',
                    'description': 'Facial recognition using DeepFace/FaceNet algorithms',
                    'is_active': True,
                    'requires_liveness_check': True,
                    'min_confidence_score': Decimal('85.00'),
                    'max_failed_attempts': 3,
                    'lockout_duration_minutes': 15,
                }
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'  [OK] Created: {face_type.display_name}'))
            else:
                self.stdout.write(f'  [-] Already exists: {face_type.display_name}')
            
            fingerprint_type, created = BiometricType.objects.get_or_create(
                name='fingerprint',
                defaults={
                    'display_name': 'Fingerprint Recognition',
                    'description': 'Fingerprint scanning and matching',
                    'is_active': False,  # Disabled by default until hardware is configured
                    'requires_liveness_check': False,
                    'min_confidence_score': Decimal('90.00'),
                    'max_failed_attempts': 3,
                    'lockout_duration_minutes': 15,
                }
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'  [OK] Created: {fingerprint_type.display_name}'))
            else:
                self.stdout.write(f'  [-] Already exists: {fingerprint_type.display_name}')
            
            # Create System Settings
            self.stdout.write('Creating system settings...')
            settings, created = BiometricSystemSettings.objects.get_or_create(
                pk=1,
                defaults={
                    'system_enabled': True,
                    'require_biometric_for_staff': False,
                    'allow_password_fallback': True,
                    'enable_liveness_detection': True,
                    'enable_anti_spoofing': True,
                    'enable_multimodal_auth': False,
                    'template_expiry_days': 365,
                    'auto_lock_after_failures': True,
                    'auto_create_attendance': True,
                    'attendance_check_in_window_minutes': 30,
                    'enable_security_alerts': True,
                    'alert_on_multiple_failures': True,
                    'alert_failure_threshold': 5,
                    'face_recognition_provider': 'deepface',
                    'face_recognition_model': 'Facenet512',
                    'enable_caching': True,
                    'cache_duration_seconds': 300,
                    'log_retention_days': 90,
                    'require_consent_form': True,
                }
            )
            if created:
                self.stdout.write(self.style.SUCCESS('  [OK] Created system settings'))
            else:
                self.stdout.write('  [-] System settings already exist')
            
            # Create sample devices (optional)
            self.stdout.write('Creating sample biometric devices...')
            
            front_desk_device, created = BiometricDevice.objects.get_or_create(
                device_id='FRONTDESK-CAM-001',
                defaults={
                    'device_name': 'Front Desk Camera',
                    'device_type': 'face_camera',
                    'location_name': 'Front Desk - Main Entrance',
                    'manufacturer': 'Generic',
                    'model_number': 'HD-CAM-1080P',
                    'is_active': True,
                    'is_online': False,
                }
            )
            if created:
                front_desk_device.supported_biometrics.add(face_type)
                self.stdout.write(self.style.SUCCESS(f'  [OK] Created: {front_desk_device.device_name}'))
            else:
                self.stdout.write(f'  [-] Already exists: {front_desk_device.device_name}')
            
            hr_office_device, created = BiometricDevice.objects.get_or_create(
                device_id='HR-OFFICE-CAM-001',
                defaults={
                    'device_name': 'HR Office Camera',
                    'device_type': 'face_camera',
                    'location_name': 'HR Office',
                    'manufacturer': 'Generic',
                    'model_number': 'HD-CAM-1080P',
                    'is_active': True,
                    'is_online': False,
                }
            )
            if created:
                hr_office_device.supported_biometrics.add(face_type)
                self.stdout.write(self.style.SUCCESS(f'  [OK] Created: {hr_office_device.device_name}'))
            else:
                self.stdout.write(f'  [-] Already exists: {hr_office_device.device_name}')
        
        self.stdout.write(self.style.SUCCESS('\n[SUCCESS] Biometric system initialized successfully!'))
        self.stdout.write(self.style.WARNING('\nNext steps:'))
        self.stdout.write('  1. Run migrations: python manage.py migrate')
        self.stdout.write('  2. Install required libraries: pip install deepface opencv-python')
        self.stdout.write('  3. Access biometric login: http://localhost:8000/hms/biometric/login/')
        self.stdout.write('  4. Access enrollment interface: http://localhost:8000/hms/biometric/enrollment/')
        self.stdout.write('  5. Configure devices and settings in Django Admin')

