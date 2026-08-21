import uuid

import django.db.models.deletion
import model_utils.fields
from django.conf import settings
from django.db import migrations, models
from django.utils import timezone


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('hospital', '1138_aiclinicalassistancerun'),
    ]

    operations = [
        migrations.CreateModel(
            name='AIClinicalChatMessage',
            fields=[
                (
                    'created',
                    model_utils.fields.AutoCreatedField(
                        default=timezone.now,
                        editable=False,
                        verbose_name='created',
                    ),
                ),
                (
                    'modified',
                    model_utils.fields.AutoLastModifiedField(
                        default=timezone.now,
                        editable=False,
                        verbose_name='modified',
                    ),
                ),
                (
                    'id',
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    'role',
                    models.CharField(
                        choices=[('doctor', 'Doctor'), ('assistant', 'AI Assistant')],
                        max_length=20,
                    ),
                ),
                (
                    'status',
                    models.CharField(
                        choices=[
                            ('pending', 'Pending'),
                            ('completed', 'Completed'),
                            ('failed', 'Failed'),
                        ],
                        db_index=True,
                        default='completed',
                        max_length=20,
                    ),
                ),
                ('content', models.TextField(blank=True)),
                ('provider_content_hash', models.CharField(blank=True, max_length=64)),
                ('model_name', models.CharField(blank=True, max_length=120)),
                ('safety_flags', models.JSONField(blank=True, default=list)),
                ('suggested_follow_ups', models.JSONField(blank=True, default=list)),
                ('input_tokens', models.PositiveIntegerField(blank=True, null=True)),
                ('output_tokens', models.PositiveIntegerField(blank=True, null=True)),
                ('latency_ms', models.PositiveIntegerField(blank=True, null=True)),
                ('celery_task_id', models.CharField(blank=True, max_length=255)),
                ('error_code', models.CharField(blank=True, max_length=80)),
                ('error_message', models.CharField(blank=True, max_length=500)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('content_purged_at', models.DateTimeField(blank=True, null=True)),
                (
                    'created_by',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='ai_clinical_chat_messages',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    'reply_to',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='replies',
                        to='hospital.aiclinicalchatmessage',
                    ),
                ),
                (
                    'run',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='chat_messages',
                        to='hospital.aiclinicalassistancerun',
                    ),
                ),
            ],
            options={
                'ordering': ['created'],
                'indexes': [
                    models.Index(
                        fields=['run', 'created'],
                        name='ai_chat_run_created_idx',
                    ),
                    models.Index(
                        fields=['run', 'status'],
                        name='ai_chat_run_status_idx',
                    ),
                ],
            },
        ),
    ]
