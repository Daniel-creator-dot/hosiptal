"""
Waiver audit: unified list of waived invoice lines and prescribe-sale waivers
with patient, billing payer, user account, reason, and links.
"""
from decimal import Decimal
from datetime import timedelta
from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone

from .models import InvoiceLine
from .models_pharmacy_walkin import WalkInPharmacySale, WalkInPharmacySaleItem
from .utils_roles import user_can_waive, get_user_role
from .views_audit_logs import is_admin


def can_view_waiver_audit(user):
    """Admins and IT can view; accountants retain read-only audit access (they cannot waive)."""
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    if user.is_superuser:
        return True
    if user_can_waive(user) or is_admin(user):
        return True
    return get_user_role(user) == 'accountant'


def _user_display(u):
    if not u:
        return '—', '—'
    full = (u.get_full_name() or '').strip()
    name = full or u.username
    return name, u.username


def _invoice_line_waived_amount(line):
    subtotal = Decimal(str(line.quantity)) * Decimal(str(line.unit_price))
    tax = Decimal(str(line.tax_amount or 0))
    return subtotal + tax


def _build_rows(
    *,
    date_from,
    date_to,
    entry_type,
    waived_by_username,
    search,
    apply_date_filter,
):
    rows = []

    def in_date(qs):
        if not apply_date_filter:
            return qs
        if date_from:
            qs = qs.filter(waived_at__date__gte=date_from)
        if date_to:
            qs = qs.filter(waived_at__date__lte=date_to)
        return qs

    if entry_type in ('', 'all', 'invoice_line'):
        qs = InvoiceLine.objects.filter(is_deleted=False, waived_at__isnull=False)
        qs = in_date(qs).select_related(
            'invoice',
            'invoice__patient',
            'invoice__payer',
            'waived_by',
            'service_code',
        )
        if waived_by_username:
            qs = qs.filter(waived_by__username__icontains=waived_by_username.strip())
        if search:
            s = search.strip()
            qs = qs.filter(
                Q(description__icontains=s)
                | Q(waiver_reason__icontains=s)
                | Q(invoice__invoice_number__icontains=s)
                | Q(invoice__patient__first_name__icontains=s)
                | Q(invoice__patient__last_name__icontains=s)
                | Q(invoice__patient__mrn__icontains=s)
                | Q(waived_by__username__icontains=s)
            )
        for line in qs.order_by('-waived_at'):
            inv = line.invoice
            patient = inv.patient
            payer = inv.payer
            name_u, login_u = _user_display(line.waived_by)
            rows.append(
                {
                    'when': line.waived_at,
                    'type': 'invoice_line',
                    'type_label': 'Invoice line',
                    'description': line.description,
                    'amount_waived': _invoice_line_waived_amount(line),
                    'patient_label': patient.full_name if patient else '—',
                    'patient_id': str(patient.pk) if patient else None,
                    'payer_label': payer.name if payer else '—',
                    'reference': inv.invoice_number,
                    'waived_by_name': name_u,
                    'waived_by_username': login_u,
                    'reason': line.waiver_reason or '—',
                    'detail_url': reverse('hospital:cashier_invoice_detail', args=[inv.pk]),
                    'patient_bill_url': (
                        reverse('hospital:cashier_patient_total_bill', args=[patient.pk])
                        if patient
                        else ''
                    ),
                }
            )

    if entry_type in ('', 'all', 'prescribe_sale'):
        qs = WalkInPharmacySale.objects.filter(is_deleted=False, waived_at__isnull=False)
        qs = in_date(qs).select_related('patient', 'payer', 'waived_by')
        if waived_by_username:
            qs = qs.filter(waived_by__username__icontains=waived_by_username.strip())
        if search:
            s = search.strip()
            qs = qs.filter(
                Q(sale_number__icontains=s)
                | Q(customer_name__icontains=s)
                | Q(waiver_reason__icontains=s)
                | Q(waived_by__username__icontains=s)
                | Q(patient__first_name__icontains=s)
                | Q(patient__last_name__icontains=s)
                | Q(patient__mrn__icontains=s)
            )
        for sale in qs.order_by('-waived_at'):
            if sale.patient_id:
                patient_label = sale.patient.full_name
                patient_id = str(sale.patient_id)
            else:
                patient_label = sale.customer_name or 'Walk-in'
                patient_id = None
            payer = sale.payer
            name_u, login_u = _user_display(sale.waived_by)
            rows.append(
                {
                    'when': sale.waived_at,
                    'type': 'prescribe_sale',
                    'type_label': 'Prescribe sale (whole)',
                    'description': f'Prescribe sale {sale.sale_number}',
                    'amount_waived': sale.total_amount or Decimal('0'),
                    'patient_label': patient_label,
                    'patient_id': patient_id,
                    'payer_label': payer.name if payer else '—',
                    'reference': sale.sale_number,
                    'waived_by_name': name_u,
                    'waived_by_username': login_u,
                    'reason': sale.waiver_reason or '—',
                    'detail_url': '',
                    'patient_bill_url': (
                        reverse('hospital:cashier_patient_total_bill', args=[patient_id])
                        if patient_id
                        else ''
                    ),
                }
            )

    if entry_type in ('', 'all', 'prescribe_line'):
        qs = WalkInPharmacySaleItem.objects.filter(
            is_deleted=False, sale__is_deleted=False, waived_at__isnull=False
        )
        qs = in_date(qs).select_related('sale', 'sale__patient', 'sale__payer', 'drug', 'waived_by')
        if waived_by_username:
            qs = qs.filter(waived_by__username__icontains=waived_by_username.strip())
        if search:
            s = search.strip()
            qs = qs.filter(
                Q(drug__name__icontains=s)
                | Q(waiver_reason__icontains=s)
                | Q(sale__sale_number__icontains=s)
                | Q(waived_by__username__icontains=s)
                | Q(sale__patient__first_name__icontains=s)
                | Q(sale__patient__last_name__icontains=s)
                | Q(sale__patient__mrn__icontains=s)
                | Q(sale__customer_name__icontains=s)
            )
        for item in qs.order_by('-waived_at'):
            sale = item.sale
            if sale.patient_id:
                patient_label = sale.patient.full_name
                patient_id = str(sale.patient_id)
            else:
                patient_label = sale.customer_name or 'Walk-in'
                patient_id = None
            payer = sale.payer
            name_u, login_u = _user_display(item.waived_by)
            qty = Decimal(str(item.quantity))
            unit = Decimal(str(item.unit_price))
            rows.append(
                {
                    'when': item.waived_at,
                    'type': 'prescribe_line',
                    'type_label': 'Prescribe sale line',
                    'description': f'{item.drug.name} × {item.quantity}',
                    'amount_waived': qty * unit,
                    'patient_label': patient_label,
                    'patient_id': patient_id,
                    'payer_label': payer.name if payer else '—',
                    'reference': sale.sale_number,
                    'waived_by_name': name_u,
                    'waived_by_username': login_u,
                    'reason': item.waiver_reason or '—',
                    'detail_url': '',
                    'patient_bill_url': (
                        reverse('hospital:cashier_patient_total_bill', args=[patient_id])
                        if patient_id
                        else ''
                    ),
                }
            )

    rows.sort(key=lambda r: r['when'] or timezone.now(), reverse=True)
    return rows


