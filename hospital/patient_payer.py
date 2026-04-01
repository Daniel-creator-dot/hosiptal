"""
Apply PatientForm payer selection (cash / insurance / corporate) to Patient.primary_insurance.
Used after patient_create and patient_edit form.save().
"""
import logging

from django.db.models import Q
from django.utils import timezone

logger = logging.getLogger(__name__)

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


def apply_patient_payer_from_form(request, patient, form):
    """
    Read payer_type and related fields from form.cleaned_data and update patient billing payer.

    Call only when form.is_valid() is True. Mutates patient (saves as needed).
    """
    from .models import Payer

    payer_type = (form.cleaned_data.get('payer_type') or '').strip()
    if not payer_type:
        return

    if payer_type == 'insurance':
        selected_insurance_company = form.cleaned_data.get('selected_insurance_company')
        selected_insurance_plan = form.cleaned_data.get('selected_insurance_plan')
        insurance_id = (form.cleaned_data.get('insurance_id') or '').strip()
        insurance_member_id = (form.cleaned_data.get('insurance_member_id') or '').strip()
        if not insurance_id and patient.insurance_id:
            insurance_id = (patient.insurance_id or '').strip()
        if not insurance_member_id and patient.insurance_member_id:
            insurance_member_id = (patient.insurance_member_id or '').strip()

        if not selected_insurance_company or not (insurance_id or insurance_member_id):
            if request is not None:
                from django.contrib import messages

                messages.warning(
                    request,
                    'Payment type is Insurance: select an insurance company and enter policy or member ID so billing can route correctly.',
                )
            return

        try:
            from .models_insurance_companies import PatientInsurance

            existing_enrollment = PatientInsurance.objects.filter(
                patient=patient,
                insurance_company=selected_insurance_company,
                is_deleted=False,
            ).first()

            if existing_enrollment:
                existing_enrollment.insurance_plan = selected_insurance_plan
                existing_enrollment.policy_number = insurance_id or ''
                existing_enrollment.member_id = insurance_member_id or insurance_id or ''
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
            patient.insurance_member_id = insurance_member_id or patient.insurance_member_id
            patient.insurance_id = insurance_id or patient.insurance_id
            patient.save(
                update_fields=[
                    'primary_insurance',
                    'insurance_company',
                    'insurance_member_id',
                    'insurance_id',
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
        selected_corporate_company = form.cleaned_data.get('selected_corporate_company')
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
            patient.save(update_fields=['primary_insurance'])

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
