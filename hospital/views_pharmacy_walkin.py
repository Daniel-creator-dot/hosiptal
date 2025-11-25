"""
Walk-in Pharmacy Sales Views
Direct sales to customers without prescriptions
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Q, Sum, F
from decimal import Decimal
import json
import logging

from .models import Drug, PharmacyStock, Patient, Staff
from .models_pharmacy_walkin import WalkInPharmacySale, WalkInPharmacySaleItem
from .models_accounting import PaymentReceipt
from .services.pharmacy_walkin_service import WalkInPharmacyService
from .utils_roles import user_has_cashier_access

logger = logging.getLogger(__name__)


@login_required
def pharmacy_walkin_sales_list(request):
    """
    List all walk-in pharmacy sales
    """
    # Filter options
    status_filter = request.GET.get('status', 'all')
    search_query = request.GET.get('q', '')
    
    # Base queryset
    sales = WalkInPharmacySale.objects.filter(is_deleted=False)
    
    # Apply filters
    if status_filter != 'all':
        sales = sales.filter(payment_status=status_filter)
    
    if search_query:
        sales = sales.filter(
            Q(sale_number__icontains=search_query) |
            Q(customer_name__icontains=search_query) |
            Q(customer_phone__icontains=search_query)
        )
    
    sales = sales.select_related('served_by', 'patient').order_by('-sale_date')[:100]
    
    # Statistics
    today = timezone.now().date()
    stats = {
        'today_sales': WalkInPharmacySale.objects.filter(
            sale_date__date=today, is_deleted=False
        ).count(),
        'today_revenue': WalkInPharmacySale.objects.filter(
            sale_date__date=today,
            payment_status='paid',
            is_deleted=False
        ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00'),
        'pending_payment': WalkInPharmacySale.objects.filter(
            payment_status='pending', is_deleted=False
        ).count(),
        'total_sales': WalkInPharmacySale.objects.filter(is_deleted=False).count(),
    }
    
    context = {
        'title': '💊 Walk-in Pharmacy Sales',
        'sales': sales,
        'stats': stats,
        'status_filter': status_filter,
        'search_query': search_query,
    }
    return render(request, 'hospital/pharmacy_walkin_sales_list.html', context)


@login_required
def pharmacy_walkin_sale_create(request):
    """
    Create a new walk-in sale
    """
    if request.method == 'POST':
        try:
            # Get customer info
            customer_type = request.POST.get('customer_type', 'walkin')
            customer_name = request.POST.get('customer_name', '')
            customer_phone = request.POST.get('customer_phone', '')
            customer_address = request.POST.get('customer_address', '')
            patient_id = request.POST.get('patient_id', '')
            
            # Get staff
            try:
                staff = Staff.objects.get(user=request.user, is_active=True)
            except Staff.DoesNotExist:
                staff = None
            
            # Create sale
            sale = WalkInPharmacySale.objects.create(
                customer_type=customer_type,
                customer_name=customer_name,
                customer_phone=customer_phone,
                customer_address=customer_address,
                patient_id=patient_id if patient_id else None,
                served_by=staff
            )
            
            # Get items from POST data (JSON)
            items_json = request.POST.get('items', '[]')
            items = json.loads(items_json)
            
            for item_data in items:
                drug_id = item_data.get('drug_id')
                quantity = int(item_data.get('quantity', 1))
                unit_price = Decimal(item_data.get('unit_price', '0'))
                dosage_instructions = item_data.get('dosage_instructions', '')
                
                drug = Drug.objects.get(id=drug_id, is_deleted=False)
                
                # Create sale item
                WalkInPharmacySaleItem.objects.create(
                    sale=sale,
                    drug=drug,
                    quantity=quantity,
                    unit_price=unit_price,
                    dosage_instructions=dosage_instructions
                )
            
            # Recalculate totals
            sale.calculate_totals()
            
            messages.success(
                request,
                f'✅ Walk-in sale {sale.sale_number} created successfully! '
                f'Total: GHS {sale.total_amount}. Customer should pay at cashier.'
            )
            
            return redirect('hospital:pharmacy_walkin_sale_detail', sale_id=sale.id)
            
        except Exception as e:
            logger.error(f"Error creating walk-in sale: {str(e)}", exc_info=True)
            messages.error(request, f'❌ Error creating sale: {str(e)}')
    
    # GET request - show form
    # Get available drugs
    drugs = Drug.objects.filter(
        is_active=True,
        is_deleted=False
    ).order_by('name')
    
    # Check stock availability
    drugs_with_stock = []
    for drug in drugs:
        stock_qty = PharmacyStock.objects.filter(
            drug=drug,
            quantity_on_hand__gt=0,
            is_deleted=False
        ).aggregate(total=Sum('quantity_on_hand'))['total'] or 0
        
        if stock_qty > 0:
            drug.available_stock = stock_qty
            drugs_with_stock.append(drug)
    
    context = {
        'title': '💊 New Walk-in Sale',
        'drugs': drugs_with_stock,
    }
    return render(request, 'hospital/pharmacy_walkin_sale_create.html', context)


@login_required
def pharmacy_walkin_sale_detail(request, sale_id):
    """
    View details of a walk-in sale
    """
    sale = get_object_or_404(
        WalkInPharmacySale.objects.select_related('served_by', 'patient', 'dispensed_by'),
        id=sale_id,
        is_deleted=False
    )
    
    items = sale.items.filter(is_deleted=False).select_related('drug')
    
    # Check if payment has been made
    receipts = PaymentReceipt.objects.filter(
        service_type='pharmacy_walkin',
        service_details__sale_id=str(sale.id),
        is_deleted=False
    ).order_by('-receipt_date')
    
    context = {
        'title': f'Walk-in Sale - {sale.sale_number}',
        'sale': sale,
        'items': items,
        'receipts': receipts,
        'can_record_payment': user_has_cashier_access(request.user),
    }
    return render(request, 'hospital/pharmacy_walkin_sale_detail.html', context)


@login_required
def pharmacy_walkin_dispense(request, sale_id):
    """
    Dispense medication for a paid walk-in sale
    """
    sale = get_object_or_404(WalkInPharmacySale, id=sale_id, is_deleted=False)
    
    # Check if already dispensed
    if sale.is_dispensed:
        messages.warning(request, '⚠️ This sale has already been dispensed.')
        return redirect('hospital:pharmacy_walkin_sale_detail', sale_id=sale_id)
    
    # Check payment status
    if sale.payment_status != 'paid':
        messages.error(
            request,
            f'❌ PAYMENT REQUIRED! Customer must pay at cashier first. '
            f'Status: {sale.get_payment_status_display()}, Due: GHS {sale.amount_due}'
        )
        return redirect('hospital:pharmacy_walkin_sale_detail', sale_id=sale_id)
    
    if request.method == 'POST':
        try:
            # Get staff
            try:
                staff = Staff.objects.get(user=request.user, is_active=True)
            except Staff.DoesNotExist:
                staff = None
            
            # Reduce stock for each item
            for item in sale.items.filter(is_deleted=False):
                item.reduce_stock()
            
            # Mark as dispensed
            sale.is_dispensed = True
            sale.dispensed_at = timezone.now()
            sale.dispensed_by = staff
            sale.counselling_notes = request.POST.get('counselling_notes', '')
            sale.save()
            
            # Send SMS notification if phone provided
            if sale.customer_phone:
                try:
                    from .services.sms_service import sms_service
                    items_list = ', '.join([
                        f"{item.drug.name} x{item.quantity}"
                        for item in sale.items.filter(is_deleted=False)[:3]
                    ])
                    message = (
                        f"Your medication has been dispensed: {items_list}. "
                        f"Thank you for choosing our pharmacy. PrimeCare Medical"
                    )
                    sms_log = sms_service.send_sms(
                        phone_number=sale.customer_phone,
                        message=message,
                        message_type='pharmacy_dispensing',
                        recipient_name=sale.customer_name or 'Customer',
                        related_object_id=sale.id if hasattr(sale, 'id') else None,
                        related_object_type='WalkInSale'
                    )
                    if sms_log.status == 'sent':
                        logger.info(f"✅ SMS sent to {sale.customer_phone}")
                    else:
                        logger.warning(f"⚠️ SMS failed: {sms_log.error_message or 'Unknown error'}")
                except Exception as e:
                    logger.error(f"❌ Error sending SMS: {str(e)}", exc_info=True)
            
            messages.success(
                request,
                f'✅ Medication dispensed successfully to {sale.customer_name}!'
            )
            
            return redirect('hospital:pharmacy_walkin_sale_detail', sale_id=sale_id)
            
        except Exception as e:
            logger.error(f"Error dispensing walk-in sale: {str(e)}", exc_info=True)
            messages.error(request, f'❌ Error dispensing: {str(e)}')
    
    items = sale.items.filter(is_deleted=False).select_related('drug')
    
    context = {
        'title': f'Dispense Walk-in Sale - {sale.sale_number}',
        'sale': sale,
        'items': items,
    }
    return render(request, 'hospital/pharmacy_walkin_dispense.html', context)


@login_required
def pharmacy_walkin_record_payment(request, sale_id):
    """
    Record payment for a walk-in sale (from cashier)
    """
    sale = get_object_or_404(WalkInPharmacySale, id=sale_id, is_deleted=False)
    
    if not user_has_cashier_access(request.user):
        messages.error(request, 'Payment must be recorded by a cashier. Please direct the customer to the cashier desk.')
        return redirect('hospital:pharmacy_walkin_sale_detail', sale_id=sale_id)

    if request.method == 'POST':
        try:
            amount_paid = Decimal(request.POST.get('amount_paid', '0'))
            payment_method = request.POST.get('payment_method', 'cash')
            notes = request.POST.get('notes', '')

            result = WalkInPharmacyService.create_payment_receipt(
                sale=sale,
                amount=amount_paid,
                payment_method=payment_method,
                received_by_user=request.user,
                notes=f"{notes}".strip()
            )

            if not result.get('success'):
                raise Exception(result.get('message') or result.get('error') or 'Payment service failed')
            
            receipt = result['receipt']
            
            messages.success(
                request,
                f'✅ Payment of GHS {amount_paid} recorded. Receipt: {receipt.receipt_number}'
            )
            
            if sale.payment_status == 'paid':
                messages.info(request, '💊 Sale is now fully paid. Customer can collect medication.')
            
            return redirect('hospital:pharmacy_walkin_sale_detail', sale_id=sale_id)
            
        except Exception as e:
            logger.error(f"Error recording payment: {str(e)}", exc_info=True)
            messages.error(request, f'❌ Error recording payment: {str(e)}')
    
    items = sale.items.filter(is_deleted=False).select_related('drug')
    context = {
        'title': f'Record Payment - {sale.sale_number}',
        'sale': sale,
        'items': items,
    }
    return render(request, 'hospital/pharmacy_walkin_record_payment.html', context)


@login_required
def api_search_drugs(request):
    """
    API endpoint to search drugs for walk-in sales
    """
    query = request.GET.get('q', '')
    
    if len(query) < 2:
        return JsonResponse({'drugs': []})
    
    drugs = Drug.objects.filter(
        Q(name__icontains=query) | Q(generic_name__icontains=query),
        is_active=True,
        is_deleted=False
    )[:20]
    
    results = []
    for drug in drugs:
        # Get available stock
        stock_qty = PharmacyStock.objects.filter(
            drug=drug,
            quantity_on_hand__gt=0,
            is_deleted=False
        ).aggregate(total=Sum('quantity_on_hand'))['total'] or 0
        
        results.append({
            'id': drug.id,
            'name': drug.name,
            'generic_name': drug.generic_name,
            'strength': drug.strength,
            'form': drug.form,
            'unit_price': str(drug.unit_price),
            'stock_available': stock_qty,
        })
    
    return JsonResponse({'drugs': results})


@login_required
def api_patient_search(request):
    """
    API endpoint to search registered patients
    """
    query = request.GET.get('q', '')
    
    if len(query) < 2:
        return JsonResponse({'patients': []})
    
    patients = Patient.objects.filter(
        Q(first_name__icontains=query) |
        Q(last_name__icontains=query) |
        Q(mrn__icontains=query) |
        Q(phone_number__icontains=query),
        is_deleted=False
    )[:10]
    
    results = [{
        'id': p.id,
        'name': p.full_name,
        'mrn': p.mrn,
        'phone': p.phone_number,
    } for p in patients]
    
    return JsonResponse({'patients': results})