@login_required
@user_passes_test(can_view_waiver_audit, login_url='/admin/login/')
def waiver_audit_view(request):
    entry_type = (request.GET.get('type') or 'all').strip()
    date_from_s = (request.GET.get('date_from') or '').strip()
    date_to_s = (request.GET.get('date_to') or '').strip()
    all_dates = request.GET.get('all_dates') == '1'
    waived_by_username = (request.GET.get('waived_by') or '').strip()
    search = (request.GET.get('q') or '').strip()
    page_number = request.GET.get('page', 1)

    date_from = None
    date_to = None
    apply_date_filter = True
    if all_dates:
        apply_date_filter = False
        date_from_s = ''
        date_to_s = ''
    else:
        if date_from_s:
            try:
                date_from = timezone.datetime.strptime(date_from_s, '%Y-%m-%d').date()
            except ValueError:
                pass
        if date_to_s:
            try:
                date_to = timezone.datetime.strptime(date_to_s, '%Y-%m-%d').date()
            except ValueError:
                pass

        if not date_from and not date_to:
            today = timezone.now().date()
            date_from = today - timedelta(days=90)
            date_to = today
            date_from_s = date_from.isoformat()
            date_to_s = date_to.isoformat()

    rows = _build_rows(
        date_from=date_from,
        date_to=date_to,
        entry_type=entry_type,
        waived_by_username=waived_by_username,
        search=search,
        apply_date_filter=apply_date_filter,
    )

    paginator = Paginator(rows, 50)
    page_obj = paginator.get_page(page_number)

    filter_params = {}
    if entry_type and entry_type != 'all':
        filter_params['type'] = entry_type
    if all_dates:
        filter_params['all_dates'] = '1'
    else:
        if date_from_s:
            filter_params['date_from'] = date_from_s
        if date_to_s:
            filter_params['date_to'] = date_to_s
    if waived_by_username:
        filter_params['waived_by'] = waived_by_username
    if search:
        filter_params['q'] = search
    filter_query = urlencode(filter_params)

    today = timezone.now().date()

    context = {
        'title': 'Waiver audit',
        'page_obj': page_obj,
        'rows': page_obj.object_list,
        'filters': {
            'type': entry_type,
            'date_from': date_from_s,
            'date_to': date_to_s,
            'waived_by': waived_by_username,
            'search': search,
            'all_dates': all_dates,
        },
        'filter_query': filter_query,
        'preset_30d': urlencode(
            {
                'date_from': (today - timedelta(days=30)).isoformat(),
                'date_to': today.isoformat(),
                **({'type': entry_type} if entry_type and entry_type != 'all' else {}),
            }
        ),
    }
    return render(request, 'hospital/admin/waiver_audit.html', context)
