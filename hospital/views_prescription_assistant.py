"""
Prescription Assistant (Top-Up) — Drug classification + AI-style chat leading to prescription.
Outstanding single-page: chat for indication/drug search + compact classification browser.
"""
import json
import logging
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.db.models import Sum

from hospital.models import Drug, PharmacyStock, Encounter
from hospital.decorators import role_required
from hospital.services.prescription_assistant_service import (
    build_chat_response,
    get_dosing_hint,
    check_interactions_for_drug_ids,
)

logger = logging.getLogger(__name__)


@login_required
@role_required('doctor', 'pharmacist', 'nurse', 'admin', message='Access denied.')
@require_http_methods(["GET"])
def prescription_assistant_view(request):
    """
    Prescription Top-Up page: AI chat + drug classification.
    ?encounter_id=... optional — links Add to prescription to this encounter.
    """
    encounter_id = request.GET.get('encounter_id', '').strip()
    encounter = None
    patient_name = None
    patient_mrn = None
    if encounter_id:
        try:
            encounter = Encounter.objects.select_related('patient').get(
                pk=encounter_id, is_deleted=False
            )
            patient_name = encounter.patient.full_name
            patient_mrn = encounter.patient.mrn
        except Encounter.DoesNotExist:
            encounter_id = ''

    # Categories for compact classification panel (same as Drug.CATEGORIES)
    categories = [{'code': c[0], 'name': c[1]} for c in Drug.CATEGORIES]
    # Top-level groups for UI (Pain, Cardiovascular, Infections, etc.)
    category_groups = [
        {'label': 'Pain & Fever', 'codes': ['analgesic', 'antipyretic', 'anti_inflammatory']},
        {'label': 'Cardiovascular', 'codes': ['antihypertensive', 'beta_blocker', 'diuretic', 'anticoagulant']},
        {'label': 'Infections', 'codes': ['antibiotic', 'antibacterial', 'antiviral', 'antifungal']},
        {'label': 'Gastrointestinal', 'codes': ['antacid', 'antiemetic', 'antidiarrheal', 'laxative']},
        {'label': 'Respiratory', 'codes': ['bronchodilator', 'cough_suppressant', 'expectorant', 'decongestant', 'cold_cure']},
        {'label': 'CNS & Psychiatric', 'codes': ['antianxiety', 'antidepressant', 'antipsychotic', 'sedative', 'sleeping_drug', 'anticonvulsant']},
        {'label': 'Other', 'codes': ['antihistamine', 'corticosteroid', 'oral_hypoglycemic', 'muscle_relaxant', 'vitamin', 'other']},
    ]

    context = {
        'page_title': 'Prescription Assistant',
        'page_description': 'Drug classification and AI assistant — find drugs and add to prescription',
        'encounter_id': encounter_id,
        'encounter': encounter,
        'patient_name': patient_name,
        'patient_mrn': patient_mrn,
        'categories': categories,
        'category_groups': category_groups,
    }
    return render(request, 'hospital/prescription_assistant.html', context)


@login_required
@role_required('doctor', 'pharmacist', 'nurse', 'admin', message='Access denied.')
@require_http_methods(["POST"])
def api_prescription_assistant_chat(request):
    """
    POST JSON: { "message": "...", "encounter_id": "uuid|null", "selected_drug_ids": ["uuid", ...] }
    Returns: { "reply", "suggested_drugs", "dosing_hint", "indication_label", "interactions", "has_critical_interaction" }
    """
    try:
        body = json.loads(request.body) if request.body else {}
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    message = (body.get('message') or '').strip()
    encounter_id = body.get('encounter_id') or None
    selected_drug_ids = body.get('selected_drug_ids') or []
    if isinstance(selected_drug_ids, str):
        selected_drug_ids = [selected_drug_ids] if selected_drug_ids else []

    result = build_chat_response(
        message=message,
        encounter_id=encounter_id,
        selected_drug_ids=selected_drug_ids,
    )
    return JsonResponse(result)


@login_required
@role_required('doctor', 'pharmacist', 'nurse', 'admin', message='Access denied.')
@require_http_methods(["GET"])
def api_prescription_assistant_dosing(request, category_code):
    """GET dosing hint for a category."""
    hint = get_dosing_hint(category_code)
    return JsonResponse(hint or {})


@login_required
@role_required('doctor', 'pharmacist', 'nurse', 'admin', message='Access denied.')
@require_http_methods(["POST"])
def api_prescription_assistant_check_interactions(request):
    """POST JSON: { "drug_ids": ["uuid", ...], "encounter_id": "uuid" } -> interactions."""
    try:
        body = json.loads(request.body) if request.body else {}
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    drug_ids = body.get('drug_ids') or []
    encounter_id = body.get('encounter_id')
    if isinstance(drug_ids, str):
        drug_ids = [drug_ids] if drug_ids else []
    result = check_interactions_for_drug_ids(drug_ids, patient=None)
    if encounter_id:
        from hospital.models import Encounter
        try:
            enc = Encounter.objects.select_related('patient').get(pk=encounter_id, is_deleted=False)
            result = check_interactions_for_drug_ids(drug_ids, patient=enc.patient)
        except Encounter.DoesNotExist:
            pass
    return JsonResponse({'warnings': result['warnings'], 'has_critical': result['has_critical']})
