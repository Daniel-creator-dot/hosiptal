"""
AI Clinical Copilot run records.

Stores structured advisory assistance for consultation encounters.
Never stores the raw provider prompt/request payload (de-identified context
is built at call time and not persisted). Clinical chart mutations must still
go through normal clinician save workflows.
"""
from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone
from model_utils.models import TimeStampedModel


class AIClinicalAssistanceRun(TimeStampedModel):
    """One local-AI clinical assistance request for an encounter."""

    STATUS_QUEUED = 'queued'
    STATUS_RUNNING = 'running'
    STATUS_SUCCEEDED = 'succeeded'
    STATUS_FAILED = 'failed'
    STATUS_EXPIRED = 'expired'
    STATUS_CANCELLED = 'cancelled'

    STATUS_CHOICES = [
        (STATUS_QUEUED, 'Queued'),
        (STATUS_RUNNING, 'Running'),
        (STATUS_SUCCEEDED, 'Succeeded'),
        (STATUS_FAILED, 'Failed'),
        (STATUS_EXPIRED, 'Expired'),
        (STATUS_CANCELLED, 'Cancelled'),
    ]

    FEEDBACK_NONE = ''
    FEEDBACK_HELPFUL = 'helpful'
    FEEDBACK_NOT_HELPFUL = 'not_helpful'
    FEEDBACK_UNSAFE = 'unsafe'

    FEEDBACK_CHOICES = [
        (FEEDBACK_NONE, 'None'),
        (FEEDBACK_HELPFUL, 'Helpful'),
        (FEEDBACK_NOT_HELPFUL, 'Not helpful'),
        (FEEDBACK_UNSAFE, 'Unsafe / incorrect'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    encounter = models.ForeignKey(
        'hospital.Encounter',
        on_delete=models.CASCADE,
        related_name='ai_clinical_assistance_runs',
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ai_clinical_assistance_runs',
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_QUEUED, db_index=True)

    model_name = models.CharField(max_length=120, blank=True)
    prompt_version = models.CharField(max_length=40, blank=True)
    schema_version = models.CharField(max_length=40, blank=True)

    # Structured advisory payload only (never the outbound prompt)
    result = models.JSONField(default=dict, blank=True)
    # Non-clinical request fingerprint for idempotency (hash of context keys, not PHI)
    context_fingerprint = models.CharField(max_length=64, blank=True, db_index=True)
    idempotency_key = models.CharField(max_length=64, blank=True, db_index=True)

    input_tokens = models.PositiveIntegerField(null=True, blank=True)
    output_tokens = models.PositiveIntegerField(null=True, blank=True)
    latency_ms = models.PositiveIntegerField(null=True, blank=True)

    error_code = models.CharField(max_length=80, blank=True)
    error_message = models.CharField(max_length=500, blank=True)

    celery_task_id = models.CharField(max_length=255, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True, db_index=True)
    result_purged_at = models.DateTimeField(null=True, blank=True)

    clinician_copied_sections = models.JSONField(default=list, blank=True)
    clinician_inserted_draft = models.BooleanField(default=False)
    clinician_feedback = models.CharField(
        max_length=20, choices=FEEDBACK_CHOICES, default=FEEDBACK_NONE, blank=True
    )
    clinician_feedback_note = models.CharField(max_length=500, blank=True)
    clinician_feedback_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created']
        indexes = [
            models.Index(fields=['encounter', '-created'], name='ai_clin_enc_created_idx'),
            models.Index(fields=['requested_by', '-created'], name='ai_clin_user_created_idx'),
            models.Index(fields=['status', 'expires_at'], name='ai_clin_status_exp_idx'),
        ]
        verbose_name = 'AI Clinical Assistance Run'
        verbose_name_plural = 'AI Clinical Assistance Runs'

    def __str__(self):
        return f'AIClinicalAssistanceRun {self.id} ({self.status})'

    @property
    def is_terminal(self) -> bool:
        return self.status in {
            self.STATUS_SUCCEEDED,
            self.STATUS_FAILED,
            self.STATUS_EXPIRED,
            self.STATUS_CANCELLED,
        }

    def mark_running(self):
        self.status = self.STATUS_RUNNING
        self.started_at = timezone.now()
        self.save(update_fields=['status', 'started_at', 'modified'])

    def mark_succeeded(self, result, *, model_name='', input_tokens=None, output_tokens=None, latency_ms=None):
        self.status = self.STATUS_SUCCEEDED
        self.result = result or {}
        self.model_name = model_name or self.model_name
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.latency_ms = latency_ms
        self.completed_at = timezone.now()
        self.error_code = ''
        self.error_message = ''
        self.save(
            update_fields=[
                'status',
                'result',
                'model_name',
                'input_tokens',
                'output_tokens',
                'latency_ms',
                'completed_at',
                'error_code',
                'error_message',
                'modified',
            ]
        )

    def mark_failed(self, error_code: str, error_message: str):
        self.status = self.STATUS_FAILED
        self.error_code = (error_code or 'error')[:80]
        self.error_message = (error_message or 'Request failed')[:500]
        self.completed_at = timezone.now()
        self.save(
            update_fields=['status', 'error_code', 'error_message', 'completed_at', 'modified']
        )

    def purge_result_payload(self):
        """Clear clinical result JSON after retention window; keep provenance."""
        if self.result_purged_at:
            return
        self.result = {}
        self.status = self.STATUS_EXPIRED if self.status == self.STATUS_SUCCEEDED else self.status
        self.result_purged_at = timezone.now()
        self.save(update_fields=['result', 'status', 'result_purged_at', 'modified'])
        self.chat_messages.exclude(content='').update(
            content='',
            content_purged_at=timezone.now(),
        )


class AIClinicalChatMessage(TimeStampedModel):
    """A retained, audited doctor/copilot chat turn linked to one assistance run."""

    ROLE_DOCTOR = 'doctor'
    ROLE_ASSISTANT = 'assistant'
    ROLE_CHOICES = [
        (ROLE_DOCTOR, 'Doctor'),
        (ROLE_ASSISTANT, 'AI Assistant'),
    ]

    STATUS_PENDING = 'pending'
    STATUS_COMPLETED = 'completed'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_FAILED, 'Failed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    run = models.ForeignKey(
        AIClinicalAssistanceRun,
        on_delete=models.CASCADE,
        related_name='chat_messages',
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_COMPLETED,
        db_index=True,
    )
    content = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ai_clinical_chat_messages',
    )
    reply_to = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='replies',
    )
    provider_content_hash = models.CharField(max_length=64, blank=True)
    model_name = models.CharField(max_length=120, blank=True)
    safety_flags = models.JSONField(default=list, blank=True)
    suggested_follow_ups = models.JSONField(default=list, blank=True)
    input_tokens = models.PositiveIntegerField(null=True, blank=True)
    output_tokens = models.PositiveIntegerField(null=True, blank=True)
    latency_ms = models.PositiveIntegerField(null=True, blank=True)
    celery_task_id = models.CharField(max_length=255, blank=True)
    error_code = models.CharField(max_length=80, blank=True)
    error_message = models.CharField(max_length=500, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    content_purged_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['created']
        indexes = [
            models.Index(fields=['run', 'created'], name='ai_chat_run_created_idx'),
            models.Index(fields=['run', 'status'], name='ai_chat_run_status_idx'),
        ]

    def __str__(self):
        return f'AIClinicalChatMessage {self.id} ({self.role}/{self.status})'

    def mark_completed(
        self,
        content,
        *,
        model_name='',
        safety_flags=None,
        suggested_follow_ups=None,
        input_tokens=None,
        output_tokens=None,
        latency_ms=None,
    ):
        self.status = self.STATUS_COMPLETED
        self.content = content or ''
        self.model_name = model_name or self.model_name
        self.safety_flags = safety_flags or []
        self.suggested_follow_ups = suggested_follow_ups or []
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.latency_ms = latency_ms
        self.completed_at = timezone.now()
        self.error_code = ''
        self.error_message = ''
        self.save(
            update_fields=[
                'status',
                'content',
                'model_name',
                'safety_flags',
                'suggested_follow_ups',
                'input_tokens',
                'output_tokens',
                'latency_ms',
                'completed_at',
                'error_code',
                'error_message',
                'modified',
            ]
        )

    def mark_failed(self, error_code, error_message):
        self.status = self.STATUS_FAILED
        self.error_code = (error_code or 'error')[:80]
        self.error_message = (error_message or 'Unable to answer this question.')[:500]
        self.completed_at = timezone.now()
        self.save(
            update_fields=[
                'status',
                'error_code',
                'error_message',
                'completed_at',
                'modified',
            ]
        )
