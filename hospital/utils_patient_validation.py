"""
Utility functions for patient validation and filtering
"""
import uuid
import logging

logger = logging.getLogger(__name__)


def is_valid_patient_id(patient_id):
    """
    Check if a patient ID is valid.
    
    Args:
        patient_id: Patient ID to validate (can be UUID, string, or None)
    
    Returns:
        bool: True if valid, False otherwise
    """
    if patient_id is None:
        return False
    
    # Convert to string for comparison
    id_str = str(patient_id).strip().upper()
    
    # Check if it's the literal string "INVALID"
    if id_str == 'INVALID' or id_str == 'NONE':
        return False
    
    # Check if it's empty
    if not id_str:
        return False
    
    # Try to validate as UUID
    try:
        uuid.UUID(str(patient_id))
        return True
    except (ValueError, TypeError, AttributeError):
        # Not a valid UUID
        return False


def get_valid_patients_queryset(queryset):
    """
    Filter a patient queryset to exclude patients with invalid IDs.
    
    Args:
        queryset: Patient queryset to filter
    
    Returns:
        Filtered queryset excluding invalid IDs
    """
    # Filter out None IDs and try to exclude invalid string IDs
    # Note: UUID fields shouldn't have string "INVALID", but we filter just in case
    return queryset.exclude(id__isnull=True)


def filter_invalid_patients(patients_list):
    """
    Filter out patients with invalid IDs from a list.
    
    Args:
        patients_list: List of patient objects or dicts with 'id' key
    
    Returns:
        Filtered list with only valid patients
    """
    valid_patients = []
    for patient in patients_list:
        # Handle both objects and dicts
        if hasattr(patient, 'id'):
            patient_id = patient.id
        elif isinstance(patient, dict):
            patient_id = patient.get('id')
        else:
            continue
        
        if is_valid_patient_id(patient_id):
            valid_patients.append(patient)
        else:
            # Log warning for debugging
            patient_name = getattr(patient, 'full_name', None) or patient.get('name', 'Unknown')
            patient_mrn = getattr(patient, 'mrn', None) or patient.get('mrn', 'Unknown')
            logger.warning(f"Skipping patient with invalid ID: MRN={patient_mrn}, Name={patient_name}, ID={patient_id}")
    
    return valid_patients

