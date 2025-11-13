"""
Admin actions for bulk operations in Django admin.
"""
from django.contrib import admin
from django.contrib import messages
from django.http import HttpResponse
import csv
from .models import Patient, Invoice, Encounter, Admission
from .bulk_operations import (
    bulk_update_invoice_status,
    bulk_complete_encounters,
    bulk_discharge_admissions,
    bulk_mark_invoices_overdue
)


def export_as_csv(modeladmin, request, queryset):
    """Export selected items as CSV"""
    model = queryset.model
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{model.__name__}_export.csv"'
    
    writer = csv.writer(response)
    
    # Write headers
    field_names = [field.name for field in model._meta.fields]
    writer.writerow(field_names)
    
    # Write data
    for obj in queryset:
        row = []
        for field in model._meta.fields:
            value = getattr(obj, field.name)
            if callable(value):
                try:
                    value = value()
                except:
                    value = ''
            row.append(str(value))
        writer.writerow(row)
    
    return response


export_as_csv.short_description = "Export selected items as CSV"


def mark_invoices_paid(modeladmin, request, queryset):
    """Mark selected invoices as paid"""
    count = bulk_update_invoice_status(
        list(queryset.values_list('id', flat=True)),
        'paid'
    )
    messages.success(request, f'{count} invoices marked as paid.')


mark_invoices_paid.short_description = "Mark selected invoices as paid"


def mark_invoices_issued(modeladmin, request, queryset):
    """Mark selected invoices as issued"""
    count = bulk_update_invoice_status(
        list(queryset.values_list('id', flat=True)),
        'issued'
    )
    messages.success(request, f'{count} invoices marked as issued.')


mark_invoices_issued.short_description = "Mark selected invoices as issued"


def complete_encounters(modeladmin, request, queryset):
    """Complete selected encounters"""
    count = bulk_complete_encounters(
        list(queryset.values_list('id', flat=True))
    )
    messages.success(request, f'{count} encounters completed.')


complete_encounters.short_description = "Complete selected encounters"


def discharge_admissions(modeladmin, request, queryset):
    """Discharge selected admissions"""
    count = bulk_discharge_admissions(
        list(queryset.values_list('id', flat=True))
    )
    messages.success(request, f'{count} admissions discharged.')


discharge_admissions.short_description = "Discharge selected admissions"

