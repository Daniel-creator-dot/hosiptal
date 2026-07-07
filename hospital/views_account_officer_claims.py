"""
Claims-focused accounting workspace for Account Officers (e.g. insurance claims billing & receivables).
"""
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count
from django.shortcuts import render
from django.utils import timezone
from decimal import Decimal

from .decorators import role_required
from .models_insurance import InsuranceClaimItem, MonthlyInsuranceClaim
from .models_accounting_advanced import InsuranceReceivable
from .insurance_claim_query import insurance_claim_item_deduped_q


@login_required
@role_required('account_officer', 'admin')
def claims_accounting_dashboard(request):
    """Home dashboard for account officers working on insurance claims and related receivables."""
    today = timezone.now().date()
    start_of_month = today.replace(day=1)

    def safe_query(fn, default=None):
        if default is None:
            default = 0
        try:
            return fn()
        except Exception:
            return default

    base_items = InsuranceClaimItem.objects.filter(is_deleted=False).filter(
        insurance_claim_item_deduped_q()
    )

    pending_qs = base_items.filter(claim_status='pending')
    in_flight_statuses = ('submitted', 'processing', 'approved', 'partially_paid')
    in_flight_qs = base_items.filter(claim_status__in=in_flight_statuses)
    rejected_qs = base_items.filter(claim_status='rejected')
    paid_month_qs = base_items.filter(
        claim_status='paid',
        paid_date__gte=start_of_month,
        paid_date__lte=today,
    )

    pending_count = safe_query(lambda: pending_qs.count(), 0)
    pending_billed = safe_query(
        lambda: pending_qs.aggregate(t=Sum('billed_amount'))['t'] or Decimal('0.00'),
        Decimal('0.00'),
    )
    in_flight_count = safe_query(lambda: in_flight_qs.count(), 0)
    in_flight_billed = safe_query(
        lambda: in_flight_qs.aggregate(t=Sum('billed_amount'))['t'] or Decimal('0.00'),
        Decimal('0.00'),
    )
    rejected_count = safe_query(lambda: rejected_qs.count(), 0)
    paid_month_count = safe_query(lambda: paid_month_qs.count(), 0)
    paid_month_amount = safe_query(
        lambda: paid_month_qs.aggregate(t=Sum('paid_amount'))['t'] or Decimal('0.00'),
        Decimal('0.00'),
    )

    monthly_base = MonthlyInsuranceClaim.objects.filter(is_deleted=False)
    monthly_draft = safe_query(
        lambda: monthly_base.filter(status__in=('draft', 'ready_for_submission')).count(),
        0,
    )
    monthly_open = safe_query(
        lambda: monthly_base.filter(
            status__in=('submitted', 'processing', 'partially_paid')
        ).count(),
        0,
    )

    insurance_ar_balance = safe_query(
        lambda: InsuranceReceivable.objects.filter(
            balance_due__gt=0
        ).aggregate(t=Sum('balance_due'))['t'] or Decimal('0.00'),
        Decimal('0.00'),
    )

    status_breakdown = safe_query(
        lambda: list(
            base_items.values('claim_status')
            .annotate(c=Count('id'))
            .order_by('-c')[:12]
        ),
        [],
    )

    top_payers_pending = safe_query(
        lambda: list(
            pending_qs.values('payer__name')
            .annotate(lines=Count('id'), billed=Sum('billed_amount'))
            .order_by('-billed')[:6]
        ),
        [],
    )

    recent_claim_lines = safe_query(
        lambda: list(
            base_items.select_related('patient', 'payer')
            .order_by('-created')[:12]
        ),
        [],
    )

    context = {
        'title': 'Claims & receivables — Account Officer',
        'today': today,
        'pending_count': pending_count,
        'pending_billed': pending_billed,
        'in_flight_count': in_flight_count,
        'in_flight_billed': in_flight_billed,
        'rejected_count': rejected_count,
        'paid_month_count': paid_month_count,
        'paid_month_amount': paid_month_amount,
        'monthly_draft': monthly_draft,
        'monthly_open': monthly_open,
        'insurance_ar_balance': insurance_ar_balance,
        'status_breakdown': status_breakdown,
        'top_payers_pending': top_payers_pending,
        'recent_claim_lines': recent_claim_lines,
    }
    return render(
        request,
        'hospital/account_officer/claims_accounting_dashboard.html',
        context,
    )
