"""
Profile query count and duplicate SQL patterns for dashboard, patient list, and billing list.

Complements measure_url_performance (single URL). Use after auth middleware changes or to
baseline regressions.

Example:
  python manage.py profile_hot_paths --user admin
  python manage.py profile_hot_paths --user accountant@example.com --print-top 5
"""
import re
from collections import Counter

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, reset_queries
from django.test import Client
from django.test.utils import override_settings
from django.urls import reverse
import time


DEFAULT_ROUTE_NAMES = [
    ('dashboard', 'hospital:dashboard', []),
    ('patient_list', 'hospital:patient_list', []),
    ('bills_list', 'hospital:bills_list', []),
]


def _fingerprint(sql: str) -> str:
    """Normalize SQL for duplicate detection (strip literals)."""
    s = re.sub(r"'[^']*'", "?", sql)
    s = re.sub(r'\b\d+\b', '?', s)
    s = re.sub(r'\s+', ' ', s).strip()[:240]
    return s


class Command(BaseCommand):
    help = 'Run GET on dashboard, patient list, and bills list; print query counts and duplicate SQL fingerprints.'

    def add_arguments(self, parser):
        parser.add_argument('--user', type=str, required=True, help='Username or email to log in as')
        parser.add_argument(
            '--print-top',
            type=int,
            default=8,
            help='How many duplicate SQL fingerprints to show per path (0 to skip)',
        )

    def handle(self, *args, **options):
        username = (options['user'] or '').strip()
        print_top = options['print_top']

        User = get_user_model()
        q_primary = {User.USERNAME_FIELD: username}
        user = User.objects.filter(**q_primary).first()
        if user is None and hasattr(User, 'email'):
            user = User.objects.filter(email__iexact=username).first()
        if user is None:
            raise CommandError(f'User not found: {username}')

        client = Client()
        client.force_login(user)
        host_kw = {'HTTP_HOST': 'localhost'}

        self.stdout.write(self.style.NOTICE(f'Profiling as {user.get_username()} (id={user.pk})'))
        for label, url_name, args in DEFAULT_ROUTE_NAMES:
            try:
                path = reverse(url_name, args=args)
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'{label}: reverse failed ({e})'))
                continue

            with override_settings(DEBUG=True):
                reset_queries()
                t0 = time.perf_counter()
                response = client.get(path, **host_kw)
                elapsed_ms = int((time.perf_counter() - t0) * 1000)
                queries = connection.queries
                n = len(queries)

            self.stdout.write(
                f'{label}: status={response.status_code} queries={n} time_ms={elapsed_ms} path={path}'
            )
            if print_top > 0 and queries:
                ctr = Counter(_fingerprint(q.get('sql', '')) for q in queries)
                for fp, count in ctr.most_common(print_top):
                    if count > 1:
                        self.stdout.write(self.style.WARNING(f'  x{count}  {fp}'))
