"""
Management command to reset all financial data, encounters, payments, and revenues
This makes the system fresh for a new accounting period
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from decimal import Decimal

# Import all relevant models
from hospital.models import Encounter, Invoice, InvoiceLine
from hospital.models_accounting import (
    Transaction, PaymentReceipt, PaymentAllocation, AccountsReceivable,
    GeneralLedger, JournalEntry, JournalEntryLine
)
from hospital.models_accounting_advanced import (
    Revenue, RevenueCategory, AdvancedAccountsReceivable, AdvancedGeneralLedger,
    AdvancedJournalEntry, AdvancedJournalEntryLine,
    Expense, ExpenseCategory
)
from hospital.models_revenue_streams import RevenueStream, DepartmentRevenue
from hospital.models_workflow import PaymentRequest, Bill
from hospital.models_ambulance import AmbulanceBilling
from hospital.models_patient_deposits import PatientDeposit
from hospital.models_telemedicine import TelemedicinePayment
from hospital.models_primecare_accounting import InsurancePaymentReceived


class Command(BaseCommand):
    help = 'Reset all encounters, payments, outstanding balances, and revenues to start fresh'

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Confirm that you want to delete all financial data',
        )

    def handle(self, *args, **options):
        if not options['confirm']:
            self.stdout.write(
                self.style.WARNING(
                    '\n*** WARNING: This will DELETE ALL financial data including:\n'
                    '   - All Encounters\n'
                    '   - All Payments and Receipts\n'
                    '   - All Outstanding Balances\n'
                    '   - All Revenues\n'
                    '   - All General Ledger Entries\n'
                    '   - All Journal Entries\n'
                    '   - All Invoice Balances\n'
                    '   - All Accounts Receivable\n'
                    '\n'
                    'This action CANNOT be undone!\n'
                    '\n'
                    'To proceed, run: python manage.py reset_all_financial_data --confirm\n'
                )
            )
            return

        self.stdout.write(self.style.WARNING('\n*** Starting comprehensive financial data reset...\n'))

        try:
            with transaction.atomic():
                # Step 1: Delete all Encounters
                self.stdout.write('Step 1: Clearing all Encounters...')
                encounter_count = Encounter.objects.filter(is_deleted=False).count()
                Encounter.objects.filter(is_deleted=False).update(is_deleted=True)
                self.stdout.write(self.style.SUCCESS(f'   [OK] Deleted {encounter_count} encounters'))

                # Step 2: Delete all Payment Receipts and Transactions
                self.stdout.write('Step 2: Clearing all Payments and Transactions...')
                receipt_count = PaymentReceipt.objects.filter(is_deleted=False).count()
                PaymentReceipt.objects.filter(is_deleted=False).update(is_deleted=True)
                self.stdout.write(self.style.SUCCESS(f'   [OK] Deleted {receipt_count} payment receipts'))

                transaction_count = Transaction.objects.filter(is_deleted=False).count()
                Transaction.objects.filter(is_deleted=False).update(is_deleted=True)
                self.stdout.write(self.style.SUCCESS(f'   [OK] Deleted {transaction_count} transactions'))

                # Step 3: Delete Payment Allocations
                self.stdout.write('Step 3: Clearing Payment Allocations...')
                allocation_count = PaymentAllocation.objects.filter(is_deleted=False).count()
                PaymentAllocation.objects.filter(is_deleted=False).update(is_deleted=True)
                self.stdout.write(self.style.SUCCESS(f'   [OK] Deleted {allocation_count} payment allocations'))

                # Step 4: Reset Invoice Balances and Status
                self.stdout.write('Step 4: Resetting Invoice Balances...')
                invoices = Invoice.objects.filter(is_deleted=False)
                invoice_count = invoices.count()
                for invoice in invoices:
                    invoice.balance = invoice.total_amount
                    if invoice.status != 'draft':
                        invoice.status = 'issued'
                    invoice.save(update_fields=['balance', 'status'])
                self.stdout.write(self.style.SUCCESS(f'   [OK] Reset {invoice_count} invoice balances'))

                # Step 5: Delete Accounts Receivable
                self.stdout.write('Step 5: Clearing Accounts Receivable...')
                ar_count = AccountsReceivable.objects.filter(is_deleted=False).count()
                AccountsReceivable.objects.filter(is_deleted=False).update(is_deleted=True)
                self.stdout.write(self.style.SUCCESS(f'   [OK] Deleted {ar_count} AR entries'))

                advanced_ar_count = AdvancedAccountsReceivable.objects.filter(is_deleted=False).count()
                AdvancedAccountsReceivable.objects.filter(is_deleted=False).update(is_deleted=True)
                self.stdout.write(self.style.SUCCESS(f'   [OK] Deleted {advanced_ar_count} advanced AR entries'))

                # Step 6: Delete all Revenues
                self.stdout.write('Step 6: Clearing all Revenues...')
                revenue_count = Revenue.objects.filter(is_deleted=False).count()
                Revenue.objects.filter(is_deleted=False).update(is_deleted=True)
                self.stdout.write(self.style.SUCCESS(f'   [OK] Deleted {revenue_count} revenue records'))

                dept_revenue_count = DepartmentRevenue.objects.filter(is_deleted=False).count()
                DepartmentRevenue.objects.filter(is_deleted=False).update(is_deleted=True)
                self.stdout.write(self.style.SUCCESS(f'   [OK] Deleted {dept_revenue_count} department revenue records'))

                # Step 7: Delete General Ledger Entries
                self.stdout.write('Step 7: Clearing General Ledger...')
                gl_count = GeneralLedger.objects.filter(is_deleted=False).count()
                GeneralLedger.objects.filter(is_deleted=False).update(is_deleted=True)
                self.stdout.write(self.style.SUCCESS(f'   [OK] Deleted {gl_count} general ledger entries'))

                advanced_gl_count = AdvancedGeneralLedger.objects.filter(is_deleted=False).count()
                AdvancedGeneralLedger.objects.filter(is_deleted=False).update(is_deleted=True)
                self.stdout.write(self.style.SUCCESS(f'   [OK] Deleted {advanced_gl_count} advanced GL entries'))

                # Step 8: Delete Journal Entries
                self.stdout.write('Step 8: Clearing Journal Entries...')
                je_count = JournalEntry.objects.filter(is_deleted=False).count()
                JournalEntry.objects.filter(is_deleted=False).update(is_deleted=True)
                self.stdout.write(self.style.SUCCESS(f'   [OK] Deleted {je_count} journal entries'))

                advanced_je_count = AdvancedJournalEntry.objects.filter(is_deleted=False).count()
                AdvancedJournalEntry.objects.filter(is_deleted=False).update(is_deleted=True)
                self.stdout.write(self.style.SUCCESS(f'   [OK] Deleted {advanced_je_count} advanced journal entries'))

                # Step 9: Delete Journal Entry Lines
                self.stdout.write('Step 9: Clearing Journal Entry Lines...')
                jel_count = JournalEntryLine.objects.filter(is_deleted=False).count()
                JournalEntryLine.objects.filter(is_deleted=False).update(is_deleted=True)
                self.stdout.write(self.style.SUCCESS(f'   [OK] Deleted {jel_count} journal entry lines'))

                advanced_jel_count = AdvancedJournalEntryLine.objects.filter(is_deleted=False).count()
                AdvancedJournalEntryLine.objects.filter(is_deleted=False).update(is_deleted=True)
                self.stdout.write(self.style.SUCCESS(f'   [OK] Deleted {advanced_jel_count} advanced journal entry lines'))

                # Step 10: Delete Payment Requests and Bills
                self.stdout.write('Step 10: Clearing Payment Requests and Bills...')
                pr_count = PaymentRequest.objects.filter(is_deleted=False).count()
                PaymentRequest.objects.filter(is_deleted=False).update(is_deleted=True)
                self.stdout.write(self.style.SUCCESS(f'   [OK] Deleted {pr_count} payment requests'))

                bill_count = Bill.objects.filter(is_deleted=False).count()
                Bill.objects.filter(is_deleted=False).update(is_deleted=True)
                self.stdout.write(self.style.SUCCESS(f'   [OK] Deleted {bill_count} bills'))

                # Step 11: Delete Ambulance Billings
                self.stdout.write('Step 11: Clearing Ambulance Billings...')
                ambulance_count = AmbulanceBilling.objects.filter(is_deleted=False).count()
                AmbulanceBilling.objects.filter(is_deleted=False).update(is_deleted=True)
                self.stdout.write(self.style.SUCCESS(f'   [OK] Deleted {ambulance_count} ambulance billings'))

                # Step 12: Reset Patient Deposits
                self.stdout.write('Step 12: Resetting Patient Deposits...')
                deposits = PatientDeposit.objects.filter(is_deleted=False)
                deposit_count = deposits.count()
                for deposit in deposits:
                    deposit.balance = deposit.amount
                    deposit.save(update_fields=['balance'])
                self.stdout.write(self.style.SUCCESS(f'   [OK] Reset {deposit_count} patient deposits'))

                # Step 13: Delete Telemedicine Payments
                self.stdout.write('Step 13: Clearing Telemedicine Payments...')
                telemedicine_count = TelemedicinePayment.objects.filter(is_deleted=False).count()
                TelemedicinePayment.objects.filter(is_deleted=False).update(is_deleted=True)
                self.stdout.write(self.style.SUCCESS(f'   [OK] Deleted {telemedicine_count} telemedicine payments'))

                # Step 14: Delete Insurance Payments
                self.stdout.write('Step 14: Clearing Insurance Payments...')
                insurance_count = InsurancePaymentReceived.objects.filter(is_deleted=False).count()
                InsurancePaymentReceived.objects.filter(is_deleted=False).update(is_deleted=True)
                self.stdout.write(self.style.SUCCESS(f'   [OK] Deleted {insurance_count} insurance payments'))

                # Step 15: Reset Account Balances (optional - keep account structure but reset balances)
                self.stdout.write('Step 15: Resetting Account Balances in General Ledger...')
                # Account balances are calculated from GL entries, so they will be 0 after GL deletion
                self.stdout.write(self.style.SUCCESS('   [OK] Account balances will be recalculated from remaining GL entries'))

            self.stdout.write(self.style.SUCCESS('\n*** SUCCESS: All financial data has been reset!\n'))
            self.stdout.write(
                self.style.SUCCESS(
                    'The system is now fresh and ready for a new accounting period.\n'
                    'All encounters, payments, outstanding balances, and revenues have been cleared.\n'
                )
            )

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'\n*** ERROR: Failed to reset financial data: {str(e)}\n')
            )
            raise
