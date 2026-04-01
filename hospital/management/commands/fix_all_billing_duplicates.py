"""
Fix all billing-related duplicates in one run.
Runs: fix_duplicate_invoices, then fix_duplicate_invoice_lines.
Use --dry-run first to preview, then run without it to apply.
"""
from django.core.management.base import BaseCommand
from django.core.management import call_command


class Command(BaseCommand):
    help = 'Fix ALL billing duplicates: invoices + invoice lines. Run with --dry-run first.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview only - no changes',
        )
        parser.add_argument(
            '--days',
            type=int,
            default=365,
            help='Invoice age window in days (default: 365)',
        )
        parser.add_argument(
            '--skip-invoices',
            action='store_true',
            help='Skip invoice deduplication, only fix lines',
        )
        parser.add_argument(
            '--skip-lines',
            action='store_true',
            help='Skip line deduplication, only fix invoices',
        )
        parser.add_argument(
            '--conservative',
            action='store_true',
            help='Only merge invoice groups of exactly 2 (skip 3+)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        days = options['days']
        skip_invoices = options['skip_invoices']
        skip_lines = options['skip_lines']
        conservative = options.get('conservative', False)

        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS('FIX ALL BILLING DUPLICATES'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        if dry_run:
            self.stdout.write(self.style.WARNING('\n*** DRY RUN - No changes will be made ***\n'))

        # 1. Fix duplicate invoices (same patient + encounter + day)
        if not skip_invoices:
            self.stdout.write(self.style.WARNING('\n[1/2] Fixing duplicate invoices...'))
            inv_opts = {'days': days, 'dry_run': dry_run, 'verbosity': options.get('verbosity', 1)}
            if conservative:
                inv_opts['conservative'] = True
            call_command('fix_duplicate_invoices', **inv_opts)
        else:
            self.stdout.write(self.style.WARNING('\n[1/2] Skipping invoice fix (--skip-invoices)'))

        # 2. Fix duplicate invoice lines (same service on same invoice)
        if not skip_lines:
            self.stdout.write(self.style.WARNING('\n[2/2] Fixing duplicate invoice lines...'))
            call_command(
                'fix_duplicate_invoice_lines',
                dry_run=dry_run,
                verbosity=options.get('verbosity', 1),
            )
        else:
            self.stdout.write(self.style.WARNING('\n[2/2] Skipping line fix (--skip-lines)'))

        self.stdout.write(self.style.SUCCESS('\n' + '=' * 70))
        self.stdout.write(self.style.SUCCESS('DONE'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        if dry_run:
            self.stdout.write(self.style.WARNING('\nRun without --dry-run to apply changes.'))
