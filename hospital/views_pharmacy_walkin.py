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
from django.db import transaction
from django.core.cache import cache
from decimal import Decimal
import hashlib
import json
import logging
import time

from .models import Drug, PharmacyStock, Patient, Staff
from .models_pharmacy_walkin import WalkInPharmacySale, WalkInPharmacySaleItem
from .models_accounting import PaymentReceipt
from .services.pharmacy_walkin_service import WalkInPharmacyService
from .utils_roles import user_has_cashier_access, is_pharmacy_user, get_user_role
from .decorators import role_required

logger = logging.getLogger(__name__)


def _user_can_confirm_walkin_invoice_payment_collected(user):
    """Pharmacy staff or admin may confirm cash was collected when the sale row is out of sync."""
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    if getattr(user, 'is_superuser', False):
        return True
    if get_user_role(user) == 'admin':
        return True
    return is_pharmacy_user(user)


def resolve_walk_in_payer_id(payer_id):
    """
    Resolve Payer from pharmacy walk-in / antenatal payer_id field.
    Accepts UUID or ic-/ca-/aca- prefixed external account ids.
    """
    if not payer_id or not str(payer_id).strip():
        return None
    payer_id = str(payer_id).strip()
    try:
        from .models import Payer
        if payer_id.startswith('ic-'):
            from .models_insurance_companies import InsuranceCompany
            ic = InsuranceCompany.objects.filter(
                pk=payer_id[3:], is_active=True, is_deleted=False
            ).first()
            if ic:
                payer, _ = Payer.objects.get_or_create(
                    name=ic.name,
                    defaults={'payer_type': 'private', 'is_active': True},
                )
                if payer.payer_type not in ('nhis', 'private'):
                    payer.payer_type = 'private'
                    payer.save(update_fields=['payer_type'])
                return payer
        elif payer_id.startswith('ca-'):
            from .models_enterprise_billing import CorporateAccount
            ca = CorporateAccount.objects.filter(
                pk=payer_id[3:], is_active=True, is_deleted=False
            ).first()
            if ca:
                payer, _ = Payer.objects.get_or_create(
                    name=ca.company_name,
                    defaults={'payer_type': 'corporate', 'is_active': True},
                )
                if payer.payer_type != 'corporate':
                    payer.payer_type = 'corporate'
                    payer.save(update_fields=['payer_type'])
                return payer
        elif payer_id.startswith('aca-'):
            from .models_accounting_advanced import AccountingCorporateAccount
            aca = AccountingCorporateAccount.objects.filter(
                pk=payer_id[4:], is_active=True, is_deleted=False
            ).first()
            if aca:
                payer, _ = Payer.objects.get_or_create(
                    name=aca.company_name,
                    defaults={'payer_type': 'corporate', 'is_active': True},
                )
                if payer.payer_type != 'corporate':
                    payer.payer_type = 'corporate'
                    payer.save(update_fields=['payer_type'])
                return payer
        return Payer.objects.filter(
            pk=payer_id, is_active=True, is_deleted=False
        ).first()
    except Exception:
        return None


def payer_for_pharmacy_drug_search(request):
    """
    Resolve payer for drug unit prices in search UI (must match sale POST pricing).
    GET: price_basis=cash → cash pricing only; payer_id → walk-in payer; else patient_id → primary_insurance.
    """
    if request.GET.get('price_basis', '').strip().lower() == 'cash':
        return None
    payer_id = request.GET.get('payer_id', '').strip()
    if payer_id:
        return resolve_walk_in_payer_id(payer_id)
    patient_id = request.GET.get('patient_id', '').strip()
    if patient_id:
        p = Patient.objects.filter(
            pk=patient_id, is_deleted=False
        ).select_related('primary_insurance').first()
        if p:
            return p.primary_insurance
    return None


_ANTENATAL_IDEM_CACHE_SECONDS = 600
_ANTENATAL_LOCK_SECONDS = 45
_ANTENATAL_LOCK_WAIT_ATTEMPTS = 50
_ANTENATAL_LOCK_WAIT_SEC = 0.04


