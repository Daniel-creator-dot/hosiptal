# Generated manually for AI Clinical Copilot

import uuid

import django.db.models.deletion
import django.utils.timezone
import model_utils.fields
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('hospital', '1137_sync_pharmacy_index_state'),
    ]

    operations = [
        migrations.CreateModel(
            name='AIClinicalAssistanceRun',
            fields=[
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, editable=False, verbose_name='created')),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, editable=False, verbose_name='modified')),
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('status', models.CharField(choices=[('queued', 'Queued'), ('running', 'Running'), ('succeeded', 'Succeeded'), ('failed', 'Failed'), ('expired', 'Expired'), ('cancelled', 'Cancelled')], db_index=True, default='queued', max_length=20)),
                ('model_name', models.CharField(blank=True, max_length=120)),
                ('prompt_version', models.CharField(blank=True, max_length=40)),
                ('schema_version', models.CharField(blank=True, max_length=40)),
                ('result', models.JSONField(blank=True, default=dict)),
                ('context_fingerprint', models.CharField(blank=True, db_index=True, max_length=64)),
                ('idempotency_key', models.CharField(blank=True, db_index=True, max_length=64)),
                ('input_tokens', models.PositiveIntegerField(blank=True, null=True)),
                ('output_tokens', models.PositiveIntegerField(blank=True, null=True)),
                ('latency_ms', models.PositiveIntegerField(blank=True, null=True)),
                ('error_code', models.CharField(blank=True, max_length=80)),
                ('error_message', models.CharField(blank=True, max_length=500)),
                ('celery_task_id', models.CharField(blank=True, max_length=255)),
                ('started_at', models.DateTimeField(blank=True, null=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('expires_at', models.DateTimeField(blank=True, db_index=True, null=True)),
                ('result_purged_at', models.DateTimeField(blank=True, null=True)),
                ('clinician_copied_sections', models.JSONField(blank=True, default=list)),
                ('clinician_inserted_draft', models.BooleanField(default=False)),
                ('clinician_feedback', models.CharField(blank=True, choices=[('', 'None'), ('helpful', 'Helpful'), ('not_helpful', 'Not helpful'), ('unsafe', 'Unsafe / incorrect')], default='', max_length=20)),
                ('clinician_feedback_note', models.CharField(blank=True, max_length=500)),
                ('clinician_feedback_at', models.DateTimeField(blank=True, null=True)),
                ('encounter', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='ai_clinical_assistance_runs', to='hospital.encounter')),
                ('requested_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='ai_clinical_assistance_runs', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'AI Clinical Assistance Run',
                'verbose_name_plural': 'AI Clinical Assistance Runs',
                'ordering': ['-created'],
                'indexes': [
                    models.Index(fields=['encounter', '-created'], name='ai_clin_enc_created_idx'),
                    models.Index(fields=['requested_by', '-created'], name='ai_clin_user_created_idx'),
                    models.Index(fields=['status', 'expires_at'], name='ai_clin_status_exp_idx'),
                ],
            },
        ),
    ]
