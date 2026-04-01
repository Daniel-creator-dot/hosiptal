"""
Comprehensive Deletion History System
Tracks all deletions from Finance, Drugs, and Inventory
Accessible by Medical Director and Administrators
"""
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q, Count
from django.core.paginator import Paginator
from django.db import ProgrammingError, OperationalError
from datetime import date, timedelta
from decimal import Decimal

from .models import Staff, Patient, Drug, Prescription, Invoice, InvoiceLine

# Import helper function from drug accountability views
try:
    from .views_drug_accountability import is_medical_director, can_approve_drug_returns
except ImportError:
    def is_medical_director(user):
        try:
            staff = Staff.objects.get(user=user, is_deleted=False)
            specialization = (staff.specialization or '').lower()
            return 'medical director' in specialization or user.is_superuser
        except Staff.DoesNotExist:
            return user.is_superuser
    
    def can_approve_drug_returns(user):
        return user.is_superuser or is_medical_director(user)

# Try to import models
try:
    from .models_procurement import Store, InventoryItem
    from .models_inventory_advanced import InventoryTransaction
    from .models_accounting import PaymentReceipt, Transaction, GeneralLedger, JournalEntry
    from .models_drug_accountability import DrugReturn, DrugAdministrationInventory
    MODELS_AVAILABLE = True
except (ImportError, Exception):
    MODELS_AVAILABLE = False
    Store = None
    InventoryItem = None
    InventoryTransaction = None
    PaymentReceipt = None
    Transaction = None
    GeneralLedger = None
    JournalEntry = None
    DrugReturn = None
    DrugAdministrationInventory = None


def can_view_deletion_history(user):
    """Check if user can view deletion history (Admin or Medical Director)"""
    return user.is_superuser or is_medical_director(user)


