"""
Patient Deposit Views
Handles recording deposits, viewing deposit history, and applying deposits to invoices
"""
import uuid

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.cache import cache
from django.db.models import Sum, Q
from django.utils import timezone
from django.core.paginator import Paginator
from django.urls import reverse
from decimal import Decimal
from datetime import datetime

from .models import Patient, Invoice
from .models_patient_deposits import PatientDeposit, DepositApplication
from .models_accounting_advanced import BankAccount
from .decorators import role_required
from .utils_roles import get_user_role


@login_required
@role_required('cashier', 'accountant', 'senior_account_officer', 'receptionist', 'admin')
def record_patient_deposit(request, patient_id=None):
    """
    Record a new patient deposit
    """
    patient = None
    if patient_id:
        patient = get_object_or_404(Patient, pk=patient_id, is_deleted=False)
    
    if request.method == 'POST':
        try:
            patient_id = request.POST.get('patient_id')
            patient = get_object_or_404(Patient, pk=patient_id, is_deleted=False)
            
            deposit_amount = Decimal(request.POST.get('deposit_amount', '0'))
            payment_method = request.POST.get('payment_method', 'cash')
            reference_number = request.POST.get('reference_number', '').strip()
            bank_account_id = request.POST.get('bank_account', '')
            notes = request.POST.get('notes', '').strip()
            
            if deposit_amount <= 0:
                messages.error(request, 'Deposit amount must be greater than zero.')
                return redirect('hospital:record_patient_deposit', patient_id=patient.pk)
            
            bank_account = None
            if bank_account_id:
                bank_account = get_object_or_404(BankAccount, pk=bank_account_id)
            
            # Idempotency: same form posted twice (double-click, back+submit) must not create two deposits
            posted_nonce = (request.POST.get('deposit_form_nonce') or '').strip()
            session_nonce = (request.session.get('patient_deposit_form_nonce') or '').strip()
            if not posted_nonce or posted_nonce != session_nonce:
                messages.warning(
                    request,
                    'This form expired or was already used. Open Record Deposit again to submit.',
                )
                return redirect('hospital:record_patient_deposit', patient_id=patient.pk)
            
            cache_key = f'patient_deposit_once:{posted_nonce}'
            if not cache.add(cache_key, 1, timeout=600):
                messages.info(
                    request,
                    'That deposit was already submitted. Check deposit history or the receipt you printed.',
                )
                return redirect('hospital:patient_deposit_history', patient_id=patient.pk)
            
            try:
                deposit = PatientDeposit.objects.create(
                    patient=patient,
                    deposit_amount=deposit_amount,
                    payment_method=payment_method,
                    reference_number=reference_number,
                    bank_account=bank_account,
                    notes=notes,
                    received_by=request.user,
                    created_by=request.user,
                    deposit_date=timezone.now()
                )
            except Exception:
                cache.delete(cache_key)
                raise
            
            request.session.pop('patient_deposit_form_nonce', None)
            request.session.modified = True
            
            messages.success(
                request, 
                f'Deposit of GHS {deposit_amount:,.2f} recorded successfully. '
                f'Deposit Number: {deposit.deposit_number}'
            )
            return redirect(
                reverse('hospital:patient_deposit_print', kwargs={'deposit_id': deposit.pk}) + '?auto_print=1'
            )
        
        except Exception as e:
            messages.error(request, f'Error recording deposit: {str(e)}')
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error recording deposit: {e}", exc_info=True)
    
    # GET request - show form
    bank_accounts = BankAccount.objects.filter(is_active=True, is_deleted=False).order_by('account_name')
    
    # Get recent patients for quick selection (last 100 patients with encounters)
    recent_patients = Patient.objects.filter(
        is_deleted=False,
        encounters__isnull=False
    ).distinct().select_related('primary_insurance').order_by('-created')[:100]
    
    deposit_form_nonce = uuid.uuid4().hex
    request.session['patient_deposit_form_nonce'] = deposit_form_nonce
    request.session.modified = True
    
    context = {
        'patient': patient,
        'bank_accounts': bank_accounts,
        'recent_patients': recent_patients,
        'deposit_form_nonce': deposit_form_nonce,
        'title': 'Record Patient Deposit',
    }
    
    return render(request, 'hospital/patient_deposits/record_deposit.html', context)


