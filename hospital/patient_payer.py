"""
Apply PatientForm payer selection (cash / insurance / corporate) to Patient.primary_insurance.
Used after patient_create and patient_edit form.save().
"""
import logging

from django.db.models import Q
from django.utils import timezone

logger = logging.getLogger(__name__)

# Patient model fields used for insurance / corporate policy & member references (persist across visits)
BILLING_REF_FIELD_NAMES = (
    'insurance_id',
    'insurance_member_id',
    'insurance_policy_number',
    'insurance_group_number',
)

# Invoices we may re-route to a new payer (exclude settled / void)
_OPEN_INVOICE_STATUSES = ('draft', 'issued', 'partially_paid', 'overdue')

# DB values for Payer that count as insurance billing (see models.Payer.INSURANCE_PAYER_TYPES)
_INSURANCE_PAYER_TYPE_VALUES = ('private', 'nhis', 'insurance')


def resolve_payer_for_insurance_company(insurance_company):
    """
    Return a Payer row for this insurance company — never reuse a same-name row that is typed 'cash'.

    get_or_create(name=...) alone can return an unrelated or wrong-typed payer and route all bills to cash.
    """
    from .models import Payer

    name = (getattr(insurance_company, 'name', None) or '').strip()
    if not name:
        raise ValueError('Insurance company has no name')

    qs = Payer.objects.filter(
        name__iexact=name,
        payer_type__in=_INSURANCE_PAYER_TYPE_VALUES,
        is_deleted=False,
    ).order_by('-is_active', '-modified')
    found = qs.first()
    if found:
        return found

    wrong = (
        Payer.objects.filter(name__iexact=name, is_deleted=False)
        .exclude(payer_type__in=_INSURANCE_PAYER_TYPE_VALUES)
        .first()
    )
    if wrong and wrong.payer_type == 'cash':
        wrong.payer_type = 'private'
        wrong.is_active = True
        wrong.save(update_fields=['payer_type', 'is_active', 'modified'])
        logger.warning(
            'Re-typed payer %s from cash to private for insurance company match',
            name,
        )
        return wrong

    if wrong and wrong.payer_type == 'corporate':
        return Payer.objects.create(
            name=name,
            payer_type='private',
            is_active=True,
        )

    return Payer.objects.create(
        name=insurance_company.name,
        payer_type='private',
        is_active=True,
    )


def ensure_corporate_payer(payer_or_name):
    """Ensure we have a Payer with payer_type corporate (fix wrong-typed same name)."""
    from .models import Payer

    if hasattr(payer_or_name, 'payer_type'):
        payer = payer_or_name
        if payer.payer_type != 'corporate':
            payer.payer_type = 'corporate'
            payer.is_active = True
            payer.save(update_fields=['payer_type', 'is_active', 'modified'])
        return payer

    corp_name = (payer_or_name or '').strip()
    if not corp_name:
        raise ValueError('Corporate name required')

    qs = Payer.objects.filter(
        payer_type='corporate',
        name__iexact=corp_name,
        is_deleted=False,
    ).order_by('-is_active')
    p = qs.first()
    if p:
        return p

    wrong = Payer.objects.filter(name__iexact=corp_name, is_deleted=False).first()
    if wrong and wrong.payer_type == 'cash':
        wrong.payer_type = 'corporate'
        wrong.is_active = True
        wrong.save(update_fields=['payer_type', 'is_active', 'modified'])
        return wrong

    return Payer.objects.create(
        name=corp_name,
        payer_type='corporate',
        is_active=True,
    )