@login_required
def deletion_history_dashboard(request):
    """Comprehensive deletion history dashboard for Medical Director and Admin"""
    if not can_view_deletion_history(request.user):
        messages.error(request, 'You do not have permission to view deletion history. Only Administrators and Medical Directors have access.')
        return redirect('hospital:dashboard')
    
    if not MODELS_AVAILABLE:
        messages.warning(request, 'Some models are not available. Deletion history may be incomplete.')
    
    try:
        # Date filters
        date_from = request.GET.get('date_from', '')
        date_to = request.GET.get('date_to', '')
        category_filter = request.GET.get('category', '')
        search_query = request.GET.get('search', '')
        
        # Default to last 30 days
        if not date_from:
            date_from = (timezone.now() - timedelta(days=30)).date().isoformat()
        if not date_to:
            date_to = timezone.now().date().isoformat()
        
        # Parse dates
        try:
            date_from_obj = date.fromisoformat(date_from) if date_from else None
            date_to_obj = date.fromisoformat(date_to) if date_to else None
        except (ValueError, AttributeError):
            date_from_obj = None
            date_to_obj = None
        
        # Collect deletions from all categories
        deletions = []
        
        # 1. FINANCE/ACCOUNTING DELETIONS
        if category_filter in ['', 'finance', 'all']:
            # Invoices
            if Invoice:
                invoice_deletions = Invoice.objects.filter(
                    is_deleted=True,
                    modified__date__gte=date_from_obj if date_from_obj else date.today() - timedelta(days=365),
                    modified__date__lte=date_to_obj if date_to_obj else date.today()
                ).select_related('patient', 'encounter', 'payer').order_by('-modified')
                
                if search_query:
                    invoice_deletions = invoice_deletions.filter(
                        Q(invoice_number__icontains=search_query) |
                        Q(patient__first_name__icontains=search_query) |
                        Q(patient__last_name__icontains=search_query) |
                        Q(patient__mrn__icontains=search_query)
                    )
                
                for inv in invoice_deletions:
                    # Try to get creator from encounter if available
                    deleted_by = 'System'
                    try:
                        if hasattr(inv, 'encounter') and inv.encounter and hasattr(inv.encounter, 'provider'):
                            if inv.encounter.provider and hasattr(inv.encounter.provider, 'user'):
                                deleted_by = inv.encounter.provider.user.get_full_name() or inv.encounter.provider.user.username
                    except Exception:
                        pass
                    
                    deletions.append({
                        'id': str(inv.id),
                        'category': 'Finance',
                        'type': 'Invoice',
                        'item_name': f"Invoice {inv.invoice_number}",
                        'description': f"Invoice for {inv.patient.full_name if inv.patient else 'Unknown'} - Amount: {inv.total_amount}",
                        'deleted_at': inv.modified,
                        'deleted_by': deleted_by,
                        'value': inv.total_amount,
                        'reference': inv.invoice_number,
                    })
            
            # Payment Receipts
            if PaymentReceipt:
                receipt_deletions = PaymentReceipt.objects.filter(
                    is_deleted=True,
                    modified__date__gte=date_from_obj if date_from_obj else date.today() - timedelta(days=365),
                    modified__date__lte=date_to_obj if date_to_obj else date.today()
                ).select_related('patient', 'received_by').order_by('-modified')
                
                if search_query:
                    receipt_deletions = receipt_deletions.filter(
                        Q(receipt_number__icontains=search_query) |
                        Q(patient__first_name__icontains=search_query) |
                        Q(patient__last_name__icontains=search_query) |
                        Q(patient__middle_name__icontains=search_query) |
                        Q(patient__mrn__icontains=search_query)
                    )
                
                for rec in receipt_deletions:
                    deletions.append({
                        'id': str(rec.id),
                        'category': 'Finance',
                        'type': 'Payment Receipt',
                        'item_name': f"Receipt {rec.receipt_number}",
                        'description': f"Payment receipt for {rec.patient.full_name if rec.patient else 'Unknown'} - Amount: {rec.amount_paid}",
                        'deleted_at': rec.modified,
                        'deleted_by': rec.received_by.get_full_name() if rec.received_by else 'System',
                        'value': rec.amount_paid,
                        'reference': rec.receipt_number,
                    })
            
            # Transactions
            if Transaction:
                try:
                    transaction_deletions = Transaction.objects.filter(
                        is_deleted=True,
                        modified__date__gte=date_from_obj if date_from_obj else date.today() - timedelta(days=365),
                        modified__date__lte=date_to_obj if date_to_obj else date.today()
                    ).select_related('debit_account', 'credit_account', 'processed_by', 'patient', 'invoice').order_by('-modified')
                    
                    if search_query:
                        transaction_deletions = transaction_deletions.filter(
                            Q(transaction_number__icontains=search_query) |
                            Q(reference_number__icontains=search_query) |
                            Q(notes__icontains=search_query)
                        )
                    
                    for trans in transaction_deletions:
                        deleted_by = 'System'
                        try:
                            if trans.processed_by:
                                deleted_by = trans.processed_by.get_full_name() or trans.processed_by.username
                        except Exception:
                            pass
                        
                        deletions.append({
                            'id': str(trans.id),
                            'category': 'Finance',
                            'type': 'Transaction',
                            'item_name': f"Transaction {trans.transaction_number}",
                            'description': f"{trans.get_transaction_type_display()} - Amount: {trans.amount}",
                            'deleted_at': trans.modified,
                            'deleted_by': deleted_by,
                            'value': trans.amount,
                            'reference': trans.transaction_number or trans.reference_number or str(trans.id),
                        })
                except Exception as e:
                    # Skip transactions if there's an error
                    pass
        
        # 2. DRUG DELETIONS
        if category_filter in ['', 'drugs', 'all']:
            # Drugs
            drug_deletions = Drug.objects.filter(
                is_deleted=True,
                modified__date__gte=date_from_obj if date_from_obj else date.today() - timedelta(days=365),
                modified__date__lte=date_to_obj if date_to_obj else date.today()
            ).order_by('-modified')
            
            if search_query:
                drug_deletions = drug_deletions.filter(
                    Q(name__icontains=search_query) |
                    Q(code__icontains=search_query) |
                    Q(category__icontains=search_query)
                )
            
            for drug in drug_deletions:
                deletions.append({
                    'id': str(drug.id),
                    'category': 'Drugs',
                    'type': 'Drug',
                    'item_name': drug.name,
                    'description': f"Drug: {drug.name} ({drug.code}) - Category: {drug.category}",
                    'deleted_at': drug.modified,
                    'deleted_by': 'System',  # Drugs don't track who deleted
                    'value': drug.unit_price or Decimal('0.00'),
                    'reference': drug.code,
                })
            
            # Prescriptions
            prescription_deletions = Prescription.objects.filter(
                is_deleted=True,
                modified__date__gte=date_from_obj if date_from_obj else date.today() - timedelta(days=365),
                modified__date__lte=date_to_obj if date_to_obj else date.today()
            ).select_related('drug', 'order__encounter__patient', 'prescribed_by__user').order_by('-modified')
            
            if search_query:
                prescription_deletions = prescription_deletions.filter(
                    Q(drug__name__icontains=search_query) |
                    Q(order__encounter__patient__first_name__icontains=search_query) |
                    Q(order__encounter__patient__last_name__icontains=search_query) |
                    Q(order__encounter__patient__middle_name__icontains=search_query) |
                    Q(order__encounter__patient__mrn__icontains=search_query)
                )
            
            for presc in prescription_deletions:
                deletions.append({
                    'id': str(presc.id),
                    'category': 'Drugs',
                    'type': 'Prescription',
                    'item_name': f"Prescription for {presc.drug.name}",
                    'description': f"Prescription: {presc.drug.name} for {presc.order.encounter.patient.full_name if presc.order and presc.order.encounter and presc.order.encounter.patient else 'Unknown'}",
                    'deleted_at': presc.modified,
                    'deleted_by': presc.prescribed_by.user.get_full_name() if presc.prescribed_by and presc.prescribed_by.user else 'System',
                    'value': Decimal('0.00'),
                    'reference': str(presc.id),
                })
        
        # 3. INVENTORY DELETIONS
        if category_filter in ['', 'inventory', 'all']:
            if InventoryItem:
                inventory_deletions = InventoryItem.objects.filter(
                    is_deleted=True,
                    modified__date__gte=date_from_obj if date_from_obj else date.today() - timedelta(days=365),
                    modified__date__lte=date_to_obj if date_to_obj else date.today()
                ).select_related('store', 'drug').order_by('-modified')
                
                if search_query:
                    inventory_deletions = inventory_deletions.filter(
                        Q(item_name__icontains=search_query) |
                        Q(item_code__icontains=search_query)
                    )
                
                for item in inventory_deletions:
                    deletions.append({
                        'id': str(item.id),
                        'category': 'Inventory',
                        'type': 'Inventory Item',
                        'item_name': item.item_name or (item.drug.name if item.drug else 'Unknown'),
                        'description': f"Inventory item: {item.item_name or (item.drug.name if item.drug else 'Unknown')} - Store: {item.store.name if item.store else 'Unknown'}",
                        'deleted_at': item.modified,
                        'deleted_by': 'System',
                        'value': (item.quantity_on_hand or 0) * (item.unit_cost or Decimal('0.00')),
                        'reference': item.item_code,
                    })
        
        # Sort by deletion date (most recent first)
        deletions.sort(key=lambda x: x['deleted_at'], reverse=True)
        
        # Statistics
        stats = {
            'total': len(deletions),
            'finance': len([d for d in deletions if d['category'] == 'Finance']),
            'drugs': len([d for d in deletions if d['category'] == 'Drugs']),
            'inventory': len([d for d in deletions if d['category'] == 'Inventory']),
            'total_value': sum(d.get('value', Decimal('0.00')) for d in deletions if isinstance(d.get('value'), Decimal)),
        }
        
        # Pagination
        paginator = Paginator(deletions, 50)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        context = {
            'page_obj': page_obj,
            'deletions': page_obj,
            'stats': stats,
            'date_from': date_from,
            'date_to': date_to,
            'category_filter': category_filter,
            'search_query': search_query,
            'is_medical_director': is_medical_director(request.user),
        }
        
        return render(request, 'hospital/deletion_history/dashboard.html', context)
        
    except (ProgrammingError, OperationalError) as e:
        messages.error(request, f'Database error: {str(e)}')
        return redirect('hospital:dashboard')
    except Exception as e:
        messages.error(request, f'Error loading deletion history: {str(e)}')
        return redirect('hospital:dashboard')


