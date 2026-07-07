"""
Corporate & insurance receivables hub: list, detail, record remittance, analytics.
"""
from __future__ import annotations

import json
from calendar import monthrange
from collections import OrderedDict
from datetime import date
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q, Sum, Count
from django.db.models.functions import TruncMonth
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .decorators import role_required
from .models import Payer
from .models_accounting_advanced import BankAccount
from .models_primecare_accounting import InsurancePaymentReceived, InsuranceReceivableEntry
from .utils_billing import (
    corporate_payer_reference_lookup,
    format_corporate_reference_label,
    patient_billing_member_id_display,
)
from .views_accountant_comprehensive import require_finance_reauth
from .services.receivable_grouping_service import (
    entries_for_company_month,
    group_receivable_entries,
    record_company_month_remittance,
)


def _category_q(category: str):
    if category == 'corporate':
        return Q(payer__payer_type='corporate')
    if category == 'insurance':
        return Q(payer__payer_type__in=Payer.INSURANCE_PAYER_TYPES)
    return Q()


def _add_months(d: date, months: int) -> date:
    y, m = d.year, d.month + months
    while m > 12:
        m -= 12
        y += 1
    while m < 1:
        m += 12
        y -= 1
    last = monthrange(y, m)[1]
    return date(y, m, min(d.day, last))


@login_required
@role_required('accountant', 'senior_account_officer', 'account_officer')
def receivables_hub(request):
    category = request.GET.get('category', 'all')
    if category not in ('all', 'insurance', 'corporate'):
        category = 'all'
    status = request.GET.get('status', '')
    open_only = request.GET.get('open', '') == '1'
    q = (request.GET.get('q') or '').strip()
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    view_mode = request.GET.get('view', 'grouped')
    if view_mode not in ('grouped', 'detail'):
        view_mode = 'grouped'

    qs = InsuranceReceivableEntry.objects.filter(is_deleted=False).select_related(
        'payer', 'invoice', 'invoice__patient'
    )
    qs = qs.filter(_category_q(category))

    if status:
        qs = qs.filter(status=status)
    if open_only:
        qs = qs.filter(outstanding_amount__gt=0)
    if date_from:
        qs = qs.filter(entry_date__gte=date_from)
    if date_to:
        qs = qs.filter(entry_date__lte=date_to)
    if q:
        qs = qs.filter(
            Q(payer__name__icontains=q)
            | Q(entry_number__icontains=q)
            | Q(invoice__invoice_number__icontains=q)
            | Q(notes__icontains=q)
        )

    open_qs = InsuranceReceivableEntry.objects.filter(is_deleted=False, outstanding_amount__gt=0)
    open_qs = open_qs.filter(_category_q(category))
    agg = open_qs.aggregate(
        total_outstanding=Sum('outstanding_amount'),
    )
    total_outstanding = agg['total_outstanding'] or Decimal('0.00')
    open_count = open_qs.count()

    if view_mode == 'grouped':
        grouped_rows = group_receivable_entries(qs)
        if open_only:
            grouped_rows = [g for g in grouped_rows if g['outstanding'] > 0]
        paginator = Paginator(grouped_rows, 30)
        page = paginator.get_page(request.GET.get('page'))
        return render(
            request,
            'hospital/accountant/receivables_hub.html',
            {
                'view_mode': view_mode,
                'grouped_entries': page,
                'entries': None,
                'category': category,
                'status': status,
                'open_only': open_only,
                'q': q,
                'date_from': date_from,
                'date_to': date_to,
                'total_outstanding': total_outstanding,
                'open_count': open_count,
            },
        )

    qs = qs.order_by('-entry_date', '-created')

    paginator = Paginator(qs, 40)
    page = paginator.get_page(request.GET.get('page'))

    corp_lookup = corporate_payer_reference_lookup(
        [e.payer_id for e in page.object_list if e.payer_id]
    )
    for entry in page.object_list:
        payer = entry.payer
        if payer and payer.payer_type == 'corporate':
            entry.payer_reference_label = format_corporate_reference_label(
                corp_lookup.get(payer.id, {})
            )
        elif payer and payer.payer_type in Payer.INSURANCE_PAYER_TYPES:
            patient = entry.invoice.patient if entry.invoice_id and entry.invoice else None
            mid = patient_billing_member_id_display(patient, payer)
            entry.payer_reference_label = mid or ''
        else:
            entry.payer_reference_label = ''

    return render(
        request,
        'hospital/accountant/receivables_hub.html',
        {
            'view_mode': view_mode,
            'grouped_entries': None,
            'entries': page,
            'category': category,
            'status': status,
            'open_only': open_only,
            'q': q,
            'date_from': date_from,
            'date_to': date_to,
            'total_outstanding': total_outstanding,
            'open_count': open_count,
        },
    )


