"""
Measure HTTP query count and wall time for a URL (staging / profiling).

Uses the same DEBUG query logging as verify_performance. Authenticate with
--user to hit protected routes.

Example:
  python manage.py measure_url_performance /hms/ --user admin
  python manage.py measure_url_performance /api/hospital/patients/ --user admin --method GET
"""
import time

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, reset_queries
from django.test import Client
from django.test.utils import override_settings


class Command(BaseCommand):
    help = 'Print query count and milliseconds for one HTTP request (profiling aid).'

    def add_arguments(self, parser):
        parser.add_argument('path', type=str, help='URL path, e.g. /hms/ or /api/hospital/patients/')
        parser.add_argument('--user', type=str, default='', help='Username to log in as (optional)')
        parser.add_argument('--method', type=str, default='GET', choices=['GET', 'POST', 'HEAD'])
        parser.add_argument('--print-queries', action='store_true', help='Print SQL statements (verbose)')

    def handle(self, *args, **options):
        path = options['path']
        if not path.startswith('/'):
            path = '/' + path
        username = (options['user'] or '').strip()
        method = options['method']

        user = None
        if username:
            User = get_user_model()
            q_primary = {User.USERNAME_FIELD: username}
            user = User.objects.filter(**q_primary).first()
            if user is None and hasattr(User, 'email'):
                user = User.objects.filter(email__iexact=username).first()
            if user is None:
                raise CommandError(f'User not found: {username}')

        client = Client()
        if user is not None:
            client.force_login(user)

        # Avoid DisallowedHost from default Client HTTP_HOST ('testserver')
        host_kw = {'HTTP_HOST': 'localhost'}
        with override_settings(DEBUG=True):
            reset_queries()
            start = time.perf_counter()
            if method == 'GET':
                response = client.get(path, **host_kw)
            elif method == 'HEAD':
                response = client.head(path, **host_kw)
            else:
                response = client.post(path, {}, **host_kw)
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            query_count = len(connection.queries)

        self.stdout.write(
            f'status={response.status_code}  queries={query_count}  time_ms={elapsed_ms}  path={path}'
        )
        if options['print_queries']:
            for i, q in enumerate(connection.queries, 1):
                self.stdout.write(f'  {i}. {q.get("sql", "")[:500]}')