def sync_open_invoices_to_primary_payer_for_date(patient, target_date=None, request=None):
    """
    After primary_insurance changes, set invoice.payer for open invoices for this patient when:
    - the invoice is for an encounter whose visit date (local) is target_date, or
    - the invoice is for an active encounter (ongoing visit — even if started on a prior day), or
    - the invoice has no encounter but was issued on target_date (local).

    Default target_date is local today so today's bill follows the payer you just set.
    """
    from .models import Invoice

    patient.refresh_from_db(fields=['primary_insurance_id'])
    new_payer_id = patient.primary_insurance_id
    if not new_payer_id:
        return 0

    if target_date is None:
        target_date = timezone.localdate()

    invoice_filter = (
        Q(
            encounter__isnull=False,
            encounter__patient_id=patient.pk,
            encounter__is_deleted=False,
            encounter__started_at__date=target_date,
        )
        | Q(
            encounter__isnull=False,
            encounter__patient_id=patient.pk,
            encounter__is_deleted=False,
            encounter__status='active',
        )
        | Q(encounter__isnull=True, issued_at__date=target_date)
    )

    qs = (
        Invoice.all_objects.filter(
            patient_id=patient.pk,
            is_deleted=False,
            status__in=_OPEN_INVOICE_STATUSES,
        )
        .filter(invoice_filter)
        .exclude(payer_id=new_payer_id)
    )

    count = qs.update(payer_id=new_payer_id)
    if count:
        logger.info(
            'Synced %s invoice(s) to payer %s for patient %s on %s',
            count,
            new_payer_id,
            patient.mrn,
            target_date,
        )
        if request is not None:
            from django.contrib import messages

            messages.info(
                request,
                f'{count} open bill(s) for this visit date ({target_date.isoformat()}) now bill to the updated payer.',
            )
    return count


def coalesce_billing_ref(cleaned_data, prior, field_name):
    """Use submitted value; if blank, keep prior snapshot (values captured before PatientForm.save())."""
    v = (cleaned_data.get(field_name) or '').strip()
    if v:
        return v
    if prior:
        return (prior.get(field_name) or '').strip()
    return ''


def _resolve_form_model_choice(form, field_name, cleaned_data):
    """Coerce ModelChoiceField values (including raw POST PK strings from duplicate bypass)."""
    val = cleaned_data.get(field_name)
    if val is None or val == '':
        return None
    if hasattr(val, '_meta'):
        return val
    field = form.fields.get(field_name) if form else None
    if field is not None and hasattr(field, 'clean'):
        try:
            return field.clean(val)
        except Exception:
            return None
    return val


def _insurance_company_from_patient_form_cleaned(cleaned_data, form=None):
    """
    Insurance payer updates require an InsuranceCompany row. Prefer the dropdown; if empty,
    resolve from the manual ``insurance_company`` text when it uniquely matches the catalog.
    """
    sel = cleaned_data.get('selected_insurance_company')
    if form is not None:
        sel = _resolve_form_model_choice(form, 'selected_insurance_company', cleaned_data)
        if sel is not None:
            cleaned_data['selected_insurance_company'] = sel
    elif sel is not None and hasattr(sel, '_meta'):
        pass
    elif sel:
        # Raw PK string without form context — resolve directly
        try:
            from .models_insurance_companies import InsuranceCompany

            sel = InsuranceCompany.objects.filter(pk=sel, is_deleted=False).first()
        except Exception:
            sel = None
    else:
        sel = None
    if sel:
        return sel
    manual = (cleaned_data.get('insurance_company') or '').strip()
    if not manual:
        return None
    try:
        from .models_insurance_companies import InsuranceCompany

        base = InsuranceCompany.objects.filter(
            is_active=True, status='active', is_deleted=False
        )
        exact = base.filter(name__iexact=manual).order_by('id').first()
        if exact:
            return exact
        partial = list(base.filter(name__icontains=manual).order_by('name')[:2])
        if len(partial) == 1:
            return partial[0]
    except Exception:
        pass
    return None