@login_required
@role_required('cashier', 'accountant', 'senior_account_officer', 'receptionist', 'admin')
def patient_deposit_list(request, patient_id=None):
    """
    List all patient deposits, optionally filtered by patient
    """
    deposits = PatientDeposit.objects.filter(is_deleted=False).select_related('patient', 'received_by', 'created_by')
    
    # Filter by patient if provided
    patient = None
    if patient_id:
        patient = get_object_or_404(Patient, pk=patient_id, is_deleted=False)
        deposits = deposits.filter(patient=patient)
    
    # Search
    search_query = request.GET.get('search', '')
    if search_query:
        deposits = deposits.filter(
            Q(deposit_number__icontains=search_query) |
            Q(patient__first_name__icontains=search_query) |
            Q(patient__last_name__icontains=search_query) |
            Q(patient__mrn__icontains=search_query) |
            Q(reference_number__icontains=search_query)
        )
    
    # Filter by status
    status_filter = request.GET.get('status', '')
    if status_filter:
        deposits = deposits.filter(status=status_filter)
    
    # Order by date (newest first)
    deposits = deposits.order_by('-deposit_date', '-deposit_number')
    
    # Pagination
    paginator = Paginator(deposits, 25)
    page = request.GET.get('page')
    deposits_page = paginator.get_page(page)
    
    # Statistics
    total_deposits = deposits.aggregate(
        total_amount=Sum('deposit_amount'),
        total_available=Sum('available_balance'),
        total_used=Sum('used_amount')
    )
    
    context = {
        'deposits': deposits_page,
        'patient': patient,
        'search_query': search_query,
        'status_filter': status_filter,
        'total_deposits': total_deposits,
        'title': 'Patient Deposits',
    }
    
    return render(request, 'hospital/patient_deposits/deposit_list.html', context)


@login_required
@role_required('cashier', 'accountant', 'senior_account_officer', 'receptionist', 'admin')
def patient_deposit_detail(request, deposit_id):
    """
    View deposit details and applications
    Also handles note updates from cashiers
    """
    deposit = get_object_or_404(PatientDeposit, pk=deposit_id, is_deleted=False)
    
    # Handle note update (POST from cashier)
    if request.method == 'POST' and request.POST.get('action') == 'update_notes':
        try:
            from .utils_roles import user_has_cashier_access
            if not user_has_cashier_access(request.user):
                messages.error(request, 'You do not have permission to update notes.')
                return redirect('hospital:patient_deposit_detail', deposit_id=deposit.pk)
            
            new_notes = request.POST.get('notes', '').strip()
            deposit.notes = new_notes
            deposit.save(update_fields=['notes', 'modified'])
            
            messages.success(request, 'Notes updated successfully. You can now print the receipt.')
            
            # Redirect to print page if print flag is set
            if request.POST.get('print_after_update') == '1':
                return redirect('hospital:patient_deposit_print', deposit_id=deposit.pk)
            
            return redirect('hospital:patient_deposit_detail', deposit_id=deposit.pk)
        
        except Exception as e:
            messages.error(request, f'Error updating notes: {str(e)}')
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error updating deposit notes: {e}", exc_info=True)
    
    # Get applications
    applications = deposit.applications.filter(is_deleted=False).select_related('invoice', 'applied_by').order_by('-applied_date')
    
    # Check if user is cashier
    from .utils_roles import user_has_cashier_access
    is_cashier = user_has_cashier_access(request.user)
    
    context = {
        'deposit': deposit,
        'applications': applications,
        'is_cashier': is_cashier,
        'title': f'Deposit {deposit.deposit_number}',
    }
    
    return render(request, 'hospital/patient_deposits/deposit_detail.html', context)