@login_required
def deletion_history_export(request):
    """Export deletion history to CSV"""
    if not can_view_deletion_history(request.user):
        messages.error(request, 'You do not have permission to export deletion history.')
        return redirect('hospital:dashboard')
    
    from django.http import HttpResponse
    import csv
    
    try:
        # Get same filters as dashboard
        date_from = request.GET.get('date_from', '')
        date_to = request.GET.get('date_to', '')
        category_filter = request.GET.get('category', '')
        search_query = request.GET.get('search', '')
        
        # Default to last 30 days
        if not date_from:
            date_from = (timezone.now() - timedelta(days=30)).date().isoformat()
        if not date_to:
            date_to = timezone.now().date().isoformat()
        
        try:
            date_from_obj = date.fromisoformat(date_from) if date_from else None
            date_to_obj = date.fromisoformat(date_to) if date_to else None
        except (ValueError, AttributeError):
            date_from_obj = None
            date_to_obj = None
        
        # Collect deletions (same logic as dashboard - simplified for export)
        deletions = []
        
        # Finance deletions
        if category_filter in ['', 'finance', 'all']:
            if Invoice:
                for inv in Invoice.objects.filter(is_deleted=True, modified__date__gte=date_from_obj if date_from_obj else date.today() - timedelta(days=365), modified__date__lte=date_to_obj if date_to_obj else date.today()):
                    deletions.append({
                        'category': 'Finance', 'type': 'Invoice',
                        'item_name': f"Invoice {inv.invoice_number}",
                        'description': f"Invoice for {inv.patient.full_name if inv.patient else 'Unknown'}",
                        'deleted_at': inv.modified, 'deleted_by': 'System',
                        'value': inv.total_amount, 'reference': inv.invoice_number,
                    })
        
        # Drug deletions
        if category_filter in ['', 'drugs', 'all']:
            for drug in Drug.objects.filter(is_deleted=True, modified__date__gte=date_from_obj if date_from_obj else date.today() - timedelta(days=365), modified__date__lte=date_to_obj if date_to_obj else date.today()):
                deletions.append({
                    'category': 'Drugs', 'type': 'Drug',
                    'item_name': drug.name, 'description': f"Drug: {drug.name} ({drug.code})",
                    'deleted_at': drug.modified, 'deleted_by': 'System',
                    'value': drug.unit_price or Decimal('0.00'), 'reference': drug.code,
                })
        
        # Inventory deletions
        if category_filter in ['', 'inventory', 'all'] and InventoryItem:
            for item in InventoryItem.objects.filter(is_deleted=True, modified__date__gte=date_from_obj if date_from_obj else date.today() - timedelta(days=365), modified__date__lte=date_to_obj if date_to_obj else date.today()):
                deletions.append({
                    'category': 'Inventory', 'type': 'Inventory Item',
                    'item_name': item.item_name or 'Unknown',
                    'description': f"Inventory item: {item.item_name or 'Unknown'}",
                    'deleted_at': item.modified, 'deleted_by': 'System',
                    'value': (item.quantity_on_hand or 0) * (item.unit_cost or Decimal('0.00')),
                    'reference': item.item_code,
                })
        
        deletions.sort(key=lambda x: x['deleted_at'], reverse=True)
        
        # Create CSV response
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="deletion_history_{timezone.now().date()}.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['Category', 'Type', 'Item Name', 'Description', 'Deleted At', 'Deleted By', 'Value', 'Reference'])
        
        for d in deletions:
            writer.writerow([
                d['category'], d['type'], d['item_name'], d['description'],
                d['deleted_at'].strftime('%Y-%m-%d %H:%M:%S') if hasattr(d['deleted_at'], 'strftime') else str(d['deleted_at']),
                d['deleted_by'], str(d['value']), d['reference']
            ])
        
        return response
        
    except Exception as e:
        messages.error(request, f'Error exporting deletion history: {str(e)}')
        return redirect('hospital:deletion_history_dashboard')