def backfill_payer_cleaned_data_from_instance(form):
    """When editing, restore payer selectors from the patient record if POST omitted them."""
    if not form or not getattr(form, 'cleaned_data', None):
        return
    instance = getattr(form, 'instance', None)
    if not instance or getattr(instance._state, 'adding', True):
        return

    cd = form.cleaned_data
    pt = (cd.get('payer_type') or '').strip()
    if not pt:
        return

    if pt == 'insurance' and not cd.get('selected_insurance_company'):
        try:
            from .models_insurance_companies import InsuranceCompany, PatientInsurance

            pi = (
                PatientInsurance.objects.filter(
                    patient=instance,
                    is_primary=True,
                    is_deleted=False,
                )
                .select_related('insurance_company', 'insurance_plan')
                .first()
            )
            if not pi:
                pi = (
                    PatientInsurance.objects.filter(patient=instance, is_deleted=False)
                    .select_related('insurance_company', 'insurance_plan')
                    .order_by('-is_primary', '-created')
                    .first()
                )
            if pi and pi.insurance_company_id:
                cd['selected_insurance_company'] = pi.insurance_company
                if pi.insurance_plan_id:
                    cd['selected_insurance_plan'] = pi.insurance_plan
                return
            payer = getattr(instance, 'primary_insurance', None)
            if payer and (payer.payer_type or '') in _INSURANCE_PAYER_TYPE_VALUES:
                ic = InsuranceCompany.objects.filter(
                    name__iexact=payer.name,
                    is_deleted=False,
                ).first()
                if ic:
                    cd['selected_insurance_company'] = ic
        except Exception:
            pass

    if pt == 'corporate' and not cd.get('selected_corporate_company'):
        try:
            from .models import Payer as PayerModel

            payer = getattr(instance, 'primary_insurance', None)
            if not payer or payer.payer_type != 'corporate':
                return
            field = form.fields.get('selected_corporate_company')
            if not field:
                cd['selected_corporate_company'] = payer
                return
            corp_model = field.queryset.model
            if corp_model is PayerModel and field.queryset.filter(pk=payer.pk).exists():
                cd['selected_corporate_company'] = payer
            else:
                from .models_enterprise_billing import CorporateAccount

                ca = CorporateAccount.objects.filter(
                    company_name__iexact=payer.name,
                    is_deleted=False,
                ).first()
                if ca and field.queryset.filter(pk=ca.pk).exists():
                    cd['selected_corporate_company'] = ca
                else:
                    cd['selected_corporate_company'] = payer
        except Exception:
            pass


def normalize_patient_form_payer_cleaned_data(form):
    """
    Ensure payer_type and ModelChoice selections are coherent after manual POST replay
    (duplicate bypass) or partial submissions.
    """
    if not form or not getattr(form, 'cleaned_data', None):
        return
    backfill_payer_cleaned_data_from_instance(form)
    cd = form.cleaned_data
    corp = _resolve_form_model_choice(form, 'selected_corporate_company', cd)
    if corp is not None:
        cd['selected_corporate_company'] = corp
    ins = _insurance_company_from_patient_form_cleaned(cd, form=form)
    if ins is not None:
        cd['selected_insurance_company'] = ins
    plan = _resolve_form_model_choice(form, 'selected_insurance_plan', cd)
    if plan is not None:
        cd['selected_insurance_plan'] = plan
    pt = (cd.get('payer_type') or '').strip()
    if not pt:
        if cd.get('selected_insurance_company'):
            cd['payer_type'] = 'insurance'
        elif cd.get('selected_corporate_company'):
            cd['payer_type'] = 'corporate'


