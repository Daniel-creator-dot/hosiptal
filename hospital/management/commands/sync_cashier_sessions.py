"""
Management command to recalculate cashier session totals
Fixes discrepancies between sessions and accounting
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from hospital.models_workflow import CashierSession
from hospital.models_accounting import Transaction
from decimal import Decimal


class Command(BaseCommand):
    help = 'Recalculate all cashier session totals to sync with transactions'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS('🔄 Recalculating cashier session totals...'))
        
        # Get all sessions (open and closed)
        sessions = CashierSession.objects.filter(is_deleted=False)
        
        fixed_count = 0
        for session in sessions:
            old_total = session.total_payments
            old_transactions = session.total_transactions
            
            # Recalculate totals
            session.calculate_totals()
            
            # Check if values changed
            if old_total != session.total_payments or old_transactions != session.total_transactions:
                self.stdout.write(
                    self.style.WARNING(
                        f'  ✓ Fixed Session {session.session_number}: '
                        f'Payments: {old_total} → {session.total_payments}, '
                        f'Transactions: {old_transactions} → {session.total_transactions}'
                    )
                )
                fixed_count += 1
            else:
                self.stdout.write(f'  - Session {session.session_number}: Already correct')
        
        self.stdout.write(self.style.SUCCESS(f'\n✅ Recalculation complete!'))
        self.stdout.write(self.style.SUCCESS(f'   Fixed: {fixed_count} session(s)'))
        self.stdout.write(self.style.SUCCESS(f'   Total: {sessions.count()} session(s) processed'))
























