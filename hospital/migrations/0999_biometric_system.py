# Generated migration for biometric system
from django.db import migrations, models
import django.db.models.deletion
import uuid
from django.conf import settings
from decimal import Decimal


class Migration(migrations.Migration):

    dependencies = [
        ('hospital', '0045_add_enhanced_telemedicine_models'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='BiometricType',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('is_deleted', models.BooleanField(default=False)),
                ('name', models.CharField(choices=[('face', 'Face Recognition'), ('fingerprint', 'Fingerprint'), ('iris', 'Iris Scan'), ('voice', 'Voice Recognition'), ('palm', 'Palm Print')], max_length=50, unique=True)),
                ('display_name', models.CharField(max_length=100)),
                ('description', models.TextField(blank=True)),
                ('is_active', models.BooleanField(default=True)),
                ('requires_liveness_check', models.BooleanField(default=True)),
                ('min_confidence_score', models.DecimalField(decimal_places=2, default=Decimal('85.00'), max_digits=5)),
                ('max_failed_attempts', models.IntegerField(default=3)),
                ('lockout_duration_minutes', models.IntegerField(default=15)),
                ('config_json', models.JSONField(blank=True, default=dict)),
            ],
            options={
                'verbose_name': 'Biometric Type',
                'verbose_name_plural': 'Biometric Types',
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='BiometricSystemSettings',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('is_deleted', models.BooleanField(default=False)),
                ('system_enabled', models.BooleanField(default=True)),
                ('require_biometric_for_staff', models.BooleanField(default=False)),
                ('allow_password_fallback', models.BooleanField(default=True)),
                ('enable_liveness_detection', models.BooleanField(default=True)),
                ('enable_anti_spoofing', models.BooleanField(default=True)),
                ('enable_multimodal_auth', models.BooleanField(default=False)),
                ('template_expiry_days', models.IntegerField(default=365)),
                ('auto_lock_after_failures', models.BooleanField(default=True)),
                ('auto_create_attendance', models.BooleanField(default=True)),
                ('attendance_check_in_window_minutes', models.IntegerField(default=30)),
                ('enable_security_alerts', models.BooleanField(default=True)),
                ('alert_on_multiple_failures', models.BooleanField(default=True)),
                ('alert_failure_threshold', models.IntegerField(default=5)),
                ('alert_recipients_json', models.JSONField(blank=True, default=list)),
                ('face_recognition_provider', models.CharField(choices=[('facenet', 'FaceNet (TensorFlow)'), ('dlib', 'Dlib'), ('opencv', 'OpenCV'), ('azure', 'Azure Face API'), ('aws', 'AWS Rekognition'), ('deepface', 'DeepFace')], default='deepface', max_length=50)),
                ('face_recognition_model', models.CharField(choices=[('VGG-Face', 'VGG-Face'), ('Facenet', 'Facenet'), ('Facenet512', 'Facenet512'), ('OpenFace', 'OpenFace'), ('DeepFace', 'DeepFace'), ('DeepID', 'DeepID'), ('ArcFace', 'ArcFace'), ('Dlib', 'Dlib')], default='Facenet512', max_length=50)),
                ('enable_caching', models.BooleanField(default=True)),
                ('cache_duration_seconds', models.IntegerField(default=300)),
                ('log_retention_days', models.IntegerField(default=90)),
                ('require_consent_form', models.BooleanField(default=True)),
            ],
            options={
                'verbose_name': 'Biometric System Settings',
                'verbose_name_plural': 'Biometric System Settings',
            },
        ),
    ]

