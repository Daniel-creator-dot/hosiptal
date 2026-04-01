"""
Management command to ensure Electricity Company of Ghana (ECG) is visible as corporate
for both front desk and accountant. Creates/updates Payer and CorporateAccount.
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from decimal import Decimal
from datetime import date
from hospital.models import Payer
from hospital.models_enterprise_billing import CorporateAccount
from hospital.models_accounting_advanced import AccountingCorporateAccount
from hospital.models_accounting import Account


# Names to search for (ECG / Electricity Company of Ghana)
ECG_NAMES = [
    'Electricity Company of Ghana',
    'ECG',
    'ECG*electricity company of ghana',
    'ECG*Electricity Company of Ghana',
    'Electricity Company of Ghana (ECG)',
]


class Command(BaseCommand):
    help = 'Ensure Electricity Company of Ghana (ECG) is visible as corporate for front desk and accountant'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making changes',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN - No changes will be made'))

        self.stdout.write('\nEnsuring ECG (Electricity Company of Ghana) is visible as corporate...\n')

        with transaction.atomic():
            # 1. Find or create Payer
            payer = None
            for name in ECG_NAMES:
                payer = Payer.objects.filter(
                    name__iexact=name,
                    is_deleted=False
                ).first()
                if payer:
                    break

            if not payer:
                # Try partial match
                payer = Payer.objects.filter(
                    name__icontains='electricity company',
                    is_deleted=False
                ).first()
            if not payer:
                payer = Payer.objects.filter(
                    name__icontains='ECG',
                    is_deleted=False
                ).first()

            if payer:
                self.stdout.write(f'Found Payer: {payer.name} (type={payer.payer_type}, active={payer.is_active})')
                if not dry_run:
                    if payer.payer_type != 'corporate':
                        payer.payer_type = 'corporate'
                        payer.save()
                        self.stdout.write(self.style.SUCCESS(f'   Updated payer_type to corporate'))
                    if not payer.is_active:
                        payer.is_active = True
                        payer.save()
                        self.stdout.write(self.style.SUCCESS(f'   Set is_active=True'))
            else:
                # Create new Payer
                display_name = 'Electricity Company of Ghana'
                if dry_run:
                    self.stdout.write(
                        self.style.SUCCESS(f'Would create Payer: {display_name} (payer_type=corporate)')
                    )
                else:
                    payer = Payer.objects.create(
                        name=display_name,
                        payer_type='corporate',
                        is_active=True,
                    )
                    self.stdout.write(self.style.SUCCESS(f'Created Payer: {payer.name} (type=corporate)'))

            # 2. Ensure CorporateAccount exists (for accountant)
            if payer:
                corp_account = CorporateAccount.objects.filter(
                    company_name__iexact=payer.name,
                    is_deleted=False
                ).first()
                if not corp_account:
                    corp_account = CorporateAccount.objects.filter(
                        company_name__icontains='Electricity',
                        is_deleted=False
                    ).first()
                if not corp_account:
                    corp_account = CorporateAccount.objects.filter(
                        company_code__iexact='ECG',
                        is_deleted=False
                    ).first()

                if corp_account:
                    self.stdout.write(f'Found CorporateAccount: {corp_account.company_name}')
                    if not corp_account.is_active and not dry_run:
                        corp_account.is_active = True
                        corp_account.save()
                        self.stdout.write(self.style.SUCCESS(f'   Set is_active=True'))
                else:
                    if dry_run:
                        self.stdout.write(
                            self.style.SUCCESS(
                                f'Would create CorporateAccount: Electricity Company of Ghana (ECG)'
                            )
                        )
                    else:
                        from django.utils import timezone
                        today = timezone.now().date()
                        corp_account = CorporateAccount.objects.create(
                            company_name='Electricity Company of Ghana',
                            company_code='ECG',
                            billing_contact_name='ECG Accounts Department',
                            billing_email='accounts@ecg.com.gh',
                            billing_phone='0302XXXXXX',
                            billing_address='Electricity Company of Ghana, Accra',
                            credit_limit=Decimal('500000.00'),
                            current_balance=Decimal('0.00'),
                            credit_status='active',
                            next_billing_date=today,
                            contract_start_date=today,
                        )
                        self.stdout.write(
                            self.style.SUCCESS(
                                f'Created CorporateAccount: {corp_account.company_name} ({corp_account.company_code})'
                            )
                        )

            # 3. Ensure AccountingCorporateAccount exists (for accountant /hms/accountant/corporate-accounts/)
            ar_account = Account.objects.filter(
                account_code='1200',
                is_active=True
            ).first()
            if not ar_account:
                ar_account = Account.objects.filter(
                    account_name__icontains='receivable',
                    is_active=True
                ).first()
            if not ar_account:
                ar_account = Account.objects.filter(is_active=True).first()
            if ar_account:
                acc_corp = AccountingCorporateAccount.objects.filter(
                    company_name__icontains='Electricity',
                    is_deleted=False
                ).first()
                if not acc_corp:
                    acc_corp = AccountingCorporateAccount.objects.filter(
                        account_number='CORP-ECG',
                        is_deleted=False
                    ).first()
                if not acc_corp and not dry_run:
                    AccountingCorporateAccount.objects.create(
                        account_number='CORP-ECG',
                        company_name='Electricity Company of Ghana',
                        contact_person='ECG Accounts Department',
                        contact_email='accounts@ecg.com.gh',
                        credit_limit=Decimal('500000.00'),
                        current_balance=Decimal('0.00'),
                        receivable_account=ar_account,
                        is_active=True,
                    )
                    self.stdout.write(
                        self.style.SUCCESS('Created AccountingCorporateAccount for accountant view')
                    )

        # Verify
        from django.db.models import Q
        corp_count = Payer.objects.filter(
            payer_type='corporate',
            is_active=True,
            is_deleted=False
        ).count()
        ecg_in_list = Payer.objects.filter(
            payer_type='corporate',
            is_active=True,
            is_deleted=False
        ).filter(Q(name__icontains='Electricity') | Q(name__icontains='ECG'))

        self.stdout.write(f'\nTotal corporate payers: {corp_count}')
        if ecg_in_list.exists():
            self.stdout.write(self.style.SUCCESS('SUCCESS: ECG will appear in corporate dropdown!'))
        else:
            self.stdout.write(self.style.ERROR('WARNING: ECG may not appear - check Payer records'))

        self.stdout.write('\nDone!\n')
