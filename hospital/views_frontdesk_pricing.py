"""
Read-only service charge reference for front desk (patient inquiries).
Uses the same catalogs as billing: imaging, laboratory, procedures, quick charges.
"""
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import render

from .decorators import role_required
from .models import LabTest, CashierQuickService
from .models_advanced import ImagingCatalog, ProcedureCatalog


def _procedure_cash_price(row):
    if getattr(row, "cash_price", None) is not None:
        return row.cash_price
    return row.price


@login_required
@role_required("receptionist")
def frontdesk_service_charges(request):
    q = (request.GET.get("q") or "").strip()

    imaging_qs = ImagingCatalog.objects.filter(is_deleted=False, is_active=True).order_by(
        "modality", "name"
    )
    lab_qs = LabTest.objects.filter(is_deleted=False, is_active=True).order_by("name")
    procedure_qs = ProcedureCatalog.objects.filter(is_deleted=False, is_active=True).order_by(
        "category", "name"
    )
    quick_qs = CashierQuickService.objects.filter(is_active=True).order_by("sort_order", "label")

    if q:
        imaging_qs = imaging_qs.filter(
            Q(name__icontains=q)
            | Q(code__icontains=q)
            | Q(modality__icontains=q)
            | Q(body_part__icontains=q)
            | Q(study_type__icontains=q)
        )
        lab_qs = lab_qs.filter(
            Q(name__icontains=q) | Q(code__icontains=q) | Q(specimen_type__icontains=q)
        )
        procedure_qs = procedure_qs.filter(
            Q(name__icontains=q) | Q(code__icontains=q) | Q(description__icontains=q)
        )
        quick_qs = quick_qs.filter(Q(label__icontains=q) | Q(billing_code__icontains=q))

    imaging_rows = list(imaging_qs)
    lab_rows = list(lab_qs)
    procedure_rows = [(p, _procedure_cash_price(p)) for p in procedure_qs]
    quick_rows = list(quick_qs)

    context = {
        "title": "Service charges (reference)",
        "search_q": q,
        "imaging_rows": imaging_rows,
        "lab_rows": lab_rows,
        "procedure_rows": procedure_rows,
        "quick_rows": quick_rows,
        "imaging_count": len(imaging_rows),
        "lab_count": len(lab_rows),
        "procedure_count": len(procedure_rows),
        "quick_count": len(quick_rows),
    }
    return render(request, "hospital/frontdesk_service_charges.html", context)
