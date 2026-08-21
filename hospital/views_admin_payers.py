"""
Admin HMS: manage corporate companies and insurance payers (add / rename / activate).
Front desk corporate dropdown uses Payer(payer_type='corporate').
Insurance front desk uses InsuranceCompany; create/edit keeps Payer in sync.
"""
import re

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .decorators import role_required
from .models import Payer

# Types admins manage here (cash is system-managed)
_MANAGED_TYPES = ('corporate', 'private', 'nhis')
_TYPE_LABELS = {
    'corporate': 'Corporate company',
    'private': 'Private insurance',
    'nhis': 'NHIS',
}


def _slug_code(name, max_len=20):
    base = re.sub(r'[^A-Za-z0-9]+', '', (name or '').upper())[:max_len] or 'CO'
    return base


def _ensure_insurance_company(name, code=None, is_active=True):
    """Create or reactivate InsuranceCompany so front-desk insurance dropdown stays populated."""
    from .models_insurance_companies import InsuranceCompany

    name = (name or '').strip()
    if not name:
        return None
    existing = InsuranceCompany.objects.filter(name__iexact=name, is_deleted=False).first()
    if existing:
        existing.is_active = is_active
        if is_active and existing.status != 'active':
            existing.status = 'active'
        existing.save(update_fields=['is_active', 'status', 'modified'])
        return existing

    code = (code or '').strip().upper() or _slug_code(name)
    # Unique code: append digits if needed
    candidate = code[:20]
    n = 2
    while InsuranceCompany.objects.filter(code__iexact=candidate, is_deleted=False).exists():
        suffix = str(n)
        candidate = (code[: max(1, 20 - len(suffix))] + suffix)[:20]
        n += 1
        if n > 99:
            candidate = f'C{timezone.now().strftime("%H%M%S")}'[:20]
            break

    return InsuranceCompany.objects.create(
        name=name,
        code=candidate,
        status='active' if is_active else 'inactive',
        is_active=is_active,
    )


def _sync_insurance_company_rename(old_name, new_name, is_active=True):
    """Rename matching InsuranceCompany when an insurance Payer is renamed."""
    from .models_insurance_companies import InsuranceCompany

    old_name = (old_name or '').strip()
    new_name = (new_name or '').strip()
    if not old_name or not new_name:
        return
    company = InsuranceCompany.objects.filter(name__iexact=old_name, is_deleted=False).first()
    if not company:
        # No linked company yet — create under new name
        _ensure_insurance_company(new_name, is_active=is_active)
        return
    # Avoid unique conflicts if another company already has new_name
    clash = (
        InsuranceCompany.objects.filter(name__iexact=new_name, is_deleted=False)
        .exclude(pk=company.pk)
        .exists()
    )
    if clash:
        return
    company.name = new_name
    company.is_active = is_active
    if is_active:
        company.status = 'active'
    company.save(update_fields=['name', 'is_active', 'status', 'modified'])


def _sync_corporate_account_rename(old_name, new_name):
    """Best-effort rename of CorporateAccount.company_name when corporate payer renamed."""
    try:
        from .models_enterprise_billing import CorporateAccount
    except Exception:
        return
    old_name = (old_name or '').strip()
    new_name = (new_name or '').strip()
    if not old_name or not new_name or old_name.lower() == new_name.lower():
        return
    for ca in CorporateAccount.objects.filter(company_name__iexact=old_name, is_deleted=False):
        if CorporateAccount.objects.filter(company_name__iexact=new_name, is_deleted=False).exclude(
            pk=ca.pk
        ).exists():
            continue
        ca.company_name = new_name
        ca.save(update_fields=['company_name', 'modified'])


@login_required
@role_required('admin', 'accountant', 'senior_account_officer')
def admin_payers_list(request):
    """List corporate companies and insurance payers for add/edit."""
    q = (request.GET.get('q') or '').strip()
    type_filter = (request.GET.get('type') or '').strip().lower()
    show_inactive = request.GET.get('inactive') == '1'

    payers = Payer.objects.filter(
        is_deleted=False,
        payer_type__in=_MANAGED_TYPES,
    )
    if not show_inactive:
        payers = payers.filter(is_active=True)
    if type_filter in _MANAGED_TYPES:
        payers = payers.filter(payer_type=type_filter)
    if q:
        payers = payers.filter(name__icontains=q)
    payers = payers.order_by('payer_type', 'name')

    paginator = Paginator(payers, 40)
    page = paginator.get_page(request.GET.get('page'))

    return render(
        request,
        'hospital/admin_payers_list.html',
        {
            'payers': page,
            'query': q,
            'type_filter': type_filter,
            'show_inactive': show_inactive,
            'type_labels': _TYPE_LABELS,
            'title': 'Companies & insurance',
        },
    )


