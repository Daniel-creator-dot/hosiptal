"""
Hospital Celery task package entrypoint.

Autodiscover loads hospital.tasks; re-export specialized task modules here.
"""
from hospital.tasks_ai_clinical import (  # noqa: F401
    execute_ai_clinical_chat_message,
    execute_ai_clinical_assistance_run,
    purge_expired_ai_clinical_results,
)

try:
    from hospital.tasks_primecare import (  # noqa: F401
        auto_match_cash_revenue,
        auto_match_credit_revenue,
    )
except Exception:
    pass
