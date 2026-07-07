"""
Verify Primecare inventory and revenue GL accounts exist and are active.
"""
from django.core.management.base import BaseCommand

from hospital.models_accounting import Account
from hospital.services.inventory_account_mapping import (
    ACCOUNT_NAMES,
    INVENTORY_CATEGORY_MAP,
)
from hospital.services.service_account_mapping import PRIMECARE_REVENUE_ACCOUNTS


class Command(BaseCommand):
    help = 'Verify inventory (1400, 511x, 2100) and Primecare revenue accounts exist'

    def handle(self, *args, **options):
        required = {}
        for cfg in INVENTORY_CATEGORY_MAP.values():
            required[cfg['asset']] = ACCOUNT_NAMES.get(cfg['asset'], ('Inventories', 'asset'))
            required[cfg['cogs']] = ACCOUNT_NAMES.get(cfg['cogs'], ('COGS', 'expense'))
            required[cfg['ap']] = ACCOUNT_NAMES.get(cfg['ap'], ('AP', 'liability'))
        seen_rev = set()
        for _key, (rev_code, rev_name) in PRIMECARE_REVENUE_ACCOUNTS.items():
            if rev_code in seen_rev:
                continue
            seen_rev.add(rev_code)
            required[rev_code] = (rev_name, 'revenue')

        unique_codes = {}
        for code, meta in required.items():
            if code not in unique_codes:
                unique_codes[code] = meta

        missing = []
        inactive = []
        for code, (name, acct_type) in sorted(unique_codes.items()):
            acct = Account.objects.filter(account_code=code, is_deleted=False).first()
            if not acct:
                missing.append(code)
                self.stdout.write(self.style.ERROR(f'Missing: {code} ({name})'))
            elif not acct.is_active:
                inactive.append(code)
                self.stdout.write(self.style.WARNING(f'Inactive: {code} ({acct.account_name})'))
            else:
                self.stdout.write(self.style.SUCCESS(f'OK: {code} — {acct.account_name}'))

        if missing or inactive:
            self.stdout.write(
                self.style.WARNING(
                    f'Done with issues: {len(missing)} missing, {len(inactive)} inactive. '
                    'Run: python manage.py setup_primecare_chart_of_accounts'
                )
            )
        else:
            self.stdout.write(self.style.SUCCESS('All required inventory/revenue accounts OK.'))