@login_required
@role_required('admin', 'accountant', 'senior_account_officer')
def admin_payer_add(request):
    return _admin_payer_form(request, None)


@login_required
@role_required('admin', 'accountant', 'senior_account_officer')
def admin_payer_edit(request, pk):
    payer = get_object_or_404(Payer, pk=pk, is_deleted=False, payer_type__in=_MANAGED_TYPES)
    return _admin_payer_form(request, payer)


def _admin_payer_form(request, instance):
    default_type = (request.GET.get('type') or '').strip().lower()
    if default_type not in _MANAGED_TYPES:
        default_type = 'corporate'

    def _render(post=None):
        return render(
            request,
            'hospital/admin_payer_form.html',
            {
                'obj': instance,
                'post': post,
                'type_labels': _TYPE_LABELS,
                'default_type': default_type if not instance else instance.payer_type,
                'title': 'Edit company / insurance' if instance else 'Add company / insurance',
            },
        )

    if request.method == 'POST':
        name = (request.POST.get('name') or '').strip()[:200]
        payer_type = (request.POST.get('payer_type') or '').strip().lower()
        is_active = request.POST.get('is_active') == '1'
        code = (request.POST.get('code') or '').strip().upper()[:20]

        errors = []
        if not name:
            errors.append('Name is required.')
        if payer_type not in _MANAGED_TYPES:
            errors.append('Select Corporate company, Private insurance, or NHIS.')

        # Duplicate name+type check (allow same name across types)
        dup = Payer.objects.filter(
            name__iexact=name,
            payer_type=payer_type,
            is_deleted=False,
        )
        if instance:
            dup = dup.exclude(pk=instance.pk)
        if dup.exists():
            errors.append(f'A {_TYPE_LABELS.get(payer_type, payer_type)} named "{name}" already exists.')

        if errors:
            for e in errors:
                messages.error(request, e)
            return _render(request.POST)

        old_name = instance.name if instance else ''

        if instance:
            instance.name = name
            instance.payer_type = payer_type
            instance.is_active = is_active
            instance.save(update_fields=['name', 'payer_type', 'is_active', 'modified'])
            payer = instance
        else:
            payer = Payer.objects.create(
                name=name,
                payer_type=payer_type,
                is_active=is_active,
            )

        # Keep insurance / corporate masters + patient snapshots / front-desk labels in sync
        from .patient_payer import propagate_payer_display_name_change

        if payer.payer_type in ('private', 'nhis'):
            if instance and old_name and old_name.strip().lower() != name.lower():
                _sync_insurance_company_rename(old_name, name, is_active=is_active)
            else:
                _ensure_insurance_company(name, code=code or None, is_active=is_active)
        elif payer.payer_type == 'corporate' and instance and old_name:
            _sync_corporate_account_rename(old_name, name)

        prop = {}
        if instance and old_name:
            prop = propagate_payer_display_name_change(old_name, name, payer=payer)
        elif not instance and payer.payer_type in ('private', 'nhis'):
            # New insurance already ensured InsuranceCompany above
            pass

        if instance:
            msg = f'Updated "{payer.name}".'
            touched = (
                prop.get('patients_by_snapshot', 0)
                + prop.get('patients_by_fk', 0)
                + prop.get('insurance_companies', 0)
                + prop.get('corporate_accounts', 0)
            )
            if touched:
                msg += ' Front desk, patient records, and company lists now show the new name.'
            messages.success(request, msg)
        else:
            messages.success(
                request,
                f'Added "{payer.name}" ({_TYPE_LABELS.get(payer_type)}). It appears in front-desk dropdowns when active.',
            )

        return redirect('hospital:admin_payers')

    return _render()
