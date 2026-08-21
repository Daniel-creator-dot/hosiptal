"""
Patient Deposit System
Allows patients to make deposits before treatment; application to invoices is cashier-driven (Apply deposit).
"""
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from decimal import Decimal
from datetime import datetime
from .models import BaseModel, Patient, Invoice
from .models_accounting import Transaction, PaymentReceipt
from .models_accounting_advanced import AdvancedJournalEntry, Account, BankAccount


class PatientDeposit(BaseModel):
    """
    Patient Deposit - Money paid by patient before treatment
    Deposits are held in a liability account and applied to invoices automatically
    """
    STATUS_CHOICES = [
        ('active', 'Active (Available)'),
        ('fully_used', 'Fully Used'),
        ('refunded', 'Refunded'),
        ('cancelled', 'Cancelled'),
    ]
    
    PAYMENT_METHOD_CHOICES = [
        ('cash', 'Cash'),
        ('mobile_money', 'Mobile Money'),
        ('bank_transfer', 'Bank Transfer'),
        ('cheque', 'Cheque'),
        ('card', 'Card'),
        ('other', 'Other'),
    ]
    
    deposit_number = models.CharField(max_length=50, unique=True, db_index=True)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='deposits')
    deposit_date = models.DateTimeField(default=timezone.now)
    
    # Amount details
    deposit_amount = models.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Total amount deposited"
    )
    available_balance = models.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        default=Decimal('0.00'),
        help_text="Remaining balance available for use"
    )
    used_amount = models.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        default=Decimal('0.00'),
        help_text="Amount already applied to invoices"
    )
    
    # Payment details
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default='cash')
    reference_number = models.CharField(max_length=100, blank=True, help_text="Payment reference/transaction ID")
    bank_account = models.ForeignKey(
        BankAccount, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        help_text="Bank account if payment was via bank transfer"
    )
    
    # Status and tracking
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    notes = models.TextField(blank=True, help_text="Additional notes about the deposit")
    
    # Accounting integration
    transaction = models.ForeignKey(
        Transaction, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='patient_deposits',
        help_text="Accounting transaction for this deposit"
    )
    journal_entry = models.ForeignKey(
        AdvancedJournalEntry, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='patient_deposits',
        help_text="Journal entry for accounting"
    )
    
    # User tracking
    received_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True,
        related_name='deposits_received',
        help_text="Staff member who received the deposit"
    )
    created_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True,
        related_name='deposits_created',
        help_text="User who created this deposit record"
    )
    
    class Meta:
        ordering = ['-deposit_date', '-deposit_number']
        verbose_name = 'Patient Deposit'
        verbose_name_plural = 'Patient Deposits'
        indexes = [
            models.Index(fields=['patient', 'status']),
            models.Index(fields=['deposit_date']),
            models.Index(fields=['deposit_number']),
        ]
    
    def __str__(self):
        return f"Deposit {self.deposit_number} - {self.patient.full_name} - GHS {self.deposit_amount}"
    
    def save(self, *args, **kwargs):
        """Auto-generate deposit number and set initial balance"""
        if not self.deposit_number:
            self.deposit_number = self.generate_deposit_number()
        
        # Set initial available balance if this is a new deposit
        if not self.pk:
            self.available_balance = self.deposit_amount
            self.used_amount = Decimal('0.00')
            if not self.status:
                self.status = 'active'
        else:
            # Fix legacy records: if deposit has amount but available/used are both 0, set available = deposit_amount
            if (self.deposit_amount and self.deposit_amount > 0 and
                    self.available_balance == 0 and self.used_amount == 0 and self.status == 'active'):
                self.available_balance = self.deposit_amount
        
        # Update status based on balance
        if self.available_balance <= 0 and self.used_amount > 0:
            self.status = 'fully_used'
        elif self.status == 'fully_used' and self.available_balance > 0:
            self.status = 'active'
        
        super().save(*args, **kwargs)
    
    @staticmethod
    def generate_deposit_number():
        """Generate unique deposit number: DEP-YYYYMMDD-XXXXX"""
        prefix = "DEP"
        today = datetime.now()
        date_str = today.strftime("%Y%m%d")
        
        # Get last deposit for today
        last_deposit = PatientDeposit.objects.filter(
            deposit_number__startswith=f"{prefix}-{date_str}"
        ).order_by('-deposit_number').first()
        
        if last_deposit and last_deposit.deposit_number:
            try:
                last_num = int(last_deposit.deposit_number.split('-')[-1])
                new_num = last_num + 1
            except (ValueError, IndexError):
                new_num = 1
        else:
            new_num = 1
        
        return f"{prefix}-{date_str}-{new_num:05d}"
    
    def apply_to_invoice(self, invoice, amount=None, create_receipt=True):
        """
        Apply this deposit to an invoice
        
        Args:
            invoice: Invoice object to apply deposit to
            amount: Amount to apply (defaults to available balance or invoice balance, whichever is smaller)
            create_receipt: If True, create a PaymentReceipt for this application. Set False when
                the caller will create a single combined receipt (e.g. "Apply deposit to bill" one-click).
        
        Returns:
            DepositApplication object
        """
        from decimal import Decimal
        from django.core.exceptions import ValidationError
        
        if self.status != 'active':
            raise ValidationError(f"Cannot apply deposit {self.deposit_number}: Status is {self.get_status_display()}")

        if getattr(invoice, 'is_deleted', False) or getattr(invoice, 'status', None) in (
            'cancelled', 'paid', 'written_off'
        ):
            raise ValidationError(
                f"Cannot apply deposit to invoice {getattr(invoice, 'invoice_number', invoice.pk)}: "
                f"invoice is {getattr(invoice, 'status', 'unavailable')}"
            )
        
        # Fix legacy: available_balance=0 but used_amount=0 and deposit_amount>0
        if (self.available_balance or Decimal('0')) <= 0 and (self.used_amount or Decimal('0')) == 0 and (self.deposit_amount or Decimal('0')) > 0:
            self.available_balance = self.deposit_amount
            self.save(update_fields=['available_balance'])
        
        if self.available_balance <= 0:
            raise ValidationError(f"Cannot apply deposit {self.deposit_number}: No available balance")
        
        # Determine amount to apply
        if amount is None:
            amount = min(self.available_balance, invoice.balance)
        else:
            amount = Decimal(str(amount))
        
        if amount <= 0:
            raise ValidationError("Amount to apply must be greater than zero")
        
        if amount > self.available_balance:
            raise ValidationError(
                f"Amount GHS {amount} exceeds available balance GHS {self.available_balance}"
            )
        
        if amount > invoice.balance:
            raise ValidationError(
                f"Amount GHS {amount} exceeds invoice balance GHS {invoice.balance}"
            )
        
        from django.db import transaction as db_transaction

        with db_transaction.atomic():
            # Create deposit application
            application = DepositApplication.objects.create(
                deposit=self,
                invoice=invoice,
                applied_amount=amount,
                applied_by=self.created_by,
                notes=f"Applied from patient deposit {self.deposit_number}"
            )
            
            # Update deposit balance
            self.used_amount += amount
            self.available_balance -= amount
            if self.available_balance <= 0:
                self.status = 'fully_used'
            self.save(update_fields=['used_amount', 'available_balance', 'status'])
            
            # Create one receipt per application only when requested (skip when caller creates one combined receipt)
            if create_receipt:
                existing_receipt = PaymentReceipt.objects.filter(
                    invoice=invoice,
                    patient=invoice.patient,
                    amount_paid=amount,
                    payment_method='deposit',
                    notes__icontains=self.deposit_number,
                    is_deleted=False
                ).first()
                if not existing_receipt:
                    txn = Transaction.objects.create(
                        transaction_type='payment_received',
                        invoice=invoice,
                        patient=invoice.patient,
                        amount=amount,
                        payment_method='deposit',
                        reference_number=self.deposit_number,
                        processed_by=self.received_by,
                        transaction_date=timezone.now(),
                        notes=f'Payment from deposit {self.deposit_number}'
                    )
                    # Tag consultation when deposit settles a consult invoice so cashier
                    # paid-detection and revenue split both see it (GL still posts via DepositApplication).
                    receipt_service_type = 'other'
                    service_details = {'deposit_number': self.deposit_number}
                    try:
                        from hospital.utils_billing import CONSULTATION_LINE_SERVICE_CODES
                        from hospital.services.receipt_revenue_allocation import (
                            build_service_details_for_invoice,
                        )
                        has_consult = invoice.lines.filter(
                            is_deleted=False,
                            waived_at__isnull=True,
                            service_code__code__in=CONSULTATION_LINE_SERVICE_CODES,
                        ).exists()
                        if has_consult:
                            receipt_service_type = 'consultation'
                            service_details = build_service_details_for_invoice(
                                invoice, amount, service_type='consultation'
                            )
                            service_details['deposit_number'] = self.deposit_number
                    except Exception:
                        pass
                    PaymentReceipt.objects.create(
                        transaction_id=txn.pk,
                        invoice=invoice,
                        patient=invoice.patient,
                        amount_paid=amount,
                        payment_method='deposit',
                        received_by=self.received_by,
                        receipt_date=timezone.now(),
                        notes=f'Payment from deposit {self.deposit_number}',
                        service_type=receipt_service_type,
                        service_details=service_details,
                    )
            # Single source of truth: invoice totals/balance from lines + receipts + deposit applications
            invoice.update_totals()
        
        return application
    
    def refund(self, amount=None, refund_method='cash', refunded_by=None, notes=''):
        """
        Withdraw / refund all or part of the unused deposit (cashier withdrawal).

        Creates a refund_issued transaction (unique ref per payout) so cashier session
        cash and cashbook see the outflow. GL peels Customer Deposits → Cash.
        """
        from decimal import Decimal
        import uuid
        from django.db import transaction as db_transaction

        # Fix legacy: available_balance=0 but used_amount=0 and deposit_amount>0
        if (self.available_balance or Decimal('0')) <= 0 and (self.used_amount or Decimal('0')) == 0 and (self.deposit_amount or Decimal('0')) > 0:
            self.available_balance = self.deposit_amount
            self.save(update_fields=['available_balance'])

        if amount is None:
            amount = self.available_balance
        else:
            amount = Decimal(str(amount))

        if amount <= 0:
            raise ValidationError('Refund amount must be greater than zero.')

        if amount > self.available_balance:
            raise ValidationError(
                f"Refund amount GHS {amount} exceeds available balance GHS {self.available_balance}"
            )

        # Unique per payout so partial refunds each get their own txn + GL entry
        refund_ref = f"REFUND-{self.deposit_number}-{uuid.uuid4().hex[:10].upper()}"

        with db_transaction.atomic():
            deposit = PatientDeposit.objects.select_for_update().get(pk=self.pk)
            # Re-check under lock
            avail = deposit.display_available_balance
            if (deposit.available_balance or Decimal('0')) <= 0 and avail > 0:
                deposit.available_balance = avail
            if amount > deposit.available_balance:
                raise ValidationError(
                    f"Refund amount GHS {amount} exceeds available balance GHS {deposit.available_balance}"
                )

            refund_transaction = Transaction.objects.create(
                transaction_type='refund_issued',
                patient=deposit.patient,
                amount=amount,
                payment_method=refund_method or 'cash',
                reference_number=refund_ref,
                processed_by=refunded_by,
                transaction_date=timezone.now(),
                notes=(
                    f"Deposit withdrawal for {deposit.deposit_number}. "
                    f"{(notes or '').strip()}"
                ).strip(),
            )

            deposit.available_balance = (deposit.available_balance or Decimal('0')) - amount
            if deposit.available_balance <= 0:
                deposit.available_balance = Decimal('0.00')
                deposit.status = 'refunded'
            deposit.save(update_fields=['available_balance', 'status'])

            # Keep in-memory instance in sync
            self.available_balance = deposit.available_balance
            self.status = deposit.status

        # Refresh open sessions: deposit intake is on received_by; processor may differ
        try:
            from .models_workflow import CashierSession

            cashier_ids = set()
            if deposit.received_by_id:
                cashier_ids.add(deposit.received_by_id)
            if refunded_by is not None:
                cashier_ids.add(getattr(refunded_by, 'pk', refunded_by))
            for cid in cashier_ids:
                open_session = (
                    CashierSession.objects.filter(
                        cashier_id=cid,
                        status='open',
                        is_deleted=False,
                    )
                    .order_by('-opened_at')
                    .first()
                )
                if open_session:
                    open_session.calculate_totals()
        except Exception:
            pass

        return refund_transaction
    
    @property
    def display_available_balance(self):
        """Available balance for display; fixes legacy records where available_balance=0 but deposit_amount is set."""
        if (self.available_balance or Decimal('0')) > 0:
            return self.available_balance
        if (self.used_amount or Decimal('0')) == 0 and (self.deposit_amount or Decimal('0')) > 0:
            return self.deposit_amount
        return max(Decimal('0'), (self.deposit_amount or Decimal('0')) - (self.used_amount or Decimal('0')))
    
    @property
    def is_fully_used(self):
        """Check if deposit is fully used"""
        return self.available_balance <= 0
    
    @property
    def can_be_applied(self):
        """Check if deposit can be applied to invoices"""
        return self.status == 'active' and (self.available_balance > 0 or (self.used_amount == 0 and self.deposit_amount > 0))


class DepositApplication(BaseModel):
    """
    Tracks how patient deposits are applied to invoices
    """
    deposit = models.ForeignKey(
        PatientDeposit, 
        on_delete=models.CASCADE, 
        related_name='applications'
    )
    invoice = models.ForeignKey(
        Invoice, 
        on_delete=models.CASCADE, 
        related_name='deposit_applications'
    )
    applied_amount = models.DecimalField(
        max_digits=15, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    applied_date = models.DateTimeField(default=timezone.now)
    applied_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True,
        related_name='deposit_applications',
        help_text="User who applied this deposit"
    )
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-applied_date']
        verbose_name = 'Deposit Application'
        verbose_name_plural = 'Deposit Applications'
        indexes = [
            models.Index(fields=['deposit', 'invoice']),
            models.Index(fields=['applied_date']),
        ]
    
    def __str__(self):
        return f"Deposit {self.deposit.deposit_number} → Invoice {self.invoice.invoice_number} - GHS {self.applied_amount}"