@login_required
@role_required('accountant', 'senior_account_officer', 'account_officer')
def receivable_company_month_detail(request, payer_id, month_key):
    """Drill-down: all subledger lines for one payer in one billing month."""
    from hospital.services.receivable_grouping_service import parse_month_key

    payer = get_object_or_404(Payer, pk=payer_id, is_deleted=False)
    try:
        parse_month_key(month_key)
    except ValueError as e:
        messages.error(request, str(e))
        return redirect('hospital:receivables_hub')
    entries = entries_for_company_month(payer_id, month_key)
    totals = entries.aggregate(
        total_amount=Sum('total_amount'),
        amount_received=Sum('amount_received'),
        outstanding=Sum('outstanding_amount'),
        line_count=Count('id'),
    )
    return render(
        request,
        'hospital/accountant/receivable_company_month_detail.html',
        {
            'payer': payer,
            'month_key': month_key,
            'entries': entries,
            'totals': totals,
        },
    )


@login_required
@role_required('accountant', 'senior_account_officer', 'account_officer')
def receivable_entry_detail(request, entry_id):
    entry = get_object_or_404(
        InsuranceReceivableEntry.objects.select_related('payer', 'invoice', 'invoice__patient'),
        id=entry_id,
        is_deleted=False,
    )
    payments = (
        InsurancePaymentReceived.objects.filter(receivable_entry=entry, is_deleted=False)
        .select_related('bank_account')
        .order_by('-entry_date', '-created')
    )
    from hospital.services.receivable_grouping_service import month_bounds

    month_key = entry.entry_date.strftime('%Y-%m') if entry.entry_date else None
    batch_payments = InsurancePaymentReceived.objects.none()
    if month_key and entry.payer_id:
        start, end = month_bounds(month_key)
        batch_payments = (
            InsurancePaymentReceived.objects.filter(
                receivable_entry__isnull=True,
                payer_id=entry.payer_id,
                entry_date__gte=start,
                entry_date__lte=end,
                is_deleted=False,
            )
            .select_related('bank_account')
            .order_by('-entry_date', '-created')
        )
    return render(
        request,
        'hospital/accountant/receivable_entry_detail.html',
        {
            'entry': entry,
            'payments': payments,
            'batch_payments': batch_payments,
        },
    )


@login_required
@role_required('accountant', 'senior_account_officer', 'account_officer')
def receivable_entry_api(request, entry_id):
    receivable = get_object_or_404(InsuranceReceivableEntry, id=entry_id, is_deleted=False)
    return JsonResponse(
        {
            'success': True,
            'total_amount': str(receivable.total_amount),
            'outstanding_amount': str(receivable.outstanding_amount),
            'amount_received': str(receivable.amount_received),
            'amount_rejected': str(receivable.amount_rejected),
            'withholding_tax': str(receivable.withholding_tax),
            'entry_number': receivable.entry_number,
            'payer_id': str(receivable.payer_id),
        }
    )


