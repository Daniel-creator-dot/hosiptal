"""
Accounting Management Views - Complete HMS Interface for All Accounting Features
Replaces Django admin access with beautiful HMS interfaces
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q, Sum, Count
from django.utils import timezone
from django.core.paginator import Paginator
from django.db import transaction
from django import forms
from decimal import Decimal
from datetime import date, timedelta

from .models_accounting import Account, Patient, Invoice
from .models_accounting_advanced import (
    AdvancedAccountsReceivable, AccountsPayable,
    AdvancedJournalEntry, AdvancedJournalEntryLine,
    Revenue, RevenueCategory, Expense, ExpenseCategory,
    ReceiptVoucher, Deposit, InitialRevaluation,
    WithholdingReceivable, BankAccount, BankTransaction,
    AdvancedGeneralLedger, Journal, FiscalYear, AccountingPeriod
)
from .decorators import role_required
from .utils_roles import get_user_role


# ==================== ACCOUNTS RECEIVABLE ====================

@login_required
@role_required('accountant', 'senior_account_officer')
def ar_list(request):
    """List all accounts receivable"""
    ar_list = AdvancedAccountsReceivable.objects.filter(is_deleted=False).select_related(
        'patient', 'invoice'
    ).order_by('-due_date')
    
    # Filters
    status_filter = request.GET.get('status', '')
    if status_filter == 'overdue':
        ar_list = ar_list.filter(is_overdue=True)
    elif status_filter == 'current':
        ar_list = ar_list.filter(is_overdue=False)
    
    aging_filter = request.GET.get('aging', '')
    if aging_filter:
        ar_list = ar_list.filter(aging_bucket=aging_filter)
    
    paginator = Paginator(ar_list, 50)
    page = request.GET.get('page')
    ar_page = paginator.get_page(page)
    
    # Summary
    total_ar = ar_list.aggregate(total=Sum('balance_due'))['total'] or Decimal('0.00')
    overdue_ar = ar_list.filter(is_overdue=True).aggregate(total=Sum('balance_due'))['total'] or Decimal('0.00')
    
    context = {
        'ar_list': ar_page,
        'total_ar': total_ar,
        'overdue_ar': overdue_ar,
        'status_filter': status_filter,
        'aging_filter': aging_filter,
    }
    
    return render(request, 'hospital/accountant/ar_list.html', context)


@login_required
@role_required('accountant', 'senior_account_officer')
def ar_create(request):
    """Create new accounts receivable entry"""
    if request.method == 'POST':
        try:
            with transaction.atomic():
                patient_id = request.POST.get('patient')
                invoice_id = request.POST.get('invoice')
                invoice_amount = Decimal(request.POST.get('invoice_amount', '0'))
                due_date = request.POST.get('due_date')
                
                if not patient_id or not invoice_amount or not due_date:
                    messages.error(request, 'Please fill in all required fields')
                    return redirect('hospital:ar_create')
                
                patient = get_object_or_404(Patient, id=patient_id, is_deleted=False)
                invoice = None
                if invoice_id:
                    invoice = get_object_or_404(Invoice, id=invoice_id, is_deleted=False)
                
                # Create AR entry
                ar = AdvancedAccountsReceivable.objects.create(
                    patient=patient,
                    invoice=invoice,
                    invoice_amount=invoice_amount,
                    amount_paid=Decimal('0.00'),
                    balance_due=invoice_amount,
                    due_date=due_date,
                )
                
                messages.success(request, f'Accounts Receivable entry created: {ar.invoice.invoice_number if invoice else "Manual Entry"}')
                return redirect('hospital:ar_detail', ar_id=ar.id)
        except Exception as e:
            messages.error(request, f'Error creating AR entry: {str(e)}')
    
    # Get patients and invoices for dropdowns
    patients = Patient.objects.filter(is_deleted=False).order_by('first_name', 'last_name')[:100]
    invoices = Invoice.objects.filter(is_deleted=False, status='issued').order_by('-created')[:100]
    
    context = {
        'patients': patients,
        'invoices': invoices,
    }
    
    return render(request, 'hospital/accountant/ar_create.html', context)


@login_required
@role_required('accountant', 'senior_account_officer')
def ar_edit(request, ar_id):
    """Edit accounts receivable entry"""
    ar = get_object_or_404(AdvancedAccountsReceivable, id=ar_id, is_deleted=False)
    
    if request.method == 'POST':
        try:
            ar.invoice_amount = Decimal(request.POST.get('invoice_amount', '0'))
            ar.amount_paid = Decimal(request.POST.get('amount_paid', '0'))
            ar.due_date = request.POST.get('due_date')
            ar.save()
            
            messages.success(request, 'Accounts Receivable updated successfully')
            return redirect('hospital:ar_detail', ar_id=ar.id)
        except Exception as e:
            messages.error(request, f'Error updating AR: {str(e)}')
    
    context = {
        'ar': ar,
    }
    
    return render(request, 'hospital/accountant/ar_edit.html', context)


@login_required
@role_required('accountant', 'senior_account_officer')
def ar_detail(request, ar_id):
    """View accounts receivable detail"""
    ar = get_object_or_404(AdvancedAccountsReceivable, id=ar_id, is_deleted=False)
    
    context = {
        'ar': ar,
    }
    
    return render(request, 'hospital/accountant/ar_detail.html', context)


# ==================== ACCOUNTS PAYABLE ====================

@login_required
@role_required('accountant', 'senior_account_officer')
def ap_list(request):
    """List all accounts payable"""
    # Optimize query - no need for select_related since AccountsPayable has no FKs in list view
    ap_queryset = AccountsPayable.objects.filter(is_deleted=False).order_by('-due_date')
    
    # Search: vendor, bill number, vendor invoice, description
    search_q = (request.GET.get('q') or '').strip()
    if search_q:
        ap_queryset = ap_queryset.filter(
            Q(vendor_name__icontains=search_q)
            | Q(bill_number__icontains=search_q)
            | Q(vendor_invoice__icontains=search_q)
            | Q(description__icontains=search_q)
        )
    
    # Filters
    status_filter = request.GET.get('status', '')
    if status_filter == 'overdue':
        ap_queryset = ap_queryset.filter(is_overdue=True)
    elif status_filter == 'current':
        ap_queryset = ap_queryset.filter(is_overdue=False)
    
    # Get summary totals BEFORE pagination (more efficient)
    total_ap = ap_queryset.aggregate(total=Sum('balance_due'))['total'] or Decimal('0.00')
    overdue_ap = ap_queryset.filter(is_overdue=True).aggregate(total=Sum('balance_due'))['total'] or Decimal('0.00')
    
    # Paginate after getting totals
    paginator = Paginator(ap_queryset, 50)
    page = request.GET.get('page')
    ap_page = paginator.get_page(page)
    
    context = {
        'ap_list': ap_page,
        'total_ap': total_ap,
        'overdue_ap': overdue_ap,
        'status_filter': status_filter,
        'search_q': search_q,
    }
    
    return render(request, 'hospital/accountant/ap_list.html', context)


@login_required
@role_required('accountant', 'senior_account_officer')
def ap_create(request):
    """Create new accounts payable entry"""
    if request.method == 'POST':
        try:
            with transaction.atomic():
                vendor_name = request.POST.get('vendor_name', '').strip()
                vendor_invoice = request.POST.get('vendor_invoice', '').strip()
                bill_date = request.POST.get('bill_date')
                due_date = request.POST.get('due_date')
                amount = Decimal(request.POST.get('amount', '0'))
                description = request.POST.get('description', '').strip()
                supply_type = request.POST.get('supply_type', 'goods')
                
                if not vendor_name or not amount or not bill_date or not due_date:
                    messages.error(request, 'Please fill in all required fields')
                    return redirect('hospital:ap_create')
                
                # Create AP entry
                ap = AccountsPayable.objects.create(
                    vendor_name=vendor_name,
                    vendor_invoice=vendor_invoice,
                    bill_date=bill_date,
                    due_date=due_date,
                    amount=amount,
                    amount_paid=Decimal('0.00'),
                    balance_due=amount,
                    description=description,
                    supply_type=supply_type,
                )
                
                messages.success(request, f'Accounts Payable entry created: {ap.bill_number}')
                return redirect('hospital:ap_detail', ap_id=ap.id)
        except Exception as e:
            messages.error(request, f'Error creating AP entry: {str(e)}')
    
    context = {}
    return render(request, 'hospital/accountant/ap_create.html', context)


@login_required
@role_required('accountant', 'senior_account_officer')
def ap_edit(request, ap_id):
    """Edit accounts payable entry"""
    from datetime import datetime
    from django.utils import timezone
    
    ap = get_object_or_404(AccountsPayable, id=ap_id, is_deleted=False)
    
    if request.method == 'POST':
        try:
            # Check if this is an "add amount" operation (when goods are brought in)
            add_amount = request.POST.get('add_amount', '').strip()
            add_description = request.POST.get('add_description', '').strip()
            
            if add_amount:
                # Add new amount to existing AP
                try:
                    # Convert to Decimal first (Decimal is imported at top of file)
                    new_amount = Decimal(str(add_amount))
                    if new_amount > 0:
                        # Try to use the method, fallback to manual if it doesn't work
                        try:
                            # Try using the method first
                            if hasattr(ap, 'add_amount') and callable(getattr(ap, 'add_amount', None)):
                                ap.add_amount(new_amount, add_description or 'Additional goods received')
                                messages.success(
                                    request, 
                                    f'Added GHS {new_amount:,.2f} to AP. New balance: GHS {ap.balance_due:,.2f}'
                                )
                            else:
                                # Method doesn't exist - use fallback
                                raise AttributeError('add_amount method not available')
                        except (AttributeError, TypeError) as method_error:
                            # Fallback: manually add amount
                            import logging
                            logger = logging.getLogger(__name__)
                            logger.warning(f'add_amount method not available, using fallback: {method_error}')
                            
                            ap.amount += new_amount
                            ap.balance_due = ap.amount - ap.amount_paid
                            if add_description:
                                if ap.description:
                                    ap.description += f"\n[Added: {timezone.now().strftime('%Y-%m-%d')}] {add_description} - GHS {new_amount:,.2f}"
                                else:
                                    ap.description = f"[Added: {timezone.now().strftime('%Y-%m-%d')}] {add_description} - GHS {new_amount:,.2f}"
                            ap.save()
                            messages.success(
                                request, 
                                f'Added GHS {new_amount:,.2f} to AP. New balance: GHS {ap.balance_due:,.2f}'
                            )
                        return redirect('hospital:ap_detail', ap_id=ap.id)
                    else:
                        messages.error(request, 'Amount to add must be greater than zero')
                        return redirect('hospital:ap_edit', ap_id=ap.id)
                except (ValueError, TypeError) as e:
                    messages.error(request, f'Invalid amount: {str(e)}')
                    return redirect('hospital:ap_edit', ap_id=ap.id)
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f'Error updating AP: {e}', exc_info=True)
                    messages.error(request, f'Error updating AP: {str(e)}')
                    return redirect('hospital:ap_edit', ap_id=ap.id)
            
            # Regular edit operation
            ap.vendor_name = request.POST.get('vendor_name', '').strip()
            ap.vendor_invoice = request.POST.get('vendor_invoice', '').strip()
            
            # Convert date strings to date objects - ALWAYS set dates
            bill_date_str = request.POST.get('bill_date', '').strip()
            if bill_date_str:
                try:
                    ap.bill_date = datetime.strptime(bill_date_str, '%Y-%m-%d').date()
                except (ValueError, TypeError) as e:
                    messages.error(request, f'Invalid bill date format: {str(e)}')
                    return redirect('hospital:ap_edit', ap_id=ap.id)
            else:
                # If empty, keep existing date or use today
                if not ap.bill_date:
                    ap.bill_date = timezone.now().date()
            
            due_date_str = request.POST.get('due_date', '').strip()
            if due_date_str:
                try:
                    ap.due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date()
                except (ValueError, TypeError) as e:
                    messages.error(request, f'Invalid due date format: {str(e)}')
                    return redirect('hospital:ap_edit', ap_id=ap.id)
            else:
                # If empty, use bill_date + 30 days or keep existing
                if not ap.due_date:
                    if ap.bill_date:
                        if isinstance(ap.bill_date, str):
                            try:
                                bill_date_obj = datetime.strptime(ap.bill_date, '%Y-%m-%d').date()
                            except:
                                bill_date_obj = timezone.now().date()
                        else:
                            bill_date_obj = ap.bill_date
                        ap.due_date = bill_date_obj + timedelta(days=30)
                    else:
                        ap.due_date = timezone.now().date() + timedelta(days=30)
            
            # CRITICAL: Ensure dates are DEFINITELY date objects before saving
            # Convert multiple times to be absolutely sure
            if isinstance(ap.bill_date, str):
                try:
                    ap.bill_date = datetime.strptime(ap.bill_date, '%Y-%m-%d').date()
                except:
                    ap.bill_date = timezone.now().date()
            
            # Double-check bill_date
            if not isinstance(ap.bill_date, date):
                ap.bill_date = timezone.now().date()
            
            if isinstance(ap.due_date, str):
                try:
                    ap.due_date = datetime.strptime(ap.due_date, '%Y-%m-%d').date()
                except:
                    ap.due_date = ap.bill_date + timedelta(days=30) if isinstance(ap.bill_date, date) else timezone.now().date() + timedelta(days=30)
            
            # Double-check due_date
            if not isinstance(ap.due_date, date):
                ap.due_date = ap.bill_date + timedelta(days=30) if isinstance(ap.bill_date, date) else timezone.now().date() + timedelta(days=30)
            
            # Update amount (this will auto-calculate balance_due in save method)
            amount_str = request.POST.get('amount', '0').strip()
            try:
                ap.amount = Decimal(amount_str)
            except (ValueError, TypeError):
                messages.error(request, 'Invalid amount')
                return redirect('hospital:ap_edit', ap_id=ap.id)
            
            ap.description = request.POST.get('description', '').strip()
            ap.supply_type = request.POST.get('supply_type', 'goods')
            
            # Final verification: ensure dates are date objects one more time
            if not isinstance(ap.bill_date, date):
                ap.bill_date = timezone.now().date()
            if not isinstance(ap.due_date, date):
                ap.due_date = ap.bill_date + timedelta(days=30)
            
            # Save will auto-calculate balance_due and overdue status
            # Don't use update_fields - let save() method handle everything
            ap.save()
            
            messages.success(request, 'Accounts Payable updated successfully')
            return redirect('hospital:ap_detail', ap_id=ap.id)
        except Exception as e:
            messages.error(request, f'Error updating AP: {str(e)}')
            import traceback
            traceback.print_exc()
    
    context = {
        'ap': ap,
    }
    
    return render(request, 'hospital/accountant/ap_edit.html', context)


@login_required
@role_required('accountant', 'senior_account_officer')
def ap_detail(request, ap_id):
    """View accounts payable detail"""
    from datetime import date as date_type
    import logging
    
    logger = logging.getLogger(__name__)
    
    try:
        ap = get_object_or_404(AccountsPayable, id=ap_id, is_deleted=False)
        
        # Ensure dates are date objects for template rendering
        # This prevents template errors if dates are strings
        try:
            if isinstance(ap.bill_date, str):
                ap.bill_date = datetime.strptime(ap.bill_date, '%Y-%m-%d').date()
            elif not isinstance(ap.bill_date, date_type):
                # If it's not a string or date, try to convert
                ap.bill_date = timezone.now().date()
        except Exception as e:
            logger.error(f"Error converting bill_date: {e}")
            ap.bill_date = timezone.now().date()
        
        try:
            if isinstance(ap.due_date, str):
                ap.due_date = datetime.strptime(ap.due_date, '%Y-%m-%d').date()
            elif not isinstance(ap.due_date, date_type):
                # Default to bill_date + 30 days
                if isinstance(ap.bill_date, date_type):
                    ap.due_date = ap.bill_date + timedelta(days=30)
                else:
                    ap.due_date = timezone.now().date() + timedelta(days=30)
        except Exception as e:
            logger.error(f"Error converting due_date: {e}")
            ap.due_date = ap.bill_date + timedelta(days=30) if isinstance(ap.bill_date, date_type) else timezone.now().date() + timedelta(days=30)
        
        context = {
            'ap': ap,
        }
        
        return render(request, 'hospital/accountant/ap_detail.html', context)
        
    except Exception as e:
        logger.error(f"Error in ap_detail view: {e}", exc_info=True)
        messages.error(request, f'Error loading AP details: {str(e)}')
        return redirect('hospital:ap_list')


# ==================== JOURNAL ENTRIES ====================

@login_required
@role_required('accountant', 'senior_account_officer')
def journal_entry_list(request):
    """List all journal entries"""
    entries = AdvancedJournalEntry.objects.filter(is_deleted=False).select_related(
        'journal', 'created_by', 'posted_by'
    ).prefetch_related('lines').order_by('-entry_date', '-entry_number')
    
    # Filters
    status_filter = request.GET.get('status', '')
    if status_filter:
        entries = entries.filter(status=status_filter)
    
    journal_filter = request.GET.get('journal', '')
    if journal_filter:
        entries = entries.filter(journal_id=journal_filter)
    
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    if date_from:
        entries = entries.filter(entry_date__gte=date_from)
    if date_to:
        entries = entries.filter(entry_date__lte=date_to)
    
    paginator = Paginator(entries, 50)
    page = request.GET.get('page')
    entries_page = paginator.get_page(page)
    
    # Totals for current page (and for full filter)
    page_total_debit = sum(e.total_debit for e in entries_page.object_list)
    page_total_credit = sum(e.total_credit for e in entries_page.object_list)
    filter_total_debit = entries.aggregate(s=Sum('total_debit'))['s'] or 0
    filter_total_credit = entries.aggregate(s=Sum('total_credit'))['s'] or 0
    
    # Get journals for filter
    journals = Journal.objects.filter(is_active=True).order_by('code')
    
    context = {
        'entries': entries_page,
        'journals': journals,
        'status_filter': status_filter,
        'journal_filter': journal_filter,
        'date_from': date_from,
        'date_to': date_to,
        'page_total_debit': page_total_debit,
        'page_total_credit': page_total_credit,
        'filter_total_debit': filter_total_debit,
        'filter_total_credit': filter_total_credit,
    }
    
    return render(request, 'hospital/accountant/journal_entry_list.html', context)


@login_required
@role_required('accountant', 'senior_account_officer')
def journal_entry_create(request):
    """Create new journal entry with lines"""
    if request.method == 'POST':
        try:
            with transaction.atomic():
                journal_id = request.POST.get('journal')
                entry_date = request.POST.get('entry_date')
                description = request.POST.get('description', '').strip()
                reference = request.POST.get('reference', '').strip()
                
                if not journal_id or not entry_date:
                    messages.error(request, 'Please fill in all required fields')
                    return redirect('hospital:journal_entry_create')
                
                journal = get_object_or_404(Journal, id=journal_id, is_deleted=False)
                
                # Create journal entry
                je = AdvancedJournalEntry.objects.create(
                    journal=journal,
                    entry_date=entry_date,
                    description=description,
                    reference=reference,
                    created_by=request.user,
                    status='draft',
                )
                
                # Process journal entry lines
                line_count = int(request.POST.get('line_count', '0'))
                total_debit = Decimal('0.00')
                total_credit = Decimal('0.00')
                
                for i in range(1, line_count + 1):
                    account_id = request.POST.get(f'line_{i}_account')
                    debit = Decimal(request.POST.get(f'line_{i}_debit', '0') or '0')
                    credit = Decimal(request.POST.get(f'line_{i}_credit', '0') or '0')
                    line_description = request.POST.get(f'line_{i}_description', '').strip()
                    
                    if account_id and (debit > 0 or credit > 0):
                        account = get_object_or_404(Account, id=account_id, is_deleted=False)
                        
                        AdvancedJournalEntryLine.objects.create(
                            journal_entry=je,
                            line_number=i,
                            account=account,
                            description=line_description or description,
                            debit_amount=debit,
                            credit_amount=credit,
                        )
                        
                        total_debit += debit
                        total_credit += credit
                
                # Update totals
                je.total_debit = total_debit
                je.total_credit = total_credit
                je.save()
                
                messages.success(request, f'Journal Entry {je.entry_number} created successfully')
                return redirect('hospital:journal_entry_detail', entry_id=je.id)
        except Exception as e:
            messages.error(request, f'Error creating journal entry: {str(e)}')
    
    # Get journals and accounts for dropdowns
    journals = Journal.objects.filter(is_active=True).order_by('code')
    accounts = Account.objects.filter(is_active=True, is_deleted=False).order_by('account_code')
    
    context = {
        'journals': journals,
        'accounts': accounts,
    }
    
    return render(request, 'hospital/accountant/journal_entry_create.html', context)


@login_required
@role_required('accountant', 'senior_account_officer')
def journal_entry_edit(request, entry_id):
    """Edit journal entry"""
    je = get_object_or_404(AdvancedJournalEntry, id=entry_id, is_deleted=False)
    
    if je.status == 'posted':
        messages.error(request, 'Posted journal entries cannot be edited')
        return redirect('hospital:journal_entry_detail', entry_id=je.id)
    
    if request.method == 'POST':
        try:
            with transaction.atomic():
                je.journal_id = request.POST.get('journal')
                je.entry_date = request.POST.get('entry_date')
                je.description = request.POST.get('description', '').strip()
                je.reference = request.POST.get('reference', '').strip()
                je.save()
                
                # Delete existing lines
                je.lines.all().delete()
                
                # Recreate lines
                line_count = int(request.POST.get('line_count', '0'))
                total_debit = Decimal('0.00')
                total_credit = Decimal('0.00')
                
                for i in range(1, line_count + 1):
                    account_id = request.POST.get(f'line_{i}_account')
                    debit = Decimal(request.POST.get(f'line_{i}_debit', '0') or '0')
                    credit = Decimal(request.POST.get(f'line_{i}_credit', '0') or '0')
                    line_description = request.POST.get(f'line_{i}_description', '').strip()
                    
                    if account_id and (debit > 0 or credit > 0):
                        account = get_object_or_404(Account, id=account_id, is_deleted=False)
                        
                        AdvancedJournalEntryLine.objects.create(
                            journal_entry=je,
                            line_number=i,
                            account=account,
                            description=line_description or je.description,
                            debit_amount=debit,
                            credit_amount=credit,
                        )
                        
                        total_debit += debit
                        total_credit += credit
                
                # Update totals
                je.total_debit = total_debit
                je.total_credit = total_credit
                je.save()
                
                messages.success(request, 'Journal Entry updated successfully')
                return redirect('hospital:journal_entry_detail', entry_id=je.id)
        except Exception as e:
            messages.error(request, f'Error updating journal entry: {str(e)}')
    
    # Get journals and accounts
    journals = Journal.objects.filter(is_active=True).order_by('code')
    accounts = Account.objects.filter(is_active=True, is_deleted=False).order_by('account_code')
    lines = je.lines.all().order_by('line_number')
    
    context = {
        'entry': je,
        'journals': journals,
        'accounts': accounts,
        'lines': lines,
    }
    
    return render(request, 'hospital/accountant/journal_entry_edit.html', context)


@login_required
@role_required('accountant', 'senior_account_officer')
def journal_entry_detail(request, entry_id):
    """View journal entry detail"""
    je = get_object_or_404(AdvancedJournalEntry, id=entry_id, is_deleted=False)
    lines = je.lines.all().order_by('line_number')
    
    context = {
        'entry': je,
        'lines': lines,
    }
    
    return render(request, 'hospital/accountant/journal_entry_detail.html', context)


@login_required
@role_required('accountant', 'senior_account_officer')
def journal_entry_post(request, entry_id):
    """Post journal entry to general ledger"""
    je = get_object_or_404(AdvancedJournalEntry, id=entry_id, is_deleted=False)
    
    if je.status == 'posted':
        messages.error(request, 'Entry already posted')
        return redirect('hospital:journal_entry_detail', entry_id=je.id)
    
    if not je.is_balanced:
        messages.error(request, 'Journal entry is not balanced. Debits must equal credits.')
        return redirect('hospital:journal_entry_detail', entry_id=je.id)
    
    try:
        je.post(request.user)
        messages.success(request, f'Journal Entry {je.entry_number} posted successfully')
    except Exception as e:
        messages.error(request, f'Error posting journal entry: {str(e)}')
    
    return redirect('hospital:journal_entry_detail', entry_id=je.id)


# ==================== REVENUE ====================

@login_required
@role_required('accountant', 'senior_account_officer')
def revenue_list(request):
    """List all revenue entries"""
    revenues = Revenue.objects.filter(is_deleted=False).select_related(
        'category', 'patient', 'invoice'
    ).order_by('-revenue_date', '-revenue_number')
    
    # Filters
    category_filter = request.GET.get('category', '')
    if category_filter:
        revenues = revenues.filter(category_id=category_filter)
    
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    if date_from:
        revenues = revenues.filter(revenue_date__gte=date_from)
    if date_to:
        revenues = revenues.filter(revenue_date__lte=date_to)
    
    paginator = Paginator(revenues, 50)
    page = request.GET.get('page')
    revenues_page = paginator.get_page(page)
    
    # Summary
    total_revenue = revenues.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    
    # Get categories for filter
    categories = RevenueCategory.objects.filter(is_active=True).order_by('code')
    
    context = {
        'revenues': revenues_page,
        'categories': categories,
        'total_revenue': total_revenue,
        'category_filter': category_filter,
        'date_from': date_from,
        'date_to': date_to,
    }
    
    return render(request, 'hospital/accountant/revenue_list.html', context)


@login_required
@role_required('accountant', 'senior_account_officer')
def revenue_create(request):
    """Create new revenue entry"""
    if request.method == 'POST':
        try:
            category_id = request.POST.get('category')
            revenue_date = request.POST.get('revenue_date')
            amount = Decimal(request.POST.get('amount', '0'))
            description = request.POST.get('description', '').strip()
            payment_method = request.POST.get('payment_method', 'cash')
            reference = request.POST.get('reference', '').strip()
            patient_id = request.POST.get('patient', '')
            
            if not category_id or not revenue_date or not amount:
                messages.error(request, 'Please fill in all required fields')
                return redirect('hospital:revenue_create')
            
            category = get_object_or_404(RevenueCategory, id=category_id, is_deleted=False)
            patient = None
            if patient_id:
                patient = get_object_or_404(Patient, id=patient_id, is_deleted=False)
            
            # Create revenue entry
            revenue = Revenue.objects.create(
                category=category,
                revenue_date=revenue_date,
                amount=amount,
                description=description,
                payment_method=payment_method,
                reference=reference,
                patient=patient,
            )
            
            messages.success(request, f'Revenue entry created: {revenue.revenue_number}')
            return redirect('hospital:revenue_detail', revenue_id=revenue.id)
        except Exception as e:
            messages.error(request, f'Error creating revenue entry: {str(e)}')
    
    # Get categories and patients for dropdowns
    categories = RevenueCategory.objects.filter(is_active=True).order_by('code')
    patients = Patient.objects.filter(is_deleted=False).order_by('first_name', 'last_name')[:100]
    
    context = {
        'categories': categories,
        'patients': patients,
    }
    
    return render(request, 'hospital/accountant/revenue_create.html', context)


@login_required
@role_required('accountant', 'senior_account_officer')
def revenue_edit(request, revenue_id):
    """Edit revenue entry"""
    revenue = get_object_or_404(Revenue, id=revenue_id, is_deleted=False)
    
    if request.method == 'POST':
        try:
            revenue.category_id = request.POST.get('category')
            revenue.revenue_date = request.POST.get('revenue_date')
            revenue.amount = Decimal(request.POST.get('amount', '0'))
            revenue.description = request.POST.get('description', '').strip()
            revenue.payment_method = request.POST.get('payment_method', 'cash')
            revenue.reference = request.POST.get('reference', '').strip()
            
            patient_id = request.POST.get('patient', '')
            if patient_id:
                revenue.patient_id = patient_id
            else:
                revenue.patient = None
            
            revenue.save()
            
            messages.success(request, 'Revenue entry updated successfully')
            return redirect('hospital:revenue_detail', revenue_id=revenue.id)
        except Exception as e:
            messages.error(request, f'Error updating revenue: {str(e)}')
    
    # Get categories and patients
    categories = RevenueCategory.objects.filter(is_active=True).order_by('code')
    patients = Patient.objects.filter(is_deleted=False).order_by('first_name', 'last_name')[:100]
    
    context = {
        'revenue': revenue,
        'categories': categories,
        'patients': patients,
    }
    
    return render(request, 'hospital/accountant/revenue_edit.html', context)


@login_required
@role_required('accountant', 'senior_account_officer')
def revenue_detail(request, revenue_id):
    """View revenue detail"""
    revenue = get_object_or_404(Revenue, id=revenue_id, is_deleted=False)
    
    context = {
        'revenue': revenue,
    }
    
    return render(request, 'hospital/accountant/revenue_detail.html', context)


# ==================== EXPENSE ====================

@login_required
@role_required('accountant', 'senior_account_officer')
def expense_list(request):
    """List all expense entries"""
    expenses = Expense.objects.filter(is_deleted=False).select_related(
        'category', 'recorded_by', 'approved_by'
    ).order_by('-expense_date', '-expense_number')
    
    # Filters
    status_filter = request.GET.get('status', '')
    if status_filter:
        expenses = expenses.filter(status=status_filter)
    
    category_filter = request.GET.get('category', '')
    if category_filter:
        expenses = expenses.filter(category_id=category_filter)
    
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    if date_from:
        expenses = expenses.filter(expense_date__gte=date_from)
    if date_to:
        expenses = expenses.filter(expense_date__lte=date_to)
    
    paginator = Paginator(expenses, 50)
    page = request.GET.get('page')
    expenses_page = paginator.get_page(page)
    
    # Summary
    total_expenses = expenses.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    
    # Get categories for filter
    categories = ExpenseCategory.objects.filter(is_active=True).order_by('code')
    
    context = {
        'expenses': expenses_page,
        'categories': categories,
        'total_expenses': total_expenses,
        'status_filter': status_filter,
        'category_filter': category_filter,
        'date_from': date_from,
        'date_to': date_to,
    }
    
    return render(request, 'hospital/accountant/expense_list.html', context)


@login_required
@role_required('accountant', 'senior_account_officer')
def expense_create(request):
    """Create new expense entry"""
    if request.method == 'POST':
        try:
            category_id = request.POST.get('category')
            expense_date = request.POST.get('expense_date')
            amount = Decimal(request.POST.get('amount', '0'))
            vendor_name = request.POST.get('vendor_name', '').strip()
            vendor_invoice = request.POST.get('vendor_invoice', '').strip()
            description = request.POST.get('description', '').strip()
            
            if not category_id or not expense_date or not amount or not vendor_name:
                messages.error(request, 'Please fill in all required fields')
                return redirect('hospital:expense_create')
            
            category = get_object_or_404(ExpenseCategory, id=category_id, is_deleted=False)
            
            # Create expense entry
            expense = Expense.objects.create(
                category=category,
                expense_date=expense_date,
                amount=amount,
                vendor_name=vendor_name,
                vendor_invoice_number=vendor_invoice,
                description=description,
                recorded_by=request.user,
                status='draft',
            )
            
            messages.success(request, f'Expense entry created: {expense.expense_number}')
            return redirect('hospital:expense_detail', expense_id=expense.id)
        except Exception as e:
            messages.error(request, f'Error creating expense entry: {str(e)}')
    
    # Get categories for dropdown
    categories = ExpenseCategory.objects.filter(is_active=True).order_by('code')
    
    context = {
        'categories': categories,
    }
    
    return render(request, 'hospital/accountant/expense_create.html', context)


@login_required
@role_required('accountant', 'senior_account_officer')
def expense_edit(request, expense_id):
    """Edit expense entry"""
    expense = get_object_or_404(Expense, id=expense_id, is_deleted=False)
    
    if expense.status in ['approved', 'paid']:
        messages.error(request, 'Approved or paid expenses cannot be edited')
        return redirect('hospital:expense_detail', expense_id=expense.id)
    
    if request.method == 'POST':
        try:
            expense.category_id = request.POST.get('category')
            expense.expense_date = request.POST.get('expense_date')
            expense.amount = Decimal(request.POST.get('amount', '0'))
            expense.vendor_name = request.POST.get('vendor_name', '').strip()
            expense.vendor_invoice_number = request.POST.get('vendor_invoice', '').strip()
            expense.description = request.POST.get('description', '').strip()
            expense.save()
            
            messages.success(request, 'Expense entry updated successfully')
            return redirect('hospital:expense_detail', expense_id=expense.id)
        except Exception as e:
            messages.error(request, f'Error updating expense: {str(e)}')
    
    # Get categories
    categories = ExpenseCategory.objects.filter(is_active=True).order_by('code')
    
    context = {
        'expense': expense,
        'categories': categories,
    }
    
    return render(request, 'hospital/accountant/expense_edit.html', context)


@login_required
@role_required('accountant', 'senior_account_officer')
def expense_detail(request, expense_id):
    """View expense detail"""
    expense = get_object_or_404(Expense, id=expense_id, is_deleted=False)
    
    context = {
        'expense': expense,
    }
    
    return render(request, 'hospital/accountant/expense_detail.html', context)


# ==================== RECEIPT VOUCHER ====================

@login_required
@role_required('accountant', 'senior_account_officer')
def receipt_voucher_list(request):
    """List all receipt vouchers"""
    vouchers = ReceiptVoucher.objects.filter(is_deleted=False).select_related(
        'patient', 'revenue_account', 'cash_account', 'received_by'
    ).order_by('-receipt_date', '-receipt_number')
    
    # Filters
    status_filter = request.GET.get('status', '')
    if status_filter:
        vouchers = vouchers.filter(status=status_filter)
    
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    if date_from:
        vouchers = vouchers.filter(receipt_date__gte=date_from)
    if date_to:
        vouchers = vouchers.filter(receipt_date__lte=date_to)
    
    paginator = Paginator(vouchers, 50)
    page = request.GET.get('page')
    vouchers_page = paginator.get_page(page)
    
    # Summary
    total_amount = vouchers.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    
    context = {
        'vouchers': vouchers_page,
        'total_amount': total_amount,
        'status_filter': status_filter,
        'date_from': date_from,
        'date_to': date_to,
    }
    
    return render(request, 'hospital/accountant/receipt_voucher_list.html', context)


@login_required
@role_required('accountant', 'senior_account_officer')
def receipt_voucher_create(request):
    """Create new receipt voucher"""
    if request.method == 'POST':
        try:
            with transaction.atomic():
                received_from = request.POST.get('received_from', '').strip()
                receipt_date = request.POST.get('receipt_date')
                amount = Decimal(request.POST.get('amount', '0'))
                payment_method = request.POST.get('payment_method', 'cash')
                description = request.POST.get('description', '').strip()
                reference = request.POST.get('reference', '').strip()
                revenue_account_id = request.POST.get('revenue_account')
                cash_account_id = request.POST.get('cash_account')
                patient_id = request.POST.get('patient', '')
                
                if not received_from or not receipt_date or not amount or not revenue_account_id or not cash_account_id:
                    messages.error(request, 'Please fill in all required fields')
                    return redirect('hospital:receipt_voucher_create')
                
                revenue_account = get_object_or_404(Account, id=revenue_account_id, is_deleted=False)
                cash_account = get_object_or_404(Account, id=cash_account_id, is_deleted=False)
                patient = None
                if patient_id:
                    patient = get_object_or_404(Patient, id=patient_id, is_deleted=False)
                
                # Create receipt voucher
                rv = ReceiptVoucher.objects.create(
                    receipt_date=receipt_date,
                    received_from=received_from,
                    amount=amount,
                    payment_method=payment_method,
                    description=description,
                    reference=reference,
                    revenue_account=revenue_account,
                    cash_account=cash_account,
                    patient=patient,
                    received_by=request.user,
                    status='draft',
                )
                
                messages.success(request, f'Receipt Voucher {rv.receipt_number} created successfully')
                return redirect('hospital:receipt_voucher_detail', voucher_id=rv.id)
        except Exception as e:
            messages.error(request, f'Error creating receipt voucher: {str(e)}')
    
    # Get accounts and patients for dropdowns
    revenue_accounts = Account.objects.filter(account_type='revenue', is_active=True, is_deleted=False).order_by('account_code')
    cash_accounts = Account.objects.filter(account_type='asset', account_code__startswith='10', is_active=True, is_deleted=False).order_by('account_code')
    patients = Patient.objects.filter(is_deleted=False).order_by('first_name', 'last_name')[:100]
    
    context = {
        'revenue_accounts': revenue_accounts,
        'cash_accounts': cash_accounts,
        'patients': patients,
    }
    
    return render(request, 'hospital/accountant/receipt_voucher_create.html', context)


@login_required
@role_required('accountant', 'senior_account_officer')
def receipt_voucher_edit(request, voucher_id):
    """Edit receipt voucher"""
    rv = get_object_or_404(ReceiptVoucher, id=voucher_id, is_deleted=False)
    
    if rv.status == 'issued':
        messages.error(request, 'Issued receipt vouchers cannot be edited')
        return redirect('hospital:receipt_voucher_detail', voucher_id=rv.id)
    
    if request.method == 'POST':
        try:
            rv.received_from = request.POST.get('received_from', '').strip()
            rv.receipt_date = request.POST.get('receipt_date')
            rv.amount = Decimal(request.POST.get('amount', '0'))
            rv.payment_method = request.POST.get('payment_method', 'cash')
            rv.description = request.POST.get('description', '').strip()
            rv.reference = request.POST.get('reference', '').strip()
            rv.revenue_account_id = request.POST.get('revenue_account')
            rv.cash_account_id = request.POST.get('cash_account')
            
            patient_id = request.POST.get('patient', '')
            if patient_id:
                rv.patient_id = patient_id
            else:
                rv.patient = None
            
            rv.save()
            
            messages.success(request, 'Receipt Voucher updated successfully')
            return redirect('hospital:receipt_voucher_detail', voucher_id=rv.id)
        except Exception as e:
            messages.error(request, f'Error updating receipt voucher: {str(e)}')
    
    # Get accounts and patients
    revenue_accounts = Account.objects.filter(account_type='revenue', is_active=True, is_deleted=False).order_by('account_code')
    cash_accounts = Account.objects.filter(account_type='asset', account_code__startswith='10', is_active=True, is_deleted=False).order_by('account_code')
    patients = Patient.objects.filter(is_deleted=False).order_by('first_name', 'last_name')[:100]
    
    context = {
        'voucher': rv,
        'revenue_accounts': revenue_accounts,
        'cash_accounts': cash_accounts,
        'patients': patients,
    }
    
    return render(request, 'hospital/accountant/receipt_voucher_edit.html', context)


@login_required
@role_required('accountant', 'senior_account_officer')
def receipt_voucher_detail(request, voucher_id):
    """View receipt voucher detail"""
    rv = get_object_or_404(ReceiptVoucher, id=voucher_id, is_deleted=False)
    
    context = {
        'voucher': rv,
    }
    
    return render(request, 'hospital/accountant/receipt_voucher_detail.html', context)


@login_required
@role_required('accountant', 'senior_account_officer')
def receipt_voucher_issue(request, voucher_id):
    """Issue receipt voucher (create journal entry)"""
    rv = get_object_or_404(ReceiptVoucher, id=voucher_id, is_deleted=False)
    
    if rv.status == 'issued':
        messages.error(request, 'Voucher already issued')
        return redirect('hospital:receipt_voucher_detail', voucher_id=rv.id)
    
    try:
        with transaction.atomic():
            # Create journal entry: Debit Cash, Credit Revenue
            je = AdvancedJournalEntry.objects.create(
                journal=Journal.objects.get_or_create(journal_type='receipt', defaults={'code': 'RV', 'name': 'Receipt Journal'})[0],
                entry_date=rv.receipt_date,
                description=f"Receipt: {rv.description}",
                reference=rv.receipt_number,
                created_by=request.user,
            )
            
            # Debit Cash
            AdvancedJournalEntryLine.objects.create(
                journal_entry=je,
                line_number=1,
                account=rv.cash_account,
                description=f"Cash receipt: {rv.received_from}",
                debit_amount=rv.amount,
                credit_amount=0,
            )
            
            # Credit Revenue
            AdvancedJournalEntryLine.objects.create(
                journal_entry=je,
                line_number=2,
                account=rv.revenue_account,
                description=f"Revenue: {rv.description}",
                debit_amount=0,
                credit_amount=rv.amount,
            )
            
            # Update totals and post
            je.total_debit = rv.amount
            je.total_credit = rv.amount
            je.save()
            je.post(request.user)
            
            # Update voucher
            rv.status = 'issued'
            rv.journal_entry = je
            rv.save()
            
            messages.success(request, f'Receipt Voucher {rv.receipt_number} issued and posted to ledger')
    except Exception as e:
        messages.error(request, f'Error issuing receipt voucher: {str(e)}')
    
    return redirect('hospital:receipt_voucher_detail', voucher_id=rv.id)


# ==================== DEPOSIT ====================

@login_required
@role_required('accountant', 'senior_account_officer')
def deposit_list(request):
    """List all deposits"""
    deposits = Deposit.objects.filter(is_deleted=False).select_related(
        'from_account', 'to_account', 'from_bank_account', 'to_bank_account', 'created_by'
    ).order_by('-deposit_date', '-deposit_number')
    
    # Filters
    deposit_type_filter = request.GET.get('type', '')
    if deposit_type_filter:
        deposits = deposits.filter(deposit_type=deposit_type_filter)
    
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    if date_from:
        deposits = deposits.filter(deposit_date__gte=date_from)
    if date_to:
        deposits = deposits.filter(deposit_date__lte=date_to)
    
    paginator = Paginator(deposits, 50)
    page = request.GET.get('page')
    deposits_page = paginator.get_page(page)
    
    # Summary
    total_amount = deposits.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    
    context = {
        'deposits': deposits_page,
        'total_amount': total_amount,
        'deposit_type_filter': deposit_type_filter,
        'date_from': date_from,
        'date_to': date_to,
    }
    
    return render(request, 'hospital/accountant/deposit_list.html', context)


@login_required
@role_required('accountant', 'senior_account_officer')
def deposit_create(request):
    """Create new deposit"""
    if request.method == 'POST':
        try:
            with transaction.atomic():
                deposit_type = request.POST.get('deposit_type')
                deposit_date = request.POST.get('deposit_date')
                amount = Decimal(request.POST.get('amount', '0'))
                description = request.POST.get('description', '').strip()
                reference = request.POST.get('reference', '').strip()
                
                if not deposit_type or not deposit_date or not amount:
                    messages.error(request, 'Please fill in all required fields')
                    return redirect('hospital:deposit_create')
                
                from_account_id = request.POST.get('from_account', '')
                to_account_id = request.POST.get('to_account', '')
                from_bank_id = request.POST.get('from_bank_account', '')
                to_bank_id = request.POST.get('to_bank_account', '')
                
                from_account = None
                to_account = None
                from_bank = None
                to_bank = None
                
                if from_account_id:
                    from_account = get_object_or_404(Account, id=from_account_id, is_deleted=False)
                if to_account_id:
                    to_account = get_object_or_404(Account, id=to_account_id, is_deleted=False)
                if from_bank_id:
                    from_bank = get_object_or_404(BankAccount, id=from_bank_id, is_deleted=False)
                if to_bank_id:
                    to_bank = get_object_or_404(BankAccount, id=to_bank_id, is_deleted=False)
                
                # Create deposit
                deposit = Deposit.objects.create(
                    deposit_type=deposit_type,
                    deposit_date=deposit_date,
                    amount=amount,
                    description=description,
                    reference=reference,
                    from_account=from_account,
                    to_account=to_account,
                    from_bank_account=from_bank,
                    to_bank_account=to_bank,
                    created_by=request.user,
                )
                
                messages.success(request, f'Deposit {deposit.deposit_number} created successfully')
                return redirect('hospital:deposit_detail', deposit_id=deposit.id)
        except Exception as e:
            messages.error(request, f'Error creating deposit: {str(e)}')
    
    # Get accounts and bank accounts for dropdowns
    accounts = Account.objects.filter(is_active=True, is_deleted=False).order_by('account_code')
    bank_accounts = BankAccount.objects.filter(is_active=True, is_deleted=False).order_by('account_name')
    
    context = {
        'accounts': accounts,
        'bank_accounts': bank_accounts,
    }
    
    return render(request, 'hospital/accountant/deposit_create.html', context)


@login_required
@role_required('accountant', 'senior_account_officer')
def deposit_edit(request, deposit_id):
    """Edit deposit"""
    deposit = get_object_or_404(Deposit, id=deposit_id, is_deleted=False)
    
    if request.method == 'POST':
        try:
            deposit.deposit_type = request.POST.get('deposit_type')
            deposit.deposit_date = request.POST.get('deposit_date')
            deposit.amount = Decimal(request.POST.get('amount', '0'))
            deposit.description = request.POST.get('description', '').strip()
            deposit.reference = request.POST.get('reference', '').strip()
            
            from_account_id = request.POST.get('from_account', '')
            to_account_id = request.POST.get('to_account', '')
            from_bank_id = request.POST.get('from_bank_account', '')
            to_bank_id = request.POST.get('to_bank_account', '')
            
            deposit.from_account_id = from_account_id if from_account_id else None
            deposit.to_account_id = to_account_id if to_account_id else None
            deposit.from_bank_account_id = from_bank_id if from_bank_id else None
            deposit.to_bank_account_id = to_bank_id if to_bank_id else None
            
            deposit.save()
            
            messages.success(request, 'Deposit updated successfully')
            return redirect('hospital:deposit_detail', deposit_id=deposit.id)
        except Exception as e:
            messages.error(request, f'Error updating deposit: {str(e)}')
    
    # Get accounts and bank accounts
    accounts = Account.objects.filter(is_active=True, is_deleted=False).order_by('account_code')
    bank_accounts = BankAccount.objects.filter(is_active=True, is_deleted=False).order_by('account_name')
    
    context = {
        'deposit': deposit,
        'accounts': accounts,
        'bank_accounts': bank_accounts,
    }
    
    return render(request, 'hospital/accountant/deposit_edit.html', context)


@login_required
@role_required('accountant', 'senior_account_officer')
def deposit_detail(request, deposit_id):
    """View deposit detail"""
    deposit = get_object_or_404(Deposit, id=deposit_id, is_deleted=False)
    
    context = {
        'deposit': deposit,
    }
    
    return render(request, 'hospital/accountant/deposit_detail.html', context)


# ==================== INITIAL REVALUATION ====================

@login_required
@role_required('accountant', 'senior_account_officer')
def initial_revaluation_list(request):
    """List all initial revaluations"""
    revaluations = InitialRevaluation.objects.filter(is_deleted=False).select_related(
        'account', 'approved_by'
    ).order_by('-revaluation_date', '-revaluation_number')
    
    # Filters
    type_filter = request.GET.get('type', '')
    if type_filter:
        revaluations = revaluations.filter(revaluation_type=type_filter)
    
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    if date_from:
        revaluations = revaluations.filter(revaluation_date__gte=date_from)
    if date_to:
        revaluations = revaluations.filter(revaluation_date__lte=date_to)
    
    paginator = Paginator(revaluations, 50)
    page = request.GET.get('page')
    revaluations_page = paginator.get_page(page)
    
    # Summary
    total_revaluation = revaluations.aggregate(total=Sum('revaluation_amount'))['total'] or Decimal('0.00')
    
    context = {
        'revaluations': revaluations_page,
        'total_revaluation': total_revaluation,
        'type_filter': type_filter,
        'date_from': date_from,
        'date_to': date_to,
    }
    
    return render(request, 'hospital/accountant/initial_revaluation_list.html', context)


@login_required
@role_required('accountant', 'senior_account_officer')
def initial_revaluation_create(request):
    """Create new initial revaluation"""
    if request.method == 'POST':
        try:
            with transaction.atomic():
                account_id = request.POST.get('account')
                revaluation_date = request.POST.get('revaluation_date')
                effective_date = request.POST.get('effective_date')
                asset_description = request.POST.get('asset_description', '').strip()
                previous_value = Decimal(request.POST.get('previous_value', '0'))
                new_value = Decimal(request.POST.get('new_value', '0'))
                reason = request.POST.get('reason', '').strip()
                
                if not account_id or not revaluation_date or not effective_date or not previous_value or not new_value:
                    messages.error(request, 'Please fill in all required fields')
                    return redirect('hospital:initial_revaluation_create')
                
                account = get_object_or_404(Account, id=account_id, is_deleted=False)
                
                # Create revaluation (amount and type calculated automatically in save)
                revaluation = InitialRevaluation.objects.create(
                    account=account,
                    revaluation_date=revaluation_date,
                    effective_date=effective_date,
                    asset_description=asset_description,
                    previous_value=previous_value,
                    new_value=new_value,
                    reason=reason,
                )
                
                messages.success(request, f'Initial Revaluation {revaluation.revaluation_number} created successfully')
                return redirect('hospital:initial_revaluation_detail', revaluation_id=revaluation.id)
        except Exception as e:
            messages.error(request, f'Error creating revaluation: {str(e)}')
    
    # Get asset accounts for dropdown
    asset_accounts = Account.objects.filter(account_type='asset', is_active=True, is_deleted=False).order_by('account_code')
    
    context = {
        'asset_accounts': asset_accounts,
    }
    
    return render(request, 'hospital/accountant/initial_revaluation_create.html', context)


@login_required
@role_required('accountant', 'senior_account_officer')
def initial_revaluation_edit(request, revaluation_id):
    """Edit initial revaluation"""
    revaluation = get_object_or_404(InitialRevaluation, id=revaluation_id, is_deleted=False)
    
    if revaluation.approved_by:
        messages.error(request, 'Approved revaluations cannot be edited')
        return redirect('hospital:initial_revaluation_detail', revaluation_id=revaluation.id)
    
    if request.method == 'POST':
        try:
            revaluation.account_id = request.POST.get('account')
            revaluation.revaluation_date = request.POST.get('revaluation_date')
            revaluation.effective_date = request.POST.get('effective_date')
            revaluation.asset_description = request.POST.get('asset_description', '').strip()
            revaluation.previous_value = Decimal(request.POST.get('previous_value', '0'))
            revaluation.new_value = Decimal(request.POST.get('new_value', '0'))
            revaluation.reason = request.POST.get('reason', '').strip()
            revaluation.save()  # Will auto-calculate revaluation_amount and type
            
            messages.success(request, 'Initial Revaluation updated successfully')
            return redirect('hospital:initial_revaluation_detail', revaluation_id=revaluation.id)
        except Exception as e:
            messages.error(request, f'Error updating revaluation: {str(e)}')
    
    # Get asset accounts
    asset_accounts = Account.objects.filter(account_type='asset', is_active=True, is_deleted=False).order_by('account_code')
    
    context = {
        'revaluation': revaluation,
        'asset_accounts': asset_accounts,
    }
    
    return render(request, 'hospital/accountant/initial_revaluation_edit.html', context)


@login_required
@role_required('accountant', 'senior_account_officer')
def initial_revaluation_detail(request, revaluation_id):
    """View initial revaluation detail"""
    revaluation = get_object_or_404(InitialRevaluation, id=revaluation_id, is_deleted=False)
    
    context = {
        'revaluation': revaluation,
    }
    
    return render(request, 'hospital/accountant/initial_revaluation_detail.html', context)


# ==================== WITHHOLDING RECEIVABLE ====================

@login_required
@role_required('accountant', 'senior_account_officer')
def withholding_receivable_list(request):
    """List all withholding receivables"""
    receivables = WithholdingReceivable.objects.filter(is_deleted=False).order_by(
        '-withholding_date', '-withholding_number'
    )
    
    # Filters
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    if date_from:
        receivables = receivables.filter(withholding_date__gte=date_from)
    if date_to:
        receivables = receivables.filter(withholding_date__lte=date_to)
    
    paginator = Paginator(receivables, 50)
    page = request.GET.get('page')
    receivables_page = paginator.get_page(page)
    
    # Summary
    total_withheld = receivables.aggregate(total=Sum('amount_withheld'))['total'] or Decimal('0.00')
    total_recovered = receivables.aggregate(total=Sum('amount_recovered'))['total'] or Decimal('0.00')
    total_balance = receivables.aggregate(total=Sum('balance'))['total'] or Decimal('0.00')
    
    context = {
        'receivables': receivables_page,
        'total_withheld': total_withheld,
        'total_recovered': total_recovered,
        'total_balance': total_balance,
        'date_from': date_from,
        'date_to': date_to,
    }
    
    return render(request, 'hospital/accountant/withholding_receivable_list.html', context)


@login_required
@role_required('accountant', 'senior_account_officer')
def withholding_receivable_create(request):
    """Create new withholding receivable"""
    if request.method == 'POST':
        try:
            payer = request.POST.get('payer', '').strip()
            withholding_date = request.POST.get('withholding_date')
            amount_withheld = Decimal(request.POST.get('amount_withheld', '0'))
            description = request.POST.get('description', '').strip()
            receivable_account_id = request.POST.get('receivable_account')
            expected_recovery_date = request.POST.get('expected_recovery_date', '')
            
            if not payer or not withholding_date or not amount_withheld or not receivable_account_id:
                messages.error(request, 'Please fill in all required fields')
                return redirect('hospital:withholding_receivable_create')
            
            receivable_account = get_object_or_404(Account, id=receivable_account_id, is_deleted=False)
            
            # Create withholding receivable
            wr = WithholdingReceivable.objects.create(
                payer=payer,
                withholding_date=withholding_date,
                amount_withheld=amount_withheld,
                amount_recovered=Decimal('0.00'),
                balance=amount_withheld,
                description=description,
                receivable_account=receivable_account,
                expected_recovery_date=expected_recovery_date if expected_recovery_date else None,
            )
            
            messages.success(request, f'Withholding Receivable {wr.withholding_number} created successfully')
            return redirect('hospital:withholding_receivable_detail', receivable_id=wr.id)
        except Exception as e:
            messages.error(request, f'Error creating withholding receivable: {str(e)}')
    
    # Get receivable accounts for dropdown
    receivable_accounts = Account.objects.filter(
        account_type='asset',
        account_name__icontains='receivable',
        is_active=True,
        is_deleted=False
    ).order_by('account_code')
    
    context = {
        'receivable_accounts': receivable_accounts,
    }
    
    return render(request, 'hospital/accountant/withholding_receivable_create.html', context)


@login_required
@role_required('accountant', 'senior_account_officer')
def withholding_receivable_edit(request, receivable_id):
    """Edit withholding receivable"""
    wr = get_object_or_404(WithholdingReceivable, id=receivable_id, is_deleted=False)
    
    if request.method == 'POST':
        try:
            wr.payer = request.POST.get('payer', '').strip()
            wr.withholding_date = request.POST.get('withholding_date')
            wr.amount_withheld = Decimal(request.POST.get('amount_withheld', '0'))
            wr.description = request.POST.get('description', '').strip()
            wr.receivable_account_id = request.POST.get('receivable_account')
            expected_recovery_date = request.POST.get('expected_recovery_date', '')
            wr.expected_recovery_date = expected_recovery_date if expected_recovery_date else None
            wr.save()  # Will auto-calculate balance
            
            messages.success(request, 'Withholding Receivable updated successfully')
            return redirect('hospital:withholding_receivable_detail', receivable_id=wr.id)
        except Exception as e:
            messages.error(request, f'Error updating withholding receivable: {str(e)}')
    
    # Get receivable accounts
    receivable_accounts = Account.objects.filter(
        account_type='asset',
        account_name__icontains='receivable',
        is_active=True,
        is_deleted=False
    ).order_by('account_code')
    
    context = {
        'receivable': wr,
        'receivable_accounts': receivable_accounts,
    }
    
    return render(request, 'hospital/accountant/withholding_receivable_edit.html', context)


@login_required
@role_required('accountant', 'senior_account_officer')
def withholding_receivable_detail(request, receivable_id):
    """View withholding receivable detail"""
    wr = get_object_or_404(WithholdingReceivable, id=receivable_id, is_deleted=False)
    
    context = {
        'receivable': wr,
    }
    
    return render(request, 'hospital/accountant/withholding_receivable_detail.html', context)


# ==================== BANK ACCOUNT ====================

@login_required
@role_required('accountant', 'senior_account_officer')
def bank_account_list(request):
    """List all bank accounts"""
    bank_accounts = BankAccount.objects.filter(is_deleted=False).select_related(
        'gl_account'
    ).order_by('bank_name', 'account_name')
    
    # Filters
    active_filter = request.GET.get('active', '')
    if active_filter == 'yes':
        bank_accounts = bank_accounts.filter(is_active=True)
    elif active_filter == 'no':
        bank_accounts = bank_accounts.filter(is_active=False)
    
    # Summary
    total_balance = bank_accounts.aggregate(total=Sum('current_balance'))['total'] or Decimal('0.00')
    
    context = {
        'bank_accounts': bank_accounts,
        'total_balance': total_balance,
        'active_filter': active_filter,
    }
    
    return render(request, 'hospital/accountant/bank_account_list.html', context)


@login_required
@role_required('accountant', 'senior_account_officer')
def bank_account_create(request):
    """Create new bank account"""
    if request.method == 'POST':
        try:
            account_name = request.POST.get('account_name', '').strip()
            account_number = request.POST.get('account_number', '').strip()
            bank_name = request.POST.get('bank_name', '').strip()
            branch = request.POST.get('branch', '').strip()
            account_type = request.POST.get('account_type', 'checking')
            currency = request.POST.get('currency', 'GHS')
            opening_balance = Decimal(request.POST.get('opening_balance', '0') or '0')
            gl_account_id = request.POST.get('gl_account')
            
            if not account_name or not account_number or not bank_name or not gl_account_id:
                messages.error(request, 'Please fill in all required fields')
                return redirect('hospital:bank_account_create')
            
            gl_account = get_object_or_404(Account, id=gl_account_id, is_deleted=False)
            
            # Create bank account
            bank = BankAccount.objects.create(
                account_name=account_name,
                account_number=account_number,
                bank_name=bank_name,
                branch=branch,
                account_type=account_type,
                currency=currency,
                opening_balance=opening_balance,
                current_balance=opening_balance,
                gl_account=gl_account,
                is_active=True,
            )
            
            messages.success(request, f'Bank Account {bank.account_name} created successfully')
            return redirect('hospital:bank_account_detail', bank_id=bank.id)
        except Exception as e:
            messages.error(request, f'Error creating bank account: {str(e)}')
    
    # Get GL accounts for dropdown
    gl_accounts = Account.objects.filter(
        account_type='asset',
        account_code__startswith='10',
        is_active=True,
        is_deleted=False
    ).order_by('account_code')
    
    context = {
        'gl_accounts': gl_accounts,
    }
    
    return render(request, 'hospital/accountant/bank_account_create.html', context)


@login_required
@role_required('accountant', 'senior_account_officer')
def bank_account_edit(request, bank_id):
    """Edit bank account"""
    bank = get_object_or_404(BankAccount, id=bank_id, is_deleted=False)
    
    if request.method == 'POST':
        try:
            bank.account_name = request.POST.get('account_name', '').strip()
            bank.account_number = request.POST.get('account_number', '').strip()
            bank.bank_name = request.POST.get('bank_name', '').strip()
            bank.branch = request.POST.get('branch', '').strip()
            bank.account_type = request.POST.get('account_type', 'checking')
            bank.currency = request.POST.get('currency', 'GHS')
            bank.opening_balance = Decimal(request.POST.get('opening_balance', '0') or '0')
            bank.gl_account_id = request.POST.get('gl_account')
            bank.is_active = request.POST.get('is_active') == 'on'
            bank.save()
            
            messages.success(request, 'Bank Account updated successfully')
            return redirect('hospital:bank_account_detail', bank_id=bank.id)
        except Exception as e:
            messages.error(request, f'Error updating bank account: {str(e)}')
    
    # Get GL accounts
    gl_accounts = Account.objects.filter(
        account_type='asset',
        account_code__startswith='10',
        is_active=True,
        is_deleted=False
    ).order_by('account_code')
    
    context = {
        'bank': bank,
        'gl_accounts': gl_accounts,
    }
    
    return render(request, 'hospital/accountant/bank_account_edit.html', context)


@login_required
@role_required('accountant', 'senior_account_officer')
def bank_account_detail(request, bank_id):
    """View bank account detail"""
    bank = get_object_or_404(BankAccount, id=bank_id, is_deleted=False)
    transactions = bank.transactions.filter(is_deleted=False).order_by('-transaction_date')[:50]
    
    context = {
        'bank': bank,
        'transactions': transactions,
    }
    
    return render(request, 'hospital/accountant/bank_account_detail.html', context)


# ==================== BANK TRANSACTION ====================

@login_required
@role_required('accountant', 'senior_account_officer')
def bank_transaction_list(request):
    """List all bank transactions"""
    transactions = BankTransaction.objects.filter(is_deleted=False).select_related(
        'bank_account'
    ).order_by('-transaction_date', '-created')
    
    # Filters
    bank_filter = request.GET.get('bank', '')
    if bank_filter:
        transactions = transactions.filter(bank_account_id=bank_filter)
    
    type_filter = request.GET.get('type', '')
    if type_filter:
        transactions = transactions.filter(transaction_type=type_filter)
    
    reconciled_filter = request.GET.get('reconciled', '')
    if reconciled_filter == 'yes':
        transactions = transactions.filter(is_reconciled=True)
    elif reconciled_filter == 'no':
        transactions = transactions.filter(is_reconciled=False)
    
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    if date_from:
        transactions = transactions.filter(transaction_date__gte=date_from)
    if date_to:
        transactions = transactions.filter(transaction_date__lte=date_to)
    
    paginator = Paginator(transactions, 50)
    page = request.GET.get('page')
    transactions_page = paginator.get_page(page)
    
    # Summary
    total_amount = transactions.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    
    # Get bank accounts for filter
    bank_accounts = BankAccount.objects.filter(is_active=True, is_deleted=False).order_by('bank_name', 'account_name')
    
    context = {
        'transactions': transactions_page,
        'bank_accounts': bank_accounts,
        'total_amount': total_amount,
        'bank_filter': bank_filter,
        'type_filter': type_filter,
        'reconciled_filter': reconciled_filter,
        'date_from': date_from,
        'date_to': date_to,
    }
    
    return render(request, 'hospital/accountant/bank_transaction_list.html', context)


@login_required
@role_required('accountant', 'senior_account_officer')
def bank_transaction_create(request):
    """Create new bank transaction"""
    if request.method == 'POST':
        try:
            bank_account_id = request.POST.get('bank_account')
            transaction_date = request.POST.get('transaction_date')
            transaction_type = request.POST.get('transaction_type')
            amount = Decimal(request.POST.get('amount', '0'))
            description = request.POST.get('description', '').strip()
            reference = request.POST.get('reference', '').strip()
            
            if not bank_account_id or not transaction_date or not transaction_type or not amount:
                messages.error(request, 'Please fill in all required fields')
                return redirect('hospital:bank_transaction_create')
            
            bank_account = get_object_or_404(BankAccount, id=bank_account_id, is_deleted=False)
            
            # Create bank transaction
            bt = BankTransaction.objects.create(
                bank_account=bank_account,
                transaction_date=transaction_date,
                transaction_type=transaction_type,
                amount=amount,
                description=description,
                reference=reference,
            )
            
            messages.success(request, f'Bank Transaction created successfully')
            return redirect('hospital:bank_transaction_detail', transaction_id=bt.id)
        except Exception as e:
            messages.error(request, f'Error creating bank transaction: {str(e)}')
    
    # Get bank accounts for dropdown
    bank_accounts = BankAccount.objects.filter(is_active=True, is_deleted=False).order_by('bank_name', 'account_name')
    
    context = {
        'bank_accounts': bank_accounts,
    }
    
    return render(request, 'hospital/accountant/bank_transaction_create.html', context)


@login_required
@role_required('accountant', 'senior_account_officer')
def bank_transaction_edit(request, transaction_id):
    """Edit bank transaction"""
    bt = get_object_or_404(BankTransaction, id=transaction_id, is_deleted=False)
    
    if bt.is_reconciled:
        messages.error(request, 'Reconciled transactions cannot be edited')
        return redirect('hospital:bank_transaction_detail', transaction_id=bt.id)
    
    if request.method == 'POST':
        try:
            bt.bank_account_id = request.POST.get('bank_account')
            bt.transaction_date = request.POST.get('transaction_date')
            bt.transaction_type = request.POST.get('transaction_type')
            bt.amount = Decimal(request.POST.get('amount', '0'))
            bt.description = request.POST.get('description', '').strip()
            bt.reference = request.POST.get('reference', '').strip()
            bt.save()
            
            messages.success(request, 'Bank Transaction updated successfully')
            return redirect('hospital:bank_transaction_detail', transaction_id=bt.id)
        except Exception as e:
            messages.error(request, f'Error updating bank transaction: {str(e)}')
    
    # Get bank accounts
    bank_accounts = BankAccount.objects.filter(is_active=True, is_deleted=False).order_by('bank_name', 'account_name')
    
    context = {
        'transaction': bt,
        'bank_accounts': bank_accounts,
    }
    
    return render(request, 'hospital/accountant/bank_transaction_edit.html', context)


@login_required
@role_required('accountant', 'senior_account_officer')
def bank_transaction_detail(request, transaction_id):
    """View bank transaction detail"""
    bt = get_object_or_404(BankTransaction, id=transaction_id, is_deleted=False)
    
    context = {
        'transaction': bt,
    }
    
    return render(request, 'hospital/accountant/bank_transaction_detail.html', context)
