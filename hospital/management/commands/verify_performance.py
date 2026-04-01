"""
Verify dashboard and key-path performance for enterprise SLAs and regression detection.
Run after deploy or in CI to ensure query count and latency stay within targets.

For per-URL profiling (query count + latency), use:
  python manage.py measure_url_performance <path> [--user USERNAME_OR_EMAIL]
"""
import time
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.test.utils import override_settings
from django.db import connection, reset_queries


# Default targets: cold run of dashboard stats + demographics + encounter + extra
DEFAULT_TARGET_QUERIES = 48   # cold dashboard path; tune for schema/indexes (CI uses looser --target-queries)
DEFAULT_TARGET_MS = 1900     # cold run on modest hardware; tune for your env


class Command(BaseCommand):
    help = (
        'Verify dashboard performance: query count and latency. '
        'Use --cold to simulate cache miss (first user after deploy). '
        'Exit code 0 if within targets, 1 otherwise (for CI).'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--cold',
            action='store_true',
            help='Clear dashboard-related caches before measuring (simulate cache miss)',
        )
        parser.add_argument(
            '--target-queries',
            type=int,
            default=DEFAULT_TARGET_QUERIES,
            help=f'Fail if query count exceeds this (default: {DEFAULT_TARGET_QUERIES})',
        )
        parser.add_argument(
            '--target-ms',
            type=int,
            default=DEFAULT_TARGET_MS,
            help=f'Fail if elapsed ms exceeds this (default: {DEFAULT_TARGET_MS})',
        )
        parser.add_argument(
            '--quiet',
            action='store_true',
            help='Only print pass/fail and exit code',
        )

    def handle(self, *args, **options):
        cold = options['cold']
        target_queries = options['target_queries']
        target_ms = options['target_ms']
        quiet = options['quiet']

        from django.core.cache import cache
        today = timezone.now().date()

        if cold:
            keys_to_clear = [
                f'hms:dashboard_stats_{today}',
                'patient_demographics',
                'encounter_statistics',
                f'hms:dashboard_extra_{today}',
            ]
            for key in keys_to_clear:
                cache.delete(key)
            if not quiet:
                self.stdout.write('Cleared dashboard caches (cold run).')

        # Enable query logging and run the same code path as dashboard
        with override_settings(DEBUG=True):
            reset_queries()
            start = time.perf_counter()
            from hospital.utils import (
                get_dashboard_stats,
                get_patient_demographics,
                get_encounter_statistics,
                get_dashboard_extra_stats,
            )
            get_dashboard_stats()
            get_patient_demographics()
            get_encounter_statistics()
            get_dashboard_extra_stats(today)
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            query_count = len(connection.queries)

        passed = query_count <= target_queries and elapsed_ms <= target_ms

        if quiet:
            self.stdout.write(
                'PASS' if passed else 'FAIL',
                ending='',
            )
            if not passed:
                self.stdout.write(
                    f' (queries={query_count} target={target_queries}, '
                    f'ms={elapsed_ms} target={target_ms})'
                )
            else:
                self.stdout.write('')
        else:
            style = self.style.SUCCESS if passed else self.style.ERROR
            self.stdout.write(
                style(
                    f'Queries: {query_count} (target <= {target_queries})  '
                    f'Time: {elapsed_ms} ms (target <= {target_ms} ms)'
                )
            )
            if passed:
                self.stdout.write(self.style.SUCCESS('Verification PASSED.'))
            else:
                self.stdout.write(
                    self.style.ERROR(
                        'Verification FAILED. Consider cache warmup, indexes, or relaxing targets.'
                    )
                )

        raise SystemExit(0 if passed else 1)
