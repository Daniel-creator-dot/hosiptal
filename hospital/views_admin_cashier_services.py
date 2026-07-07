"""
Admin UI: cashier-visible manual service charges (supplements built-in catalog in code).
"""
import re
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.auth.decorators import login_required

from .decorators import role_required
from .models import CashierQuickService

_BILLING_CODE_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9\-]{0,79}$')


def _normalize_billing_code(raw):
    s = (raw or '').strip().upper().replace(' ', '-')
    while '--' in s:
        s = s.replace('--', '-')
    return s.strip('-')


def _admin_price_book_display_rows():
    """
    Single list for the admin table: built-in catalogue (code) first, then DB rows.
    Each row is a dict so the template can treat built-ins (no pk) like extras.
    """
    from .views_centralized_cashier import BUILTIN_ADDABLE_SERVICES, SERVICE_CODE_MAP

    rows = []
    for item_key, label, cash_amt, ins_amt in BUILTIN_ADDABLE_SERVICES:
        rows.append(
            {
                'is_builtin': True,
                'item_key': item_key,
                'label': label,
                'billing_code': SERVICE_CODE_MAP.get(item_key, item_key),
                'amount_cash': cash_amt,
                'amount_insurance': ins_amt,
                'amount_corporate': None,
                'is_active': True,
                'pk': None,
            }
        )
    for obj in CashierQuickService.objects.all().order_by('sort_order', 'label'):
        ins_amt = obj.amount_insurance if obj.amount_insurance is not None else obj.amount_cash
        rows.append(
            {
                'is_builtin': False,
                'item_key': None,
                'label': obj.label,
                'billing_code': obj.billing_code,
                'amount_cash': obj.amount_cash,
                'amount_insurance': ins_amt,
                'amount_corporate': obj.amount_corporate,
                'sort_order': obj.sort_order,
                'is_active': bool(obj.is_active),
                'pk': obj.pk,
            }
        )
    return rows


@login_required
@role_required('admin')
def admin_cashier_quick_services_list(request):
    rows = _admin_price_book_display_rows()
    return render(request, 'hospital/admin_cashier_quick_services_list.html', {'rows': rows})


@login_required
@role_required('admin')
def admin_cashier_quick_service_add(request):
    return _admin_cashier_quick_service_form(request, None)


@login_required
@role_required('admin')
def admin_cashier_quick_service_edit(request, pk):
    return _admin_cashier_quick_service_form(request, get_object_or_404(CashierQuickService, pk=pk))


def _admin_cashier_quick_service_form(request, instance):
    def _render_form(post=None, is_active_checked=None):
        if is_active_checked is None:
            if instance:
                is_active_checked = instance.is_active
            else:
                is_active_checked = True
        return render(
            request,
            'hospital/admin_cashier_quick_service_form.html',
            {'obj': instance, 'post': post, 'is_active_checked': is_active_checked},
        )

    if request.method == 'POST':
        billing_code = _normalize_billing_code(request.POST.get('billing_code'))
        label = (request.POST.get('label') or '').strip()[:200]
        sort_order = int(request.POST.get('sort_order') or 0)
        is_active = request.POST.get('is_active') == '1'
        ins_raw = (request.POST.get('amount_insurance') or '').strip()
        corp_raw = (request.POST.get('amount_corporate') or '').strip()
        try:
            amount_cash = Decimal(str(request.POST.get('amount_cash') or '0').strip() or '0')
        except (InvalidOperation, ValueError):
            amount_cash = Decimal('0')
        amount_insurance = None
        if ins_raw:
            try:
                amount_insurance = Decimal(str(ins_raw))
            except (InvalidOperation, ValueError):
                messages.error(request, 'Invalid insurance amount.')
                return _render_form(request.POST, request.POST.get('is_active') == '1')
        amount_corporate = None
        if corp_raw:
            try:
                amount_corporate = Decimal(str(corp_raw))
            except (InvalidOperation, ValueError):
                messages.error(request, 'Invalid corporate amount.')
                return _render_form(request.POST, request.POST.get('is_active') == '1')

        errors = []
        if not billing_code or not _BILLING_CODE_RE.match(billing_code):
            errors.append('Billing code must be 1–80 characters: letters, numbers, hyphen only.')
        if not label:
            errors.append('Label is required.')
        if amount_cash <= 0:
            errors.append('Cash amount must be greater than zero.')
        if amount_insurance is not None and amount_insurance < 0:
            errors.append('Insurance amount cannot be negative.')
        if amount_corporate is not None and amount_corporate <= 0:
            errors.append('Corporate amount must be greater than zero when set.')

        qs = CashierQuickService.objects.filter(billing_code__iexact=billing_code)
        if instance:
            qs = qs.exclude(pk=instance.pk)
        if billing_code and qs.exists():
            errors.append('That billing code is already used.')

        if errors:
            for e in errors:
                messages.error(request, e)
            return _render_form(request.POST, request.POST.get('is_active') == '1')

        if instance:
            obj = instance
        else:
            obj = CashierQuickService()
        obj.billing_code = billing_code
        obj.label = label
        obj.amount_cash = amount_cash
        obj.amount_insurance = amount_insurance
        obj.amount_corporate = amount_corporate
        obj.sort_order = max(0, sort_order)
        obj.is_active = is_active
        obj.save()
        messages.success(
            request,
            f'Saved "{obj.label}" ({obj.billing_code}). It appears on Cashier → Add Services when active.',
        )
        return redirect('hospital:admin_cashier_quick_services')

    return _render_form()