def _antenatal_submission_fingerprint(user_id, patient_id, payer_id, items):
    """Stable hash for duplicate POST detection (double-click / retry same payload)."""
    norm_items = sorted(
        (
            str(it.get('drug_id', '')),
            int(it.get('quantity', 1) or 1),
        )
        for it in items
    )
    payload = json.dumps(
        [user_id, str(patient_id), payer_id or '', norm_items],
        separators=(',', ':'),
    )
    return hashlib.sha256(payload.encode()).hexdigest()


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
    
    sales = sales.select_related('served_by', 'patient', 'payer').order_by('-sale_date')[:100]
    
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
    
    # Doctors should not see amounts (policy: only pharmacy/cashier see prices)
    show_prices = True
    try:
        staff = Staff.objects.get(user=request.user, is_active=True, is_deleted=False)
        if staff.profession == 'doctor':
            show_prices = False
    except (Staff.DoesNotExist, AttributeError):
        pass
    
    context = {
        'title': '💊 Walk-in Pharmacy Sales',
        'sales': sales,
        'stats': stats,
        'status_filter': status_filter,
        'search_query': search_query,
        'show_prices': show_prices,
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
            payer_id = request.POST.get('payer_id', '')
            
            # Get staff
            try:
                staff = Staff.objects.get(user=request.user, is_active=True)
            except Staff.DoesNotExist:
                staff = None
            
            payer = resolve_walk_in_payer_id(payer_id)

            # Keep customer details populated for registered patients so list views never show blanks.
            if patient_id and customer_type == 'registered':
                try:
                    selected_patient = Patient.objects.filter(id=patient_id, is_deleted=False).first()
                except Exception:
                    selected_patient = None
                if selected_patient:
                    if not customer_name:
                        customer_name = selected_patient.full_name or customer_name
                    if not customer_phone:
                        customer_phone = selected_patient.phone_number or customer_phone

            # Create sale
            sale = WalkInPharmacySale.objects.create(
                customer_type=customer_type,
                customer_name=customer_name,
                customer_phone=customer_phone,
                customer_address=customer_address,
                patient_id=patient_id if patient_id else None,
                payer=payer,
                served_by=staff
            )
            
            # Get items from POST data (JSON)
            items_json = request.POST.get('items', '[]')
            items = json.loads(items_json)

            from .utils_billing import get_drug_price_for_prescription

            for item_data in items:
                drug_id = item_data.get('drug_id')
                quantity = int(item_data.get('quantity', 1))
                dosage_instructions = item_data.get('dosage_instructions', '')

                drug = Drug.objects.get(id=drug_id, is_deleted=False)
                unit_price = get_drug_price_for_prescription(drug, payer=payer)
                
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
            
            # Ensure an Invoice exists so the sale appears on the Invoices page (/hms/invoices/)
            try:
                patient = WalkInPharmacyService.ensure_sale_patient(sale)
                WalkInPharmacyService.ensure_sale_invoice(sale, patient)
            except Exception as e:
                logger.warning("Could not ensure invoice for prescribe sale %s: %s", sale.sale_number, e)
            
            messages.success(
                request,
                f'✅ Prescribe sale {sale.sale_number} created successfully! '
                f'Total: GHS {sale.total_amount}. Customer should pay at cashier.'
            )
            
            return redirect('hospital:pharmacy_walkin_sale_detail', sale_id=sale.id)
            
        except Exception as e:
            logger.error(f"Error creating walk-in sale: {str(e)}", exc_info=True)
            messages.error(request, f'❌ Error creating sale: {str(e)}')
    
    # GET request - show form
    from .models import Payer
    drugs = Drug.objects.filter(
        is_active=True,
        is_deleted=False
    ).order_by('name')
    cash_payers = Payer.objects.filter(payer_type='cash', is_active=True, is_deleted=False).order_by('name')
    # Corporate: Payer + CorporateAccount + AccountingCorporateAccount (merged, deduped by name)
    corporate_names_seen = set()
    corporate_payers = []
    for p in Payer.objects.filter(payer_type='corporate', is_active=True, is_deleted=False).order_by('name'):
        corporate_payers.append({'id': str(p.id), 'name': p.name})
        corporate_names_seen.add(p.name.lower())
    try:
        from .models_enterprise_billing import CorporateAccount
        for ca in CorporateAccount.objects.filter(is_active=True, is_deleted=False).order_by('company_name'):
            if ca.company_name.lower() not in corporate_names_seen:
                corporate_payers.append({'id': f'ca-{ca.id}', 'name': ca.company_name})
                corporate_names_seen.add(ca.company_name.lower())
    except Exception:
        pass
    try:
        from .models_accounting_advanced import AccountingCorporateAccount
        for aca in AccountingCorporateAccount.objects.filter(is_active=True, is_deleted=False).order_by('company_name'):
            if aca.company_name.lower() not in corporate_names_seen:
                corporate_payers.append({'id': f'aca-{aca.id}', 'name': aca.company_name})
                corporate_names_seen.add(aca.company_name.lower())
    except Exception:
        pass
    # Insurance: Payer + InsuranceCompany (merged, deduped by name)
    insurance_names_seen = set()
    insurance_payers = []
    for p in Payer.objects.filter(payer_type__in=['nhis', 'private'], is_active=True, is_deleted=False).order_by('name'):
        insurance_payers.append({'id': str(p.id), 'name': p.name})
        insurance_names_seen.add(p.name.lower())
    try:
        from .models_insurance_companies import InsuranceCompany
        for ic in InsuranceCompany.objects.filter(is_active=True, is_deleted=False).order_by('name'):
            if ic.name.lower() not in insurance_names_seen:
                insurance_payers.append({'id': f'ic-{ic.id}', 'name': ic.name})
                insurance_names_seen.add(ic.name.lower())
    except Exception:
        pass
    
    # Stock from both PharmacyStock and InventoryItem (pharmacy store)
    pharmacy_store = None
    try:
        from .models_procurement import Store, InventoryItem
        pharmacy_store = Store.get_main_pharmacy_store()
    except Exception:
        pass
    
    drugs_with_stock = []
    for drug in drugs:
        stock_ps = PharmacyStock.objects.filter(
            drug=drug,
            quantity_on_hand__gt=0,
            is_deleted=False
        ).aggregate(total=Sum('quantity_on_hand'))['total'] or 0
        stock_inv = 0
        if pharmacy_store:
            try:
                stock_inv = InventoryItem.objects.filter(
                    store=pharmacy_store,
                    drug=drug,
                    is_deleted=False,
                    is_active=True
                ).aggregate(total=Sum('quantity_on_hand'))['total'] or 0
            except Exception:
                pass
        stock_qty = max(stock_ps, stock_inv)
        if stock_qty > 0:
            drug.available_stock = stock_qty
            drugs_with_stock.append(drug)
    
    context = {
        'title': '💊 New Prescribe Sale',
        'drugs': drugs_with_stock,
        'cash_payers': cash_payers,
        'corporate_payers': corporate_payers,
        'insurance_payers': insurance_payers,
    }
    return render(request, 'hospital/pharmacy_walkin_sale_create.html', context)


@login_required
@role_required('midwife', 'pharmacist', 'nurse', 'admin', message='Access denied. Only midwives, pharmacists, and nurses can bill antenatal items.')
def antenatal_items_billing(request):
    """
    Bill pharmacy items to antenatal patients.
    Select patient → Select items from pharmacy → Create sale (patient pays at cashier).
    """
    if request.method == 'POST':
        patient_id = request.POST.get('patient_id', '').strip()
        if not patient_id:
            messages.error(request, '❌ Please select a patient.')
            return redirect('hospital:antenatal_items_billing')
        patient = get_object_or_404(Patient, pk=patient_id, is_deleted=False)
        payer_id = request.POST.get('payer_id', '')
        items_json = request.POST.get('items', '[]')
        try:
            items = json.loads(items_json)
        except json.JSONDecodeError:
            messages.error(request, '❌ Invalid items data.')
            return redirect('hospital:antenatal_items_billing')
        if not items:
            messages.error(request, '❌ Please add at least one item.')
            return redirect('hospital:antenatal_items_billing')

        fp = _antenatal_submission_fingerprint(
            request.user.pk, patient_id, request.POST.get('payer_id', '').strip(), items
        )
        idem_key = f'antenatal_bill_idem:{fp}'
        lock_key = f'antenatal_bill_lock:{fp}'
        existing_sale_id = cache.get(idem_key)
        if existing_sale_id:
            messages.info(
                request,
                'That bill was already created (duplicate submit). Opening the existing sale.',
            )
            return redirect('hospital:pharmacy_walkin_sale_detail', sale_id=existing_sale_id)
        if not cache.add(lock_key, 1, timeout=_ANTENATAL_LOCK_SECONDS):
            for _ in range(_ANTENATAL_LOCK_WAIT_ATTEMPTS):
                time.sleep(_ANTENATAL_LOCK_WAIT_SEC)
                existing_sale_id = cache.get(idem_key)
                if existing_sale_id:
                    messages.info(
                        request,
                        'Bill already created. Opening the existing sale.',
                    )
                    return redirect(
                        'hospital:pharmacy_walkin_sale_detail',
                        sale_id=existing_sale_id,
                    )
            messages.warning(
                request,
                'Submission is still processing or conflicted. Check the cashier list before creating again.',
            )
            return redirect('hospital:antenatal_items_billing')

        try:
            try:
                staff = Staff.objects.get(user=request.user, is_active=True)
            except Staff.DoesNotExist:
                staff = None
            payer = resolve_walk_in_payer_id(payer_id)
            if not payer:
                from .models import Payer
                payer = getattr(patient, 'primary_insurance', None) or Payer.objects.filter(payer_type='cash', is_active=True, is_deleted=False).first()
            sale = WalkInPharmacySale.objects.create(
                customer_type='registered',
                customer_name=patient.full_name,
                customer_phone=patient.phone_number or '',
                patient=patient,
                payer=payer,
                served_by=staff,
                notes='Antenatal items'
            )
            from .utils_billing import get_drug_price_for_prescription
            for item_data in items:
                drug_id = item_data.get('drug_id')
                quantity = int(item_data.get('quantity', 1))
                drug = Drug.objects.get(id=drug_id, is_deleted=False)
                unit_price = get_drug_price_for_prescription(drug, payer=payer)
                WalkInPharmacySaleItem.objects.create(
                    sale=sale,
                    drug=drug,
                    quantity=quantity,
                    unit_price=unit_price,
                    dosage_instructions=item_data.get('dosage_instructions', '')
                )
            sale.calculate_totals()
            try:
                WalkInPharmacyService.ensure_sale_invoice(sale, sale.patient)
            except Exception as e:
                logger.warning("Could not ensure invoice for antenatal sale %s: %s", sale.sale_number, e)
            cache.set(idem_key, sale.id, timeout=_ANTENATAL_IDEM_CACHE_SECONDS)
            messages.success(
                request,
                f'✅ Antenatal items bill created for {patient.full_name}. Sale: {sale.sale_number}. Total: GHS {sale.total_amount}. Patient pays at cashier.'
            )
            return redirect('hospital:pharmacy_walkin_sale_detail', sale_id=sale.id)
        except Exception as e:
            logger.error(f"Antenatal items billing error: {e}", exc_info=True)
            messages.error(request, f'❌ Error: {str(e)}')
            return redirect('hospital:antenatal_items_billing')
        finally:
            cache.delete(lock_key)
    from .models import Payer
    corporate_payers = []
    insurance_payers = []
    cash_payer = Payer.objects.filter(payer_type='cash', is_active=True, is_deleted=False).first()
    for p in Payer.objects.filter(payer_type='corporate', is_active=True, is_deleted=False).order_by('name'):
        corporate_payers.append({'id': str(p.id), 'name': p.name})
    try:
        from .models_enterprise_billing import CorporateAccount
        for ca in CorporateAccount.objects.filter(is_active=True, is_deleted=False).order_by('company_name'):
            corporate_payers.append({'id': f'ca-{ca.id}', 'name': ca.company_name})
    except Exception:
        pass
    try:
        from .models_accounting_advanced import AccountingCorporateAccount
        for aca in AccountingCorporateAccount.objects.filter(is_active=True, is_deleted=False).order_by('company_name'):
            corporate_payers.append({'id': f'aca-{aca.id}', 'name': aca.company_name})
    except Exception:
        pass
    for p in Payer.objects.filter(payer_type__in=['nhis', 'private'], is_active=True, is_deleted=False).order_by('name'):
        insurance_payers.append({'id': str(p.id), 'name': p.name})
    try:
        from .models_insurance_companies import InsuranceCompany
        for ic in InsuranceCompany.objects.filter(is_active=True, is_deleted=False).order_by('name'):
            insurance_payers.append({'id': f'ic-{ic.id}', 'name': ic.name})
    except Exception:
        pass
    antenatal_items = list(Drug.objects.filter(
        category='vitamin',
        is_active=True,
        is_deleted=False
    ).order_by('name')[:30])
    context = {
        'corporate_payers': corporate_payers,
        'insurance_payers': insurance_payers,
        'antenatal_items': antenatal_items,
    }
    return render(request, 'hospital/antenatal_items_billing.html', context)


@login_required
def pharmacy_walkin_sale_detail(request, sale_id):
    """
    View details of a walk-in sale
    """
    sale = get_object_or_404(
        WalkInPharmacySale.objects.select_related('served_by', 'patient', 'dispensed_by', 'payer'),
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
    
    # Doctors should not see amounts
    show_prices = True
    try:
        staff = Staff.objects.get(user=request.user, is_active=True, is_deleted=False)
        if staff.profession == 'doctor':
            show_prices = False
    except (Staff.DoesNotExist, AttributeError):
        pass
    
    context = {
        'title': f'Prescribe Sale - {sale.sale_number}',
        'sale': sale,
        'items': items,
        'receipts': receipts,
        'show_prices': show_prices,
    }
    return render(request, 'hospital/pharmacy_walkin_sale_detail.html', context)


@login_required
def pharmacy_walkin_dispense(request, sale_id):
    """
    Dispense medication for a paid walk-in sale
    """
    sale = get_object_or_404(
        WalkInPharmacySale.objects.select_related('payer'),
        id=sale_id,
        is_deleted=False
    )

    from .services.pharmacy_invoice_payment_link import sync_walkin_sale_payment_from_invoices

    sync_walkin_sale_payment_from_invoices(sale)

    # Check if already dispensed
    if sale.is_dispensed:
        messages.warning(request, '⚠️ This sale has already been dispensed.')
        return redirect('hospital:pharmacy_walkin_sale_detail', sale_id=sale_id)

    def _can_dispense_now():
        return sale.payment_status == 'paid' or getattr(sale, 'is_billed_to_company', False)

    can_dispense = _can_dispense_now()

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'confirm_cash_collected_on_invoice':
            if not _user_can_confirm_walkin_invoice_payment_collected(request.user):
                messages.error(request, 'You do not have permission to confirm payment for this sale.')
                return redirect('hospital:pharmacy_walkin_dispense', sale_id=sale_id)
            if request.POST.get('confirm') != 'on':
                messages.error(request, 'Check the box to confirm payment was collected (cashier / invoice).')
                return redirect('hospital:pharmacy_walkin_dispense', sale_id=sale_id)
            sync_walkin_sale_payment_from_invoices(sale)
            if _can_dispense_now():
                messages.info(request, 'Payment is already recorded on this sale.')
                return redirect('hospital:pharmacy_walkin_dispense', sale_id=sale_id)
            sale.amount_paid = sale.total_amount or Decimal('0.00')
            sale.save()
            messages.success(
                request,
                'Payment marked as collected. You can dispense below — stock will update when you complete dispensing.',
            )
            return redirect('hospital:pharmacy_walkin_dispense', sale_id=sale_id)

        if not _can_dispense_now():
            messages.error(
                request,
                f'❌ Payment must be recorded before dispensing. '
                f'Status: {sale.get_payment_status_display()}, Due: GHS {sale.amount_due}',
            )
            return redirect('hospital:pharmacy_walkin_dispense', sale_id=sale_id)

        try:
            # Get staff
            try:
                staff = Staff.objects.get(user=request.user, is_active=True)
            except Staff.DoesNotExist:
                staff = None

            # Mark as dispensed inside a transaction so stock-deduction failures
            # roll back the status change and do not show false success.
            with transaction.atomic():
                sale.is_dispensed = True
                sale.dispensed_at = timezone.now()
                sale.dispensed_by = staff
                sale.counselling_notes = request.POST.get('counselling_notes', '')
                sale.save()

            # Send customer service review SMS when medicine is dispensed
            if sale.customer_phone:
                try:
                    from .services.patient_feedback_service import send_customer_service_review_sms_to_phone
                    send_customer_service_review_sms_to_phone(
                        sale.customer_phone,
                        recipient_name=sale.customer_name or 'Customer',
                        message_type='pharmacy_dispensing_feedback',
                        related_object_id=sale.id if hasattr(sale, 'id') else None,
                        related_object_type='WalkInSale',
                    )
                except Exception as e:
                    logger.warning("Could not send customer service review SMS: %s", e)

            messages.success(
                request,
                f'✅ Medication dispensed successfully to {sale.customer_name}!'
            )

            return redirect('hospital:pharmacy_walkin_sale_detail', sale_id=sale_id)

        except Exception as e:
            logger.error(f"Error dispensing walk-in sale: {str(e)}", exc_info=True)
            messages.error(request, f'❌ Error dispensing: {str(e)}')

    items = sale.items.filter(is_deleted=False).select_related('drug')
    can_dispense = _can_dispense_now()
    context = {
        'title': f'Dispense Prescribe Sale - {sale.sale_number}',
        'sale': sale,
        'items': items,
        'can_dispense': can_dispense,
        'is_billed_to_company': getattr(sale, 'is_billed_to_company', False),
        'show_payment_confirm': (not can_dispense) and _user_can_confirm_walkin_invoice_payment_collected(request.user),
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
    API endpoint to search drugs for walk-in sales.
    Stock quantity from BOTH PharmacyStock and InventoryItem (pharmacy store)
    so changes in either place show in pharmacy.
    Unit prices use get_drug_price_for_prescription (same as consultation and dispensing).
    """
    query = request.GET.get('q', '')
    
    if len(query) < 2:
        return JsonResponse({'drugs': []})

    from .utils_billing import get_drug_price_for_prescription

    search_payer = payer_for_pharmacy_drug_search(request)
    
    drugs = Drug.objects.filter(
        Q(name__icontains=query) | Q(generic_name__icontains=query) | Q(atc_code__icontains=query) | Q(strength__icontains=query),
        is_active=True,
        is_deleted=False
    )[:25]
    
    # Get pharmacy store for InventoryItem (procurement/inventory system)
    pharmacy_store = None
    try:
        from .models_procurement import Store, InventoryItem
        pharmacy_store = Store.get_main_pharmacy_store()
    except Exception:
        pass
    
    results = []
    for drug in drugs:
        # Stock from PharmacyStock (tally, admin)
        stock_ps = PharmacyStock.objects.filter(
            drug=drug,
            quantity_on_hand__gt=0,
            is_deleted=False
        ).aggregate(total=Sum('quantity_on_hand'))['total'] or 0
        
        # Stock from InventoryItem - pharmacy store (procurement, store transfers)
        stock_inv = 0
        if pharmacy_store:
            try:
                inv = InventoryItem.objects.filter(
                    store=pharmacy_store,
                    drug=drug,
                    is_deleted=False,
                    is_active=True
                ).aggregate(total=Sum('quantity_on_hand'))['total'] or 0
                stock_inv = inv
            except Exception:
                pass
        
        # Use the higher - inventory may be updated in store, PharmacyStock in tally/admin
        stock_qty = max(stock_ps, stock_inv)

        unit_price = get_drug_price_for_prescription(drug, payer=search_payer)
        results.append({
            'id': drug.id,
            'name': drug.name,
            'generic_name': drug.generic_name,
            'strength': drug.strength,
            'form': drug.form,
            'unit_price': str(unit_price.quantize(Decimal('0.01'))),
            'stock_available': stock_qty,
        })
    
    return JsonResponse({'drugs': results})


@login_required
def api_patient_search(request):
    """
    API endpoint to search registered patients
    Includes deposit balance and recent encounter information
    antenatal=1: Prioritize antenatal patients (females with antenatal encounters)
    """
    query = request.GET.get('q', '').strip()
    antenatal_only = request.GET.get('antenatal', '').lower() in ('1', 'true', 'yes')
    
    if len(query) < 2:
        return JsonResponse({'patients': []})
    
    # Enhanced search: also search by full name combination
    query_parts = query.split()
    search_query = Q(
        Q(first_name__icontains=query) |
        Q(last_name__icontains=query) |
        Q(middle_name__icontains=query) |
        Q(mrn__icontains=query) |
        Q(phone_number__icontains=query)
    )
    
    # If query has multiple words, search for full name combinations
    if len(query_parts) >= 2:
        first_part = query_parts[0]
        last_parts = ' '.join(query_parts[1:])
        search_query |= Q(
            Q(first_name__icontains=first_part) &
            Q(last_name__icontains=last_parts)
        )
        search_query |= Q(
            Q(first_name__icontains=last_parts) &
            Q(last_name__icontains=first_part)
        )
    
    base_qs = Patient.objects.filter(
        search_query,
        is_deleted=False
    ).exclude(id__isnull=True).select_related('primary_insurance').distinct()
    
    # When antenatal=1, prioritize antenatal patients (females with antenatal encounters)
    if antenatal_only:
        from .models import Encounter
        antenatal_patient_ids = Encounter.objects.filter(
            is_deleted=False,
            encounter_type__icontains='antenatal'
        ).values_list('patient_id', flat=True).distinct()
        antenatal_qs = base_qs.filter(
            id__in=antenatal_patient_ids,
            gender='F'
        )[:15]
        other_qs = base_qs.exclude(id__in=antenatal_patient_ids)[:10]
        patients = list(antenatal_qs) + list(other_qs)
        seen = set()
        patients = [p for p in patients if p.id not in seen and not seen.add(p.id)][:20]
    else:
        patients = list(base_qs[:20])
    
    # Import validation utility
    from hospital.utils_patient_validation import is_valid_patient_id
    from hospital.models_patient_deposits import PatientDeposit
    from hospital.models import Encounter
    from django.db.models import Count, Sum
    
    results = []
    for p in patients:
        # Validate patient ID - skip if invalid
        if not is_valid_patient_id(p.id):
            continue
        
        # Get deposit balance
        deposit_balance = Decimal('0.00')
        try:
            deposit_sum = PatientDeposit.objects.filter(
                patient=p,
                status='active',
                is_deleted=False
            ).aggregate(total=Sum('available_balance'))['total']
            deposit_balance = deposit_sum if deposit_sum else Decimal('0.00')
        except Exception:
            pass
        
        # Get recent encounter count (last 30 days)
        recent_encounters = 0
        try:
            from django.utils import timezone
            from datetime import timedelta
            thirty_days_ago = timezone.now() - timedelta(days=30)
            recent_encounters = Encounter.objects.filter(
                patient=p,
                is_deleted=False,
                started_at__gte=thirty_days_ago
            ).count()
        except Exception:
            pass
        
        # Get payer type
        payer_type = 'cash'
        if p.primary_insurance:
            payer_type = p.primary_insurance.payer_type or 'cash'
        
        results.append({
            'id': str(p.id),
            'name': p.full_name,
            'full_name': p.full_name,
            'mrn': p.mrn,
            'phone': p.phone_number or '',
            'deposit_balance': float(deposit_balance),
            'recent_encounters': recent_encounters,
            'payer_type': payer_type,
        })
    
    return JsonResponse({'patients': results})













