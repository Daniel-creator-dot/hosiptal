"""Celery tasks for AI Clinical Copilot."""
from __future__ import annotations

import logging

from celery import shared_task
from celery.exceptions import MaxRetriesExceededError, Retry
from django.conf import settings

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    name='hospital.tasks_ai_clinical.execute_ai_clinical_assistance_run',
    max_retries=2,
    default_retry_delay=8,
    acks_late=True,
)
def execute_ai_clinical_assistance_run(self, run_id: str):
    """Execute a queued AI clinical assistance run with bounded retries."""
    from hospital.services.ai_clinical_assistant_service import (
        AIClinicalAssistantError,
        execute_run,
    )

    max_retries = int(getattr(settings, 'AI_CLINICAL_ASSISTANT_MAX_RETRIES', 2) or 2)
    try:
        status = execute_run(run_id)
        if status == 'failed' and self.request.retries < max_retries:
            # Only retry transient provider failures
            from hospital.models_ai_clinical import AIClinicalAssistanceRun

            run = AIClinicalAssistanceRun.objects.filter(pk=run_id).first()
            if run and run.error_code in {
                'provider_error',
                'provider_timeout',
                'empty_response',
            }:
                # Reset to queued for retry claim
                AIClinicalAssistanceRun.objects.filter(pk=run_id).update(
                    status=AIClinicalAssistanceRun.STATUS_QUEUED,
                    error_code='',
                    error_message='',
                )
                raise self.retry(
                    countdown=8 * (self.request.retries + 1),
                    max_retries=max_retries,
                )
        return status
    except AIClinicalAssistantError:
        return 'failed'
    except Retry:
        raise
    except MaxRetriesExceededError:
        logger.warning('AI clinical assistance run %s exhausted retries', run_id)
        return 'failed'
    except Exception as exc:
        logger.warning(
            'AI clinical assistance run %s transient failure: %s',
            run_id,
            type(exc).__name__,
        )
        if self.request.retries < max_retries:
            raise self.retry(
                exc=exc,
                countdown=8 * (self.request.retries + 1),
                max_retries=max_retries,
            )
        # Final attempt already failed; ensure run is marked failed
        try:
            from hospital.models_ai_clinical import AIClinicalAssistanceRun

            run = AIClinicalAssistanceRun.objects.filter(pk=run_id).first()
            if run and run.status not in (
                AIClinicalAssistanceRun.STATUS_SUCCEEDED,
                AIClinicalAssistanceRun.STATUS_FAILED,
            ):
                run.mark_failed('provider_error', 'The AI provider request failed after retries.')
        except Exception:
            pass
        return 'failed'


@shared_task(
    bind=True,
    name='hospital.tasks_ai_clinical.execute_ai_clinical_chat_message',
    max_retries=2,
    default_retry_delay=8,
    acks_late=True,
)
def execute_ai_clinical_chat_message(self, message_id: str):
    """Generate one asynchronous doctor/copilot chat answer."""
    from hospital.models_ai_clinical import AIClinicalChatMessage
    from hospital.services.ai_clinical_assistant_service import execute_chat_message

    max_retries = int(getattr(settings, 'AI_CLINICAL_ASSISTANT_MAX_RETRIES', 2) or 2)
    status = execute_chat_message(message_id)
    if status != 'failed':
        return status

    message = AIClinicalChatMessage.objects.filter(pk=message_id).first()
    if (
        message
        and message.error_code in {'provider_error', 'provider_timeout', 'empty_response'}
        and self.request.retries < max_retries
    ):
        AIClinicalChatMessage.objects.filter(pk=message_id).update(
            status=AIClinicalChatMessage.STATUS_PENDING,
            error_code='',
            error_message='',
        )
        raise self.retry(
            countdown=8 * (self.request.retries + 1),
            max_retries=max_retries,
        )
    return 'failed'


@shared_task(name='hospital.tasks_ai_clinical.purge_expired_ai_clinical_results')
def purge_expired_ai_clinical_results():
    """Clear expired AI result payloads while retaining provenance metadata."""
    from hospital.services.ai_clinical_assistant_service import purge_expired_results

    count = purge_expired_results(limit=500)
    logger.info('Purged clinical result payload from %s AI runs', count)
    return count
