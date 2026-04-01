"""
Professional Payment Synchronization Command
Syncs ALL payments to accounting system with comprehensive reporting
"""
from django.core.management.base import BaseCommand
from django.db import transaction as db_transaction
from django.utils import timezone
from django.db.models import Sum, Count, Q
from decimal import Decimal

from hospital.models_accounting import Transaction, Account, PaymentReceipt
from hospital.models_accounting_advanced import (
    Revenue, RevenueCategory, ReceiptVoucher, AdvancedJournalEntry,
    AdvancedJournalEntryLine, Journal, AdvancedGeneralLedger
)
from hospital.models import Invoice
from hospital.services.accounting_sync_service import AccountingSyncService


class Command(BaseCommand):
    help = 'Sync ALL payments to accounting system (Professional Grade)'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be synced without actually syncing'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed progress'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Re-sync even if already synced'
        )
    
    def handle(self, *args, **options):
        dry_run = options['dry_run']
        verbose = options['verbose']
        force = options['force']
        
        self.stdout.write(self.style.SUCCESS('=' * 80))
        self.stdout.write(self.style.SUCCESS('PROFESSIONAL PAYMENT SYNCHRONIZATION SYSTEM'))
        self.stdout.write(self.style.SUCCESS('=' * 80))
        self.stdout.write('')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be saved'))
            self.stdout.write('')
        
        # Step 1: Analyze current state
        self.stdout.write('Analyzing current payment synchronization status...')
        analysis = self._analyze_sync_status()
        self._display_analysis(analysis)
        
        # Step 2: Ensure accounts exist
        self.stdout.write('')
        self.stdout.write('Ensuring accounting accounts exist...')
        accounts = self._ensure_accounts()
        self.stdout.write(self.style.SUCCESS(f'✓ Accounts ready'))
        
        # Step 3: Sync payments
        if not dry_run:
            self.stdout.write('')
            self.stdout.write('Synchronizing payments to accounting...')
            stats = self._sync_all_payments(accounts, force, verbose)
            self._display_sync_results(stats)
        else:
            self.stdout.write('')
            self.stdout.write(self.style.WARNING('DRY RUN - Would sync payments (see analysis above)'))
        
        # Step 4: Final status
        self.stdout.write('')
        self.stdout.write('Final synchronization status:')
        final_analysis = self._analyze_sync_status()
        self._display_analysis(final_analysis)
        
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=' * 80))
        self.stdout.write(self.style.SUCCESS('SYNCHRONIZATION COMPLETE'))
        self.stdout.write(self.style.SUCCESS('=' * 80))
        self.stdout.write('')
        self.stdout.write('View synchronized data at:')
        self.stdout.write('  - Revenue: /admin/hospital/revenue/')
        self.stdout.write('  - Receipt Vouchers: /admin/hospital/receiptvoucher/')
        self.stdout.write('  - Journal Entries: /admin/hospital/advancedjournalentry/')
        self.stdout.write('  - General Ledger: /admin/hospital/advancedgeneralledger/')
    
    def _analyze_sync_status(self):
        """Analyze current sync status"""
        # Get all payment receipts (primary payment model)
        all_receipts = PaymentReceipt.objects.filter(is_deleted=False)
        
        # Also get transactions as backup
        all_transactions = Transaction.objects.filter(
            transaction_type='payment_received',
            is_deleted=False
        )
        
        # Get paid invoices (another source of payments)
        from hospital.models import Invoice
        paid_invoices = Invoice.objects.filter(
            status__in=['paid', 'partially_paid'],
            is_deleted=False
        )
        
        # Combine all sources
        total_payments = all_receipts.count() + all_transactions.count()
        
        receipts_amount = all_receipts.aggregate(
            total=Sum('amount_paid')
        )['total'] or Decimal('0.00')
        
        transactions_amount = all_transactions.aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0.00')
        
        # Calculate paid amount from invoices
        invoices_paid_amount = Decimal('0.00')
        for invoice in paid_invoices:
            invoices_paid_amount += invoice.total_amount - invoice.balance
        
        total_amount = receipts_amount + transactions_amount + invoices_paid_amount
        
        # Check which are synced (have revenue entries)
        synced_refs = set(
            Revenue.objects.exclude(reference__isnull=True)
            .exclude(reference='')
            .values_list('reference', flat=True)
        )
        
        # Also check by invoice number
        synced_invoice_refs = set(
            Revenue.objects.exclude(invoice__isnull=True)
            .values_list('invoice__invoice_number', flat=True)
        )
        
        # Check receipts
        synced_receipts = all_receipts.filter(receipt_number__in=synced_refs)
        synced_receipt_count = synced_receipts.count()
        synced_receipt_amount = synced_receipts.aggregate(
            total=Sum('amount_paid')
        )['total'] or Decimal('0.00')
        
        # Check transactions
        synced_transactions = all_transactions.filter(transaction_number__in=synced_refs)
        synced_trans_count = synced_transactions.count()
        synced_trans_amount = synced_transactions.aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0.00')
        
        # Check invoices
        synced_invoices = paid_invoices.filter(invoice_number__in=synced_invoice_refs)
        synced_invoice_count = synced_invoices.count()
        synced_invoice_amount = Decimal('0.00')
        for inv in synced_invoices:
            synced_invoice_amount += inv.total_amount - inv.balance
        
        synced_count = synced_receipt_count + synced_trans_count + synced_invoice_count
        synced_amount = synced_receipt_amount + synced_trans_amount + synced_invoice_amount
        
        unsynced_count = total_payments - synced_count
        unsynced_amount = total_amount - synced_amount
        
        # Count by payment method
        by_method = {}
        for receipt in all_receipts:
            method = receipt.payment_method or 'cash'
            if method not in by_method:
                by_method[method] = {'total': 0, 'amount': Decimal('0.00'), 'synced': 0, 'synced_amount': Decimal('0.00')}
            by_method[method]['total'] += 1
            by_method[method]['amount'] += receipt.amount_paid
            if receipt.receipt_number in synced_refs:
                by_method[method]['synced'] += 1
                by_method[method]['synced_amount'] += receipt.amount_paid
        
        for trans in all_transactions:
            method = trans.payment_method or 'cash'
            if method not in by_method:
                by_method[method] = {'total': 0, 'amount': Decimal('0.00'), 'synced': 0, 'synced_amount': Decimal('0.00')}
            by_method[method]['total'] += 1
            by_method[method]['amount'] += trans.amount
            if trans.transaction_number in synced_refs:
                by_method[method]['synced'] += 1
                by_method[method]['synced_amount'] += trans.amount
        
        return {
            'total_payments': total_payments,
            'total_amount': total_amount,
            'synced_count': synced_count,
            'synced_amount': synced_amount,
            'unsynced_count': unsynced_count,
            'unsynced_amount': unsynced_amount,
            'sync_percentage': (synced_count / total_payments * 100) if total_payments > 0 else 0,
            'by_method': by_method,
            'synced_refs': synced_refs,
            'receipts': all_receipts,
            'transactions': all_transactions,
            'paid_invoices': paid_invoices,
            'synced_invoice_refs': synced_invoice_refs
        }
    
    def _display_analysis(self, analysis):
        """Display analysis results"""
        self.stdout.write('')
        self.stdout.write('  Total Payments: {}'.format(analysis['total_payments']))
        self.stdout.write('  Total Amount: GHS {:.2f}'.format(analysis['total_amount']))
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('  Synced: {} payments (GHS {:.2f})'.format(
            analysis['synced_count'], analysis['synced_amount']
        )))
        self.stdout.write(self.style.WARNING('  Unsynced: {} payments (GHS {:.2f})'.format(
            analysis['unsynced_count'], analysis['unsynced_amount']
        )))
        self.stdout.write('  Sync Rate: {:.1f}%'.format(analysis['sync_percentage']))
        
        if analysis['by_method']:
            self.stdout.write('')
            self.stdout.write('  By Payment Method:')
            for method, data in analysis['by_method'].items():
                sync_rate = (data['synced'] / data['total'] * 100) if data['total'] > 0 else 0
                self.stdout.write('    {}: {} total (GHS {:.2f}), {} synced ({:.1f}%)'.format(
                    method.upper(), data['total'], data['amount'],
                    data['synced'], sync_rate
                ))
    
    def _ensure_accounts(self):
        """Ensure required accounts exist"""
        accounts = {}
        
        # Cash account
        accounts['cash'], _ = Account.objects.get_or_create(
            account_code='1000',
            defaults={
                'account_name': 'Cash on Hand',
                'account_type': 'asset',
                'is_active': True
            }
        )
        
        # Revenue account
        accounts['revenue'], _ = Account.objects.get_or_create(
            account_code='4000',
            defaults={
                'account_name': 'Patient Services Revenue',
                'account_type': 'revenue',
                'is_active': True
            }
        )
        
        # Revenue category
        accounts['revenue_category'], _ = RevenueCategory.objects.get_or_create(
            code='REV-PATIENT',
            defaults={
                'name': 'Patient Services',
                'account': accounts['revenue']
            }
        )
        
        # Receipt Journal
        accounts['journal'], _ = Journal.objects.get_or_create(
            code='RJ',
            defaults={
                'name': 'Receipt Journal',
                'journal_type': 'receipt'
            }
        )
        
        return accounts
    
    @db_transaction.atomic
    def _sync_all_payments(self, accounts, force, verbose):
        """Sync all payments to accounting"""
        stats = {
            'synced': 0,
            'skipped': 0,
            'errors': 0,
            'total_amount': Decimal('0.00'),
            'errors_list': []
        }
        
        # Get already synced references
        synced_refs = set(
            Revenue.objects.exclude(reference__isnull=True)
            .exclude(reference='')
            .values_list('reference', flat=True)
        )
        
        # Sync PaymentReceipts first (primary payment model)
        all_receipts = PaymentReceipt.objects.filter(
            is_deleted=False
        ).select_related('patient', 'invoice', 'received_by', 'transaction').order_by('receipt_date')
        
        if not force:
            receipts_to_sync = all_receipts.exclude(receipt_number__in=synced_refs)
        else:
            receipts_to_sync = all_receipts
        
        # Also sync Transactions (backup)
        all_transactions = Transaction.objects.filter(
            transaction_type='payment_received',
            is_deleted=False
        ).select_related('patient', 'invoice', 'processed_by').order_by('transaction_date')
        
        if not force:
            transactions_to_sync = all_transactions.exclude(transaction_number__in=synced_refs)
        else:
            transactions_to_sync = all_transactions
        
        total_to_sync = receipts_to_sync.count() + transactions_to_sync.count()
        
        if total_to_sync == 0:
            self.stdout.write('  ✓ All payments already synced!')
            return stats
        
        self.stdout.write('  Syncing {} payments ({} receipts + {} transactions)...'.format(
            total_to_sync, receipts_to_sync.count(), transactions_to_sync.count()
        ))
        
        # Sync receipts
        for idx, receipt in enumerate(receipts_to_sync, 1):
            try:
                if not force and receipt.receipt_number in synced_refs:
                    stats['skipped'] += 1
                    continue
                
                self._sync_single_receipt(receipt, accounts)
                
                stats['synced'] += 1
                stats['total_amount'] += receipt.amount_paid
                
                if verbose and idx % 10 == 0:
                    self.stdout.write('    Progress: {}/{} payments synced...'.format(idx, total_to_sync))
            
            except Exception as e:
                stats['errors'] += 1
                error_msg = 'Receipt {}: {}'.format(receipt.receipt_number, str(e))
                stats['errors_list'].append(error_msg)
                if verbose:
                    self.stdout.write(self.style.ERROR('    {}'.format(error_msg)))
        
        # Sync transactions
        for idx, transaction in enumerate(transactions_to_sync, receipts_to_sync.count() + 1):
            try:
                if not force and transaction.transaction_number in synced_refs:
                    stats['skipped'] += 1
                    continue
                
                self._sync_single_transaction(transaction, accounts)
                
                stats['synced'] += 1
                stats['total_amount'] += transaction.amount
                
                if verbose and idx % 10 == 0:
                    self.stdout.write('    Progress: {}/{} payments synced...'.format(idx, total_to_sync))
            
            except Exception as e:
                stats['errors'] += 1
                error_msg = 'Transaction {}: {}'.format(transaction.transaction_number, str(e))
                stats['errors_list'].append(error_msg)
                if verbose:
                    self.stdout.write(self.style.ERROR('    {}'.format(error_msg)))
        
        # Also sync from paid invoices (if no receipts/transactions exist)
        if total_to_sync == 0:
            from hospital.models import Invoice
            paid_invoices = Invoice.objects.filter(
                status__in=['paid', 'partially_paid'],
                is_deleted=False
            ).select_related('patient')
            
            synced_invoice_refs = set(
                Revenue.objects.exclude(invoice__isnull=True)
                .values_list('invoice__invoice_number', flat=True)
            )
            
            if not force:
                invoices_to_sync = paid_invoices.exclude(invoice_number__in=synced_invoice_refs)
            else:
                invoices_to_sync = paid_invoices
            
            invoice_count = invoices_to_sync.count()
            if invoice_count > 0:
                self.stdout.write('  Found {} paid invoices to sync...'.format(invoice_count))
                
                for idx, invoice in enumerate(invoices_to_sync, 1):
                    try:
                        if not force and invoice.invoice_number in synced_invoice_refs:
                            stats['skipped'] += 1
                            continue
                        
                        # Calculate paid amount
                        paid_amount = invoice.total_amount - invoice.balance
                        if paid_amount > 0:
                            self._sync_single_invoice(invoice, paid_amount, accounts)
                            stats['synced'] += 1
                            stats['total_amount'] += paid_amount
                            
                            if verbose and idx % 10 == 0:
                                self.stdout.write('    Progress: {}/{} invoices synced...'.format(idx, invoice_count))
                    
                    except Exception as e:
                        stats['errors'] += 1
                        error_msg = 'Invoice {}: {}'.format(invoice.invoice_number, str(e))
                        stats['errors_list'].append(error_msg)
                        if verbose:
                            self.stdout.write(self.style.ERROR('    {}'.format(error_msg)))
        
        return stats
    
    def _sync_single_payment(self, payment, accounts):
        """Sync a single payment to accounting"""
        # Get payment date
        payment_date = payment.transaction_date
        if hasattr(payment_date, 'date'):
            payment_date = payment_date.date()
        
        # Create Revenue entry
        revenue = Revenue.objects.create(
            revenue_date=payment_date,
            category=accounts['revenue_category'],
            description='Payment: {} - {}'.format(
                payment.patient.full_name if payment.patient else 'Patient',
                payment.transaction_number
            ),
            amount=payment.amount,
            patient=payment.patient,
            invoice=payment.invoice,
            payment_method=payment.payment_method or 'cash',
            reference=payment.transaction_number,
            recorded_by=payment.processed_by,
        )
        
        # Create Receipt Voucher
        receipt_voucher = ReceiptVoucher.objects.create(
            receipt_date=payment_date,
            received_from=payment.patient.full_name if payment.patient else 'Patient',
            patient=payment.patient,
            amount=payment.amount,
            payment_method=payment.payment_method or 'cash',
            description=revenue.description,
            reference=payment.transaction_number,
            status='issued',
            revenue_account=accounts['revenue'],
            cash_account=accounts['cash'],
            invoice=payment.invoice,
            received_by=payment.processed_by,
        )
        
        # Create Journal Entry
        journal_entry = AdvancedJournalEntry.objects.create(
            journal=accounts['journal'],
            entry_date=payment_date,
            description=revenue.description,
            reference_number=payment.transaction_number,
            status='posted',
            posted_by=payment.processed_by,
        )
        
        # Create Journal Entry Lines
        # Debit: Cash
        AdvancedJournalEntryLine.objects.create(
            journal_entry=journal_entry,
            account=accounts['cash'],
            description='Payment received',
            debit_amount=payment.amount,
            credit_amount=Decimal('0.00'),
        )
        
        # Credit: Revenue
        AdvancedJournalEntryLine.objects.create(
            journal_entry=journal_entry,
            account=accounts['revenue'],
            description='Revenue from patient services',
            debit_amount=Decimal('0.00'),
            credit_amount=payment.amount,
        )
        
        # Post to General Ledger
        # Debit entry
        AdvancedGeneralLedger.objects.create(
            account=accounts['cash'],
            transaction_date=payment_date,
            description=revenue.description,
            reference_number=payment.transaction_number,
            debit_amount=payment.amount,
            credit_amount=Decimal('0.00'),
            balance=self._calculate_balance(accounts['cash'], payment.amount, True),
        )
        
        # Credit entry
        AdvancedGeneralLedger.objects.create(
            account=accounts['revenue'],
            transaction_date=payment_date,
            description=revenue.description,
            reference_number=payment.transaction_number,
            debit_amount=Decimal('0.00'),
            credit_amount=payment.amount,
            balance=self._calculate_balance(accounts['revenue'], payment.amount, False),
        )
    
    def _sync_single_receipt(self, receipt, accounts):
        """Sync a single payment receipt to accounting"""
        # Get payment date
        payment_date = receipt.receipt_date
        if hasattr(payment_date, 'date'):
            payment_date = payment_date.date()
        
        # Check if already synced
        if Revenue.objects.filter(reference=receipt.receipt_number).exists():
            return
        
        # Create Revenue entry
        revenue = Revenue.objects.create(
            revenue_date=payment_date,
            category=accounts['revenue_category'],
            description='Payment: {} - {}'.format(
                receipt.patient.full_name if receipt.patient else 'Patient',
                receipt.receipt_number
            ),
            amount=receipt.amount_paid,
            patient=receipt.patient,
            invoice=receipt.invoice,
            payment_method=receipt.payment_method or 'cash',
            reference=receipt.receipt_number,
            recorded_by=receipt.received_by,
        )
        
        # Create Receipt Voucher if doesn't exist
        if not ReceiptVoucher.objects.filter(reference=receipt.receipt_number).exists():
            ReceiptVoucher.objects.create(
                receipt_date=payment_date,
                received_from=receipt.patient.full_name if receipt.patient else 'Patient',
                patient=receipt.patient,
                amount=receipt.amount_paid,
                payment_method=receipt.payment_method or 'cash',
                description=revenue.description,
                reference=receipt.receipt_number,
                status='issued',
                revenue_account=accounts['revenue'],
                cash_account=accounts['cash'],
                invoice=receipt.invoice,
                received_by=receipt.received_by,
            )
        
        # Create Journal Entry if doesn't exist
        if not AdvancedJournalEntry.objects.filter(reference_number=receipt.receipt_number).exists():
            journal_entry = AdvancedJournalEntry.objects.create(
                journal=accounts['journal'],
                entry_date=payment_date,
                description=revenue.description,
                reference_number=receipt.receipt_number,
                status='draft',
                posted_by=receipt.received_by,
            )
            
            # Create Journal Entry Lines
            AdvancedJournalEntryLine.objects.create(
                journal_entry=journal_entry,
                line_number=1,
                account=accounts['cash'],
                description='Payment received',
                debit_amount=receipt.amount_paid,
                credit_amount=Decimal('0.00'),
            )
            
            AdvancedJournalEntryLine.objects.create(
                journal_entry=journal_entry,
                line_number=2,
                account=accounts['revenue'],
                description='Revenue from patient services',
                debit_amount=Decimal('0.00'),
                credit_amount=receipt.amount_paid,
            )
            
            # Post journal entry
            journal_entry.post(user=receipt.received_by)
    
    def _sync_single_transaction(self, transaction, accounts):
        """Sync a single transaction to accounting"""
        # Get payment date
        payment_date = transaction.transaction_date
        if hasattr(payment_date, 'date'):
            payment_date = payment_date.date()
        
        # Check if already synced
        if Revenue.objects.filter(reference=transaction.transaction_number).exists():
            return
        
        # Create Revenue entry
        revenue = Revenue.objects.create(
            revenue_date=payment_date,
            category=accounts['revenue_category'],
            description='Payment: {} - {}'.format(
                transaction.patient.full_name if transaction.patient else 'Patient',
                transaction.transaction_number
            ),
            amount=transaction.amount,
            patient=transaction.patient,
            invoice=transaction.invoice,
            payment_method=transaction.payment_method or 'cash',
            reference=transaction.transaction_number,
            recorded_by=transaction.processed_by,
        )
        
        # Create Receipt Voucher if doesn't exist
        if not ReceiptVoucher.objects.filter(reference=transaction.transaction_number).exists():
            ReceiptVoucher.objects.create(
                receipt_date=payment_date,
                received_from=transaction.patient.full_name if transaction.patient else 'Patient',
                patient=transaction.patient,
                amount=transaction.amount,
                payment_method=transaction.payment_method or 'cash',
                description=revenue.description,
                reference=transaction.transaction_number,
                status='issued',
                revenue_account=accounts['revenue'],
                cash_account=accounts['cash'],
                invoice=transaction.invoice,
                received_by=transaction.processed_by,
            )
        
        # Create Journal Entry if doesn't exist
        if not AdvancedJournalEntry.objects.filter(reference_number=transaction.transaction_number).exists():
            journal_entry = AdvancedJournalEntry.objects.create(
                journal=accounts['journal'],
                entry_date=payment_date,
                description=revenue.description,
                reference_number=transaction.transaction_number,
                status='draft',
                posted_by=transaction.processed_by,
            )
            
            # Create Journal Entry Lines
            AdvancedJournalEntryLine.objects.create(
                journal_entry=journal_entry,
                line_number=1,
                account=accounts['cash'],
                description='Payment received',
                debit_amount=transaction.amount,
                credit_amount=Decimal('0.00'),
            )
            
            AdvancedJournalEntryLine.objects.create(
                journal_entry=journal_entry,
                line_number=2,
                account=accounts['revenue'],
                description='Revenue from patient services',
                debit_amount=Decimal('0.00'),
                credit_amount=transaction.amount,
            )
            
            # Post journal entry
            journal_entry.post(user=transaction.processed_by)
    
    def _sync_single_invoice(self, invoice, paid_amount, accounts):
        """Sync a single paid invoice to accounting"""
        # Get invoice date
        invoice_date = invoice.issued_at
        if hasattr(invoice_date, 'date'):
            invoice_date = invoice_date.date()
        elif hasattr(invoice_date, 'date'):
            invoice_date = invoice_date
        else:
            invoice_date = timezone.now().date()
        
        # Check if already synced
        if Revenue.objects.filter(invoice=invoice).exists():
            return
        
        # Determine service type from invoice lines
        service_type = 'general'
        if invoice.lines.exists():
            first_line = invoice.lines.first()
            if first_line.service_code:
                service_code = first_line.service_code
                if hasattr(service_code, 'category'):
                    cat = service_code.category.lower()
                    if 'lab' in cat or 'test' in cat:
                        service_type = 'lab'
                    elif 'pharmacy' in cat or 'drug' in cat or 'medication' in cat:
                        service_type = 'pharmacy'
                    elif 'imaging' in cat or 'xray' in cat or 'scan' in cat:
                        service_type = 'imaging'
                    elif 'consultation' in cat or 'consult' in cat:
                        service_type = 'consultation'
        
        # Create Revenue entry
        revenue = Revenue.objects.create(
            revenue_date=invoice_date,
            category=accounts['revenue_category'],
            description='Payment for Invoice {} - {}'.format(
                invoice.invoice_number,
                invoice.patient.full_name if invoice.patient else 'Patient'
            ),
            amount=paid_amount,
            patient=invoice.patient,
            invoice=invoice,
            payment_method='cash',  # Default, can be updated if payment method is tracked
            reference=invoice.invoice_number,
            recorded_by=invoice.created_by,
        )
        
        # Create Receipt Voucher if doesn't exist
        if not ReceiptVoucher.objects.filter(reference=invoice.invoice_number).exists():
            ReceiptVoucher.objects.create(
                receipt_date=invoice_date,
                received_from=invoice.patient.full_name if invoice.patient else 'Patient',
                patient=invoice.patient,
                amount=paid_amount,
                payment_method='cash',
                description=revenue.description,
                reference=invoice.invoice_number,
                status='issued',
                revenue_account=accounts['revenue'],
                cash_account=accounts['cash'],
                invoice=invoice,
                received_by=invoice.created_by,
            )
        
        # Create Journal Entry if doesn't exist
        if not AdvancedJournalEntry.objects.filter(reference_number=invoice.invoice_number).exists():
            journal_entry = AdvancedJournalEntry.objects.create(
                journal=accounts['journal'],
                entry_date=invoice_date,
                description=revenue.description,
                reference_number=invoice.invoice_number,
                status='draft',
                posted_by=invoice.created_by,
            )
            
            # Create Journal Entry Lines
            AdvancedJournalEntryLine.objects.create(
                journal_entry=journal_entry,
                line_number=1,
                account=accounts['cash'],
                description='Payment received',
                debit_amount=paid_amount,
                credit_amount=Decimal('0.00'),
            )
            
            AdvancedJournalEntryLine.objects.create(
                journal_entry=journal_entry,
                line_number=2,
                account=accounts['revenue'],
                description='Revenue from patient services',
                debit_amount=Decimal('0.00'),
                credit_amount=paid_amount,
            )
            
            # Post journal entry
            journal_entry.post(user=invoice.created_by)
    
    def _calculate_balance(self, account, amount, is_debit):
        """Calculate account balance"""
        # Get current balance from last GL entry
        last_entry = AdvancedGeneralLedger.objects.filter(
            account=account,
            is_voided=False
        ).order_by('-transaction_date', '-id').first()
        
        if not last_entry:
            # First entry
            if account.account_type in ['asset', 'expense']:
                return amount if is_debit else -amount
            else:  # liability, equity, revenue
                return -amount if is_debit else amount
        
        current_balance = last_entry.balance
        
        # Calculate new balance
        if account.account_type in ['asset', 'expense']:
            if is_debit:
                return current_balance + amount
            else:
                return current_balance - amount
        else:  # liability, equity, revenue
            if is_debit:
                return current_balance - amount
            else:
                return current_balance + amount
    
    def _display_sync_results(self, stats):
        """Display sync results"""
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=' * 80))
        self.stdout.write(self.style.SUCCESS('SYNC RESULTS'))
        self.stdout.write(self.style.SUCCESS('=' * 80))
        self.stdout.write('  Payments synced: {}'.format(stats['synced']))
        self.stdout.write('  Total amount: GHS {:.2f}'.format(stats['total_amount']))
        self.stdout.write('  Skipped (already synced): {}'.format(stats['skipped']))
        self.stdout.write('  Errors: {}'.format(stats['errors']))
        
        if stats['errors_list'] and len(stats['errors_list']) <= 10:
            self.stdout.write('')
            self.stdout.write('  Errors:')
            for error in stats['errors_list']:
                self.stdout.write(self.style.ERROR('    {}'.format(error)))