@login_required
@role_required('accountant', 'senior_account_officer', 'account_officer')
@require_finance_reauth
def receivable_record_remittance(request):
    batch_payer_id = request.GET.get('payer') or request.POST.get('batch_payer', '')
    batch_month = request.GET.get('month') or request.POST.get('batch_month', '')
    batch_summary = None
    if batch_payer_id and batch_month:
        try:
            payer_obj = Payer.objects.get(pk=batch_payer_id, is_deleted=False)
            open_entries = entries_for_company_month(payer_obj.id, batch_month, open_only=True)
            batch_summary = {
                'payer': payer_obj,
                'month_key': batch_month,
                'line_count': open_entries.count(),
                'outstanding': open_entries.aggregate(t=Sum('outstanding_amount'))['t'] or Decimal('0.00'),
            }
        except Payer.DoesNotExist:
            batch_summary = None

    if request.method == 'POST':
        try:
            entry_date = request.POST.get('entry_date')
            payer_id = request.POST.get('payer')
            receivable_entry_id = request.POST.get('receivable_entry', '').strip()
            batch_payer = request.POST.get('batch_payer', '').strip()
            batch_month_post = request.POST.get('batch_month', '').strip()
            bank_account_id = request.POST.get('bank_account')

            total_amount = Decimal(request.POST.get('total_amount', '0'))
            amount_received = Decimal(request.POST.get('amount_received', '0'))
            amount_rejected = Decimal(request.POST.get('amount_rejected', '0'))
            withholding_tax = Decimal(request.POST.get('withholding_tax', '0'))
            withholding_tax_rate = Decimal(request.POST.get('withholding_tax_rate', '0'))
            payment_reference = request.POST.get('payment_reference', '')
            notes = request.POST.get('notes', '')

            if amount_received + amount_rejected + withholding_tax != total_amount:
                messages.error(request, 'Amount received + rejected + WHT must equal total amount.')
                return redirect('hospital:receivable_record_remittance')

            payer = get_object_or_404(Payer, id=payer_id or batch_payer)
            bank_account = get_object_or_404(BankAccount, id=bank_account_id)

            if batch_payer and batch_month_post:
                payment, _entries = record_company_month_remittance(
                    user=request.user,
                    payer=payer,
                    month_key=batch_month_post,
                    entry_date=entry_date,
                    bank_account=bank_account,
                    total_amount=total_amount,
                    amount_received=amount_received,
                    amount_rejected=amount_rejected,
                    withholding_tax=withholding_tax,
                    withholding_tax_rate=withholding_tax_rate,
                    payment_reference=payment_reference,
                    notes=notes,
                )
                messages.success(
                    request,
                    f'Recorded batch remittance of GHS {amount_received:,.2f} for '
                    f'{payer.name} ({batch_month_post}) — {payment.entry_number}.',
                )
                return redirect(
                    'hospital:receivable_company_month_detail',
                    payer_id=payer.id,
                    month_key=batch_month_post,
                )

            if not receivable_entry_id:
                messages.error(
                    request,
                    'Select a company/month batch or a single receivable line.',
                )
                return redirect('hospital:receivable_record_remittance')

            receivable_entry = get_object_or_404(
                InsuranceReceivableEntry,
                id=receivable_entry_id,
                payer=payer,
                is_deleted=False,
            )
            outstanding = receivable_entry.outstanding_amount or Decimal('0')
            if total_amount > outstanding:
                raise ValueError(
                    f'Remittance total GHS {total_amount:.2f} exceeds outstanding '
                    f'GHS {outstanding:.2f} for {receivable_entry.entry_number}.'
                )

            payment = InsurancePaymentReceived.objects.create(
                entry_date=entry_date,
                payer=payer,
                receivable_entry=receivable_entry,
                total_amount=total_amount,
                amount_received=amount_received,
                amount_rejected=amount_rejected,
                withholding_tax=withholding_tax,
                withholding_tax_rate=withholding_tax_rate,
                bank_account=bank_account,
                payment_reference=payment_reference,
                notes=notes,
                processed_by=request.user,
            )
            payment.create_accounting_entries(request.user)
            messages.success(
                request,
                f'Recorded remittance of GHS {amount_received:,.2f} against {receivable_entry.entry_number}.',
            )
            return redirect('hospital:accountant_receivable_entry_detail', entry_id=receivable_entry.id)
        except Exception as e:
            messages.error(request, f'Error recording payment: {e}')
            return redirect('hospital:receivable_record_remittance')

    payers = Payer.objects.filter(
        payer_type__in=list(Payer.INSURANCE_PAYER_TYPES) + ['corporate'],
        is_active=True,
        is_deleted=False,
    ).order_by('name')
    bank_accounts = BankAccount.objects.filter(is_active=True, is_deleted=False)
    receivable_entries = (
        InsuranceReceivableEntry.objects.filter(
            outstanding_amount__gt=0,
            is_deleted=False,
            status__in=['pending', 'partially_paid', 'matched'],
        )
        .select_related('payer', 'invoice')
        .order_by('-entry_date', '-created')
    )
    batch_groups = group_receivable_entries(
        InsuranceReceivableEntry.objects.filter(
            is_deleted=False,
            outstanding_amount__gt=0,
        )
    )
    return render(
        request,
        'hospital/accountant/receivable_record_remittance.html',
        {
            'payers': payers,
            'bank_accounts': bank_accounts,
            'receivable_entries': receivable_entries,
            'batch_groups': batch_groups[:200],
            'batch_summary': batch_summary,
            'batch_payer_id': batch_payer_id,
            'batch_month': batch_month,
            'today': timezone.now().date(),
        },
    )


