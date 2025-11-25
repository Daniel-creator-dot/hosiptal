"""
Data Validation and Integrity Checks
Validates data integrity and performs consistency checks
"""
from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


def validate_patient_data(patient):
    """
    Validate patient data integrity
    Returns list of validation errors
    """
    errors = []
    
    # Check required fields
    if not patient.first_name or not patient.first_name.strip():
        errors.append("First name is required")
    
    if not patient.last_name or not patient.last_name.strip():
        errors.append("Last name is required")
    
    # Check date of birth is not in the future
    if patient.date_of_birth and patient.date_of_birth > timezone.now().date():
        errors.append("Date of birth cannot be in the future")
    
    # Check age is reasonable (not more than 150 years)
    if patient.date_of_birth:
        age = (timezone.now().date() - patient.date_of_birth).days / 365.25
        if age > 150:
            errors.append("Patient age appears to be invalid (over 150 years)")
        if age < 0:
            errors.append("Date of birth cannot be in the future")
    
    # Check MRN format
    if patient.mrn and len(patient.mrn) < 5:
        errors.append("MRN appears to be too short")
    
    # Check phone number format (if provided)
    if patient.phone_number:
        # Basic phone validation
        if len(patient.phone_number.replace('+', '').replace('-', '').replace(' ', '')) < 9:
            errors.append("Phone number appears to be invalid")
    
    return errors


def validate_encounter_data(encounter):
    """
    Validate encounter data integrity
    """
    errors = []
    
    if not encounter.patient:
        errors.append("Patient is required")
    
    if not encounter.encounter_type:
        errors.append("Encounter type is required")
    
    # Check dates
    if encounter.ended_at and encounter.started_at:
        if encounter.ended_at < encounter.started_at:
            errors.append("End date cannot be before start date")
    
    return errors


def validate_order_data(order):
    """
    Validate order data integrity
    """
    errors = []
    
    if not order.encounter:
        errors.append("Encounter is required")
    
    if not order.order_type:
        errors.append("Order type is required")
    
    if not order.requested_by:
        errors.append("Requested by is required")
    
    return errors


def validate_invoice_data(invoice):
    """
    Validate invoice data integrity
    """
    errors = []
    
    if not invoice.patient:
        errors.append("Patient is required")
    
    if invoice.total_amount and invoice.total_amount < 0:
        errors.append("Total amount cannot be negative")
    
    # Check invoice lines total matches invoice total
    if hasattr(invoice, 'lines'):
        line_total = sum(line.amount for line in invoice.lines.all() if not line.is_deleted)
        if abs(line_total - float(invoice.total_amount or 0)) > 0.01:
            errors.append(f"Invoice total ({invoice.total_amount}) doesn't match line items total ({line_total})")
    
    return errors


def validate_staff_data(staff):
    """
    Validate staff data integrity
    """
    errors = []
    
    if not staff.user:
        errors.append("User account is required")
    
    if not staff.profession:
        errors.append("Profession is required")
    
    if not staff.department:
        errors.append("Department is required")
    
    return errors


def validate_leave_request_data(leave_request):
    """
    Validate leave request data integrity
    """
    errors = []
    
    if not leave_request.staff:
        errors.append("Staff is required")
    
    if leave_request.start_date and leave_request.end_date:
        if leave_request.end_date < leave_request.start_date:
            errors.append("End date cannot be before start date")
        
        # Check leave duration is reasonable (not more than 1 year)
        duration = (leave_request.end_date - leave_request.start_date).days
        if duration > 365:
            errors.append("Leave duration cannot exceed 365 days")
        if duration < 0:
            errors.append("Leave duration cannot be negative")
    
    return errors


def run_data_integrity_checks():
    """
    Run comprehensive data integrity checks across all models
    Returns dictionary of errors by model
    """
    from .models import Patient, Encounter, Order, Invoice, Staff
    from .models_advanced import LeaveRequest
    
    results = {
        'patient_errors': [],
        'encounter_errors': [],
        'order_errors': [],
        'invoice_errors': [],
        'staff_errors': [],
        'leave_errors': [],
    }
    
    # Check patients
    try:
        for patient in Patient.objects.filter(is_deleted=False)[:100]:  # Limit to avoid performance issues
            errors = validate_patient_data(patient)
            if errors:
                results['patient_errors'].append({
                    'id': str(patient.id),
                    'mrn': patient.mrn,
                    'name': patient.full_name,
                    'errors': errors
                })
    except Exception as e:
        logger.error(f"Error validating patients: {e}")
    
    # Check encounters
    try:
        for encounter in Encounter.objects.filter(is_deleted=False)[:100]:
            errors = validate_encounter_data(encounter)
            if errors:
                results['encounter_errors'].append({
                    'id': str(encounter.id),
                    'patient': encounter.patient.full_name if encounter.patient else 'Unknown',
                    'errors': errors
                })
    except Exception as e:
        logger.error(f"Error validating encounters: {e}")
    
    # Check orders
    try:
        for order in Order.objects.filter(is_deleted=False)[:100]:
            errors = validate_order_data(order)
            if errors:
                results['order_errors'].append({
                    'id': str(order.id),
                    'errors': errors
                })
    except Exception as e:
        logger.error(f"Error validating orders: {e}")
    
    # Check invoices
    try:
        for invoice in Invoice.objects.filter(is_deleted=False)[:100]:
            errors = validate_invoice_data(invoice)
            if errors:
                results['invoice_errors'].append({
                    'id': str(invoice.id),
                    'invoice_number': invoice.invoice_number,
                    'errors': errors
                })
    except Exception as e:
        logger.error(f"Error validating invoices: {e}")
    
    # Check staff
    try:
        for staff in Staff.objects.filter(is_deleted=False)[:100]:
            errors = validate_staff_data(staff)
            if errors:
                results['staff_errors'].append({
                    'id': str(staff.id),
                    'name': staff.user.get_full_name() if staff.user else 'Unknown',
                    'errors': errors
                })
    except Exception as e:
        logger.error(f"Error validating staff: {e}")
    
    # Check leave requests
    try:
        for leave in LeaveRequest.objects.filter(is_deleted=False)[:100]:
            errors = validate_leave_request_data(leave)
            if errors:
                results['leave_errors'].append({
                    'id': str(leave.id),
                    'errors': errors
                })
    except Exception as e:
        logger.error(f"Error validating leave requests: {e}")
    
    return results






