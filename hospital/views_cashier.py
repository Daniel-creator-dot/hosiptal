"""
Cashier and Payment Processing Views
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q, Sum, F
from django.http import JsonResponse
from django.core.paginator import Paginator
from datetime import date, timedelta
from decimal import Decimal
from .models import Patient, Invoice, Admission
from .models_workflow import Bill, PaymentRequest, CashierSession
from .models_accounting import Transaction, PaymentReceipt
from .models_payment_verification import LabResultRelease, PharmacyDispensing
from .services.auto_billing_service import AutoBillingService
from .utils_roles import user_has_cashier_access
from .models_pharmacy_walkin import WalkInPharmacySale
from .services.pharmacy_walkin_service import WalkInPharmacyService


def is_cashier(user):
    """Only allow Administrators and Accounting to access cashier views."""
    return user_has_cashier_access(user)


@login_required
@user_passes_test(is_cashier, login_url='/admin/login/')
def cashier_dashboard(request):
    """
    Unified Cashier Dashboard
    Shows ALL pending payments: Bills, Lab Tests, Prescriptions, Invoices
    """
    # Get or create open session
    session = CashierSession.objects.filter(
        cashier=request.user,
        status='open',
        is_deleted=False
    ).first()
    
    if not session:
        session = CashierSession.objects.create(
            cashier=request.user,
            opening_cash=Decimal('0.00'),
        )
    else:
        # Recalculate totals to ensure accuracy
        session.calculate_totals()
    
    # 🧪 PENDING LAB TESTS (not paid)
    from .models import LabResult, Prescription
    
    # Include tests that are either verified OR explicitly sent to cashier
    all_labs = LabResult.objects.filter(
        is_deleted=False
    ).filter(
        Q(verified_by__isnull=False) | Q(release_record__sent_to_cashier_at__isnull=False)
    ).select_related(
        'test',
        'order__encounter__patient',
        'release_record'
    ).order_by('-created')
    
    pending_labs = []
    for lab in all_labs:
        release_record = getattr(lab, 'release_record', None)

        # Skip if already paid
        if release_record and release_record.payment_receipt_id:
            continue

        # Ensure a bill exists for this lab
        try:
            AutoBillingService.create_lab_bill(lab)
        except Exception:
            # Don't block the dashboard if billing fails; lab should still be visible
            pass

        pending_labs.append(lab)
    
    # 💊 PENDING PRESCRIPTIONS (not paid)
    all_prescriptions = Prescription.objects.filter(
        is_deleted=False
    ).select_related('drug', 'order__encounter__patient', 'prescribed_by').order_by('-created')
    
    pending_pharmacy = []
    for rx in all_prescriptions:
        try:
            if hasattr(rx, 'dispensing_record') and rx.dispensing_record.payment_receipt:
                continue  # Already paid
        except:
            pass
        # Ensure bill exists
        try:
            if not hasattr(rx, 'dispensing_record'):
                AutoBillingService.create_pharmacy_bill(rx)
        except:
            pass
        # Calculate total price
        unit_price = getattr(rx.drug, 'unit_price', Decimal('0.00'))
        rx.total_price = unit_price * rx.quantity
        pending_pharmacy.append(rx)
    
    # 💼 Walk-in sales awaiting payment
    walkin_qs = WalkInPharmacySale.objects.filter(
        is_deleted=False,
        payment_status__in=['pending', 'partial']
    ).select_related('patient').order_by('-sale_date')
    
    pending_walkin_sales = []
    for sale in walkin_qs:
        patient = WalkInPharmacyService.ensure_sale_patient(sale)
        sale.patient = patient
        sale.pending_amount = sale.amount_due or (sale.total_amount - sale.amount_paid)
        if sale.pending_amount and sale.pending_amount < 0:
            sale.pending_amount = Decimal('0.00')
        pending_walkin_sales.append(sale)
    
    # Get pending payment requests (existing system)
    pending_payments = PaymentRequest.objects.filter(
        status='pending',
        is_deleted=False
    ).select_related('patient', 'invoice')[:20]
    
    # Today's statistics
    today = timezone.now().date()
    today_transactions = Transaction.objects.filter(
        processed_by=request.user,
        transaction_date__date=today,
        is_deleted=False
    )
    
    today_total = today_transactions.filter(
        transaction_type='payment_received'
    ).aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')
    
    today_count = today_transactions.count()
    
    # Unpaid bills (existing system)
    unpaid_bills = Bill.objects.filter(
        status__in=['issued', 'partially_paid'],
        patient_portion__gt=0,
        is_deleted=False
    ).select_related('patient', 'invoice')[:20]
    
    # Get outstanding debt summary
    outstanding_debt = Invoice.objects.filter(
        status__in=['issued', 'partially_paid', 'overdue'],
        balance__gt=0,
        is_deleted=False
    ).aggregate(Sum('balance'))['balance__sum'] or Decimal('0.00')
    
    # Get patients with debt
    patients_with_debt_count = Patient.objects.filter(
        invoices__balance__gt=0,
        invoices__status__in=['issued', 'partially_paid', 'overdue'],
        invoices__is_deleted=False,
        is_deleted=False
    ).distinct().count()
    
    total_pending_payments = pending_payments.count() + len(pending_labs) + len(pending_pharmacy) + len(pending_walkin_sales)

    context = {
        'session': session,
        'pending_payments': pending_payments,
        'unpaid_bills': unpaid_bills,
        'pending_labs': pending_labs[:20],  # NEW: Lab tests
        'pending_pharmacy': pending_pharmacy[:20],  # NEW: Pharmacy
        'pending_walkin_sales': pending_walkin_sales[:20],
        'today_total': today_total,
        'today_count': today_count,
        'outstanding_debt': outstanding_debt,
        'patients_with_debt_count': patients_with_debt_count,
        'total_pending_labs': len(pending_labs),
        'total_pending_pharmacy': len(pending_pharmacy),
        'total_pending_walkin': len(pending_walkin_sales),
        'total_pending_payments': total_pending_payments,
    }
    return render(request, 'hospital/cashier_dashboard.html', context)


@login_required
@user_passes_test(is_cashier, login_url='/admin/login/')
def process_payment(request, payment_request_id=None, bill_id=None, invoice_id=None):
    """Process payment for a bill, invoice, or payment request"""
    if payment_request_id:
        payment_request = get_object_or_404(PaymentRequest, pk=payment_request_id, is_deleted=False)
        invoice = payment_request.invoice
        bill = invoice.bills.filter(is_deleted=False).first()
    elif bill_id:
        bill = get_object_or_404(Bill, pk=bill_id, is_deleted=False)
        invoice = bill.invoice
        payment_request = None
    elif invoice_id:
        invoice = get_object_or_404(Invoice, pk=invoice_id, is_deleted=False)
        bill = invoice.bills.filter(is_deleted=False).first()
        payment_request = None
    else:
        messages.error(request, 'Invalid payment request')
        return redirect('hospital:cashier_dashboard')
    
    if request.method == 'POST':
        amount_paid = Decimal(request.POST.get('amount', 0))
        payment_method = request.POST.get('payment_method', 'cash')
        reference_number = request.POST.get('reference_number', '')
        
        if amount_paid <= 0:
            messages.error(request, 'Payment amount must be greater than zero')
            if invoice_id:
                return redirect('hospital:process_payment_invoice', invoice_id=invoice_id)
            elif bill_id:
                return redirect('hospital:process_payment_bill', bill_id=bill_id)
            else:
                return redirect('hospital:cashier_dashboard')
        
        # Use invoice directly if no bill
        if not invoice:
            if bill:
                invoice = bill.invoice
            else:
                messages.error(request, 'Invalid payment request - no invoice or bill')
                return redirect('hospital:cashier_dashboard')
        
        # Create transaction
        transaction = Transaction.objects.create(
            transaction_type='payment_received',
            invoice=invoice,
            patient=invoice.patient,
            amount=amount_paid,
            payment_method=payment_method,
            reference_number=reference_number,
            processed_by=request.user,
            notes=request.POST.get('notes', ''),
        )
        
        # Detect service type from bill/invoice
        service_type = 'other'  # Default
        if bill:
            # Detect from bill type or items
            if hasattr(bill, 'service_type'):
                service_type = bill.service_type
            elif hasattr(bill, 'bill_type'):
                # Map bill_type to service_type
                type_mapping = {
                    'lab': 'lab',
                    'laboratory': 'lab',
                    'pharmacy': 'pharmacy',
                    'medication': 'pharmacy',
                    'imaging': 'imaging',
                    'radiology': 'imaging',
                    'consultation': 'consultation',
                    'procedure': 'procedure',
                    'admission': 'admission',
                    'emergency': 'emergency',
                }
                service_type = type_mapping.get(bill.bill_type, 'other')
        elif invoice and hasattr(invoice, 'encounter'):
            # Detect from encounter type
            encounter = invoice.encounter
            if encounter:
                if encounter.encounter_type == 'er':
                    service_type = 'emergency'
                elif encounter.encounter_type == 'surgery':
                    service_type = 'procedure'
                elif encounter.current_activity:
                    # Check current activities
                    if 'Lab' in encounter.current_activity:
                        service_type = 'lab'
                    elif 'Pharmacy' in encounter.current_activity:
                        service_type = 'pharmacy'
                    elif 'Imaging' in encounter.current_activity:
                        service_type = 'imaging'
                    elif 'Consulting' in encounter.current_activity:
                        service_type = 'consultation'
        
        # Create payment receipt with service type
        receipt = PaymentReceipt.objects.create(
            transaction=transaction,
            invoice=invoice,
            patient=invoice.patient,
            amount_paid=amount_paid,
            payment_method=payment_method,
            received_by=request.user,
            service_type=service_type,  # Track service type for revenue reporting
        )
        
        # Update bill status if exists
        if bill:
            remaining = bill.patient_portion - amount_paid
            if remaining <= 0:
                bill.status = 'paid'
                bill.patient_portion = Decimal('0.00')
            else:
                bill.status = 'partially_paid'
                bill.patient_portion = remaining
            bill.save()
        
        # Update invoice
        paid_amount = invoice.total_amount - invoice.balance + amount_paid
        if paid_amount >= invoice.total_amount:
            invoice.status = 'paid'
            invoice.balance = Decimal('0.00')
        else:
            invoice.status = 'partially_paid'
            invoice.balance = invoice.total_amount - paid_amount
        invoice.save()
        
        # Calculate remaining for payment request status
        remaining = invoice.balance
        
        # Update payment request if exists
        if payment_request:
            payment_request.status = 'completed' if remaining <= 0 else 'processing'
            payment_request.processed_by = request.user
            payment_request.processed_at = timezone.now()
            payment_request.save()
        
        # Update cashier session
        session = CashierSession.objects.filter(
            cashier=request.user,
            status='open',
            is_deleted=False
        ).first()
        if session:
            session.calculate_totals()
        
        messages.success(request, f'Payment of GHS {amount_paid} processed. Receipt: {receipt.receipt_number}')
        return redirect('hospital:payment_receipt', receipt_id=receipt.pk)
    
    # If processing from invoice directly, get or create a bill
    if invoice and not bill:
        bill = invoice.bills.filter(is_deleted=False).first()
    
    # Ensure we have a valid invoice or bill
    if not invoice and not bill:
        messages.error(request, 'Invalid payment request - no invoice or bill found')
        return redirect('hospital:cashier_dashboard')
    
    # Get patient from invoice or bill
    patient = None
    if invoice:
        patient = invoice.patient
    elif bill:
        patient = bill.patient
    
    context = {
        'invoice': invoice,
        'bill': bill,
        'patient': patient,
        'payment_request': payment_request,
    }
    return render(request, 'hospital/process_payment.html', context)


@login_required
@user_passes_test(is_cashier, login_url='/admin/login/')
def payment_receipt(request, receipt_id):
    """Display payment receipt"""
    receipt = get_object_or_404(PaymentReceipt, pk=receipt_id, is_deleted=False)
    
    context = {
        'receipt': receipt,
    }
    return render(request, 'hospital/payment_receipt.html', context)


@login_required
@user_passes_test(is_cashier, login_url='/admin/login/')
def close_session(request, session_id):
    """Close cashier session and reconcile"""
    session = get_object_or_404(CashierSession, pk=session_id, is_deleted=False, cashier=request.user)
    
    if request.method == 'POST':
        actual_cash = Decimal(request.POST.get('actual_cash', 0))
        closing_notes = request.POST.get('notes', '')
        
        session.closing_cash = actual_cash
        session.actual_cash = actual_cash
        session.notes = closing_notes
        session.closed_at = timezone.now()
        session.status = 'closed'
        session.save()
        
        messages.success(request, 'Session closed successfully')
        return redirect('hospital:cashier_dashboard')
    
    # Calculate expected totals
    session.calculate_totals()
    
    context = {
        'session': session,
    }
    return render(request, 'hospital/close_session.html', context)


@login_required
@user_passes_test(is_cashier, login_url='/admin/login/')
def cashier_session_detail(request):
    """
    Show the cashier's active session (or open a new one) with quick stats.
    """
    session = CashierSession.objects.filter(
        cashier=request.user,
        status='open',
        is_deleted=False
    ).first()

    if not session:
        session = CashierSession.objects.create(
            cashier=request.user,
            opening_cash=Decimal('0.00'),
        )

    session.calculate_totals()

    today = timezone.now().date()
    recent_transactions = Transaction.objects.filter(
        processed_by=request.user,
        transaction_date__date=today,
        is_deleted=False
    ).order_by('-transaction_date')[:15]

    recent_receipts = PaymentReceipt.objects.filter(
        received_by=request.user,
        receipt_date__date=today,
        is_deleted=False
    ).select_related('patient').order_by('-receipt_date')[:15]

    context = {
        'session': session,
        'recent_transactions': recent_transactions,
        'recent_receipts': recent_receipts,
        'today': today,
    }
    return render(request, 'hospital/cashier_session_detail.html', context)


@login_required
@user_passes_test(is_cashier, login_url='/admin/login/')
def cashier_bills(request):
    """List all payment receipts (bills) for cashier"""
    from .models_accounting import PaymentReceipt
    
    status_filter = request.GET.get('status', '')
    query = request.GET.get('q', '')
    
    # Use PaymentReceipts instead of Bills (modern payment system)
    receipts = PaymentReceipt.objects.filter(is_deleted=False).select_related(
        'patient', 'invoice', 'received_by', 'transaction'
    ).order_by('-receipt_date')
    
    if query:
        receipts = receipts.filter(
            Q(receipt_number__icontains=query) |
            Q(patient__first_name__icontains=query) |
            Q(patient__last_name__icontains=query) |
            Q(patient__mrn__icontains=query)
        )
    
    # Map invoice status to payment status for filtering
    if status_filter:
        if status_filter == 'paid':
            # Show all receipts (they're all paid by definition)
            pass
        elif status_filter == 'issued':
            # Show recent receipts
            from datetime import timedelta
            from django.utils import timezone
            receipts = receipts.filter(receipt_date__gte=timezone.now() - timedelta(days=7))
    
    # Statistics - use PaymentReceipts instead of Bills
    # Total issued = all receipts from last 30 days
    from datetime import timedelta
    from django.utils import timezone
    last_30_days = timezone.now() - timedelta(days=30)
    
    total_issued = PaymentReceipt.objects.filter(
        receipt_date__gte=last_30_days,
        is_deleted=False
    ).count()
    
    total_paid = PaymentReceipt.objects.filter(is_deleted=False).count()
    
    total_revenue = PaymentReceipt.objects.filter(
        is_deleted=False
    ).aggregate(Sum('amount_paid'))['amount_paid__sum'] or Decimal('0.00')
    
    # Outstanding = unpaid invoices (not from receipts)
    from .models import Invoice
    total_outstanding = Invoice.objects.filter(
        status__in=['issued', 'partially_paid', 'overdue'],
        balance__gt=0,
        is_deleted=False
    ).aggregate(Sum('balance'))['balance__sum'] or Decimal('0.00')
    
    receipts_list = list(receipts[:50])
    context = {
        'bills': receipts_list,  # Keep variable name for template compatibility
        'bills_count': len(receipts_list),
        'status_filter': status_filter,
        'total_issued': total_issued,
        'total_paid': total_paid,
        'total_outstanding': total_outstanding,
    }
    return render(request, 'hospital/cashier_bills.html', context)


@login_required
@user_passes_test(is_cashier, login_url='/admin/login/')
def cashier_invoices(request):
    """List all invoices for cashier"""
    status_filter = request.GET.get('status', '')
    query = request.GET.get('q', '')
    patient_mrn = request.GET.get('patient_mrn', '')
    
    invoices = Invoice.objects.filter(is_deleted=False).select_related(
        'patient', 'payer', 'encounter'
    ).order_by('-issued_at')
    
    # If patient_mrn is provided, redirect to patient invoices page
    if patient_mrn:
        try:
            patient = Patient.objects.get(mrn__iexact=patient_mrn, is_deleted=False)
            return redirect('hospital:cashier_patient_invoices', patient_id=patient.pk)
        except Patient.DoesNotExist:
            messages.warning(request, f'Patient with MRN "{patient_mrn}" not found')
    
    if query:
        invoices = invoices.filter(
            Q(invoice_number__icontains=query) |
            Q(patient__first_name__icontains=query) |
            Q(patient__last_name__icontains=query) |
            Q(patient__mrn__icontains=query)
        )
    
    if status_filter:
        # Handle comma-separated status filters
        status_list = [s.strip() for s in status_filter.split(',') if s.strip()]
        if len(status_list) > 1:
            invoices = invoices.filter(status__in=status_list)
        elif len(status_list) == 1:
            invoices = invoices.filter(status=status_list[0])
    
    # Statistics
    total_invoices = invoices.count()
    total_revenue = Invoice.objects.filter(
        status='paid',
        is_deleted=False
    ).aggregate(Sum('total_amount'))['total_amount__sum'] or Decimal('0.00')
    
    outstanding_balance = Invoice.objects.filter(
        status__in=['issued', 'partially_paid', 'overdue'],
        balance__gt=0,
        is_deleted=False
    ).aggregate(Sum('balance'))['balance__sum'] or Decimal('0.00')
    
    paginator = Paginator(invoices, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'invoices': page_obj,
        'status_filter': status_filter,
        'query': query,
        'total_invoices': total_invoices,
        'total_revenue': total_revenue,
        'outstanding_balance': outstanding_balance,
    }
    return render(request, 'hospital/cashier_invoices.html', context)


@login_required
@user_passes_test(is_cashier, login_url='/admin/login/')
def cashier_invoice_detail(request, pk):
    """Invoice detail view for cashier"""
    invoice = get_object_or_404(Invoice, pk=pk, is_deleted=False)
    invoice_lines = invoice.lines.filter(is_deleted=False)
    
    # Get payment history
    transactions = Transaction.objects.filter(
        invoice=invoice,
        is_deleted=False
    ).order_by('-transaction_date')[:10]
    
    context = {
        'invoice': invoice,
        'invoice_lines': invoice_lines,
        'transactions': transactions,
    }
    return render(request, 'hospital/cashier_invoice_detail.html', context)


@login_required
@user_passes_test(is_cashier, login_url='/admin/login/')
def customer_debt(request):
    """
    Enhanced Customer Debt Tracking
    Includes: Unpaid Invoices + Unpaid Lab Tests + Unpaid Pharmacy
    """
    query = request.GET.get('q', '')
    min_debt = request.GET.get('min_debt', '0')
    
    try:
        min_debt = Decimal(min_debt)
    except (ValueError, TypeError):
        min_debt = Decimal('0.00')
    
    # Get all patients (we'll calculate debt for each)
    patients = Patient.objects.filter(is_deleted=False)
    
    if query:
        patients = patients.filter(
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(mrn__icontains=query) |
            Q(phone_number__icontains=query)
        )
    
    # Calculate debt for each patient
    patient_debts = []
    
    for patient in patients:
        # 1. Invoice debt
        invoice_debt = Invoice.objects.filter(
            patient=patient,
            balance__gt=0,
            status__in=['issued', 'partially_paid', 'overdue'],
            is_deleted=False
        ).aggregate(Sum('balance'))['balance__sum'] or Decimal('0.00')
        
        # 2. Unpaid Lab Tests debt
        from .models import LabResult
        lab_tests = LabResult.objects.filter(
            order__encounter__patient=patient,
            is_deleted=False,
            verified_by__isnull=False
        )
        
        lab_debt = Decimal('0.00')
        unpaid_labs = []
        for lab in lab_tests:
            try:
                if not (hasattr(lab, 'release_record') and lab.release_record.payment_receipt):
                    lab_debt += lab.test.price
                    unpaid_labs.append(lab)
            except:
                lab_debt += lab.test.price
                unpaid_labs.append(lab)
        
        # 3. Unpaid Pharmacy debt
        from .models import Prescription
        prescriptions = Prescription.objects.filter(
            order__encounter__patient=patient,
            is_deleted=False
        )
        
        pharmacy_debt = Decimal('0.00')
        unpaid_prescriptions = []
        for rx in prescriptions:
            try:
                if not (hasattr(rx, 'dispensing_record') and rx.dispensing_record.payment_receipt):
                    unit_price = getattr(rx.drug, 'unit_price', Decimal('0.00'))
                    rx_total = unit_price * rx.quantity
                    pharmacy_debt += rx_total
                    rx.total_price = rx_total
                    unpaid_prescriptions.append(rx)
            except:
                unit_price = getattr(rx.drug, 'unit_price', Decimal('0.00'))
                rx_total = unit_price * rx.quantity
                pharmacy_debt += rx_total
                rx.total_price = rx_total
                unpaid_prescriptions.append(rx)
        
        # 4. Unpaid Bed Charges (Active Admissions)
        bed_debt = Decimal('0.00')
        active_admissions = []
        patient_admissions = Admission.objects.filter(
            encounter__patient=patient,
            status='admitted',
            is_deleted=False
        ).select_related('ward', 'bed', 'encounter')
        
        for admission in patient_admissions:
            try:
                from .services.bed_billing_service import bed_billing_service
                charges = bed_billing_service.get_bed_charges_summary(admission)
                bed_debt += charges['current_charges']
                admission.bed_charges = charges
                active_admissions.append(admission)
            except:
                pass
        
        # Total debt for this patient
        total_patient_debt = invoice_debt + lab_debt + pharmacy_debt + bed_debt
        
        # Only include patients with debt >= min_debt
        if total_patient_debt >= min_debt:
            outstanding_invoices = Invoice.objects.filter(
                patient=patient,
                balance__gt=0,
                status__in=['issued', 'partially_paid', 'overdue'],
                is_deleted=False
            ).order_by('-issued_at')
            
            patient_debts.append({
                'patient': patient,
                'total_debt': total_patient_debt,
                'invoice_debt': invoice_debt,
                'lab_debt': lab_debt,
                'pharmacy_debt': pharmacy_debt,
                'bed_debt': bed_debt,
                'invoice_count': outstanding_invoices.count(),
                'invoices': outstanding_invoices[:5],
                'unpaid_labs': unpaid_labs[:5],
                'unpaid_prescriptions': unpaid_prescriptions[:5],
                'active_admissions': active_admissions[:5],
                'unpaid_labs_count': len(unpaid_labs),
                'unpaid_prescriptions_count': len(unpaid_prescriptions),
                'active_admissions_count': len(active_admissions),
            })
    
    # Sort by total debt descending
    patient_debts.sort(key=lambda x: x['total_debt'], reverse=True)
    
    # Calculate total debt
    total_debt = sum(item['total_debt'] for item in patient_debts)
    total_invoice_debt = sum(item['invoice_debt'] for item in patient_debts)
    total_lab_debt = sum(item['lab_debt'] for item in patient_debts)
    total_pharmacy_debt = sum(item['pharmacy_debt'] for item in patient_debts)
    total_bed_debt = sum(item['bed_debt'] for item in patient_debts)
    
    paginator = Paginator(patient_debts, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'patient_debts': page_obj,
        'total_debt': total_debt,
        'total_invoice_debt': total_invoice_debt,
        'total_lab_debt': total_lab_debt,
        'total_pharmacy_debt': total_pharmacy_debt,
        'total_bed_debt': total_bed_debt,
        'query': query,
        'min_debt': min_debt,
        'patient_count': len(patient_debts),
    }
    return render(request, 'hospital/customer_debt.html', context)


@login_required
@user_passes_test(is_cashier, login_url='/admin/login/')
def patient_invoices(request, patient_id):
    """View all invoices for a specific patient"""
    patient = get_object_or_404(Patient, pk=patient_id, is_deleted=False)
    
    invoices = Invoice.objects.filter(
        patient=patient,
        is_deleted=False
    ).select_related('payer', 'encounter').order_by('-issued_at')
    
    # Calculate total outstanding
    outstanding = invoices.filter(
        balance__gt=0,
        status__in=['issued', 'partially_paid', 'overdue']
    ).aggregate(Sum('balance'))['balance__sum'] or Decimal('0.00')
    
    # Total paid
    total_paid = invoices.filter(
        status='paid'
    ).aggregate(Sum('total_amount'))['total_amount__sum'] or Decimal('0.00')
    
    context = {
        'patient': patient,
        'invoices': invoices,
        'outstanding': outstanding,
        'total_paid': total_paid,
    }
    return render(request, 'hospital/patient_invoices.html', context)

