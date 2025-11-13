"""
Django management command to import General Ledger from Excel

Usage:
    python manage.py import_gl_excel "/path/to/file.xlsx" --ledger "LEDGER 2025" --tb "TB 2025"
"""
import os
import json
from django.core.management.base import BaseCommand, CommandError
from hospital.utils_excel_import import import_gl_from_excel, get_trial_balance


class Command(BaseCommand):
    help = 'Import General Ledger and Trial Balance from Excel workbook'

    def add_arguments(self, parser):
        parser.add_argument('xlsx_path', type=str, help='Path to Excel workbook')
        parser.add_argument(
            '--ledger',
            type=str,
            default='LEDGER 2025',
            help='Ledger sheet name (default: LEDGER 2025)'
        )
        parser.add_argument(
            '--tb',
            type=str,
            default='TB 2025',
            help='Trial Balance sheet name (default: TB 2025)'
        )
        parser.add_argument(
            '--user',
            type=str,
            default=None,
            help='Username of user importing (for audit trail)'
        )
        parser.add_argument(
            '--auto-post',
            action='store_true',
            help='Automatically post journal entries if balanced'
        )
        parser.add_argument(
            '--show-tb',
            action='store_true',
            help='Show trial balance after import'
        )

    def handle(self, *args, **options):
        xlsx_path = options['xlsx_path']
        sheet_ledger = options['ledger']
        sheet_tb = options['tb']
        username = options.get('user')
        auto_post = options.get('auto_post', False)
        show_tb = options.get('show_tb', False)

        if not os.path.exists(xlsx_path):
            raise CommandError(f'Excel file not found: {xlsx_path}')

        # Get user if specified
        entered_by = None
        if username:
            from django.contrib.auth.models import User
            try:
                entered_by = User.objects.get(username=username)
            except User.DoesNotExist:
                raise CommandError(f'User not found: {username}')

        try:
            self.stdout.write(f'Importing from {xlsx_path}...')
            result = import_gl_from_excel(
                xlsx_path=xlsx_path,
                sheet_ledger=sheet_ledger,
                sheet_tb=sheet_tb,
                entered_by=entered_by,
                auto_post=auto_post,
            )
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'\n✓ Import completed successfully!\n'
                    f'  - Journal entries created: {result["journals"]}\n'
                    f'  - Journal lines created: {result["lines"]}\n'
                    f'  - Accounts created: {result["accounts_created"]}\n'
                    f'  - Unbalanced journals: {len(result["unbalanced_warnings"])}'
                )
            )
            
            if result['unbalanced_warnings']:
                self.stdout.write(
                    self.style.WARNING('\n⚠ Unbalanced Journals:')
                )
                for warning in result['unbalanced_warnings']:
                    self.stdout.write(f'  - {warning}')
            
            if show_tb:
                self.stdout.write('\nTrial Balance:')
                tb = get_trial_balance()
                self.stdout.write(json.dumps(tb, indent=2))
                
        except Exception as e:
            raise CommandError(f'Import failed: {str(e)}')