@login_required
@role_required('cashier', 'accountant', 'senior_account_officer', 'admin')
def apply_deposit_manually(request, deposit_id):
    """
    Manually apply a deposit to an invoice
    """
    deposit = get_object_or_404(PatientDeposit, pk=deposit_id, is_deleted=False)
    
    if request.method == 'POST':
        import logging
        from django.core.exceptions import ValidationError
        logger = logging.getLogger(__name__)
        try:
            invoice_id = request.POST.get('invoice_id')
            amount = Decimal(request.POST.get('amount', '0'))
            
            invoice = get_object_or_404(Invoice, pk=invoice_id, is_deleted=False)
            # Refresh invoice and ensure balance is current (may have been paid elsewhere)
            try:
                invoice.update_totals()
            except Exception:
                invoice.refresh_from_db()
            
            if invoice.balance <= 0:
                messages.warning(
                    request,
                    f'Invoice {invoice.invoice_number} has no outstanding balance (GHS 0.00). '
                    'It may have been paid already. Please select another invoice.'
                )
            elif amount <= 0:
                messages.error(request, 'Amount to apply must be greater than zero.')
            elif amount > invoice.balance:
                messages.error(
                    request,
                    f'Amount GHS {amount:,.2f} exceeds this invoice\'s balance (GHS {invoice.balance:,.2f}). '
                    'Enter an amount up to the invoice balance.'
                )
            else:
                # Apply deposit (creates PaymentReceipt inside apply_to_invoice)
                application = deposit.apply_to_invoice(invoice, amount)
                messages.success(
                    request,
                    f'Deposit of GHS {amount:,.2f} applied to Invoice {invoice.invoice_number} successfully.'
                )
                # Issue receipt: redirect to POS receipt print for the receipt just created
                from .models_accounting import PaymentReceipt
                receipt = (
                    PaymentReceipt.objects.filter(
                        invoice=invoice,
                        patient=deposit.patient,
                        payment_method='deposit',
                        amount_paid=amount,
                        notes__icontains=deposit.deposit_number,
                        is_deleted=False,
                    )
                    .order_by('-receipt_date')
                    .first()
                )
                if receipt:
                    pos_url = reverse('hospital:receipt_pos_print', args=[str(receipt.pk)]) + '?auto_print=1'
                    return redirect(pos_url)
                return redirect('hospital:patient_deposit_detail', deposit_id=deposit.pk)
        
        except ValidationError as e:
            messages.error(request, f'Error applying deposit: {list(e.messages) if e.messages else str(e)}')
            logger.warning(f"ValidationError applying deposit: {e}")
        except Exception as e:
            messages.error(request, f'Error applying deposit: {str(e)}')
            logger.error(f"Error applying deposit: {e}", exc_info=True)
    
    # GET request - show form
    # Get patient's unpaid invoices
    invoices = Invoice.objects.filter(
        patient=deposit.patient,
        is_deleted=False,
        status__in=['issued', 'partially_paid', 'overdue'],
        balance__gt=0
    ).order_by('-issued_at')
    
    context = {
        'deposit': deposit,
        'invoices': invoices,
        'title': f'Apply Deposit {deposit.deposit_number}',
    }
    
    return render(request, 'hospital/patient_deposits/apply_deposit.html', context)


@login_required
@role_required('cashier', 'accountant', 'senior_account_officer', 'admin')
def patient_deposit_history(request, patient_id):
    """
    View deposit history for a specific patient.
    Shows deposit balance, outstanding bills (amount after deposit), and
    a button to finally collect payment for outstanding.
    """
    patient = get_object_or_404(Patient, pk=patient_id, is_deleted=False)
    
    deposits = PatientDeposit.objects.filter(
        patient=patient,
        is_deleted=False
    ).select_related('received_by', 'created_by').order_by('-deposit_date')
    
    # Statistics (use patient.deposit_balance for available so it matches display)
    stats_agg = deposits.aggregate(
        total_deposited=Sum('deposit_amount'),
        total_available=Sum('available_balance'),
        total_used=Sum('used_amount')
    )
    stats = {
        'total_deposited': stats_agg['total_deposited'] or Decimal('0.00'),
        'total_available': stats_agg['total_available'] or Decimal('0.00'),
        'total_used': stats_agg['total_used'] or Decimal('0.00'),
        'total_count': deposits.count(),
    }
    
    # Get all applications for this patient
    applications = DepositApplication.objects.filter(
        deposit__patient=patient,
        is_deleted=False
    ).select_related('deposit', 'invoice', 'applied_by').order_by('-applied_date')
    
    # Single source of truth for outstanding (same as /patients/<id>/outstanding/)
    from .services.patient_outstanding_service import get_patient_outstanding
    outstanding_data = get_patient_outstanding(patient)
    deposit_balance = outstanding_data['deposit_balance']
    total_outstanding = outstanding_data['total_outstanding']
    amount_to_collect = outstanding_data['amount_due_after_deposit']
    stats['total_available'] = deposit_balance
    # Build list of outstanding invoices for "collect payment" (cash/self-pay only)
    outstanding_invoices = []
    try:
        from .models import Payer
        cash_payer_ids = list(
            Payer.objects.filter(payer_type__in=('cash', 'self_pay')).values_list('pk', flat=True)
        )
        qs = Invoice.objects.filter(
            patient=patient,
            is_deleted=False,
            balance__gt=0
        ).exclude(status='paid').select_related('payer')
        for inv in qs:
            payer_type = getattr(inv.payer, 'payer_type', None) if inv.payer else None
            if inv.payer_id in cash_payer_ids or payer_type in ('cash', 'self_pay', None):
                try:
                    inv.update_totals()
                except Exception:
                    inv.refresh_from_db()
                if inv.balance and inv.balance > 0:
                    outstanding_invoices.append(inv)
    except Exception:
        pass
    
    context = {
        'patient': patient,
        'deposits': deposits,
        'applications': applications,
        'stats': stats,
        'outstanding_invoices': outstanding_invoices,
        'total_outstanding': total_outstanding,
        'deposit_balance': deposit_balance,
        'amount_to_collect': amount_to_collect,
        'title': f'Deposit History - {patient.full_name}',
    }
    
    return render(request, 'hospital/patient_deposits/patient_history.html', context)