def _serialize_chart(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, (date,)):
        return obj.isoformat()
    return obj


@login_required
@role_required('accountant', 'senior_account_officer', 'account_officer')
def receivables_analytics(request):
    category = request.GET.get('category', 'all')
    if category not in ('all', 'insurance', 'corporate'):
        category = 'all'

    today = timezone.now().date()
    start = _add_months(date(today.year, today.month, 1), -17)

    base_ire = InsuranceReceivableEntry.objects.filter(is_deleted=False, entry_date__gte=start)
    base_ire = base_ire.filter(_category_q(category))

    billing_rows = (
        base_ire.annotate(m=TruncMonth('entry_date'))
        .values('m')
        .annotate(total=Sum('total_amount'))
        .order_by('m')
    )
    billing_by_month = OrderedDict()
    for row in billing_rows:
        key = row['m'].date() if hasattr(row['m'], 'date') else row['m']
        if key:
            billing_by_month[key.isoformat()[:7]] = row['total'] or Decimal('0.00')

    base_ipr = InsurancePaymentReceived.objects.filter(is_deleted=False, entry_date__gte=start)
    if category == 'corporate':
        base_ipr = base_ipr.filter(payer__payer_type='corporate')
    elif category == 'insurance':
        base_ipr = base_ipr.filter(payer__payer_type__in=Payer.INSURANCE_PAYER_TYPES)

    collections_rows = (
        base_ipr.annotate(m=TruncMonth('entry_date'))
        .values('m')
        .annotate(total=Sum('amount_received'))
        .order_by('m')
    )
    collections_by_month = OrderedDict()
    for row in collections_rows:
        key = row['m'].date() if hasattr(row['m'], 'date') else row['m']
        if key:
            collections_by_month[key.isoformat()[:7]] = row['total'] or Decimal('0.00')

    labels = sorted(set(billing_by_month.keys()) | set(collections_by_month.keys()))
    billing_series = [float(billing_by_month.get(lb, Decimal('0.00'))) for lb in labels]
    collections_series = [float(collections_by_month.get(lb, Decimal('0.00'))) for lb in labels]

    open_qs = InsuranceReceivableEntry.objects.filter(
        is_deleted=False,
        outstanding_amount__gt=0,
    ).filter(_category_q(category))

    total_outstanding = open_qs.aggregate(t=Sum('outstanding_amount'))['t'] or Decimal('0.00')
    open_lines = open_qs.count()

    top_payers = (
        open_qs.values('payer__name')
        .annotate(total=Sum('outstanding_amount'))
        .order_by('-total')[:12]
    )
    payer_labels = [row['payer__name'] or '—' for row in top_payers]
    payer_values = [float(row['total'] or 0) for row in top_payers]

    today_d = timezone.now().date()
    aging = {'current': Decimal('0'), '0_30': Decimal('0'), '31_60': Decimal('0'), '61_90': Decimal('0'), '90_plus': Decimal('0')}
    for row in open_qs.select_related('payer'):
        days_old = (today_d - row.entry_date).days
        if days_old <= 0:
            bucket = 'current'
        elif days_old <= 30:
            bucket = '0_30'
        elif days_old <= 60:
            bucket = '31_60'
        elif days_old <= 90:
            bucket = '61_90'
        else:
            bucket = '90_plus'
        aging[bucket] += row.outstanding_amount or Decimal('0')

    chart_payload = {
        'labels': labels,
        'billing': billing_series,
        'collections': collections_series,
        'payerLabels': payer_labels,
        'payerValues': payer_values,
        'aging': {k: float(v) for k, v in aging.items()},
    }
    chart_json = json.dumps(chart_payload, default=_serialize_chart)

    return render(
        request,
        'hospital/accountant/receivables_analytics.html',
        {
            'category': category,
            'total_outstanding': total_outstanding,
            'open_lines': open_lines,
            'chart_json': chart_json,
            'aging': aging,
        },
    )
