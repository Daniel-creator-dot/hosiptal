"""
Run slow outbound notifications (SMS, queue alerts) off the HTTP request thread
so form submissions return quickly with success messages.
"""
import logging
import threading

from django.db import connection

logger = logging.getLogger(__name__)


def run_deferred(target, *args, **kwargs):
    """Fire-and-forget background work; closes DB connection when done."""

    def _wrapper():
        try:
            target(*args, **kwargs)
        except Exception as exc:
            logger.warning('Deferred notification failed: %s', exc, exc_info=True)
        finally:
            connection.close()

    threading.Thread(target=_wrapper, daemon=True).start()
