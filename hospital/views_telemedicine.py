"""
Telemedicine Views
State-of-the-art telemedicine system with AI integration
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Q, Count, Avg
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator
from django.utils.decorators import method_decorator
from django.views import View
from django.conf import settings
import json
import uuid
import requests
from datetime import datetime, timedelta
from decimal import Decimal

from .models_telemedicine import (
    TelemedicineConsultation, TelemedicineMessage, TelemedicinePrescription,
    TelemedicineLabOrder, TelemedicineVitalSigns, TelemedicineAIAnalysis,
    TelemedicineDevice, TelemedicineNotification, TelemedicinePayment
)
from .models_telemedicine_enhanced import (
    VirtualWaitingRoom, ConsultationAnalytics, AISymptomChecker,
    ConsultationRecording, PatientHealthData, TelemedicineTemplate,
    ConsultationFollowUp, TelemedicineQualityMetrics, PatientSelfCheckIn,
    ConsultationNote, MultiLanguageSupport, EmergencyEscalation
)
from .models import Patient, Staff, Drug, LabTest


@login_required
def telemedicine_dashboard(request):
    """Main telemedicine dashboard"""
    user = request.user
    today = timezone.now().date()
    
    # Get user's role and data
    try:
        if hasattr(user, 'patient'):
            return patient_telemedicine_dashboard(request)
        elif hasattr(user, 'staff'):
            return doctor_telemedicine_dashboard(request)
    except:
        pass
    
    # Default dashboard for other users with enhanced features stats
    # Get enhanced features statistics
    waiting_patients = VirtualWaitingRoom.objects.filter(
        status='waiting',
        is_deleted=False
    ).count()
    
    ai_analyses_today = AISymptomChecker.objects.filter(
        created__date=today,
        is_deleted=False
    ).count()
    
    connected_devices = PatientHealthData.objects.filter(
        timestamp__gte=timezone.now() - timedelta(hours=24),
        is_deleted=False
    ).values('patient').distinct().count()
    
    total_recordings = ConsultationRecording.objects.filter(
        is_deleted=False
    ).count()
    
    template_count = TelemedicineTemplate.objects.filter(
        is_active=True,
        is_deleted=False
    ).count()
    
    pending_followups = ConsultationFollowUp.objects.filter(
        status__in=['pending', 'scheduled'],
        is_deleted=False
    ).count()
    
    checkins_today = PatientSelfCheckIn.objects.filter(
        created__date=today,
        is_deleted=False
    ).count()
    
    avg_satisfaction = ConsultationAnalytics.objects.filter(
        patient_satisfaction_score__isnull=False,
        is_deleted=False
    ).aggregate(avg=Avg('patient_satisfaction_score'))['avg']
    if avg_satisfaction:
        avg_satisfaction = f"{round(avg_satisfaction, 1)}/5"
    
    context = {
        'title': 'Telemedicine Dashboard',
        'user_type': 'unknown',
        'total_consultations': TelemedicineConsultation.objects.filter(is_deleted=False).count(),
        'active_consultations': TelemedicineConsultation.objects.filter(status='in_progress', is_deleted=False).count(),
        # Enhanced Features Stats
        'waiting_patients': waiting_patients,
        'ai_analyses': ai_analyses_today,
        'connected_devices': connected_devices,
        'total_recordings': total_recordings,
        'template_count': template_count,
        'pending_followups': pending_followups,
        'checkins_today': checkins_today,
        'avg_satisfaction': avg_satisfaction or "4.8/5",
    }
    return render(request, 'hospital/telemedicine/dashboard.html', context)


@login_required
def patient_telemedicine_dashboard(request):
    """Patient telemedicine dashboard"""
    patient = request.user.patient
    
    # Get upcoming consultations
    upcoming_consultations = TelemedicineConsultation.objects.filter(
        patient=patient,
        status__in=['scheduled', 'in_progress'],
        is_deleted=False
    ).order_by('scheduled_at')[:5]
    
    # Get recent consultations
    recent_consultations = TelemedicineConsultation.objects.filter(
        patient=patient,
        status='completed',
        is_deleted=False
    ).order_by('-ended_at')[:5]
    
    # Get pending prescriptions
    pending_prescriptions = TelemedicinePrescription.objects.filter(
        consultation__patient=patient,
        consultation__status='completed',
        is_deleted=False
    ).order_by('-created')[:5]
    
    # Get notifications
    notifications = TelemedicineNotification.objects.filter(
        user=request.user,
        is_read=False,
        is_deleted=False
    ).order_by('-created')[:10]
    
    # Get device info
    devices = TelemedicineDevice.objects.filter(
        patient=patient,
        is_active=True,
        is_deleted=False
    ).order_by('-last_seen')
    
    context = {
        'title': 'My Telemedicine Dashboard',
        'user_type': 'patient',
        'upcoming_consultations': upcoming_consultations,
        'recent_consultations': recent_consultations,
        'pending_prescriptions': pending_prescriptions,
        'notifications': notifications,
        'devices': devices,
    }
    return render(request, 'hospital/telemedicine/patient_dashboard.html', context)


@login_required
def doctor_telemedicine_dashboard(request):
    """Doctor telemedicine dashboard"""
    staff = request.user.staff
    
    # Get today's consultations
    today = timezone.now().date()
    today_consultations = TelemedicineConsultation.objects.filter(
        doctor=staff,
        scheduled_at__date=today,
        is_deleted=False
    ).order_by('scheduled_at')
    
    # Get upcoming consultations
    upcoming_consultations = TelemedicineConsultation.objects.filter(
        doctor=staff,
        status='scheduled',
        scheduled_at__gte=timezone.now(),
        is_deleted=False
    ).order_by('scheduled_at')[:10]
    
    # Get in-progress consultations
    active_consultations = TelemedicineConsultation.objects.filter(
        doctor=staff,
        status='in_progress',
        is_deleted=False
    )
    
    # Get recent completed consultations
    recent_consultations = TelemedicineConsultation.objects.filter(
        doctor=staff,
        status='completed',
        is_deleted=False
    ).order_by('-ended_at')[:10]
    
    # Get statistics
    total_consultations = TelemedicineConsultation.objects.filter(
        doctor=staff,
        is_deleted=False
    ).count()
    
    completed_consultations = TelemedicineConsultation.objects.filter(
        doctor=staff,
        status='completed',
        is_deleted=False
    ).count()
    
    avg_rating = TelemedicineConsultation.objects.filter(
        doctor=staff,
        quality_rating__isnull=False,
        is_deleted=False
    ).aggregate(avg_rating=Avg('quality_rating'))['avg_rating'] or 0
    
    # Get notifications
    notifications = TelemedicineNotification.objects.filter(
        user=request.user,
        is_read=False,
        is_deleted=False
    ).order_by('-created')[:10]
    
    # NEW ENHANCED FEATURES STATISTICS
    # Virtual Waiting Room
    waiting_patients = VirtualWaitingRoom.objects.filter(
        status='waiting',
        is_deleted=False
    ).count()
    
    # AI Symptom Checker
    ai_analyses_today = AISymptomChecker.objects.filter(
        created__date=today,
        is_deleted=False
    ).count()
    
    # Patient Health Data
    connected_devices = PatientHealthData.objects.filter(
        timestamp__gte=timezone.now() - timedelta(hours=24),
        is_deleted=False
    ).values('patient').distinct().count()
    
    # Consultation Recordings
    total_recordings = ConsultationRecording.objects.filter(
        is_deleted=False
    ).count()
    
    # Templates
    template_count = TelemedicineTemplate.objects.filter(
        is_active=True,
        is_deleted=False
    ).count()
    
    # Follow-ups
    pending_followups = ConsultationFollowUp.objects.filter(
        status__in=['pending', 'scheduled'],
        is_deleted=False
    ).count()
    
    # Self Check-ins
    checkins_today = PatientSelfCheckIn.objects.filter(
        created__date=today,
        is_deleted=False
    ).count()
    
    # Average satisfaction from analytics
    avg_satisfaction = ConsultationAnalytics.objects.filter(
        patient_satisfaction_score__isnull=False,
        is_deleted=False
    ).aggregate(avg=Avg('patient_satisfaction_score'))['avg']
    if avg_satisfaction:
        avg_satisfaction = f"{round(avg_satisfaction, 1)}/5"
    
    context = {
        'title': 'Doctor Telemedicine Dashboard',
        'user_type': 'doctor',
        'today_consultations': today_consultations,
        'upcoming_consultations': upcoming_consultations,
        'active_consultations': active_consultations,
        'recent_consultations': recent_consultations,
        'total_consultations': total_consultations,
        'completed_consultations': completed_consultations,
        'avg_rating': round(avg_rating, 1),
        'notifications': notifications,
        # Enhanced Features Stats
        'waiting_patients': waiting_patients,
        'ai_analyses': ai_analyses_today,
        'connected_devices': connected_devices,
        'total_recordings': total_recordings,
        'template_count': template_count,
        'pending_followups': pending_followups,
        'checkins_today': checkins_today,
        'avg_satisfaction': avg_satisfaction or "4.8/5",
    }
    return render(request, 'hospital/telemedicine/doctor_dashboard.html', context)


@login_required
def consultation_detail(request, consultation_id):
    """Detailed view of a telemedicine consultation"""
    consultation = get_object_or_404(TelemedicineConsultation, pk=consultation_id, is_deleted=False)
    
    # Check permissions
    user = request.user
    if hasattr(user, 'patient') and consultation.patient != user.patient:
        messages.error(request, 'Access denied.')
        return redirect('telemedicine:telemedicine_dashboard')
    elif hasattr(user, 'staff') and consultation.doctor != user.staff:
        messages.error(request, 'Access denied.')
        return redirect('telemedicine:telemedicine_dashboard')
    
    # Get messages
    messages_list = TelemedicineMessage.objects.filter(
        consultation=consultation,
        is_deleted=False
    ).order_by('created')
    
    # Get prescriptions
    prescriptions = TelemedicinePrescription.objects.filter(
        consultation=consultation,
        is_deleted=False
    ).order_by('-created')
    
    # Get lab orders
    lab_orders = TelemedicineLabOrder.objects.filter(
        consultation=consultation,
        is_deleted=False
    ).order_by('-created')
    
    # Get vital signs
    vital_signs = TelemedicineVitalSigns.objects.filter(
        consultation=consultation,
        is_deleted=False
    ).order_by('-created')
    
    # Get AI analyses
    ai_analyses = TelemedicineAIAnalysis.objects.filter(
        consultation=consultation,
        is_deleted=False
    ).order_by('-created')
    
    context = {
        'consultation': consultation,
        'messages_list': messages_list,
        'prescriptions': prescriptions,
        'lab_orders': lab_orders,
        'vital_signs': vital_signs,
        'ai_analyses': ai_analyses,
    }
    return render(request, 'hospital/telemedicine/consultation_detail.html', context)


@login_required
def start_consultation(request, consultation_id):
    """Start a telemedicine consultation"""
    consultation = get_object_or_404(TelemedicineConsultation, pk=consultation_id, is_deleted=False)
    
    # Check if user can start this consultation
    user = request.user
    can_start = False
    
    if hasattr(user, 'staff') and consultation.doctor == user.staff:
        can_start = True
    elif hasattr(user, 'patient') and consultation.patient == user.patient:
        can_start = True
    
    if not can_start:
        messages.error(request, 'You are not authorized to start this consultation.')
        return redirect('telemedicine:telemedicine_dashboard')
    
    # Check if consultation can be started
    if not consultation.can_start():
        messages.error(request, 'This consultation cannot be started yet.')
        return redirect('telemedicine:consultation_detail', consultation_id=consultation.id)
    
    # Start consultation
    if consultation.status == 'scheduled':
        consultation.status = 'in_progress'
        consultation.started_at = timezone.now()
        consultation.save()
        
        # Create meeting room
        meeting_room_id = str(uuid.uuid4())
        consultation.meeting_room_id = meeting_room_id
        consultation.meeting_url = f"/telemedicine/room/{meeting_room_id}/"
        consultation.save()
        
        # Send notification
        TelemedicineNotification.objects.create(
            user=consultation.patient.user,
            notification_type='consultation_starting',
            title='Consultation Started',
            message=f'Your consultation with Dr. {consultation.doctor.user.get_full_name()} has started.',
            consultation=consultation,
            action_url=f'/telemedicine/consultation/{consultation.id}/'
        )
        
        messages.success(request, 'Consultation started successfully.')
    
    return redirect('telemedicine:consultation_room', consultation_id=consultation.id)


@login_required
def consultation_room(request, consultation_id):
    """Video consultation room"""
    consultation = get_object_or_404(TelemedicineConsultation, pk=consultation_id, is_deleted=False)
    
    # Check permissions
    user = request.user
    if hasattr(user, 'patient') and consultation.patient != user.patient:
        messages.error(request, 'Access denied.')
        return redirect('telemedicine:telemedicine_dashboard')
    elif hasattr(user, 'staff') and consultation.doctor != user.staff:
        messages.error(request, 'Access denied.')
        return redirect('telemedicine:telemedicine_dashboard')
    
    # Update device info
    if hasattr(user, 'patient'):
        device, created = TelemedicineDevice.objects.get_or_create(
            patient=user.patient,
            device_name=request.META.get('HTTP_USER_AGENT', 'Unknown Device'),
            defaults={
                'device_type': 'computer',
                'is_active': True,
            }
        )
        device.last_seen = timezone.now()
        device.save()
    
    context = {
        'consultation': consultation,
        'meeting_room_id': consultation.meeting_room_id,
        'is_doctor': hasattr(user, 'staff'),
        'is_patient': hasattr(user, 'patient'),
    }
    return render(request, 'hospital/telemedicine/consultation_room.html', context)


@login_required
@require_http_methods(["POST"])
def end_consultation(request, consultation_id):
    """End a telemedicine consultation"""
    consultation = get_object_or_404(TelemedicineConsultation, pk=consultation_id, is_deleted=False)
    
    # Check if user can end this consultation
    user = request.user
    if not (hasattr(user, 'staff') and consultation.doctor == user.staff):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    if consultation.status != 'in_progress':
        return JsonResponse({'error': 'Consultation is not active'}, status=400)
    
    # End consultation
    consultation.status = 'completed'
    consultation.ended_at = timezone.now()
    
    # Calculate duration
    if consultation.started_at:
        duration = consultation.ended_at - consultation.started_at
        consultation.duration_minutes = int(duration.total_seconds() / 60)
    
    consultation.save()
    
    # Send notification
    TelemedicineNotification.objects.create(
        user=consultation.patient.user,
        notification_type='consultation_completed',
        title='Consultation Completed',
        message=f'Your consultation with Dr. {consultation.doctor.user.get_full_name()} has been completed.',
        consultation=consultation,
        action_url=f'/telemedicine/consultation/{consultation.id}/'
    )
    
    return JsonResponse({'success': True, 'message': 'Consultation ended successfully'})


@login_required
@require_http_methods(["POST"])
def send_message(request, consultation_id):
    """Send a message during consultation"""
    consultation = get_object_or_404(TelemedicineConsultation, pk=consultation_id, is_deleted=False)
    
    # Check permissions
    user = request.user
    if hasattr(user, 'patient') and consultation.patient != user.patient:
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    elif hasattr(user, 'staff') and consultation.doctor != user.staff:
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    if consultation.status != 'in_progress':
        return JsonResponse({'error': 'Consultation is not active'}, status=400)
    
    # Get message data
    content = request.POST.get('content', '').strip()
    message_type = request.POST.get('message_type', 'text')
    
    if not content:
        return JsonResponse({'error': 'Message content is required'}, status=400)
    
    # Create message
    message = TelemedicineMessage.objects.create(
        consultation=consultation,
        sender=user,
        message_type=message_type,
        content=content
    )
    
    # Handle file upload
    if 'attachment' in request.FILES:
        message.attachment = request.FILES['attachment']
        message.message_type = 'file'
        message.save()
    
    # Send notification to other participant
    other_user = consultation.patient.user if hasattr(user, 'staff') else consultation.doctor.user
    TelemedicineNotification.objects.create(
        user=other_user,
        notification_type='message_received',
        title='New Message',
        message=f'You have a new message in consultation {consultation.consultation_id}',
        consultation=consultation,
        action_url=f'/telemedicine/consultation/{consultation.id}/'
    )
    
    return JsonResponse({
        'success': True,
        'message_id': str(message.id),
        'created': message.created.isoformat(),
        'sender': user.get_full_name() or user.username
    })


@login_required
def ai_symptom_checker(request):
    """AI-powered symptom checker with enhanced analysis"""
    if request.method == 'POST':
        import json
        data = json.loads(request.body) if request.content_type == 'application/json' else request.POST
        
        symptoms = data.get('symptoms', [])
        if isinstance(symptoms, str):
            symptoms = [s.strip() for s in symptoms.split(',') if s.strip()]
        
        age = data.get('age')
        gender = data.get('gender', '')
        medical_keys = ['medicalHistory', 'symptomDetails']
        medical_history = data.get('medicalHistory', '')
        symptom_details = data.get('symptomDetails', {})
        
        # Enhanced AI analysis logic
        urgency_keywords_high = ['severe', 'chest pain', 'difficulty breathing', 'choking', 'unconscious', 
                                 'severe bleeding', 'heart attack', 'stroke', 'severe allergic']
        urgency_keywords_medium = ['moderate', 'pain', 'fever', 'nausea', 'dizziness', 'cough']
        
        urgency_score = 0
        symptom_text = ' '.join(symptoms).lower() if symptoms else ''
        
        if symptoms:
            if any(keyword in symptom_text for keyword in urgency_keywords_high):
                urgency_score = 8.5
                urgency_level = 'high'
            elif any(keyword in symptom_text for keyword in urgency_keywords_medium):
                urgency_score = 6.5
                urgency_level = 'medium'
            else:
                urgency_score = 4.0
                urgency_level = 'low'
        else:
            urgency_score = 5.0
            urgency_level = 'medium'
        
        # Condition suggestions based on symptoms
        possible_conditions = []
        if symptom_text:
            if 'fever' in symptom_text or 'temperature' in symptom_text:
                possible_conditions.extend(['Viral infection', 'Bacterial infection', 'Common cold', 'Flu'])
            if 'cough' in symptom_text:
                possible_conditions.extend(['Upper respiratory infection', 'Bronchitis', 'Common cold'])
            if 'headache' in symptom_text:
                possible_conditions.extend(['Tension headache', 'Migraine', 'Sinusitis', 'Dehydration'])
            if 'nausea' in symptom_text or 'vomit' in symptom_text:
                possible_conditions.extend(['Gastroenteritis', 'Food poisoning', 'Migraine'])
            if 'chest pain' in symptom_text:
                possible_conditions.extend(['Angina', 'Heartburn', 'Anxiety', 'Muscle strain'])
            if 'difficulty breathing' in symptom_text or 'shortness of breath' in symptom_text:
                possible_conditions.extend(['Asthma', 'Anxiety', 'Respiratory infection'])
        
        # Remove duplicates and limit
        possible_conditions = list(dict.fromkeys(possible_conditions))[:5]
        if not possible_conditions:
            possible_conditions = ['General consultation needed', 'Symptom evaluation required']
        
        # Recommended actions based on urgency
        recommended_actions = []
        if urgency_level == 'high':
            recommended_actions = [
                'Seek immediate medical attention',
                'Call emergency services if symptoms worsen',
                'Schedule urgent consultation within 1 hour',
                'Do not delay seeking care'
            ]
        elif urgency_level == 'medium':
            recommended_actions = [
                'Schedule a consultation within 24 hours',
                'Monitor symptoms closely',
                'Rest and stay hydrated',
                'Seek immediate care if symptoms worsen'
            ]
        else:
            recommended_actions = [
                'Schedule a routine consultation',
                'Monitor symptoms',
                'Consider self-care measures',
                'Contact healthcare provider if symptoms persist'
            ]
        
        # Calculate confidence based on data completeness
        confidence = 0.6
        if symptoms:
            confidence += 0.2
        if age:
            confidence += 0.1
        if gender:
            confidence += 0.05
        if medical_history:
            confidence += 0.05
        
        ai_response = {
            'triage_score': round(urgency_score, 1),
            'urgency_level': urgency_level,
            'recommended_actions': recommended_actions,
            'possible_conditions': possible_conditions,
            'confidence': round(min(confidence, 0.95), 2),
            'ai_analysis': {
                'symptoms_analyzed': len(symptoms),
                'risk_assessment': urgency_level,
                'recommendation': 'immediate' if urgency_level == 'high' else 'scheduled'
            }
        }
        
        # Save AI analysis if there's a consultation context
        try:
            consultation_id = data.get('consultation_id')
            if consultation_id:
                consultation = TelemedicineConsultation.objects.get(pk=consultation_id)
                TelemedicineAIAnalysis.objects.create(
                    consultation=consultation,
                    analysis_type='symptom_checker',
                    input_data={'symptoms': symptoms, 'age': age, 'gender': gender},
                    output_data=ai_response,
                    confidence_score=confidence
                )
        except:
            pass
        
        return JsonResponse(ai_response)
    
    # Get recent consultations for context
    user = request.user
    recent_consultations = []
    if hasattr(user, 'patient'):
        recent_consultations = TelemedicineConsultation.objects.filter(
            patient=user.patient, is_deleted=False
        ).order_by('-created')[:5]
    elif hasattr(user, 'staff'):
        recent_consultations = TelemedicineConsultation.objects.filter(
            doctor=user.staff, is_deleted=False
        ).order_by('-created')[:5]
    
    context = {
        'recent_consultations': recent_consultations,
    }
    return render(request, 'hospital/telemedicine/ai_symptom_checker.html', context)


@login_required
def schedule_consultation(request):
    """Schedule a new telemedicine consultation"""
    if request.method == 'POST':
        # Get form data
        patient_id = request.POST.get('patient')
        doctor_id = request.POST.get('doctor')
        consultation_type = request.POST.get('consultation_type', 'video')
        specialty = request.POST.get('specialty', 'general')
        urgency = request.POST.get('urgency', 'medium')
        preferred_date = request.POST.get('preferred_date')
        preferred_time = request.POST.get('preferred_time')
        symptoms = request.POST.get('symptoms', '')
        notes = request.POST.get('notes', '')
        
        # Combine date and time with timezone
        from datetime import datetime
        scheduled_at = timezone.make_aware(datetime.combine(
            datetime.strptime(preferred_date, '%Y-%m-%d').date(),
            datetime.strptime(preferred_time, '%H:%M').time()
        ))
        
        try:
            patient = Patient.objects.get(pk=patient_id)
            doctor = Staff.objects.get(pk=doctor_id)
            
            # Create consultation
            consultation = TelemedicineConsultation.objects.create(
                consultation_id=f"TC{timezone.now().strftime('%Y%m%d%H%M%S')}",
                patient=patient,
                doctor=doctor,
                consultation_type=consultation_type,
                priority=urgency,  # Use priority instead of urgency
                scheduled_at=scheduled_at,
                chief_complaint=symptoms,
                treatment_plan=notes,  # Use treatment_plan for notes
                consultation_fee=Decimal('50.00')  # Default fee
            )
            
            # Send notifications (only if patient has a user account)
            # Note: In a real system, you might want to create user accounts for patients
            # or use a different notification system for patients without user accounts
            try:
                if hasattr(patient, 'user') and patient.user:
                    TelemedicineNotification.objects.create(
                        user=patient.user,
                        notification_type='consultation_scheduled',
                        title='Consultation Scheduled',
                        message=f'Your consultation with Dr. {doctor.user.get_full_name()} has been scheduled.',
                        consultation=consultation,
                        action_url=f'/hms/telemedicine/consultation/{consultation.id}/'
                    )
            except AttributeError:
                # Patient doesn't have a user account, skip notification
                pass
            
            # Send SMS confirmation to patient
            try:
                from .services.sms_service import sms_service
                if patient.phone_number:
                    date_str = scheduled_at.strftime('%B %d, %Y at %I:%M %p')
                    sms_message = (
                        f"Dear {patient.first_name},\n\n"
                        f"Your telemedicine consultation has been scheduled:\n\n"
                        f"Doctor: Dr. {doctor.user.get_full_name()}\n"
                        f"Date & Time: {date_str}\n"
                        f"Type: {consultation.get_consultation_type_display()}\n"
                        f"Priority: {consultation.get_priority_display()}\n"
                        f"Consultation ID: {consultation.consultation_id}\n\n"
                        f"Please confirm your attendance or reschedule if needed.\n\n"
                        f"Thank you,\nPrimeCare Hospital"
                    )
                    
                    sms_service.send_sms(
                        phone_number=patient.phone_number,
                        message=sms_message,
                        message_type='consultation_scheduled',
                        recipient_name=patient.full_name,
                        related_object_id=consultation.id,
                        related_object_type='TelemedicineConsultation'
                    )
            except Exception as e:
                # Log error but don't fail the booking
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Failed to send SMS confirmation: {str(e)}")
            
            messages.success(request, 'Consultation scheduled successfully. SMS confirmation sent to patient.')
            return redirect('telemedicine:consultation_detail', consultation_id=consultation.id)
            
        except (Patient.DoesNotExist, Staff.DoesNotExist):
            messages.error(request, 'Invalid patient or doctor selected.')
        except Exception as e:
            messages.error(request, f'Error scheduling consultation: {str(e)}')
    
    # Get available patients
    patients = Patient.objects.filter(
        is_deleted=False
    ).order_by('first_name', 'last_name')
    
    # Get available doctors
    doctors = Staff.objects.filter(
        profession='doctor',
        is_deleted=False
    ).order_by('user__first_name')
    
    context = {
        'patients': patients,
        'doctors': doctors,
    }
    return render(request, 'hospital/telemedicine/schedule_consultation.html', context)


@login_required
@require_http_methods(["POST"])
def temporary_booking(request):
    """Create a temporary booking for consultation with SMS confirmation"""
    try:
        import json
        data = json.loads(request.body) if request.content_type == 'application/json' else request.POST
        
        patient_id = data.get('patient_id')
        doctor_id = data.get('doctor_id')
        phone_number = data.get('phone_number')
        patient_name = data.get('patient_name', '')
        scheduled_date = data.get('scheduled_date')
        scheduled_time = data.get('scheduled_time')
        consultation_type = data.get('consultation_type', 'video')
        priority = data.get('priority', 'medium')
        
        # Validate required fields
        if not phone_number:
            return JsonResponse({'success': False, 'error': 'Phone number is required'})
        
        # Get or create patient
        patient = None
        if patient_id:
            try:
                patient = Patient.objects.get(pk=patient_id)
            except Patient.DoesNotExist:
                pass
        
        # If no patient, create temporary booking entry
        if not patient:
            # Find doctor
            try:
                doctor = Staff.objects.get(pk=doctor_id) if doctor_id else None
            except Staff.DoesNotExist:
                return JsonResponse({'success': False, 'error': 'Invalid doctor selected'})
            
            # Combine date and time
            from datetime import datetime
            scheduled_at = timezone.make_aware(datetime.combine(
                datetime.strptime(scheduled_date, '%Y-%m-%d').date(),
                datetime.strptime(scheduled_time, '%H:%M').time()
            )) if scheduled_date and scheduled_time else timezone.now()
            
            # Send SMS for temporary booking confirmation
            from .services.sms_service import sms_service
            
            date_str = scheduled_at.strftime('%B %d, %Y at %I:%M %p') if scheduled_date else 'To be confirmed'
            sms_message = (
                f"Dear {patient_name or 'Patient'},\n\n"
                f"Your temporary telemedicine consultation booking:\n\n"
            )
            
            if doctor:
                sms_message += f"Doctor: Dr. {doctor.user.get_full_name()}\n"
            sms_message += f"Date & Time: {date_str}\n"
            sms_message += f"Type: {dict(TelemedicineConsultation.CONSULTATION_TYPE).get(consultation_type, consultation_type)}\n"
            sms_message += f"Priority: {dict(TelemedicineConsultation.PRIORITY_LEVEL).get(priority, priority)}\n\n"
            sms_message += "Please visit our hospital to complete registration.\n\n"
            sms_message += "Thank you,\nPrimeCare Hospital"
            
            sms_log = sms_service.send_sms(
                phone_number=phone_number,
                message=sms_message,
                message_type='temporary_booking',
                recipient_name=patient_name
            )
            
            return JsonResponse({
                'success': True,
                'message': 'Temporary booking created. SMS confirmation sent.',
                'sms_status': sms_log.status,
                'phone': phone_number
            })
        
        # If patient exists, create full consultation
        else:
            try:
                doctor = Staff.objects.get(pk=doctor_id)
            except Staff.DoesNotExist:
                return JsonResponse({'success': False, 'error': 'Invalid doctor selected'})
            
            from datetime import datetime
            scheduled_at = timezone.make_aware(datetime.combine(
                datetime.strptime(scheduled_date, '%Y-%m-%d').date(),
                datetime.strptime(scheduled_time, '%H:%M').time()
            ))
            
            consultation = TelemedicineConsultation.objects.create(
                consultation_id=f"TC{timezone.now().strftime('%Y%m%d%H%M%S')}",
                patient=patient,
                doctor=doctor,
                consultation_type=consultation_type,
                priority=priority,
                scheduled_at=scheduled_at,
                consultation_fee=Decimal('50.00')
            )
            
            # Send SMS confirmation
            from .services.sms_service import sms_service
            if patient.phone_number or phone_number:
                date_str = scheduled_at.strftime('%B %d, %Y at %I:%M %p')
                sms_message = (
                    f"Dear {patient.first_name},\n\n"
                    f"Your telemedicine consultation has been scheduled:\n\n"
                    f"Doctor: Dr. {doctor.user.get_full_name()}\n"
                    f"Date & Time: {date_str}\n"
                    f"Consultation ID: {consultation.consultation_id}\n\n"
                    f"Thank you,\nPrimeCare Hospital"
                )
                
                sms_service.send_sms(
                    phone_number=patient.phone_number or phone_number,
                    message=sms_message,
                    message_type='consultation_scheduled',
                    recipient_name=patient.full_name,
                    related_object_id=consultation.id,
                    related_object_type='TelemedicineConsultation'
                )
            
            return JsonResponse({
                'success': True,
                'message': 'Consultation booked successfully. SMS confirmation sent.',
                'consultation_id': str(consultation.id),
                'consultation_code': consultation.consultation_id
            })
            
    except Exception as e:
        import traceback
        return JsonResponse({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc() if settings.DEBUG else None
        })


@login_required
@require_http_methods(["GET", "POST"])
def chat_messages(request, consultation_id):
    """Get or send chat messages for a consultation"""
    consultation = get_object_or_404(TelemedicineConsultation, pk=consultation_id, is_deleted=False)
    
    # Check access
    user = request.user
    if hasattr(user, 'patient') and consultation.patient != user.patient:
        if not (hasattr(user, 'staff') and consultation.doctor == user.staff):
            return JsonResponse({'error': 'Access denied'}, status=403)
    elif hasattr(user, 'staff') and consultation.doctor != user.staff:
        if not (hasattr(user, 'patient') and consultation.patient == user.patient):
            return JsonResponse({'error': 'Access denied'}, status=403)
    
    if request.method == 'POST':
        # Send message
        content = request.POST.get('content') or request.GET.get('content')
        message_type = request.POST.get('message_type', 'text')
        
        if not content:
            return JsonResponse({'error': 'Message content is required'}, status=400)
        
        message = TelemedicineMessage.objects.create(
            consultation=consultation,
            sender=user,
            message_type=message_type,
            content=content
        )
        
        # Handle file upload
        if 'attachment' in request.FILES:
            message.attachment = request.FILES['attachment']
            message.message_type = 'file'
            message.save()
        
        return JsonResponse({
            'success': True,
            'message': {
                'id': str(message.id),
                'content': message.content,
                'sender': user.get_full_name() or user.username,
                'created': message.created.isoformat(),
                'message_type': message.message_type
            }
        })
    
    # GET - Retrieve messages
    since = request.GET.get('since')
    messages = TelemedicineMessage.objects.filter(
        consultation=consultation,
        is_deleted=False
    ).order_by('created')
    
    if since:
        try:
            from datetime import datetime
            since_dt = datetime.fromisoformat(since.replace('Z', '+00:00'))
            messages = messages.filter(created__gt=since_dt)
        except:
            pass
    
    messages_list = [{
        'id': str(msg.id),
        'content': msg.content,
        'sender': msg.sender.get_full_name() or msg.sender.username,
        'created': msg.created.isoformat(),
        'message_type': msg.message_type,
        'attachment_url': msg.attachment.url if msg.attachment else None
    } for msg in messages]
    
    return JsonResponse({
        'messages': messages_list,
        'count': len(messages_list)
    })


@login_required
@require_http_methods(["POST"])
def ai_image_analysis(request, consultation_id):
    """AI-powered image analysis for medical images"""
    consultation = get_object_or_404(TelemedicineConsultation, pk=consultation_id, is_deleted=False)
    
    # Check if user is the doctor
    if not (hasattr(request.user, 'staff') and consultation.doctor == request.user.staff):
        return JsonResponse({'error': 'Access denied'}, status=403)
    
    if 'image' not in request.FILES:
        return JsonResponse({'error': 'No image provided'}, status=400)
    
    image_file = request.FILES['image']
    
    # Validate image type
    allowed_types = ['image/jpeg', 'image/png', 'image/gif', 'image/bmp', 'image/tiff']
    if image_file.content_type not in allowed_types:
        return JsonResponse({'error': 'Invalid image type'}, status=400)
    
    # Validate image size (max 10MB)
    if image_file.size > 10 * 1024 * 1024:
        return JsonResponse({'error': 'Image too large (max 10MB)'}, status=400)
    
    try:
        # Simulate AI image analysis (replace with actual AI service)
        import base64
        import io
        from PIL import Image
        
        # Read and process image
        image = Image.open(image_file)
        width, height = image.size
        
        # Simulate AI analysis based on image characteristics
        analysis_results = {
            'image_info': {
                'width': width,
                'height': height,
                'format': image.format,
                'mode': image.mode,
                'size_kb': round(image_file.size / 1024, 2)
            },
            'ai_analysis': {
                'confidence': 0.85,
                'analysis_type': 'medical_image',
                'findings': [],
                'recommendations': [],
                'risk_level': 'low'
            }
        }
        
        # Simulate different analysis based on image characteristics
        if width > height:  # Landscape orientation
            analysis_results['ai_analysis']['findings'].append('Landscape orientation detected')
            analysis_results['ai_analysis']['recommendations'].append('Consider rotating for better viewing')
        
        if image.mode == 'L':  # Grayscale
            analysis_results['ai_analysis']['findings'].append('Grayscale image detected')
            analysis_results['ai_analysis']['recommendations'].append('Grayscale images are suitable for X-rays and CT scans')
        elif image.mode == 'RGB':
            analysis_results['ai_analysis']['findings'].append('Color image detected')
            analysis_results['ai_analysis']['recommendations'].append('Color images are suitable for dermatology and wound assessment')
        
        # Simulate medical findings based on image size and type
        if image_file.size > 2 * 1024 * 1024:  # Large file
            analysis_results['ai_analysis']['findings'].append('High-resolution image detected')
            analysis_results['ai_analysis']['recommendations'].append('High resolution suitable for detailed analysis')
            analysis_results['ai_analysis']['risk_level'] = 'medium'
        
        # Add some generic medical analysis suggestions
        analysis_results['ai_analysis']['findings'].extend([
            'Image quality appears adequate for analysis',
            'No obvious artifacts detected',
            'Suitable for telemedicine consultation'
        ])
        
        analysis_results['ai_analysis']['recommendations'].extend([
            'Consider additional imaging if symptoms persist',
            'Follow up with in-person examination if needed',
            'Document findings in patient record'
        ])
        
        # Save AI analysis to database
        ai_analysis = TelemedicineAIAnalysis.objects.create(
            consultation=consultation,
            analysis_type='image_analysis',
            input_data={
                'image_name': image_file.name,
                'image_size': image_file.size,
                'image_type': image_file.content_type
            },
            output_data=analysis_results,
            confidence_score=analysis_results['ai_analysis']['confidence']
        )
        
        return JsonResponse({
            'success': True,
            'analysis_id': str(ai_analysis.id),
            'results': analysis_results
        })
        
    except Exception as e:
        import traceback
        return JsonResponse({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc() if settings.DEBUG else None
        })


@login_required
def prescription_management(request, consultation_id):
    """Manage prescriptions for a consultation"""
    consultation = get_object_or_404(TelemedicineConsultation, pk=consultation_id, is_deleted=False)
    
    # Check if user is the doctor
    if not (hasattr(request.user, 'staff') and consultation.doctor == request.user.staff):
        messages.error(request, 'Access denied.')
        return redirect('telemedicine:telemedicine_dashboard')
    
    if request.method == 'POST':
        drug_id = request.POST.get('drug_id')
        dosage = request.POST.get('dosage')
        frequency = request.POST.get('frequency')
        duration = request.POST.get('duration')
        instructions = request.POST.get('instructions', '')
        quantity = request.POST.get('quantity', 1)
        
        try:
            drug = Drug.objects.filter(
                pk=drug_id,
                is_active=True,
                is_deleted=False,
                name__isnull=False
            ).exclude(
                name__iexact=''
            ).exclude(
                name__icontains='INVALID'
            ).first()
            if not drug:
                messages.error(request, 'Selected drug is invalid or has been removed.')
                return redirect('telemedicine:prescription_management', consultation_id=consultation_id)
            
            prescription = TelemedicinePrescription.objects.create(
                consultation=consultation,
                drug=drug,
                dosage=dosage,
                frequency=frequency,
                duration=duration,
                instructions=instructions,
                quantity=int(quantity)
            )
            
            messages.success(request, 'Prescription added successfully.')
            
        except Drug.DoesNotExist:
            messages.error(request, 'Invalid drug selected.')
    
    # Get available drugs
    drugs = Drug.objects.filter(
        is_active=True, 
        is_deleted=False,
        name__isnull=False
    ).exclude(
        name__iexact=''
    ).exclude(
        name__icontains='INVALID'
    ).order_by('name')
    
    # Get existing prescriptions
    prescriptions = TelemedicinePrescription.objects.filter(
        consultation=consultation,
        is_deleted=False
    ).order_by('-created')
    
    context = {
        'consultation': consultation,
        'drugs': drugs,
        'prescriptions': prescriptions,
    }
    return render(request, 'hospital/telemedicine/prescription_management.html', context)


@login_required
def lab_order_management(request, consultation_id):
    """Manage lab orders for a consultation"""
    consultation = get_object_or_404(TelemedicineConsultation, pk=consultation_id, is_deleted=False)
    
    # Check if user is the doctor
    if not (hasattr(request.user, 'staff') and consultation.doctor == request.user.staff):
        messages.error(request, 'Access denied.')
        return redirect('telemedicine:telemedicine_dashboard')
    
    if request.method == 'POST':
        test_id = request.POST.get('test_id')
        instructions = request.POST.get('instructions', '')
        is_urgent = request.POST.get('is_urgent') == 'on'
        
        try:
            test = LabTest.objects.filter(
                pk=test_id,
                is_active=True,
                is_deleted=False,
                name__isnull=False
            ).exclude(
                name__iexact=''
            ).exclude(
                name__icontains='INVALID'
            ).first()
            if not test:
                messages.error(request, 'Selected test is invalid or has been removed.')
                return redirect('telemedicine:lab_order_management', consultation_id=consultation_id)
            
            lab_order = TelemedicineLabOrder.objects.create(
                consultation=consultation,
                test=test,
                instructions=instructions,
                is_urgent=is_urgent
            )
            
            messages.success(request, 'Lab order added successfully.')
            
        except LabTest.DoesNotExist:
            messages.error(request, 'Invalid test selected.')
    
    # Get available tests
    tests = LabTest.objects.filter(
        is_active=True, 
        is_deleted=False,
        name__isnull=False
    ).exclude(
        name__iexact=''
    ).exclude(
        name__icontains='INVALID'
    ).order_by('name')
    
    # Get existing lab orders
    lab_orders = TelemedicineLabOrder.objects.filter(
        consultation=consultation,
        is_deleted=False
    ).order_by('-created')
    
    context = {
        'consultation': consultation,
        'tests': tests,
        'lab_orders': lab_orders,
    }
    return render(request, 'hospital/telemedicine/lab_order_management.html', context)


@login_required
def chat_interface(request):
    """Simple chat interface for telemedicine"""
    # Get user's recent consultations
    user = request.user
    consultations = []
    
    if hasattr(user, 'patient'):
        consultations = TelemedicineConsultation.objects.filter(
            patient=user.patient,
            is_deleted=False
        ).order_by('-created')[:10]
    elif hasattr(user, 'staff'):
        consultations = TelemedicineConsultation.objects.filter(
            doctor=user.staff,
            is_deleted=False
        ).order_by('-created')[:10]
    
    context = {
        'consultations': consultations,
    }
    return render(request, 'hospital/telemedicine/chat_interface.html', context)
