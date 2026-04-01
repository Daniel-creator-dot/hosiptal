"""
💰 AUTOMATIC ACCOUNTING SYNCHRONIZATION SERVICE
Every payment automatically creates accounting entries
Real-time financial data, complete audit trail
"""
from django.db import transaction
from django.utils import timezone
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


class AccountingSyncService:
    """
    Automatically sync payments with accounting system
    Creates debit/credit entries for every transaction
    """
    
    # Account codes (customize based on your Chart of Accounts)
    ACCOUNT_CODES = {
        'cash': '1010',  # Cash on Hand
        'card': '1020',  # Card Receipts
        'mobile_money': '1030',  # Mobile Money
        'bank_transfer': '1040',  # Bank Transfer
        'revenue_lab': '4010',  # Lab Revenue
        'revenue_pharmacy': '4020',  # Pharmacy Revenue
        'revenue_imaging': '4030',  # Imaging Revenue
        'revenue_consultation': '4040',  # Consultation Revenue
        'revenue_procedure': '4050',  # Procedure Revenue
        'revenue_admission': '4060',  # Admission/Bed Revenue
        'accounts_receivable': '1200',  # A/R
        'unearned_revenue': '2010',  # Unearned Revenue
    }
    
    @staticmethod
    def sync_payment_to_accounting(payment_receipt, service_type='general'):
        """
        Automatically create accounting entries for payment
        
        Args:
            payment_receipt: PaymentReceipt object
            service_type: 'lab', 'pharmacy', 'imaging', 'consultation', 'procedure'
        
        Returns:
            dict with accounting entry details
        """
        try:
            with transaction.atomic():
                # 1. Get accounts
                debit_account = AccountingSyncService._get_payment_account(
                    payment_receipt.payment_method
                )
                credit_account = AccountingSyncService._get_revenue_account(
                    service_type
                )
                
                if not debit_account or not credit_account:
                    # Create default accounts if not exist
                    debit_account = AccountingSyncService._ensure_default_accounts(
                        payment_receipt.payment_method
                    )
                    credit_account = AccountingSyncService._ensure_revenue_account(
                        service_type
                    )
                
                # 2. Create journal entry
                journal_entry = AccountingSyncService._create_journal_entry(
                    payment_receipt=payment_receipt,
                    debit_account=debit_account,
                    credit_account=credit_account,
                    amount=payment_receipt.amount_paid,
                    description=f"Payment for {service_type} - Receipt {payment_receipt.receipt_number}"
                )
                
                # 3. Update accounts receivable if applicable
                if payment_receipt.invoice:
                    AccountingSyncService._update_accounts_receivable(
                        payment_receipt.invoice,
                        payment_receipt.amount_paid
                    )
                
                logger.info(
                    f"✅ Accounting sync complete for receipt {payment_receipt.receipt_number}"
                )
                
                return {
                    'success': True,
                    'journal_entry': journal_entry,
                    'debit_account': debit_account.account_code,
                    'credit_account': credit_account.account_code,
                    'amount': payment_receipt.amount_paid,
                    'message': 'Accounting entries created successfully'
                }
                
        except Exception as e:
            logger.error(f"❌ Accounting sync error: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'message': f'Accounting sync failed: {str(e)}'
            }
    
    @staticmethod
    def _get_payment_account(payment_method):
        """Get the account based on payment method"""
        from hospital.models_accounting import Account
        
        account_code_map = {
            'cash': AccountingSyncService.ACCOUNT_CODES['cash'],
            'card': AccountingSyncService.ACCOUNT_CODES['card'],
            'mobile_money': AccountingSyncService.ACCOUNT_CODES['mobile_money'],
            'bank_transfer': AccountingSyncService.ACCOUNT_CODES['bank_transfer'],
        }
        
        account_code = account_code_map.get(payment_method, AccountingSyncService.ACCOUNT_CODES['cash'])
        
        try:
            return Account.objects.get(account_code=account_code, is_deleted=False)
        except Account.DoesNotExist:
            return None
    
    @staticmethod
    def _get_revenue_account(service_type):
        """Get the revenue account based on service type"""
        from hospital.models_accounting import Account
        
        account_code_map = {
            'lab': AccountingSyncService.ACCOUNT_CODES['revenue_lab'],
            'lab_test': AccountingSyncService.ACCOUNT_CODES['revenue_lab'],
            'pharmacy': AccountingSyncService.ACCOUNT_CODES['revenue_pharmacy'],
            'pharmacy_prescription': AccountingSyncService.ACCOUNT_CODES['revenue_pharmacy'],
            'imaging': AccountingSyncService.ACCOUNT_CODES['revenue_imaging'],
            'imaging_study': AccountingSyncService.ACCOUNT_CODES['revenue_imaging'],
            'consultation': AccountingSyncService.ACCOUNT_CODES['revenue_consultation'],
            'procedure': AccountingSyncService.ACCOUNT_CODES['revenue_procedure'],
            'admission': AccountingSyncService.ACCOUNT_CODES['revenue_admission'],
            'bed': AccountingSyncService.ACCOUNT_CODES['revenue_admission'],
            'combined': '4000',  # General Revenue for combined payments (individual services sync separately)
            'general': '4000',  # General Revenue
        }
        
        account_code = account_code_map.get(
            service_type,
            '4000'  # Default to General Revenue (4000)
        )
        
        try:
            return Account.objects.get(account_code=account_code, is_deleted=False)
        except Account.DoesNotExist:
            return None
    
    @staticmethod
    def _ensure_default_accounts(payment_method):
        """Create default payment account if not exists"""
        from hospital.models_accounting import Account
        
        account_map = {
            'cash': ('1010', 'Cash on Hand', 'asset'),
            'card': ('1020', 'Card Receipts', 'asset'),
            'mobile_money': ('1030', 'Mobile Money', 'asset'),
            'bank_transfer': ('1040', 'Bank Transfer', 'asset'),
        }
        
        code, name, acc_type = account_map.get(payment_method, ('1010', 'Cash on Hand', 'asset'))
        
        account, created = Account.objects.get_or_create(
            account_code=code,
            defaults={
                'account_name': name,
                'account_type': acc_type,
                'is_active': True
            }
        )
        
        if created:
            logger.info(f"✅ Created account: {code} - {name}")
        
        return account
    
    @staticmethod
    def _ensure_revenue_account(service_type):
        """Create default revenue account if not exists"""
        from hospital.models_accounting import Account
        
        account_map = {
            'lab': ('4010', 'Laboratory Revenue', 'revenue'),
            'lab_test': ('4010', 'Laboratory Revenue', 'revenue'),
            'pharmacy': ('4020', 'Pharmacy Revenue', 'revenue'),
            'pharmacy_prescription': ('4020', 'Pharmacy Revenue', 'revenue'),
            'imaging': ('4030', 'Imaging Revenue', 'revenue'),
            'imaging_study': ('4030', 'Imaging Revenue', 'revenue'),
            'consultation': ('4040', 'Consultation Revenue', 'revenue'),
            'procedure': ('4050', 'Procedure Revenue', 'revenue'),
            'admission': ('4060', 'Admission Revenue', 'revenue'),
            'bed': ('4060', 'Admission Revenue', 'revenue'),
            'combined': ('4000', 'General Revenue', 'revenue'),  # Combined payments
            'general': ('4000', 'General Revenue', 'revenue'),
        }
        
        code, name, acc_type = account_map.get(
            service_type,
            ('4000', 'General Revenue', 'revenue')  # Default to General Revenue
        )
        
        account, created = Account.objects.get_or_create(
            account_code=code,
            defaults={
                'account_name': name,
                'account_type': acc_type,
                'is_active': True
            }
        )
        
        if created:
            logger.info(f"✅ Created account: {code} - {name}")
        
        return account
    
    @staticmethod
    def _create_journal_entry(payment_receipt, debit_account, credit_account, amount, description):
        """Create journal entry with debit and credit + POST TO GENERAL LEDGER"""
        from hospital.models_accounting import JournalEntry, JournalEntryLine, GeneralLedger
        
        # Create journal entry
        journal_entry = JournalEntry.objects.create(
            entry_date=payment_receipt.receipt_date.date() if hasattr(payment_receipt.receipt_date, 'date') else payment_receipt.receipt_date,
            entry_type='payment',
            reference_number=payment_receipt.receipt_number,
            ref=payment_receipt.receipt_number,  # Also populate ref field
            description=description,
            entered_by=payment_receipt.received_by,
            posted_by=payment_receipt.received_by,
            status='posted',
            is_posted=True
        )
        
        # Debit line (increase asset - cash/card/etc)
        JournalEntryLine.objects.create(
            journal_entry=journal_entry,
            account=debit_account,
            debit_amount=amount,
            credit_amount=Decimal('0.00'),
            description=f"Debit {debit_account.account_name}"
        )
        
        # Credit line (increase revenue)
        JournalEntryLine.objects.create(
            journal_entry=journal_entry,
            account=credit_account,
            debit_amount=Decimal('0.00'),
            credit_amount=amount,
            description=f"Credit {credit_account.account_name}"
        )
        
        # 🔥 POST TO GENERAL LEDGER (THIS IS THE KEY!)
        # Check for existing entries to prevent duplicates
        transaction_date = payment_receipt.receipt_date.date() if hasattr(payment_receipt.receipt_date, 'date') else payment_receipt.receipt_date
        
        # Check if debit entry already exists
        existing_debit = GeneralLedger.objects.filter(
            account=debit_account,
            reference_number=payment_receipt.receipt_number,
            reference_type='payment',
            reference_id=str(payment_receipt.pk),
            debit_amount=amount,
            is_deleted=False
        ).first()
        
        # Check if credit entry already exists
        existing_credit = GeneralLedger.objects.filter(
            account=credit_account,
            reference_number=payment_receipt.receipt_number,
            reference_type='payment',
            reference_id=str(payment_receipt.pk),
            credit_amount=amount,
            is_deleted=False
        ).first()
        
        if existing_debit or existing_credit:
            logger.warning(
                f"⚠️ Duplicate GL entries detected for receipt {payment_receipt.receipt_number}. "
                f"Skipping creation to prevent duplicates."
            )
            # Return existing journal entry if found
            existing_journal = JournalEntry.objects.filter(
                reference_number=payment_receipt.receipt_number
            ).first()
            if existing_journal:
                return existing_journal
        
        # Debit entry to General Ledger
        GeneralLedger.objects.create(
            account=debit_account,
            transaction_date=transaction_date,
            description=description,
            reference_number=payment_receipt.receipt_number,
            reference_type='payment',
            reference_id=str(payment_receipt.pk),
            debit_amount=amount,
            credit_amount=Decimal('0.00'),
            balance=AccountingSyncService._calculate_account_balance(debit_account, amount, is_debit=True),
            entered_by=payment_receipt.received_by
        )
        
        # Credit entry to General Ledger
        GeneralLedger.objects.create(
            account=credit_account,
            transaction_date=transaction_date,
            description=description,
            reference_number=payment_receipt.receipt_number,
            reference_type='payment',
            reference_id=str(payment_receipt.pk),
            debit_amount=Decimal('0.00'),
            credit_amount=amount,
            balance=AccountingSyncService._calculate_account_balance(credit_account, amount, is_debit=False),
            entered_by=payment_receipt.received_by
        )
        
        logger.info(
            f"✅ Journal entry created & POSTED TO GL: DR {debit_account.account_code} / "
            f"CR {credit_account.account_code} - GHS {amount}"
        )
        
        return journal_entry
    
    @staticmethod
    def _update_accounts_receivable(invoice, payment_amount):
        """Update A/R when payment received"""
        from hospital.models_accounting import Account, JournalEntry, JournalEntryLine
        
        try:
            # Get A/R account
            ar_account = Account.objects.get(
                account_code=AccountingSyncService.ACCOUNT_CODES['accounts_receivable'],
                is_deleted=False
            )
            
            # If this payment reduces A/R balance
            if invoice.balance > 0:
                # Create A/R adjustment entry
                journal_entry = JournalEntry.objects.create(
                    entry_date=timezone.now().date(),
                    entry_type='adjustment',
                    reference_number=f"AR-{invoice.invoice_number}",
                    ref=f"AR-{invoice.invoice_number}",
                    description=f"A/R reduction for invoice {invoice.invoice_number}",
                    status='posted',
                    is_posted=True
                )
                
                # Debit: (already done in main entry)
                # Credit: Accounts Receivable (decrease A/R)
                JournalEntryLine.objects.create(
                    journal_entry=journal_entry,
                    account=ar_account,
                    debit_amount=Decimal('0.00'),
                    credit_amount=payment_amount,
                    description="Reduce A/R"
                )
                
                logger.info(f"✅ A/R updated for invoice {invoice.invoice_number}")
                
        except Account.DoesNotExist:
            logger.warning("A/R account not found, skipping A/R update")
        except Exception as e:
            logger.error(f"Error updating A/R: {str(e)}")
    
    @staticmethod
    def _calculate_account_balance(account, amount, is_debit=True):
        """Calculate running balance for an account"""
        from hospital.models_accounting import GeneralLedger
        from django.db.models import Sum
        
        # Get current balance from latest entry
        latest_entry = GeneralLedger.objects.filter(
            account=account,
            is_deleted=False
        ).order_by('-transaction_date', '-created').first()
        
        current_balance = latest_entry.balance if latest_entry else Decimal('0.00')
        
        # Calculate new balance based on account type
        if account.account_type in ['asset', 'expense']:
            # Debit increases, Credit decreases
            new_balance = current_balance + amount if is_debit else current_balance - amount
        else:
            # liability, equity, revenue: Credit increases, Debit decreases
            new_balance = current_balance - amount if is_debit else current_balance + amount
        
        return new_balance
    
    @staticmethod
    def get_daily_revenue_summary(date=None):
        """Get revenue summary for a specific date"""
        if not date:
            date = timezone.now().date()
        
        from hospital.models_accounting import PaymentReceipt
        from django.db.models import Sum, Count
        
        receipts = PaymentReceipt.objects.filter(
            receipt_date__date=date,
            is_deleted=False
        )
        
        summary = {
            'date': date,
            'total_receipts': receipts.count(),
            'total_revenue': receipts.aggregate(Sum('amount_paid'))['amount_paid__sum'] or Decimal('0.00'),
            'by_payment_method': {},
            'by_service': {}
        }
        
        # By payment method
        for method in ['cash', 'card', 'mobile_money', 'bank_transfer']:
            amount = receipts.filter(payment_method=method).aggregate(Sum('amount_paid'))['amount_paid__sum']
            summary['by_payment_method'][method] = amount or Decimal('0.00')
        
        return summary


# Export
__all__ = ['AccountingSyncService']

