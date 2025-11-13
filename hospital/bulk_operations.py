"""
Bulk operations for Hospital Management System.
"""
from django.db import transaction
from django.utils import timezone
from .models import Patient, Invoice, Encounter, Admission


@transaction.atomic
def bulk_create_patients(patient_data_list):
    """Bulk create patients"""
    patients = []
    for data in patient_data_list:
        patient = Patient(**data)
        patients.append(patient)
    return Patient.objects.bulk_create(patients)


@transaction.atomic
def bulk_update_invoice_status(invoice_ids, new_status):
    """Bulk update invoice status"""
    return Invoice.objects.filter(
        id__in=invoice_ids,
        is_deleted=False
    ).update(status=new_status)


@transaction.atomic
def bulk_complete_encounters(encounter_ids):
    """Bulk complete encounters"""
    now = timezone.now()
    encounters = Encounter.objects.filter(
        id__in=encounter_ids,
        status='active',
        is_deleted=False
    )
    
    for encounter in encounters:
        encounter.status = 'completed'
        encounter.ended_at = now
        encounter.save()
    
    return encounters.count()


@transaction.atomic
def bulk_discharge_admissions(admission_ids):
    """Bulk discharge admissions"""
    now = timezone.now()
    admissions = Admission.objects.filter(
        id__in=admission_ids,
        status='admitted',
        is_deleted=False
    )
    
    count = 0
    for admission in admissions:
        admission.discharge()
        count += 1
    
    return count


def bulk_mark_invoices_overdue():
    """Mark all overdue invoices"""
    from datetime import timedelta
    overdue_date = timezone.now() - timedelta(days=0)  # Today or before
    
    invoices = Invoice.objects.filter(
        status__in=['issued', 'partially_paid'],
        due_at__lt=overdue_date,
        balance__gt=0,
        is_deleted=False
    )
    
    count = invoices.update(status='overdue')
    return count

