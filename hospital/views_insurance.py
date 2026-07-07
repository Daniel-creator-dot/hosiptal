"""
Views for Insurance Claims Management
World-class insurance tracking and monthly claims generation
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist
import json
from urllib.parse import urlencode

from django.db.models import Q, Sum, Count, Avg
from django.db.models.functions import TruncMonth
from django.utils import timezone
from django.core.paginator import Paginator
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST
from decimal import Decimal
from datetime import date, datetime, timedelta
import calendar

from .models import Patient, Invoice, InvoiceLine, Payer, ServiceCode
from .models_insurance import InsuranceClaimItem, MonthlyInsuranceClaim
from .insurance_claim_query import (
    apply_insurance_claim_item_filters,
    batch_insurance_plan_names_for_patients,
    insurance_claim_item_deduped_q,
    paginate_claim_patient_groups,
)


def _apply_insurance_claim_item_filters(qs, get_params):
    """Backward-compatible alias."""
    return apply_insurance_claim_item_filters(qs, get_params)


def _parse_dashboard_date(s):
    if not s:
        return None
    try:
        return datetime.strptime(s.strip(), '%Y-%m-%d').date()
    except ValueError:
        return None


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

    query = (request.GET.get('q') or '').strip()
    status_filter = (request.GET.get('status') or '').strip()
    payer_filter = (request.GET.get('payer') or '').strip()
    date_from = (request.GET.get('date_from') or '').strip()
    date_to = (request.GET.get('date_to') or '').strip()

    try:
        per_page = int(request.GET.get('per_page', '25'))
    except (TypeError, ValueError):
        per_page = 25
    per_page = max(10, min(per_page, 100))

    filtered_qs = _apply_insurance_claim_item_filters(_claim_base, request.GET)
    filtered_ordered = filtered_qs.order_by('-service_date', '-created')

    filtered_summary = filtered_ordered.aggregate(
        total_items=Count('id'),
        total_billed=Sum('billed_amount'),
        total_paid=Sum('paid_amount'),
    )
    tb = filtered_summary.get('total_billed') or Decimal('0.00')
    tp = filtered_summary.get('total_paid') or Decimal('0.00')
    filtered_summary['total_outstanding'] = tb - tp

    encounter_filter = (request.GET.get('encounter') or '').strip()
    recent_claims_page, groups_truncated = paginate_claim_patient_groups(
        filtered_qs,
        per_page=per_page,
        page_number=request.GET.get('page'),
    )

    claims_by_status = (
        filtered_ordered.values('claim_status')
        .annotate(count=Count('id'), total_amount=Sum('billed_amount'))
        .order_by('claim_status')
    )

    df = _parse_dashboard_date(date_from)
    dt = _parse_dashboard_date(date_to)
    if df and dt and df > dt:
        df, dt = dt, df
    if df and not dt:
        chart_to = today
        chart_from = df
    elif dt and not df:
        chart_to = dt
        chart_from = dt - timedelta(days=365)
    elif df and dt:
        chart_from, chart_to = df, dt
    else:
        chart_to = today
        chart_from = today - timedelta(days=395)
    if (chart_to - chart_from).days > 800:
        chart_from = chart_to - timedelta(days=800)

    trend_qs = (
        _claim_base.filter(service_date__gte=chart_from, service_date__lte=chart_to)
        .annotate(month=TruncMonth('service_date'))
        .values('month')
        .annotate(item_count=Count('id'), total_billed=Sum('billed_amount'))
        .order_by('month')
    )
    chart_monthly_trend = []
    for row in trend_qs:
        m = row['month']
        if m is None:
            continue
        if isinstance(m, datetime):
            label = timezone.localtime(m).strftime('%b %Y') if timezone.is_aware(m) else m.strftime('%b %Y')
        elif isinstance(m, date):
            label = m.strftime('%b %Y')
        else:
            label = str(m)[:7]
        chart_monthly_trend.append(
            {
                'label': label,
                'count': row['item_count'],
                'billed': float(row['total_billed'] or 0),
            }
        )

    payer_qs = (
        _claim_base.filter(service_date__gte=chart_from, service_date__lte=chart_to)
        .values('payer__name')
        .annotate(item_count=Count('id'), total_billed=Sum('billed_amount'))
        .order_by('-total_billed')[:12]
    )
    chart_top_payers = [
        {
            'name': (row['payer__name'] or 'Unknown')[:80],
            'count': row['item_count'],
            'billed': float(row['total_billed'] or 0),
        }
        for row in payer_qs
    ]

    payers = Payer.objects.filter(
        is_active=True, is_deleted=False, payer_type__in=['nhis', 'private', 'corporate']
    ).order_by('name')

    qd = request.GET.copy()
    qd.pop('page', None)
    pagination_base = qd.urlencode()

    filters_active = bool(
        query or status_filter or payer_filter or date_from or date_to or encounter_filter
    )
    has_any_claims = _claim_base.exists()
    filtered_empty = not filtered_ordered.exists()

    _list_filters = {}
    for k in ('q', 'status', 'payer', 'date_from', 'date_to', 'encounter'):
        v = (request.GET.get(k) or '').strip()
        if v:
            _list_filters[k] = v
    claim_items_list_query = urlencode(_list_filters) if _list_filters else ''

    context = {
        'stats': stats,
        'monthly_claims': monthly_claims,
        'recent_claims': recent_claims_page,
        'claims_grouped_by_patient': True,
        'claims_groups_truncated': groups_truncated,
        'encounter_filter': encounter_filter,
        'claims_by_status': claims_by_status,
        'current_month': calendar.month_name[current_month],
        'current_year': current_year,
        'query': query,
        'status_filter': status_filter,
        'payer_filter': payer_filter,
        'date_from': date_from,
        'date_to': date_to,
        'per_page': per_page,
        'payers': payers,
        'claim_status_choices': InsuranceClaimItem.CLAIM_STATUS_CHOICES,
        'filtered_summary': filtered_summary,
        'filters_active': filters_active,
        'pagination_base': pagination_base,
        'chart_monthly_trend_json': json.dumps(chart_monthly_trend),
        'chart_top_payers_json': json.dumps(chart_top_payers),
        'chart_range_label': f'{chart_from.isoformat()} → {chart_to.isoformat()}',
        'today_iso': today.isoformat(),
        'preset_7_from': (today - timedelta(days=7)).isoformat(),
        'preset_30_from': (today - timedelta(days=30)).isoformat(),
        'month_start_iso': today.replace(day=1).isoformat(),
        'has_any_claims': has_any_claims,
        'filtered_empty': filtered_empty,
        'claim_items_list_query': claim_items_list_query,
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
    claim_items = _apply_insurance_claim_item_filters(claim_items, request.GET)
    claim_items_ordered = claim_items.order_by('-service_date', '-created')

    # Statistics
    stats = claim_items_ordered.aggregate(
        total_items=Count('id'),
        total_billed=Sum('billed_amount'),
        total_paid=Sum('paid_amount'),
        total_outstanding=Sum('billed_amount') - Sum('paid_amount') if Sum('billed_amount') else Decimal('0.00')
    )

    claim_items_page, groups_truncated = paginate_claim_patient_groups(
        claim_items,
        per_page=50,
        page_number=request.GET.get('page'),
    )
    
    payers = Payer.objects.filter(is_active=True, is_deleted=False, payer_type__in=['nhis', 'private', 'corporate'])
    
    encounter_filter = (request.GET.get('encounter') or '').strip()

    context = {
        'claim_items': claim_items_page,
        'claims_grouped_by_patient': True,
        'claims_groups_truncated': groups_truncated,
        'stats': stats,
        'payers': payers,
        'query': query,
        'status_filter': status_filter,
        'payer_filter': payer_filter,
        'date_from': date_from,
        'date_to': date_to,
        'encounter_filter': encounter_filter,
    }

    return render(request, 'hospital/insurance/claim_items_list.html', context)


@login_required
def insurance_claim_item_detail(request, pk):
    """View detailed information about a specific claim item"""
    claim_item = get_object_or_404(
        InsuranceClaimItem.objects.select_related(
            'patient', 'payer', 'invoice', 'service_code', 'encounter', 'encounter__provider__user'
        ),
        pk=pk,
        is_deleted=False,
    )
    admission_icd10 = ''
    enc = claim_item.encounter
    if enc:
        try:
            admission_icd10 = (enc.admission.diagnosis_icd10 or '').strip()
        except ObjectDoesNotExist:
            pass

    plan_map = batch_insurance_plan_names_for_patients([claim_item.patient_id])
    insurance_plan_name = plan_map.get(claim_item.patient_id, '')

    context = {
        'claim_item': claim_item,
        'admission_icd10': admission_icd10,
        'insurance_plan_name': insurance_plan_name,
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
