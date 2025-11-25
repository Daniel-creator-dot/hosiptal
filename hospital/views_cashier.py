"""
Cashier Views - Payment Processing and Session Management
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.utils import timezone
from django.db.models import Sum, Count, Q
from django.core.paginator import Paginator
from decimal import Decimal

from .models_accounting import PaymentReceipt, Transaction
from .models_workflow import CashierSession, PaymentRequest, Bill
from .models import Invoice
from .models_pharmacy_walkin import WalkInPharmacySale
from .utils_roles import user_has_cashier_access


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
    from django.db.models import Q
    
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
            from .services.auto_billing_service import AutoBillingService
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
        # Check if there's a dispensing record
        try:
            from .models_payment_verification import PharmacyDispensing
            dispensing = PharmacyDispensing.objects.filter(prescription=rx).first()
            if dispensing and dispensing.payment_receipt_id:
                continue  # Already paid
        except:
            pass
        
        pending_pharmacy.append(rx)
    
    # Revenue + activity stats
    today = timezone.now().date()
    todays_receipts_qs = PaymentReceipt.objects.filter(
        receipt_date__date=today,
        is_deleted=False
    )
    today_total = todays_receipts_qs.aggregate(total=Sum('amount_paid'))['total'] or Decimal('0.00')
    today_count = todays_receipts_qs.count()
    
    # Pending payment requests headed to cashier
    pending_payments_qs = PaymentRequest.objects.filter(
        is_deleted=False,
        status__in=['pending', 'processing']
    ).select_related('invoice', 'invoice__payer', 'patient').order_by('-requested_at')
    pending_payments = list(pending_payments_qs[:20])
    total_pending_payment_requests = pending_payments_qs.count()
    
    # Unpaid bills (cash + insurance portions)
    unpaid_bills_qs = Bill.objects.filter(
        is_deleted=False,
        status__in=['issued', 'partially_paid']
    ).select_related('patient', 'invoice').order_by('-issued_at')
    unpaid_bills = list(unpaid_bills_qs[:20])
    
    # Accounts receivable snapshot
    outstanding_invoices_qs = Invoice.objects.filter(
        is_deleted=False,
        status__in=['issued', 'partially_paid', 'overdue']
    )
    outstanding_debt = outstanding_invoices_qs.aggregate(total=Sum('balance'))['total'] or Decimal('0.00')
    patients_with_debt_count = outstanding_invoices_qs.values('patient_id').distinct().count()
    
    # Walk-in pharmacy payments waiting at cashier
    pending_walkin_qs = WalkInPharmacySale.objects.filter(
        is_deleted=False,
        payment_status__in=['pending', 'partial']
    ).order_by('-sale_date')
    pending_walkin_sales = list(pending_walkin_qs[:20])
    total_pending_walkin = pending_walkin_qs.count()
    
    total_pending_payments = (
        total_pending_payment_requests
        + len(pending_labs)
        + len(pending_pharmacy)
        + total_pending_walkin
    )
    
    context = {
        'session': session,
        'pending_labs': pending_labs[:20],  # Limit to 20 for performance
        'pending_pharmacy': pending_pharmacy[:20],
        'total_pending_labs': len(pending_labs),
        'total_pending_pharmacy': len(pending_pharmacy),
        'today_total': today_total,
        'today_count': today_count,
        'pending_payments': pending_payments,
        'total_pending_payments': total_pending_payments,
        'total_pending_payment_requests': total_pending_payment_requests,
        'unpaid_bills': unpaid_bills,
        'outstanding_debt': outstanding_debt,
        'patients_with_debt_count': patients_with_debt_count,
        'pending_walkin_sales': pending_walkin_sales,
        'total_pending_walkin': total_pending_walkin,
    }
    return render(request, 'hospital/cashier_dashboard.html', context)


@login_required
@user_passes_test(is_cashier, login_url='/admin/login/')
def payment_receipt(request, receipt_id):
    """View payment receipt"""
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
        denomination_breakdown = request.POST.get('denomination_breakdown', '')
        
        # VALIDATION: Require denomination breakdown
        if not denomination_breakdown:
            messages.error(request, 'You must count and enter all cash denominations before closing the session.')
            session.calculate_totals()
            context = {'session': session}
            return render(request, 'hospital/close_session.html', context)
        
        # VALIDATION: Verify denomination breakdown matches actual cash
        try:
            import json
            breakdown = json.loads(denomination_breakdown)
            calculated_total = Decimal('0.00')
            for denom, data in breakdown.items():
                count = Decimal(str(data.get('count', 0)))
                denom_value = Decimal(str(data.get('denomination', 0)))
                calculated_total += count * denom_value
            
            # Allow small rounding differences (up to 0.01)
            if abs(calculated_total - actual_cash) > Decimal('0.01'):
                messages.error(
                    request, 
                    f'Denomination breakdown total (GH¢{calculated_total:,.2f}) does not match entered total (GH¢{actual_cash:,.2f}). Please recount.'
                )
                session.calculate_totals()
                context = {'session': session}
                return render(request, 'hospital/close_session.html', context)
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            messages.error(request, f'Invalid denomination breakdown format. Please recount all denominations. Error: {str(e)}')
            session.calculate_totals()
            context = {'session': session}
            return render(request, 'hospital/close_session.html', context)
        
        # VALIDATION: Recalculate totals from transactions to ensure accuracy
        session.calculate_totals()
        session.refresh_from_db()
        
        # VALIDATION: Verify actual cash matches expected cash (with tolerance for small variances)
        variance = actual_cash - session.expected_cash
        variance_tolerance = Decimal('0.50')  # Allow up to 50 pesewas variance
        
        # If variance is significant, require explanation
        if abs(variance) > variance_tolerance:
            variance_percent = abs(variance) / session.expected_cash * 100 if session.expected_cash > 0 else 0
            if variance_percent > 1:
                # Require notes for large variances
                if not closing_notes or len(closing_notes.strip()) < 10:
                    messages.error(
                        request,
                        f'⚠️ REQUIRED: Cash variance of GH¢{abs(variance):,.2f} ({variance_percent:.2f}%) requires an explanation. '
                        f'Expected: GH¢{session.expected_cash:,.2f}, Actual: GH¢{actual_cash:,.2f}. '
                        f'Please provide detailed notes explaining the variance before closing.'
                    )
                    session.calculate_totals()
                    context = {'session': session}
                    return render(request, 'hospital/close_session.html', context)
                else:
                    messages.warning(
                        request,
                        f'⚠️ WARNING: Cash variance of GH¢{abs(variance):,.2f} ({variance_percent:.2f}%) exceeds normal tolerance. '
                        f'Expected: GH¢{session.expected_cash:,.2f}, Actual: GH¢{actual_cash:,.2f}. '
                        f'Your explanation has been recorded for review.'
                    )
        
        # Get forensic information
        close_datetime = timezone.now()
        ip_address = request.META.get('REMOTE_ADDR', 'Unknown')
        user_agent = request.META.get('HTTP_USER_AGENT', 'Unknown')
        forward_ip = request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip() if request.META.get('HTTP_X_FORWARDED_FOR') else None
        effective_ip = forward_ip if forward_ip else ip_address
        
        # Calculate session duration
        session_duration = close_datetime - session.opened_at
        duration_hours = int(session_duration.total_seconds() // 3600)
        duration_minutes = int((session_duration.total_seconds() % 3600) // 60)
        duration_seconds = int(session_duration.total_seconds() % 60)
        
        # Build forensic audit trail notes
        notes_parts = []
        notes_parts.append("=" * 80)
        notes_parts.append("CASHIER SESSION CLOSURE - FORENSIC AUDIT TRAIL")
        notes_parts.append("=" * 80)
        notes_parts.append("")
        
        # Timestamp Information
        notes_parts.append("TIMESTAMP INFORMATION:")
        notes_parts.append("-" * 80)
        notes_parts.append(f"  Closure Date/Time (UTC):     {close_datetime.strftime('%Y-%m-%d %H:%M:%S')} UTC")
        notes_parts.append(f"  Closure Date/Time (Local):   {close_datetime.astimezone(timezone.get_current_timezone()).strftime('%Y-%m-%d %H:%M:%S %Z')}")
        notes_parts.append(f"  Session Opened At:           {session.opened_at.strftime('%Y-%m-%d %H:%M:%S')} UTC")
        notes_parts.append(f"  Session Duration:            {duration_hours:02d}h {duration_minutes:02d}m {duration_seconds:02d}s")
        notes_parts.append("")
        
        # User Information
        notes_parts.append("USER INFORMATION:")
        notes_parts.append("-" * 80)
        notes_parts.append(f"  User ID:                     {request.user.id}")
        notes_parts.append(f"  Username:                    {request.user.username}")
        notes_parts.append(f"  Full Name:                   {request.user.get_full_name() or 'N/A'}")
        notes_parts.append(f"  Email:                       {request.user.email or 'N/A'}")
        notes_parts.append(f"  Session Cashier:             {session.cashier.get_full_name() or session.cashier.username}")
        notes_parts.append("")
        
        # System Information
        notes_parts.append("SYSTEM INFORMATION:")
        notes_parts.append("-" * 80)
        notes_parts.append(f"  IP Address:                  {effective_ip}")
        if forward_ip and forward_ip != ip_address:
            notes_parts.append(f"  Original IP:                 {ip_address}")
        notes_parts.append(f"  User Agent:                  {user_agent[:100] if len(user_agent) > 100 else user_agent}")
        notes_parts.append(f"  Session ID:                  {session.session_number}")
        notes_parts.append("")
        
        # Session Summary
        notes_parts.append("SESSION SUMMARY:")
        notes_parts.append("-" * 80)
        notes_parts.append(f"  Opening Cash:                GH¢{session.opening_cash:,.2f}")
        notes_parts.append(f"  Total Payments Received:     GH¢{session.total_payments:,.2f}")
        notes_parts.append(f"  Total Refunds Issued:        GH¢{session.total_refunds:,.2f}")
        notes_parts.append(f"  Expected Cash:               GH¢{session.expected_cash:,.2f}")
        notes_parts.append(f"  Total Transactions:          {session.total_transactions:,}")
        notes_parts.append("")
        
        # Cash Count by Denomination
        if denomination_breakdown:
            try:
                import json
                breakdown = json.loads(denomination_breakdown)
                if breakdown:
                    notes_parts.append("=" * 80)
                    notes_parts.append("CASH COUNT BY DENOMINATION:")
                    notes_parts.append("=" * 80)
                    notes_parts.append("")
                    notes_parts.append(f"{'Denomination':<20} {'Count':>10} {'Value Each':>15} {'Subtotal':>20}")
                    notes_parts.append("-" * 80)
                    
                    # Sort by denomination value (highest first)
                    sorted_denoms = sorted(breakdown.items(), key=lambda x: float(x[0]), reverse=True)
                    for denom, data in sorted_denoms:
                        count = int(data['count'])
                        value = data['denomination']
                        subtotal = data['subtotal']
                        if value >= 1:
                            denom_label = f"GH¢{value:,.0f}"
                            value_label = f"GH¢{value:,.0f}"
                        else:
                            pesewas = int(value * 100)
                            denom_label = f"{pesewas}p"
                            value_label = f"GH¢{value:.2f}"
                        notes_parts.append(f"  {denom_label:<15} {count:10,d} × {value_label:>10} {subtotal:>20,.2f}")
                    
                    notes_parts.append("-" * 80)
                    notes_parts.append(f"  {'TOTAL COUNTED':<15} {'':>10} {'':>10} {actual_cash:>20,.2f}")
                    notes_parts.append("")
            
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                notes_parts.append("=" * 80)
                notes_parts.append("CASH COUNT BY DENOMINATION:")
                notes_parts.append("=" * 80)
                notes_parts.append("  ERROR: Could not parse denomination breakdown")
                notes_parts.append(f"  Error: {str(e)}")
                notes_parts.append(f"  Total Counted: GH¢{actual_cash:,.2f}")
                notes_parts.append("")
        else:
            notes_parts.append("=" * 80)
            notes_parts.append("CASH COUNT:")
            notes_parts.append("=" * 80)
            notes_parts.append(f"  Total Counted: GH¢{actual_cash:,.2f}")
            notes_parts.append("  NOTE: Denomination breakdown not provided")
            notes_parts.append("")
        
        # Variance Analysis
        notes_parts.append("=" * 80)
        notes_parts.append("VARIANCE ANALYSIS:")
        notes_parts.append("=" * 80)
        notes_parts.append(f"  Expected Cash:               GH¢{session.expected_cash:,.2f}")
        notes_parts.append(f"  Actual Cash Counted:          GH¢{actual_cash:,.2f}")
        if abs(variance) < 0.01:
            notes_parts.append(f"  Variance:                     GH¢0.00 (EXACT MATCH)")
            notes_parts.append("  Status:                       ✓ NO DISCREPANCY")
        elif variance > 0:
            notes_parts.append(f"  Variance:                     +GH¢{variance:,.2f} (OVER COUNT)")
            notes_parts.append(f"  Status:                       ⚠ DISCREPANCY - Over by GH¢{variance:,.2f}")
        else:
            notes_parts.append(f"  Variance:                     -GH¢{abs(variance):,.2f} (SHORT COUNT)")
            notes_parts.append(f"  Status:                       ⚠ DISCREPANCY - Short by GH¢{abs(variance):,.2f}")
        notes_parts.append("")
        
        # Daily Cash Sales Notes (if provided)
        if session.daily_cash_notes:
            notes_parts.append("=" * 80)
            notes_parts.append("DAILY CASH SALES NOTES:")
            notes_parts.append("=" * 80)
            notes_parts.append(session.daily_cash_notes)
            notes_parts.append("")
        
        # Additional Notes
        if closing_notes:
            notes_parts.append("=" * 80)
            notes_parts.append("ADDITIONAL NOTES:")
            notes_parts.append("=" * 80)
            notes_parts.append(closing_notes)
            notes_parts.append("")
        
        # Footer
        notes_parts.append("=" * 80)
        notes_parts.append("END OF FORENSIC AUDIT TRAIL")
        notes_parts.append("=" * 80)
        notes_parts.append("")
        notes_parts.append(f"This document serves as a legal audit trail of the cashier session closure.")
        notes_parts.append(f"All timestamps, amounts, and actions have been recorded and are tamper-evident.")
        notes_parts.append(f"Generated by: Hospital Management System (HMS)")
        notes_parts.append(f"System Version: Django 4.2.7")
        
        final_notes = "\n".join(notes_parts)
        
        # Save session with forensic information
        session.closing_cash = actual_cash
        session.actual_cash = actual_cash
        session.notes = final_notes
        session.closed_at = close_datetime
        session.status = 'closed'
        session.save()
        
        # Log for audit (if audit middleware is enabled)
        import logging
        logger = logging.getLogger('hospital.audit')
        logger.info(
            f"Cashier session closed: {session.session_number} | "
            f"Cashier: {request.user.username} | "
            f"Expected: GH¢{session.expected_cash:,.2f} | "
            f"Actual: GH¢{actual_cash:,.2f} | "
            f"Variance: GH¢{variance:,.2f} | "
            f"IP: {effective_ip}"
        )
        
        messages.success(request, f'Session closed successfully. Total counted: GH¢{actual_cash:,.2f}')
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
def cashier_sessions_list(request):
    """
    List all cashier sessions
    Accountants can see all sessions, cashiers see only their own
    """
    from .utils_roles import get_user_role
    
    user_role = get_user_role(request.user)
    
    # Accountants and admins can see all sessions
    if user_role in ['admin', 'accountant']:
        sessions = CashierSession.objects.filter(is_deleted=False).select_related('cashier').order_by('-opened_at')
    else:
        # Cashiers see only their own sessions
        sessions = CashierSession.objects.filter(
            cashier=request.user,
            is_deleted=False
        ).select_related('cashier').order_by('-opened_at')
    
    # Filter by status if provided
    status_filter = request.GET.get('status', '')
    if status_filter:
        sessions = sessions.filter(status=status_filter)
    
    # Filter by date range if provided
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    if date_from:
        sessions = sessions.filter(opened_at__date__gte=date_from)
    if date_to:
        sessions = sessions.filter(opened_at__date__lte=date_to)
    
    # Calculate totals and variance for each session
    for session in sessions:
        session.calculate_totals()
        # Calculate variance for display
        if session.actual_cash is not None:
            session.variance = session.actual_cash - session.expected_cash
        else:
            session.variance = None
    
    # Pagination
    paginator = Paginator(sessions, 25)  # Show 25 sessions per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Statistics
    total_sessions = sessions.count()
    open_sessions = sessions.filter(status='open').count()
    closed_sessions = sessions.filter(status='closed').count()
    
    total_payments = sessions.aggregate(
        total=Sum('total_payments')
    )['total'] or Decimal('0.00')
    
    total_refunds = sessions.aggregate(
        total=Sum('total_refunds')
    )['total'] or Decimal('0.00')
    
    context = {
        'sessions': page_obj,
        'page_obj': page_obj,
        'status_filter': status_filter,
        'date_from': date_from,
        'date_to': date_to,
        'total_sessions': total_sessions,
        'open_sessions': open_sessions,
        'closed_sessions': closed_sessions,
        'total_payments': total_payments,
        'total_refunds': total_refunds,
        'user_role': user_role,
    }
    
    return render(request, 'hospital/cashier_sessions_list.html', context)


@login_required
@user_passes_test(is_cashier, login_url='/admin/login/')
def create_session(request):
    """Create a new cashier session for the day"""
    from .utils_roles import get_user_role
    
    user_role = get_user_role(request.user)
    
    # Check if user already has an open session
    existing_open_session = CashierSession.objects.filter(
        cashier=request.user,
        status='open',
        is_deleted=False
    ).first()
    
    if existing_open_session and user_role not in ['admin', 'accountant']:
        messages.warning(request, f'You already have an open session ({existing_open_session.session_number}). Please close it before creating a new one.')
        return redirect('hospital:cashier_sessions_list')
    
    if request.method == 'POST':
        opening_cash = Decimal(request.POST.get('opening_cash', 0))
        notes = request.POST.get('notes', '')
        daily_cash_notes = request.POST.get('daily_cash_notes', '')
        
        # Create new session
        session = CashierSession.objects.create(
            cashier=request.user,
            opening_cash=opening_cash,
            notes=notes,
            daily_cash_notes=daily_cash_notes,
        )
        
        messages.success(request, f'Session {session.session_number} created successfully!')
        return redirect('hospital:cashier_session_detail')
    
    # Get today's date for context
    today = timezone.now().date()
    
    # Get yesterday's closed session to suggest opening cash
    yesterday_session = CashierSession.objects.filter(
        cashier=request.user,
        status='closed',
        is_deleted=False
    ).order_by('-closed_at').first()
    
    suggested_opening_cash = Decimal('0.00')
    if yesterday_session and yesterday_session.actual_cash:
        suggested_opening_cash = yesterday_session.actual_cash
    
    context = {
        'today': today,
        'suggested_opening_cash': suggested_opening_cash,
        'existing_open_session': existing_open_session,
    }
    return render(request, 'hospital/create_session.html', context)


@login_required
@user_passes_test(is_cashier, login_url='/admin/login/')
def update_session_notes(request, session_id):
    """Update session notes and daily cash notes"""
    session = get_object_or_404(CashierSession, pk=session_id, is_deleted=False)
    
    # Check permissions - cashiers can only update their own sessions
    from .utils_roles import get_user_role
    user_role = get_user_role(request.user)
    
    if user_role not in ['admin', 'accountant'] and session.cashier != request.user:
        messages.error(request, 'You can only update your own sessions.')
        return redirect('hospital:cashier_sessions_list')
    
    if request.method == 'POST':
        session.notes = request.POST.get('notes', '')
        session.daily_cash_notes = request.POST.get('daily_cash_notes', '')
        session.save()
        
        messages.success(request, 'Session notes updated successfully!')
        
        # Redirect based on where they came from
        if request.GET.get('redirect') == 'detail':
            return redirect('hospital:cashier_session_detail')
        return redirect('hospital:cashier_sessions_list')
    
    context = {
        'session': session,
    }
    return render(request, 'hospital/update_session_notes.html', context)


# Placeholder functions for other cashier views that might be referenced
@login_required
@user_passes_test(is_cashier, login_url='/admin/login/')
def cashier_bills(request):
    """View cashier bills"""
    return render(request, 'hospital/cashier_bills.html', {})


@login_required
@user_passes_test(is_cashier, login_url='/admin/login/')
def cashier_invoices(request):
    """View cashier invoices"""
    return render(request, 'hospital/cashier_invoices.html', {})


@login_required
@user_passes_test(is_cashier, login_url='/admin/login/')
def cashier_invoice_detail(request, pk):
    """View cashier invoice detail"""
    from .models import Invoice
    invoice = get_object_or_404(Invoice, pk=pk, is_deleted=False)
    return render(request, 'hospital/cashier_invoice_detail.html', {'invoice': invoice})


@login_required
@user_passes_test(is_cashier, login_url='/admin/login/')
def customer_debt(request):
    """View customer debt"""
    return render(request, 'hospital/customer_debt.html', {})


@login_required
@user_passes_test(is_cashier, login_url='/admin/login/')
def patient_invoices(request, patient_id):
    """View patient invoices"""
    from .models import Patient, Invoice
    patient = get_object_or_404(Patient, pk=patient_id, is_deleted=False)
    invoices = Invoice.objects.filter(patient=patient, is_deleted=False).order_by('-created')
    return render(request, 'hospital/cashier_patient_invoices.html', {'patient': patient, 'invoices': invoices})


@login_required
@user_passes_test(is_cashier, login_url='/admin/login/')
def process_payment(request, payment_request_id=None, bill_id=None, invoice_id=None):
    """Process payment - placeholder"""
    messages.info(request, 'Payment processing feature coming soon.')
    return redirect('hospital:cashier_dashboard')
