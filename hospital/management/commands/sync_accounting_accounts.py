"""
Management command to sync and link all accounting accounts
"""
from django.core.management.base import BaseCommand
from hospital.utils_account_linking import sync_all_accounts, link_cashbook_to_accounts


class Command(BaseCommand):
    help = 'Sync and link all accounting accounts to ensure proper relationships'

    def add_arguments(self, parser):
        parser.add_argument(
            '--cashbook-only',
            action='store_true',
            help='Only sync cashbook entries',
        )

    def handle(self, *args, **options):
        self.stdout.write('Syncing accounting accounts...')
        
        if options['cashbook_only']:
            results = link_cashbook_to_accounts()
            self.stdout.write(
                self.style.SUCCESS(
                    f'Linked {results["linked"]} cashbook entries to accounts'
                )
            )
            if results['errors']:
                for error in results['errors']:
                    self.stdout.write(self.style.ERROR(f'Error: {error}'))
        else:
            results = sync_all_accounts()
            self.stdout.write(
                self.style.SUCCESS(
                    f'Checked {results["accounts_checked"]} accounts, '
                    f'linked {results["accounts_linked"]} accounts, '
                    f'synced {results["bank_accounts_synced"]} bank accounts'
                )
            )
            if results['errors']:
                for error in results['errors']:
                    self.stdout.write(self.style.ERROR(f'Error: {error}'))
        
        self.stdout.write(self.style.SUCCESS('Account sync completed!'))