@login_required
@role_required('cashier', 'accountant', 'senior_account_officer', 'admin')
def refund_deposit(request, deposit_id):
    """
    Refund a patient deposit
    """
    deposit = get_object_or_404(PatientDeposit, pk=deposit_id, is_deleted=False)
    
    # Fix legacy: available_balance=0 but used_amount=0 and deposit_amount>0
    if (deposit.available_balance or Decimal('0')) <= 0 and (deposit.used_amount or Decimal('0')) == 0 and (deposit.deposit_amount or Decimal('0')) > 0 and deposit.status == 'active':
        deposit.available_balance = deposit.deposit_amount
        deposit.save(update_fields=['available_balance'])
    
    if deposit.available_balance <= 0:
        messages.error(request, 'This deposit has no available balance to refund.')
        return redirect('hospital:patient_deposit_detail', deposit_id=deposit.pk)
    
    if request.method == 'POST':
        try:
            amount = request.POST.get('amount', '')
            refund_method = request.POST.get('refund_method', 'cash')
            notes = request.POST.get('notes', '').strip()
            
            if amount:
                amount = Decimal(amount)
            else:
                amount = None  # Full refund
            
            # Process refund
            refund_transaction = deposit.refund(
                amount=amount,
                refund_method=refund_method,
                refunded_by=request.user,
                notes=notes
            )
            
            messages.success(
                request,
                f'Refund of GHS {refund_transaction.amount:,.2f} processed successfully. '
                f'Transaction: {refund_transaction.transaction_number}'
            )
            
            return redirect('hospital:patient_deposit_detail', deposit_id=deposit.pk)
        
        except Exception as e:
            messages.error(request, f'Error processing refund: {str(e)}')
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error processing refund: {e}", exc_info=True)
    
    # GET request - show form
    context = {
        'deposit': deposit,
        'title': f'Refund Deposit {deposit.deposit_number}',
    }
    
    return render(request, 'hospital/patient_deposits/refund_deposit.html', context)


@login_required
@role_required('cashier', 'accountant', 'senior_account_officer', 'receptionist', 'admin')
def patient_deposit_print(request, deposit_id):
    """
    Print-friendly deposit receipt view
    Cashiers can print after updating notes for finance review
    """
    deposit = get_object_or_404(PatientDeposit, pk=deposit_id, is_deleted=False)
    
    # Get applications
    applications = deposit.applications.filter(is_deleted=False).select_related('invoice', 'applied_by').order_by('-applied_date')
    
    # Get hospital name from settings
    from django.conf import settings
    hospital_name = getattr(settings, 'HOSPITAL_NAME', 'Hospital Management System')
    
    context = {
        'deposit': deposit,
        'applications': applications,
        'hospital_name': hospital_name,
        'title': f'Deposit Receipt - {deposit.deposit_number}',
    }
    
    return render(request, 'hospital/patient_deposits/deposit_print.html', context)