def apply_patient_payer_from_form(request, patient, form, billing_ref_prior=None):
    """
    Read payer_type and related fields from form.cleaned_data and update patient billing payer.

    Call only when form.is_valid() is True. Mutates patient (saves as needed).
    """
    from .models import Payer

    normalize_patient_form_payer_cleaned_data(form)

    payer_type = (form.cleaned_data.get('payer_type') or '').strip()
    if not payer_type:
        return

    if payer_type == 'insurance':
        cd = form.cleaned_data
        selected_insurance_company = _insurance_company_from_patient_form_cleaned(cd, form=form)
        selected_insurance_plan = _resolve_form_model_choice(
            form, 'selected_insurance_plan', cd
        ) or form.cleaned_data.get('selected_insurance_plan')
        prior = billing_ref_prior
        insurance_id = coalesce_billing_ref(cd, prior, 'insurance_id')
        insurance_member_id = coalesce_billing_ref(cd, prior, 'insurance_member_id')
        insurance_policy_number = coalesce_billing_ref(cd, prior, 'insurance_policy_number')
        insurance_group_number = coalesce_billing_ref(cd, prior, 'insurance_group_number')

        if not selected_insurance_company:
            if request is not None:
                from django.contrib import messages

                messages.warning(
                    request,
                    'Payment type is Insurance: choose the company from the dropdown (or type a name that '
                    'matches your insurance catalog exactly). Until then, billing stays on Cash/self-pay.',
                )
            return

        # Policy/member ID optional at registration — use MRN placeholder so payer routing works immediately
        if not (insurance_id or insurance_member_id):
            fallback_ref = (patient.mrn or '').strip() or f'REG-{patient.pk}'
            insurance_id = insurance_id or fallback_ref
            insurance_member_id = insurance_member_id or fallback_ref

        try:
            from .models_insurance_companies import PatientInsurance

            existing_enrollment = PatientInsurance.objects.filter(
                patient=patient,
                insurance_company=selected_insurance_company,
                is_deleted=False,
            ).first()

            if existing_enrollment:
                existing_enrollment.insurance_plan = selected_insurance_plan
                existing_enrollment.policy_number = insurance_id or existing_enrollment.policy_number or ''
                existing_enrollment.member_id = (
                    insurance_member_id or insurance_id or existing_enrollment.member_id or ''
                )
                existing_enrollment.is_primary = True
                existing_enrollment.status = 'active'
                existing_enrollment.save()
            else:
                PatientInsurance.objects.create(
                    patient=patient,
                    insurance_company=selected_insurance_company,
                    insurance_plan=selected_insurance_plan,
                    policy_number=insurance_id or '',
                    member_id=insurance_member_id or insurance_id or '',
                    is_primary_subscriber=True,
                    relationship_to_subscriber='self',
                    effective_date=timezone.now().date(),
                    is_primary=True,
                    status='active',
                )

            payer = resolve_payer_for_insurance_company(selected_insurance_company)
            patient.primary_insurance = payer
            patient.insurance_company = selected_insurance_company.name
            patient.insurance_member_id = insurance_member_id
            patient.insurance_id = insurance_id
            patient.insurance_policy_number = insurance_policy_number
            patient.insurance_group_number = insurance_group_number
            patient.save(
                update_fields=[
                    'primary_insurance',
                    'insurance_company',
                    'insurance_member_id',
                    'insurance_id',
                    'insurance_policy_number',
                    'insurance_group_number',
                ]
            )

            sync_open_invoices_to_primary_payer_for_date(patient, request=request)

            logger.info(
                'Patient %s primary payer set to insurance %s',
                patient.mrn,
                payer.name,
            )
            if request is not None:
                from django.contrib import messages

                messages.success(
                    request,
                    f'Billing payer updated: {selected_insurance_company.name}. New bills and today\'s open bills for this visit date use this payer.',
                )
        except Exception as e:
            logger.exception('Insurance payer update failed for %s', patient.mrn)
            if request is not None:
                from django.contrib import messages

                messages.warning(
                    request,
                    f'Patient saved, but insurance payer update failed: {e}',
                )

    elif payer_type == 'corporate':
        selected_corporate_company = _resolve_form_model_choice(
            form, 'selected_corporate_company', form.cleaned_data
        ) or form.cleaned_data.get('selected_corporate_company')
        employee_id = form.cleaned_data.get('employee_id')

        if not selected_corporate_company:
            if request is not None:
                from django.contrib import messages

                messages.warning(
                    request,
                    'Payment type is Corporate: select a corporate company so bills route correctly.',
                )
            return

        try:
            selected = selected_corporate_company
            if hasattr(selected, 'payer_type'):
                payer = ensure_corporate_payer(selected)
            else:
                corp_name = getattr(selected, 'company_name', None) or str(selected)
                payer = ensure_corporate_payer(corp_name)

            try:
                from .models_enterprise_billing import CorporateEmployee, CorporateAccount

                corporate_account = CorporateAccount.objects.filter(
                    company_name=payer.name,
                    is_active=True,
                    is_deleted=False,
                ).first()

                if corporate_account:
                    corporate_employee, created = CorporateEmployee.objects.get_or_create(
                        corporate_account=corporate_account,
                        patient=patient,
                        defaults={
                            'employee_id': employee_id or f'EMP{patient.mrn}',
                            'enrollment_date': timezone.now().date(),
                            'is_active': True,
                        },
                    )

                    if not created and employee_id:
                        corporate_employee.employee_id = employee_id
                        corporate_employee.save(update_fields=['employee_id'])
            except ImportError:
                pass
            except Exception as e:
                logger.warning('CorporateEmployee sync skipped: %s', e)

            patient.primary_insurance = payer
            cd = form.cleaned_data
            prior = billing_ref_prior
            ins_id = coalesce_billing_ref(cd, prior, 'insurance_id')
            ins_mem = coalesce_billing_ref(cd, prior, 'insurance_member_id')
            ins_pol = coalesce_billing_ref(cd, prior, 'insurance_policy_number')
            ins_grp = coalesce_billing_ref(cd, prior, 'insurance_group_number')
            patient.insurance_id = ins_id
            patient.insurance_member_id = ins_mem
            patient.insurance_policy_number = ins_pol
            patient.insurance_group_number = ins_grp
            patient.save(
                update_fields=[
                    'primary_insurance',
                    'insurance_id',
                    'insurance_member_id',
                    'insurance_policy_number',
                    'insurance_group_number',
                ]
            )

            sync_open_invoices_to_primary_payer_for_date(patient, request=request)

            logger.info('Patient %s primary payer set to corporate %s', patient.mrn, payer.name)
            if request is not None:
                from django.contrib import messages

                messages.success(
                    request,
                    f'Billing payer updated: {payer.name} (corporate). New bills and today\'s open bills for this visit date bill this account.',
                )
        except Exception as e:
            logger.exception('Corporate payer update failed for %s', patient.mrn)
            if request is not None:
                from django.contrib import messages

                messages.warning(
                    request,
                    f'Patient saved, but corporate payer update failed: {e}',
                )

    elif payer_type == 'cash':
        receiving_point = (form.cleaned_data.get('receiving_point') or '').strip()

        try:
            payer, _ = Payer.objects.get_or_create(
                name='Cash',
                defaults={
                    'payer_type': 'cash',
                    'is_active': True,
                },
            )
            patient.primary_insurance = payer
            update_fields = ['primary_insurance']
            if receiving_point:
                note_line = f'Cash receiving point: {receiving_point}'
                patient.notes = (
                    f'{patient.notes}\n{note_line}'.strip()
                    if (patient.notes or '').strip()
                    else note_line
                )
                update_fields.append('notes')
            patient.save(update_fields=update_fields)

            sync_open_invoices_to_primary_payer_for_date(patient, request=request)

            logger.info('Patient %s primary payer set to Cash', patient.mrn)
            if request is not None:
                from django.contrib import messages

                messages.success(
                    request,
                    'Billing payer updated: Cash. New bills and today\'s open bills for this visit date are cash/self-pay.',
                )
        except Exception as e:
            logger.exception('Cash payer update failed for %s', patient.mrn)
            if request is not None:
                from django.contrib import messages

                messages.warning(
                    request,
                    f'Patient saved, but cash payer update failed: {e}',
                )
