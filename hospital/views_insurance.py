"""
Views for Insurance Claims Management
World-class insurance tracking and monthly claims generation
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Sum, Count, Avg
from django.utils import timezone
from django.core.paginator import Paginator
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST
from decimal import Decimal
from datetime import date, datetime
import calendar

from .models import Patient, Invoice, InvoiceLine, Payer, ServiceCode
from .models_insurance import InsuranceClaimItem, MonthlyInsuranceClaim
from .insurance_claim_query import insurance_claim_item_deduped_q


@login_required
def insurance_claims_dashboard(request):
    """Main dashboard for insurance claims management"""
    today = timezone.now().date()
    current_month = today.month
    current_year = today.year
    
    # Statistics
    _claim_base = InsuranceClaimItem.objects.filter(is_deleted=False).filter(
        insurance_claim_item_deduped_q()
    )
    stats = {
        'total_pending_claims': _claim_base.filter(claim_status='pending').count(),
        'total_submitted_claims': _claim_base.filter(
            claim_status__in=['submitted', 'processing'],
        ).count(),
        'total_paid_claims': _claim_base.filter(claim_status='paid').count(),
        'total_rejected_claims': _claim_base.filter(claim_status='rejected').count(),
        'total_outstanding_amount': (
            (
                _claim_base.filter(
                    claim_status__in=[
                        'pending',
                        'submitted',
                        'processing',
                        'approved',
                        'partially_paid',
                    ],
                ).aggregate(total=Sum('billed_amount'))['total']
                or Decimal('0.00')
            )
            - (
                _claim_base.filter(
                    claim_status__in=[
                        'pending',
                        'submitted',
                        'processing',
                        'approved',
                        'partially_paid',
                    ],
                ).aggregate(total=Sum('paid_amount'))['total']
                or Decimal('0.00')
            )
        ),
    }
    
    # Monthly claims statistics
    monthly_claims = MonthlyInsuranceClaim.objects.filter(
        claim_year=current_year,
        claim_month=current_month,
        is_deleted=False
    ).select_related('payer').annotate(
        item_count=Count('claim_items')
    )
    
    # Recent claim items
    recent_claims = (
        InsuranceClaimItem.objects.filter(is_deleted=False)
        .filter(insurance_claim_item_deduped_q())
        .select_related('patient', 'payer')
        .order_by('-created')[:10]
    )
    
    # Claims by status
    claims_by_status = (
        InsuranceClaimItem.objects.filter(is_deleted=False)
        .filter(insurance_claim_item_deduped_q())
        .values('claim_status')
        .annotate(count=Count('id'), total_amount=Sum('billed_amount'))
        .order_by('claim_status')
    )
    
    context = {
        'stats': stats,
        'monthly_claims': monthly_claims,
        'recent_claims': recent_claims,
        'claims_by_status': claims_by_status,
        'current_month': calendar.month_name[current_month],
        'current_year': current_year,
    }
    
    return render(request, 'hospital/insurance/claims_dashboard.html', context)


@login_required
def insurance_claim_items_list(request):
    """List all insurance claim items with filtering"""
    query = request.GET.get('q', '')
    status_filter = request.GET.get('status', '')
    payer_filter = request.GET.get('payer', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    claim_items = (
        InsuranceClaimItem.objects.filter(is_deleted=False)
        .filter(insurance_claim_item_deduped_q())
        .select_related('patient', 'payer', 'invoice', 'service_code')
    )
    
    if query:
        claim_items = claim_items.filter(
            Q(patient__first_name__icontains=query) |
            Q(patient__last_name__icontains=query) |
            Q(patient__mrn__icontains=query) |
            Q(patient_insurance_id__icontains=query) |
            Q(service_description__icontains=query) |
            Q(claim_reference__icontains=query)
        )
    
    if status_filter:
        claim_items = claim_items.filter(claim_status=status_filter)
    
    if payer_filter:
        claim_items = claim_items.filter(payer_id=payer_filter)
    
    if date_from:
        try:
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d').date()
            claim_items = claim_items.filter(service_date__gte=date_from_obj)
        except ValueError:
            pass
    
    if date_to:
        try:
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d').date()
            claim_items = claim_items.filter(service_date__lte=date_to_obj)
        except ValueError:
            pass
    
    claim_items = claim_items.order_by('-service_date', '-created')
    
    # Statistics
    stats = claim_items.aggregate(
        total_items=Count('id'),
        total_billed=Sum('billed_amount'),
        total_paid=Sum('paid_amount'),
        total_outstanding=Sum('billed_amount') - Sum('paid_amount') if Sum('billed_amount') else Decimal('0.00')
    )
    
    paginator = Paginator(claim_items, 50)
    page = request.GET.get('page')
    claim_items_page = paginator.get_page(page)
    
    payers = Payer.objects.filter(is_active=True, is_deleted=False, payer_type__in=['nhis', 'private', 'corporate'])
    
    context = {
        'claim_items': claim_items_page,
        'stats': stats,
        'payers': payers,
        'query': query,
        'status_filter': status_filter,
        'payer_filter': payer_filter,
        'date_from': date_from,
        'date_to': date_to,
    }
    
    return render(request, 'hospital/insurance/claim_items_list.html', context)


@login_required
def insurance_claim_item_detail(request, pk):
    """View detailed information about a specific claim item"""
    claim_item = get_object_or_404(InsuranceClaimItem, pk=pk, is_deleted=False)
    
    context = {
        'claim_item': claim_item,
    }
    
    return render(request, 'hospital/insurance/claim_item_detail.html', context)


@login_required
def monthly_claims_list(request):
    """List all monthly insurance claims"""
    query = request.GET.get('q', '')
    payer_filter = request.GET.get('payer', '')
    year_filter = request.GET.get('year', str(timezone.now().year))
    month_filter = request.GET.get('month', '')
    status_filter = request.GET.get('status', '')
    
    monthly_claims = MonthlyInsuranceClaim.objects.filter(
        is_deleted=False
    ).select_related('payer')
    
    if payer_filter:
        monthly_claims = monthly_claims.filter(payer_id=payer_filter)
    
    if year_filter:
        try:
            monthly_claims = monthly_claims.filter(claim_year=int(year_filter))
        except ValueError:
            pass
    
    if month_filter:
        try:
            monthly_claims = monthly_claims.filter(claim_month=int(month_filter))
        except ValueError:
            pass
    
    if status_filter:
        monthly_claims = monthly_claims.filter(status=status_filter)
    
    if query:
        monthly_claims = monthly_claims.filter(
            Q(claim_number__icontains=query) |
            Q(payer__name__icontains=query) |
            Q(submission_reference__icontains=query)
        )
    
    monthly_claims = monthly_claims.order_by('-claim_year', '-claim_month', '-created')
    
    paginator = Paginator(monthly_claims, 25)
    page = request.GET.get('page')
    monthly_claims_page = paginator.get_page(page)
    
    payers = Payer.objects.filter(is_active=True, is_deleted=False, payer_type__in=['nhis', 'private', 'corporate'])
    current_year = timezone.now().year
    years = range(current_year - 5, current_year + 2)
    months = [(i, calendar.month_name[i]) for i in range(1, 13)]
    
    context = {
        'monthly_claims': monthly_claims_page,
        'payers': payers,
        'years': years,
        'months': months,
        'query': query,
        'payer_filter': payer_filter,
        'year_filter': year_filter,
        'month_filter': month_filter,
        'status_filter': status_filter,
    }
    
    return render(request, 'hospital/insurance/monthly_claims_list.html', context)


@login_required
def monthly_claim_detail(request, pk):
    """View detailed information about a monthly claim"""
    monthly_claim = get_object_or_404(MonthlyInsuranceClaim, pk=pk, is_deleted=False)
    claim_items = monthly_claim.claim_items.all().select_related(
        'patient', 'invoice', 'service_code'
    ).order_by('service_date', 'patient')
    
    # Summary statistics
    summary = {
        'by_status': claim_items.values('claim_status').annotate(
            count=Count('id'),
            total_billed=Sum('billed_amount'),
            total_paid=Sum('paid_amount')
        ),
        'by_service': claim_items.values('service_code__code', 'service_code__description').annotate(
            count=Count('id'),
            total_billed=Sum('billed_amount')
        ).order_by('-count')[:10],
    }
    
    context = {
        'monthly_claim': monthly_claim,
        'claim_items': claim_items,
        'summary': summary,
    }
    
    return render(request, 'hospital/insurance/monthly_claim_detail.html', context)


@login_required
@require_POST
def generate_monthly_claims(request):
    """Generate monthly claims for all payers for a specific month/year"""
    month = int(request.POST.get('month', timezone.now().month))
    year = int(request.POST.get('year', timezone.now().year))
    
    # Get all active insurance payers
    payers = Payer.objects.filter(
        is_active=True,
        is_deleted=False,
        payer_type__in=['nhis', 'private', 'corporate']
    )
    
    created_count = 0
    updated_count = 0
    
    for payer in payers:
        # Get all pending claim items for this payer in this month
        claim_items = (
            InsuranceClaimItem.objects.filter(
                payer=payer,
                service_date__year=year,
                service_date__month=month,
                claim_status='pending',
                monthly_claim__isnull=True,
                is_deleted=False,
            ).filter(insurance_claim_item_deduped_q())
        )
        
        if not claim_items.exists():
            continue
        
        # Get or create monthly claim
        monthly_claim, created = MonthlyInsuranceClaim.objects.get_or_create(
            payer=payer,
            claim_month=month,
            claim_year=year,
            defaults={
                'status': 'draft',
            }
        )
        
        # Add claim items to monthly claim
        monthly_claim.add_claim_items(claim_items)
        
        if created:
            created_count += 1
        else:
            updated_count += 1
        
        messages.success(request, f'Monthly claim generated for {payer.name}: {claim_items.count()} items')
    
    if created_count == 0 and updated_count == 0:
        messages.info(request, 'No pending claims found for the selected month/year')
    else:
        messages.success(request, f'Generated {created_count} new monthly claims, updated {updated_count} existing claims')
    
    return redirect('hospital:monthly_claims_list')


@login_required
@require_POST
def submit_monthly_claim(request, pk):
    """Submit monthly claim to insurance company"""
    monthly_claim = get_object_or_404(MonthlyInsuranceClaim, pk=pk, is_deleted=False)
    submission_reference = request.POST.get('submission_reference', '')
    
    monthly_claim.mark_as_submitted(submission_reference)
    
    messages.success(request, f'Monthly claim {monthly_claim.claim_number} submitted successfully')
    return redirect('hospital:monthly_claim_detail', pk=monthly_claim.pk)


@login_required
def patient_insurance_claims(request, patient_id):
    """View all insurance claims for a specific patient"""
    patient = get_object_or_404(Patient, pk=patient_id, is_deleted=False)
    
    claim_items = (
        InsuranceClaimItem.objects.filter(patient=patient, is_deleted=False)
        .filter(insurance_claim_item_deduped_q())
        .select_related('payer', 'invoice', 'service_code')
        .order_by('-service_date')
    )
    
    # Statistics
    stats = claim_items.aggregate(
        total_claims=Count('id'),
        total_billed=Sum('billed_amount'),
        total_paid=Sum('paid_amount'),
        total_outstanding=Sum('billed_amount') - Sum('paid_amount') if Sum('billed_amount') else Decimal('0.00')
    )
    
    # By status
    by_status = claim_items.values('claim_status').annotate(
        count=Count('id'),
        total=Sum('billed_amount')
    )
    
    context = {
        'patient': patient,
        'claim_items': claim_items,
        'stats': stats,
        'by_status': by_status,
    }
    
    return render(request, 'hospital/insurance/patient_claims.html', context)


# ==================== URL alias views ====================

@login_required
def insurance_list(request):
    """Redirect to insurance claims dashboard"""
    return redirect('hospital:insurance_claims_dashboard')


@login_required
def claims_list(request):
    """Alias for insurance_claim_items_list"""
    return insurance_claim_items_list(request)


@login_required
def claim_detail(request, pk):
    """Alias for insurance_claim_item_detail"""
    return insurance_claim_item_detail(request, pk)


@login_required
def create_claim_from_invoice(request, invoice_id):
    """Create insurance claim items from an invoice"""
    invoice = get_object_or_404(Invoice, pk=invoice_id, is_deleted=False)
    
    # Check if patient has insurance
    if not invoice.patient.primary_insurance:
        messages.error(request, f'Patient {invoice.patient.full_name} does not have primary insurance set.')
        return redirect('hospital:invoice_detail', pk=invoice.pk)
    
    payer = invoice.payer or invoice.patient.primary_insurance
    
    # Get patient insurance ID
    patient_insurance_id = (
        invoice.patient.insurance_member_id or 
        invoice.patient.insurance_id or 
        invoice.patient.insurance_policy_number or
        ''
    )
    
    if not patient_insurance_id:
        messages.warning(request, 'Patient insurance ID not set. Please set it in patient profile.')
    
    # Create claim items from invoice lines
    created_count = 0
    for line in invoice.lines.filter(is_deleted=False):
        # Check if claim item already exists for this invoice line
        existing_claim = InsuranceClaimItem.objects.filter(
            invoice_line=line,
            is_deleted=False
        ).first()
        
        if existing_claim:
            continue
        
        # Get service date from invoice or encounter
        service_date = invoice.issued_at.date()
        if invoice.encounter:
            service_date = invoice.encounter.started_at.date()
        
        # Create claim item
        claim_item = InsuranceClaimItem.objects.create(
            patient=invoice.patient,
            payer=payer,
            patient_insurance_id=patient_insurance_id,
            invoice=invoice,
            invoice_line=line,
            encounter=invoice.encounter,
            service_code=line.service_code,
            service_description=line.description,
            service_date=service_date,
            billed_amount=line.line_total,
            claim_status='pending',
        )
        created_count += 1
    
    if created_count > 0:
        messages.success(request, f'Created {created_count} insurance claim item(s) from invoice.')
    else:
        messages.info(request, 'No new claim items created. Claim items may already exist for this invoice.')
    
    return redirect('hospital:invoice_detail', pk=invoice.pk)


@login_required
@require_POST
def submit_claim(request, pk):
    """Submit a single insurance claim item"""
    claim_item = get_object_or_404(InsuranceClaimItem, pk=pk, is_deleted=False)
    claim_reference = request.POST.get('claim_reference', '')
    
    if claim_item.claim_status != 'pending':
        messages.warning(request, f'Claim is already {claim_item.get_claim_status_display()}. Cannot submit again.')
        return redirect('hospital:claim_detail', pk=claim_item.pk)
    
    claim_item.mark_as_submitted(claim_reference)
    messages.success(request, f'Claim submitted successfully with reference: {claim_reference or "N/A"}')
    
    return redirect('hospital:claim_detail', pk=claim_item.pk)


@login_required
@require_POST
def process_claim_payment(request, pk):
    """Process payment for an insurance claim item"""
    claim_item = get_object_or_404(InsuranceClaimItem, pk=pk, is_deleted=False)
    
    try:
        paid_amount = Decimal(request.POST.get('paid_amount', '0'))
        approved_amount = Decimal(request.POST.get('approved_amount', paid_amount))
        
        if paid_amount <= 0:
            messages.error(request, 'Paid amount must be greater than zero.')
            return redirect('hospital:claim_detail', pk=claim_item.pk)
        
        if approved_amount:
            claim_item.mark_as_approved(approved_amount)
        
        claim_item.mark_as_paid(paid_amount)
        
        messages.success(request, f'Payment of {paid_amount} GHS processed for claim.')
        return redirect('hospital:claim_detail', pk=claim_item.pk)
        
    except (ValueError, TypeError) as e:
        messages.error(request, f'Invalid payment amount: {str(e)}')
        return redirect('hospital:claim_detail', pk=claim_item.pk)
