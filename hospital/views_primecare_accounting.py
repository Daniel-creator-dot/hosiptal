"""
Primecare Medical Centre - Accounting Views
Implements Record Deposit and Received Payment interfaces
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q, Sum
from django.http import JsonResponse
from datetime import date, timedelta
from decimal import Decimal
from .models_primecare_accounting import (
    UndepositedFunds, InsuranceReceivableEntry, InsurancePaymentReceived
)
from .models_accounting import Account
from .models_accounting_advanced import BankAccount, Journal
from .models import Payer


def is_accountant(user):
    """Check if user is an accountant"""
    return user.groups.filter(name__in=['Accountant', 'Admin', 'Cashier']).exists() or user.is_staff


@login_required
@user_passes_test(is_accountant, login_url='/hms/login/')
def record_deposit(request):
    """
    Record Deposit Interface
    Moves funds from Undeposited Funds to Bank Account
    """
    if request.method == 'POST':
        try:
            deposit_date = request.POST.get('deposit_date')
            bank_account_id = request.POST.get('bank_account')
            deposit_reference = request.POST.get('deposit_reference', '')
            notes = request.POST.get('notes', '')
            
            # Get undeposited funds entries to deposit
            entry_ids = request.POST.getlist('entry_ids')
            
            if not entry_ids:
                messages.error(request, 'Please select at least one undeposited funds entry to deposit.')
                return redirect('primecare:record_deposit')
            
            bank_account = get_object_or_404(BankAccount, id=bank_account_id)
            
            total_amount = Decimal('0.00')
            entries_to_deposit = []
            
            for entry_id in entry_ids:
                entry = get_object_or_404(UndepositedFunds, id=entry_id, status='pending')
                entries_to_deposit.append(entry)
                total_amount += entry.total_amount
            
            # Create journal entry for deposit
            from .models_accounting_advanced import AdvancedJournalEntry, AdvancedJournalEntryLine
            
            journal, _ = Journal.objects.get_or_create(
                code='BANK',
                defaults={'name': 'Bank Journal', 'journal_type': 'bank'}
            )
            
            je = AdvancedJournalEntry.objects.create(
                journal=journal,
                entry_date=deposit_date,
                description=f"Bank deposit - {deposit_reference}",
                reference=deposit_reference,
                created_by=request.user,
                status='draft',
            )
            
            # Get accounts
            undeposited_account, _ = Account.objects.get_or_create(
                account_code='1015',
                defaults={
                    'account_name': 'Undeposited Funds',
                    'account_type': 'asset',
                }
            )
            
            # Debit: Bank Account
            AdvancedJournalEntryLine.objects.create(
                journal_entry=je,
                line_number=1,
                account=bank_account.account,
                description=f"Deposit to {bank_account.account_name}",
                debit_amount=total_amount,
                credit_amount=0,
            )
            
            # Credit: Undeposited Funds
            AdvancedJournalEntryLine.objects.create(
                journal_entry=je,
                line_number=2,
                account=undeposited_account,
                description=f"Undeposited funds deposited to bank",
                debit_amount=0,
                credit_amount=total_amount,
            )
            
            # Update totals and post
            je.total_debit = total_amount
            je.total_credit = total_amount
            je.save()
            je.post(request.user)
            
            # Update undeposited funds entries
            for entry in entries_to_deposit:
                entry.status = 'deposited'
                entry.bank_account = bank_account
                entry.deposit_date = deposit_date
                entry.deposit_reference = deposit_reference
                entry.journal_entry = je
                entry.save()
            
            messages.success(
                request, 
                f'Successfully recorded deposit of GHS {total_amount:,.2f} to {bank_account.account_name}'
            )
            return redirect('primecare:record_deposit')
        
        except Exception as e:
            messages.error(request, f'Error recording deposit: {str(e)}')
            return redirect('primecare:record_deposit')
    
    # GET request - show form
    # Get pending undeposited funds
    pending_funds = UndepositedFunds.objects.filter(
        status='pending',
        is_deleted=False
    ).order_by('-entry_date')
    
    # Get bank accounts
    bank_accounts = BankAccount.objects.filter(is_active=True, is_deleted=False)
    
    # Calculate totals
    total_pending = pending_funds.aggregate(Sum('total_amount'))['total_amount__sum'] or Decimal('0.00')
    
    context = {
        'pending_funds': pending_funds,
        'bank_accounts': bank_accounts,
        'total_pending': total_pending,
        'today': timezone.now().date(),
    }
    
    return render(request, 'hospital/primecare/record_deposit.html', context)


@login_required
@user_passes_test(is_accountant, login_url='/hms/login/')
def received_payment(request):
    """
    Received Payment Interface
    Records payment from insurance companies with rejections and WHT
    """
    if request.method == 'POST':
        try:
            entry_date = request.POST.get('entry_date')
            payer_id = request.POST.get('payer')
            receivable_entry_id = request.POST.get('receivable_entry', '')
            bank_account_id = request.POST.get('bank_account')
            
            total_amount = Decimal(request.POST.get('total_amount', '0'))
            amount_received = Decimal(request.POST.get('amount_received', '0'))
            amount_rejected = Decimal(request.POST.get('amount_rejected', '0'))
            withholding_tax = Decimal(request.POST.get('withholding_tax', '0'))
            withholding_tax_rate = Decimal(request.POST.get('withholding_tax_rate', '0'))
            payment_reference = request.POST.get('payment_reference', '')
            notes = request.POST.get('notes', '')
            
            # Validation
            if amount_received + amount_rejected + withholding_tax != total_amount:
                messages.error(
                    request, 
                    'Amount received + rejected + WHT must equal total amount'
                )
                return redirect('primecare:received_payment')
            
            payer = get_object_or_404(Payer, id=payer_id)
            bank_account = get_object_or_404(BankAccount, id=bank_account_id)
            
            # Get receivable entry if provided
            receivable_entry = None
            if receivable_entry_id:
                receivable_entry = get_object_or_404(
                    InsuranceReceivableEntry, 
                    id=receivable_entry_id,
                    payer=payer
                )
            
            # Create payment received entry
            payment = InsurancePaymentReceived.objects.create(
                entry_date=entry_date,
                payer=payer,
                receivable_entry=receivable_entry,
                total_amount=total_amount,
                amount_received=amount_received,
                amount_rejected=amount_rejected,
                withholding_tax=withholding_tax,
                withholding_tax_rate=withholding_tax_rate,
                bank_account=bank_account,
                payment_reference=payment_reference,
                notes=notes,
                processed_by=request.user,
            )
            
            # Create accounting entries
            payment.create_accounting_entries(request.user)
            
            messages.success(
                request,
                f'Successfully recorded payment of GHS {amount_received:,.2f} from {payer.name}'
            )
            return redirect('primecare:received_payment')
        
        except Exception as e:
            messages.error(request, f'Error recording payment: {str(e)}')
            return redirect('primecare:received_payment')
    
    # GET request - show form
    # Get payers (insurance companies) - include all insurance types
    payers = Payer.objects.filter(
        payer_type__in=['insurance', 'corporate', 'nhis', 'private'],
        is_active=True,
        is_deleted=False
    ).order_by('name')
    
    # Get bank accounts
    bank_accounts = BankAccount.objects.filter(is_active=True, is_deleted=False)
    
    # Get receivable entries
    receivable_entries = InsuranceReceivableEntry.objects.filter(
        status__in=['matched', 'partially_paid'],
        outstanding_amount__gt=0,
        is_deleted=False
    ).select_related('payer').order_by('-entry_date')
    
    context = {
        'payers': payers,
        'bank_accounts': bank_accounts,
        'receivable_entries': receivable_entries,
        'today': timezone.now().date(),
    }
    
    return render(request, 'hospital/primecare/received_payment.html', context)


@login_required
@user_passes_test(is_accountant, login_url='/hms/login/')
def get_receivable_details(request, receivable_id):
    """Get receivable entry details for AJAX"""
    try:
        receivable = get_object_or_404(InsuranceReceivableEntry, id=receivable_id)
        
        return JsonResponse({
            'success': True,
            'total_amount': str(receivable.total_amount),
            'outstanding_amount': str(receivable.outstanding_amount),
            'amount_received': str(receivable.amount_received),
            'amount_rejected': str(receivable.amount_rejected),
            'withholding_tax': str(receivable.withholding_tax),
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })














