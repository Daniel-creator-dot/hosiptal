"""
Pre-employment and Pre-admission screening views.
One-click templates → lab + imaging orders; structured report generation.
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.db.models import Q
from django.db.utils import ProgrammingError
from django.utils import timezone
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from .models import Encounter, Order, LabTest, LabResult, Staff
from .models_advanced import ImagingStudy, ImagingCatalog
from .models_screening import ScreeningCheckTemplate, ScreeningReport
from .decorators import role_required


def _screening_tables_exist():
    """Return True if screening DB tables exist (migration 1082 applied)."""
    try:
        ScreeningCheckTemplate.objects.exists()
        ScreeningReport.objects.exists()
        return True
    except ProgrammingError:
        return False


@login_required
@role_required('doctor', 'admin', 'nurse', 'midwife', message='Access denied. Clinical role required.')
def screening_templates_list(request, encounter_id=None):
    """
    List screening templates by category (pre-employment / pre-admission).
    Optional encounter_id: show 'Apply to this encounter' for each template.
    """
    if not _screening_tables_exist():
        return render(request, 'hospital/screening/migrations_required.html')

    encounter = None
    if encounter_id:
        encounter = get_object_or_404(Encounter, pk=encounter_id, is_deleted=False)

    try:
        pre_employment = list(ScreeningCheckTemplate.objects.filter(
            category='pre_employment',
            is_active=True,
            is_deleted=False
        ).prefetch_related('lab_tests', 'imaging_items').order_by('sort_order', 'name'))
        pre_admission = list(ScreeningCheckTemplate.objects.filter(
            category='pre_admission',
            is_active=True,
            is_deleted=False
        ).prefetch_related('lab_tests', 'imaging_items').order_by('sort_order', 'name'))
    except ProgrammingError:
        return render(request, 'hospital/screening/migrations_required.html')

    context = {
        'pre_employment_templates': pre_employment,
        'pre_admission_templates': pre_admission,
        'encounter': encounter,
        'page_title': 'Screening check templates',
    }
    return render(request, 'hospital/screening/templates_list.html', context)


@login_required
@role_required('doctor', 'admin', message='Only doctors can apply screening templates.')
@require_http_methods(['POST'])
def apply_screening_template(request, encounter_id, template_id):
    """
    Apply a screening template to an encounter: create one lab order (with all
    template lab tests as LabResults) and one imaging order (with all template
    imaging items as ImagingStudies). Redirects to encounter detail.
    """
    if not _screening_tables_exist():
        return render(request, 'hospital/screening/migrations_required.html')
    encounter = get_object_or_404(Encounter, pk=encounter_id, is_deleted=False)
    template = get_object_or_404(
        ScreeningCheckTemplate,
        pk=template_id,
        is_active=True,
        is_deleted=False
    )
    doctor = getattr(request.user, 'staff_profile', None)
    if not doctor:
        messages.error(request, 'Staff profile not found.')
        return redirect('hospital:encounter_detail', pk=encounter_id)

    lab_tests = list(template.lab_tests.filter(is_active=True, is_deleted=False))
    imaging_items = list(template.imaging_items.filter(is_active=True, is_deleted=False))

    if not lab_tests and not imaging_items:
        messages.warning(
            request,
            f'Template "{template.name}" has no lab tests or imaging studies. Add items in admin.'
        )
        return redirect('hospital:encounter_detail', pk=encounter_id)

    try:
        with transaction.atomic():
            if lab_tests:
                lab_order = Order.objects.create(
                    encounter=encounter,
                    order_type='lab',
                    status='pending',
                    priority='routine',
                    notes=f'Screening: {template.name}',
                    requested_by=doctor,
                    requested_at=timezone.now(),
                )
                for test in lab_tests:
                    if not LabResult.objects.filter(
                        order=lab_order,
                        test=test,
                        is_deleted=False,
                    ).exists():
                        LabResult.objects.create(
                            order=lab_order,
                            test=test,
                            status='pending',
                        )

            if imaging_items:
                imaging_order = Order.objects.create(
                    encounter=encounter,
                    order_type='imaging',
                    status='pending',
                    priority='routine',
                    notes=f'Screening: {template.name}',
                    requested_by=doctor,
                    requested_at=timezone.now(),
                )
                patient = encounter.patient
                for item in imaging_items:
                    if not ImagingStudy.objects.filter(
                        order=imaging_order,
                        modality=item.modality,
                        study_type=item.study_type or item.name,
                        is_deleted=False,
                    ).exists():
                        ImagingStudy.objects.create(
                            order=imaging_order,
                            patient=patient,
                            encounter=encounter,
                            modality=item.modality,
                            body_part=item.body_part or 'General',
                            study_type=item.study_type or item.name or item.code,
                            status='scheduled',
                            priority='routine',
                        )

        lab_count = len(lab_tests)
        img_count = len(imaging_items)
        parts = []
        if lab_count:
            parts.append(f'{lab_count} lab test(s)')
        if img_count:
            parts.append(f'{img_count} imaging study(ies)')
        messages.success(
            request,
            f'Template "{template.name}" applied: {", ".join(parts)} sent to lab and imaging.'
        )
    except Exception as e:
        messages.error(request, f'Failed to apply template: {str(e)}')

    return redirect('hospital:encounter_detail', pk=encounter_id)


@login_required
@role_required('doctor', 'admin', message='Only doctors can complete screening reports.')
def screening_report_form(request, encounter_id):
    """
    Create or edit the screening report for an encounter.
    GET: show form with encounter, template (if any), and auto-summary from lab/imaging.
    POST: save report.
    """
    if not _screening_tables_exist():
        return render(request, 'hospital/screening/migrations_required.html')
    encounter = get_object_or_404(Encounter, pk=encounter_id, is_deleted=False)
    try:
        report = encounter.screening_report
    except ScreeningReport.DoesNotExist:
        report = ScreeningReport(encounter=encounter)
    except ProgrammingError:
        return render(request, 'hospital/screening/migrations_required.html')

    doctor = getattr(request.user, 'staff_profile', None)
    if not doctor:
        messages.error(request, 'Staff profile not found.')
        return redirect('hospital:encounter_detail', pk=encounter_id)

    # Build suggested lab/imaging summaries from results
    lab_summary_parts = []
    for order in encounter.orders.filter(order_type='lab', is_deleted=False):
        for lr in order.lab_results.filter(is_deleted=False):
            if lr.status == 'completed':
                val = lr.qualitative_result or lr.value or '—'
                lab_summary_parts.append(f"{lr.test.name}: {val}")
    suggested_lab_summary = '\n'.join(lab_summary_parts) if lab_summary_parts else ''

    imaging_summary_parts = []
    for study in encounter.imaging_studies.filter(is_deleted=False):
        if study.report_text or study.impression or study.findings:
            imaging_summary_parts.append(
                f"{study.get_modality_display()} ({study.body_part}): "
                f"{study.impression or study.findings or study.report_text}"
            )
    suggested_imaging_summary = '\n'.join(imaging_summary_parts) if imaging_summary_parts else ''

    if request.method == 'POST':
        report.overall_result = request.POST.get('overall_result', report.overall_result)
        report.result_notes = request.POST.get('result_notes', '')
        report.lab_summary = request.POST.get('lab_summary', '')
        report.imaging_summary = request.POST.get('imaging_summary', '')
        report.physical_exam_notes = request.POST.get('physical_exam_notes', '')
        report.general_remarks = request.POST.get('general_remarks', '')
        report.recommended_actions = request.POST.get('recommended_actions', '')
        report.requesting_organization = request.POST.get('requesting_organization', '')
        report.requesting_contact = request.POST.get('requesting_contact', '')
        report.reported_by = doctor
        report.reported_at = timezone.now()
        report.save()
        messages.success(request, 'Screening report saved.')
        return redirect('hospital:screening_report_print', encounter_id=encounter_id)

    context = {
        'encounter': encounter,
        'report': report,
        'suggested_lab_summary': suggested_lab_summary,
        'suggested_imaging_summary': suggested_imaging_summary,
        'page_title': 'Screening report',
    }
    return render(request, 'hospital/screening/report_form.html', context)


@login_required
def screening_report_print(request, encounter_id):
    """
    Printable screening report for an encounter (fit/unfit, lab/imaging summary, doctor sign-off).
    """
    if not _screening_tables_exist():
        return render(request, 'hospital/screening/migrations_required.html')
    encounter = get_object_or_404(Encounter, pk=encounter_id, is_deleted=False)
    try:
        report = encounter.screening_report
    except ScreeningReport.DoesNotExist:
        messages.info(request, 'No screening report yet. Complete the report first.')
        return redirect('hospital:screening_report_form', encounter_id=encounter_id)
    except ProgrammingError:
        return render(request, 'hospital/screening/migrations_required.html')

    # Lab results for this encounter (completed)
    lab_results = []
    for order in encounter.orders.filter(order_type='lab', is_deleted=False):
        for lr in order.lab_results.filter(is_deleted=False).select_related('test'):
            lab_results.append(lr)

    imaging_studies = list(
        encounter.imaging_studies.filter(is_deleted=False).order_by('modality', 'body_part')
    )

    context = {
        'encounter': encounter,
        'report': report,
        'lab_results': lab_results,
        'imaging_studies': imaging_studies,
        'patient': encounter.patient,
    }
    return render(request, 'hospital/screening/report_print.html', context)


@login_required
def screening_dashboard(request):
    """
    Entry point: list recent screening encounters and quick links to templates.
    """
    if not _screening_tables_exist():
        return render(request, 'hospital/screening/migrations_required.html')

    from django.db.models import Q

    # Optional filter by company: show general (for_company='') + templates for that company
    company_filter = (request.GET.get('company') or '').strip()
    pre_emp_q = Q(category='pre_employment', is_active=True, is_deleted=False)
    pre_adm_q = Q(category='pre_admission', is_active=True, is_deleted=False)
    if company_filter:
        company_q = Q(for_company='') | Q(for_company__iexact=company_filter)
        pre_emp_q &= company_q
        pre_adm_q &= company_q

    try:
        recent = list(Encounter.objects.filter(
            Q(encounter_type='pre_employment') | Q(encounter_type='pre_admission'),
            is_deleted=False,
        ).select_related('patient', 'provider', 'provider__user').order_by('-started_at')[:20])
        pre_employment_templates = list(ScreeningCheckTemplate.objects.filter(pre_emp_q).order_by('sort_order', 'name')[:5])
        pre_admission_templates = list(ScreeningCheckTemplate.objects.filter(pre_adm_q).order_by('sort_order', 'name')[:5])
        # Full lists for templates section on dashboard
        pre_employment_all = list(ScreeningCheckTemplate.objects.filter(pre_emp_q).prefetch_related('lab_tests', 'imaging_items').order_by('sort_order', 'name'))
        pre_admission_all = list(ScreeningCheckTemplate.objects.filter(pre_adm_q).prefetch_related('lab_tests', 'imaging_items').order_by('sort_order', 'name'))
    except ProgrammingError:
        return render(request, 'hospital/screening/migrations_required.html')
    except Exception:
        return render(request, 'hospital/screening/migrations_required.html')

    context = {
        'recent_screening_encounters': recent,
        'pre_employment_templates': pre_employment_templates,
        'pre_admission_templates': pre_admission_templates,
        'pre_employment_all': pre_employment_all,
        'pre_admission_all': pre_admission_all,
        'company_filter': company_filter,
        'page_title': 'Screening (Pre-employment & Pre-admission)',
    }
    return render(request, 'hospital/screening/dashboard.html', context)
