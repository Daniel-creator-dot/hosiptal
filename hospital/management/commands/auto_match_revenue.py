"""
Automated Revenue Matching - Scheduled Task
Matches cash revenue after 24 hours and credit revenue after 48 hours
Run this as a scheduled task (cron/celery beat)
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from hospital.models_primecare_accounting import UndepositedFunds, InsuranceReceivableEntry


class Command(BaseCommand):
    help = 'Automatically match revenue entries after hold periods'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be matched without actually matching',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        now = timezone.now()
        
        self.stdout.write('=' * 70)
        self.stdout.write('AUTOMATED REVENUE MATCHING')
        self.stdout.write('=' * 70)
        self.stdout.write()
        
        matched_cash = 0
        matched_credit = 0
        
        # Match cash revenue (24-hour hold)
        self.stdout.write('Matching Cash Revenue (24-hour hold)...')
        cutoff_time = now - timedelta(hours=24)
        
        pending_cash = UndepositedFunds.objects.filter(
            status='pending',
            entry_date__lte=cutoff_time.date(),
            is_deleted=False
        )
        
        self.stdout.write(f'Found {pending_cash.count()} cash entries ready for matching')
        
        for entry in pending_cash:
            if dry_run:
                self.stdout.write(
                    self.style.WARNING(
                        f'  [DRY RUN] Would match: {entry.entry_number} - GHS {entry.total_amount}'
                    )
                )
            else:
                try:
                    # Use system user for automated matching
                    from django.contrib.auth import get_user_model
                    User = get_user_model()
                    system_user = User.objects.filter(is_superuser=True).first()
                    
                    if system_user:
                        entry.match_to_revenue(system_user)
                        matched_cash += 1
                        self.stdout.write(
                            self.style.SUCCESS(
                                f'  ✅ Matched: {entry.entry_number} - GHS {entry.total_amount}'
                            )
                        )
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(
                            f'  ❌ Error matching {entry.entry_number}: {e}'
                        )
                    )
        
        self.stdout.write()
        
        # Match credit revenue (48-hour hold)
        self.stdout.write('Matching Credit Revenue (48-hour hold)...')
        cutoff_time = now - timedelta(hours=48)
        
        pending_credit = InsuranceReceivableEntry.objects.filter(
            status='pending',
            entry_date__lte=cutoff_time.date(),
            is_deleted=False
        )
        
        self.stdout.write(f'Found {pending_credit.count()} credit entries ready for matching')
        
        for entry in pending_credit:
            if dry_run:
                self.stdout.write(
                    self.style.WARNING(
                        f'  [DRY RUN] Would match: {entry.entry_number} - {entry.payer.name} - GHS {entry.total_amount}'
                    )
                )
            else:
                try:
                    from django.contrib.auth import get_user_model
                    User = get_user_model()
                    system_user = User.objects.filter(is_superuser=True).first()
                    
                    if system_user:
                        entry.match_to_revenue(system_user)
                        matched_credit += 1
                        self.stdout.write(
                            self.style.SUCCESS(
                                f'  ✅ Matched: {entry.entry_number} - {entry.payer.name} - GHS {entry.total_amount}'
                            )
                        )
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(
                            f'  ❌ Error matching {entry.entry_number}: {e}'
                        )
                    )
        
        self.stdout.write()
        self.stdout.write('=' * 70)
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN COMPLETE - No changes made'))
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'✅ MATCHING COMPLETE! Matched {matched_cash} cash entries and {matched_credit} credit entries'
                )
            )
        self.stdout.write('=' * 70)














