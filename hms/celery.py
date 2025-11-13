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
app.autodiscover_tasks()

# Celery Beat Schedule
app.conf.beat_schedule = {
    'health-check-every-5-minutes': {
        'task': 'hms.tasks.health_check_task',
        'schedule': 300.0,  # 5 minutes
    },
    'cleanup-old-sessions': {
        'task': 'hms.tasks.cleanup_old_sessions',
        'schedule': 86400.0,  # 24 hours
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
}

app.conf.timezone = 'UTC'

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
