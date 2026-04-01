import os
from celery import Celery
from django.conf import settings

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')

app = Celery('hms')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django apps.
# Discover tasks from all Django apps plus the project-level `hms.tasks`
installed_apps = list(getattr(settings, 'INSTALLED_APPS', []))
if 'hms' not in installed_apps:
    installed_apps.append('hms')
app.autodiscover_tasks(lambda: installed_apps)

# Celery Beat Schedule
app.conf.beat_schedule = {
    'health-check-every-5-minutes': {
        'task': 'hms.tasks.health_check_task',
        'schedule': 300.0,  # 5 minutes
    },
    'cleanup-old-sessions': {
        'task': 'hms.tasks.cleanup_old_sessions',
        'schedule': 86400.0,  # 24 hours (for very old sessions)
    },
    'cleanup-expired-sessions-realtime': {
        'task': 'hms.tasks.cleanup_expired_sessions_realtime',
        'schedule': 300.0,  # 5 minutes (real-time cleanup of expired sessions)
    },
    'send-birthday-wishes-daily': {
        'task': 'hms.tasks.send_birthday_wishes',
        'schedule': 86400.0,  # Daily at midnight (24 hours)
    },
    'upcoming-birthday-reminders': {
        'task': 'hms.tasks.upcoming_birthday_reminders',
        'schedule': 86400.0,  # Daily at midnight (24 hours)
    },
    'automated-database-backup': {
        'task': 'hms.tasks.automated_database_backup',
        'schedule': 86400.0,  # Daily backup (24 hours)
    },
    'verify-database-integrity': {
        'task': 'hms.tasks.verify_database_integrity',
        'schedule': 604800.0,  # Weekly verification (7 days)
    },
    'auto-match-cash-revenue-daily': {
        'task': 'hospital.tasks_primecare.auto_match_cash_revenue',
        'schedule': 86400.0,  # Daily
    },
    'auto-match-credit-revenue-daily': {
        'task': 'hospital.tasks_primecare.auto_match_credit_revenue',
        'schedule': 86400.0,  # Daily
    },
}

app.conf.timezone = 'UTC'

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
