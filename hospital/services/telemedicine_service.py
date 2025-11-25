"""
Telemedicine Service
Advanced telemedicine functionality with AI integration
"""
import requests
import json
from django.conf import settings
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal
import uuid

from ..models_telemedicine import (
    TelemedicineConsultation, TelemedicineMessage, TelemedicinePrescription,
    TelemedicineLabOrder, TelemedicineVitalSigns, TelemedicineAIAnalysis,
    TelemedicineDevice, TelemedicineNotification, TelemedicinePayment
)


class TelemedicineService:
    """Advanced telemedicine service with AI integration"""
    
    def __init__(self):
        self.ai_api_key = getattr(settings, 'AI_API_KEY', 'your-ai-api-key')
        self.ai_base_url = getattr(settings, 'AI_BASE_URL', 'https://api.openai.com/v1')
        self.webrtc_config = {
            'iceServers': [
                {'urls': 'stun:stun.l.google.com:19302'},
                {'urls': 'stun:stun1.l.google.com:19302'}
            ]
        }
    
    def create_consultation(self, patient, doctor, consultation_type='video', 
                          scheduled_at=None, chief_complaint='', priority='medium'):
        """Create a new telemedicine consultation"""
        try:
            # Generate consultation ID
            consultation_id = f"TC{timezone.now().strftime('%Y%m%d%H%M%S')}"
            
            # Set default scheduled time if not provided
            if not scheduled_at:
                scheduled_at = timezone.now() + timedelta(hours=1)
            
            # Create consultation
            consultation = TelemedicineConsultation.objects.create(
                consultation_id=consultation_id,
                patient=patient,
                doctor=doctor,
                consultation_type=consultation_type,
                scheduled_at=scheduled_at,
                chief_complaint=chief_complaint,
                priority=priority,
                consultation_fee=Decimal('50.00')  # Default fee
            )
            
            # Create meeting room
            meeting_room_id = str(uuid.uuid4())
            consultation.meeting_room_id = meeting_room_id
            consultation.meeting_url = f"/hms/telemedicine/room/{meeting_room_id}/"
            consultation.save()
            
            # Send notifications
            self._send_consultation_notifications(consultation)
            
            return consultation
            
        except Exception as e:
            raise Exception(f"Failed to create consultation: {str(e)}")
    
    def start_consultation(self, consultation):
        """Start a telemedicine consultation"""
        try:
            if consultation.status != 'scheduled':
                raise Exception("Consultation is not in scheduled status")
            
            if not consultation.can_start():
                raise Exception("Consultation cannot be started yet")
            
            # Update consultation status
            consultation.status = 'in_progress'
            consultation.started_at = timezone.now()
            consultation.save()
            
            # Send notifications
            self._send_consultation_started_notifications(consultation)
            
            return consultation
            
        except Exception as e:
            raise Exception(f"Failed to start consultation: {str(e)}")
    
    def end_consultation(self, consultation, quality_rating=None):
        """End a telemedicine consultation"""
        try:
            if consultation.status != 'in_progress':
                raise Exception("Consultation is not in progress")
            
            # Update consultation status
            consultation.status = 'completed'
            consultation.ended_at = timezone.now()
            
            # Calculate duration
            if consultation.started_at:
                duration = consultation.ended_at - consultation.started_at
                consultation.duration_minutes = int(duration.total_seconds() / 60)
            
            if quality_rating:
                consultation.quality_rating = quality_rating
            
            consultation.save()
            
            # Send notifications
            self._send_consultation_completed_notifications(consultation)
            
            return consultation
            
        except Exception as e:
            raise Exception(f"Failed to end consultation: {str(e)}")
    
    def send_message(self, consultation, sender, content, message_type='text', attachment=None):
        """Send a message during consultation"""
        try:
            if consultation.status != 'in_progress':
                raise Exception("Consultation is not active")
            
            # Create message
            message = TelemedicineMessage.objects.create(
                consultation=consultation,
                sender=sender,
                message_type=message_type,
                content=content,
                attachment=attachment
            )
            
            # Send notification to other participant
            self._send_message_notification(consultation, message)
            
            return message
            
        except Exception as e:
            raise Exception(f"Failed to send message: {str(e)}")
    
    def analyze_symptoms(self, symptoms_data):
        """AI-powered symptom analysis"""
        try:
            # Prepare data for AI analysis
            analysis_data = {
                'symptoms': symptoms_data.get('symptoms', []),
                'age': symptoms_data.get('age'),
                'gender': symptoms_data.get('gender'),
                'medical_history': symptoms_data.get('medical_history', ''),
                'symptom_details': symptoms_data.get('symptom_details', {})
            }
            
            # Call AI service (simulated for now)
            ai_response = self._call_ai_symptom_analyzer(analysis_data)
            
            # Create AI analysis record
            ai_analysis = TelemedicineAIAnalysis.objects.create(
                analysis_type='symptom_checker',
                input_data=analysis_data,
                ai_response=ai_response,
                confidence_score=ai_response.get('confidence', 0.0)
            )
            
            return ai_response
            
        except Exception as e:
            raise Exception(f"Failed to analyze symptoms: {str(e)}")
    
    def generate_prescription(self, consultation, drug, dosage, frequency, duration, instructions=''):
        """Generate prescription during consultation"""
        try:
            if consultation.status != 'in_progress':
                raise Exception("Consultation is not active")
            
            # Create prescription
            prescription = TelemedicinePrescription.objects.create(
                consultation=consultation,
                drug=drug,
                dosage=dosage,
                frequency=frequency,
                duration=duration,
                instructions=instructions
            )
            
            # Send notification
            self._send_prescription_notification(consultation, prescription)
            
            return prescription
            
        except Exception as e:
            raise Exception(f"Failed to generate prescription: {str(e)}")
    
    def create_lab_order(self, consultation, test, instructions='', is_urgent=False):
        """Create lab order during consultation"""
        try:
            if consultation.status != 'in_progress':
                raise Exception("Consultation is not active")
            
            # Create lab order
            lab_order = TelemedicineLabOrder.objects.create(
                consultation=consultation,
                test=test,
                instructions=instructions,
                is_urgent=is_urgent
            )
            
            # Send notification
            self._send_lab_order_notification(consultation, lab_order)
            
            return lab_order
            
        except Exception as e:
            raise Exception(f"Failed to create lab order: {str(e)}")
    
    def record_vital_signs(self, consultation, recorded_by, vital_data):
        """Record vital signs during consultation"""
        try:
            if consultation.status != 'in_progress':
                raise Exception("Consultation is not active")
            
            # Create vital signs record
            vital_signs = TelemedicineVitalSigns.objects.create(
                consultation=consultation,
                recorded_by=recorded_by,
                **vital_data
            )
            
            # Send notification
            self._send_vital_signs_notification(consultation, vital_signs)
            
            return vital_signs
            
        except Exception as e:
            raise Exception(f"Failed to record vital signs: {str(e)}")
    
    def process_payment(self, consultation, payment_method, amount=None):
        """Process payment for consultation"""
        try:
            if not amount:
                amount = consultation.consultation_fee
            
            # Create payment record
            payment = TelemedicinePayment.objects.create(
                consultation=consultation,
                amount=amount,
                payment_method=payment_method,
                payment_status='pending'
            )
            
            # Process payment (integrate with payment gateway)
            # This would integrate with actual payment processors
            payment.payment_status = 'completed'
            payment.paid_at = timezone.now()
            payment.transaction_id = f"TXN{timezone.now().strftime('%Y%m%d%H%M%S')}"
            payment.save()
            
            # Update consultation payment status
            consultation.payment_status = 'paid'
            consultation.save()
            
            return payment
            
        except Exception as e:
            raise Exception(f"Failed to process payment: {str(e)}")
    
    def get_consultation_stats(self, doctor=None, patient=None, date_range=None):
        """Get consultation statistics"""
        try:
            queryset = TelemedicineConsultation.objects.filter(is_deleted=False)
            
            if doctor:
                queryset = queryset.filter(doctor=doctor)
            if patient:
                queryset = queryset.filter(patient=patient)
            if date_range:
                queryset = queryset.filter(created__range=date_range)
            
            stats = {
                'total_consultations': queryset.count(),
                'completed_consultations': queryset.filter(status='completed').count(),
                'active_consultations': queryset.filter(status='in_progress').count(),
                'scheduled_consultations': queryset.filter(status='scheduled').count(),
                'avg_duration': queryset.filter(duration_minutes__isnull=False).aggregate(
                    avg_duration=models.Avg('duration_minutes')
                )['avg_duration'] or 0,
                'avg_rating': queryset.filter(quality_rating__isnull=False).aggregate(
                    avg_rating=models.Avg('quality_rating')
                )['avg_rating'] or 0,
            }
            
            return stats
            
        except Exception as e:
            raise Exception(f"Failed to get consultation stats: {str(e)}")
    
    def _call_ai_symptom_analyzer(self, data):
        """Call AI service for symptom analysis"""
        # This would integrate with actual AI services like OpenAI, Google Health, etc.
        # For now, return simulated response
        
        symptoms = data.get('symptoms', [])
        age = data.get('age', 30)
        gender = data.get('gender', 'unknown')
        
        # Simulate AI analysis
        triage_score = min(10, len(symptoms) * 1.5 + (age / 10))
        
        response = {
            'triage_score': round(triage_score, 1),
            'urgency_level': 'high' if triage_score > 8 else 'medium' if triage_score > 5 else 'low',
            'recommended_actions': [
                'Schedule a consultation within 24 hours' if triage_score > 7 else 'Monitor symptoms closely',
                'Seek immediate care if symptoms worsen',
                'Follow up with your primary care provider'
            ],
            'possible_conditions': self._get_possible_conditions(symptoms),
            'confidence': 0.85,
            'ai_insights': self._generate_ai_insights(symptoms, age, gender)
        }
        
        return response
    
    def _get_possible_conditions(self, symptoms):
        """Get possible conditions based on symptoms"""
        condition_map = {
            'fever': ['Common cold', 'Viral infection', 'Bacterial infection'],
            'cough': ['Common cold', 'Bronchitis', 'Pneumonia'],
            'headache': ['Tension headache', 'Migraine', 'Sinusitis'],
            'fatigue': ['Anemia', 'Depression', 'Chronic fatigue syndrome'],
            'chest_pain': ['Angina', 'Heart attack', 'Costochondritis'],
            'shortness_breath': ['Asthma', 'COPD', 'Pneumonia']
        }
        
        conditions = []
        for symptom in symptoms:
            if symptom in condition_map:
                conditions.extend(condition_map[symptom])
        
        # Remove duplicates and return top 3
        return list(set(conditions))[:3]
    
    def _generate_ai_insights(self, symptoms, age, gender):
        """Generate AI insights based on symptoms and demographics"""
        insights = []
        
        if 'fever' in symptoms and 'cough' in symptoms:
            insights.append("Fever with cough may indicate respiratory infection")
        
        if age > 65 and 'chest_pain' in symptoms:
            insights.append("Chest pain in elderly patients requires immediate evaluation")
        
        if 'fatigue' in symptoms and len(symptoms) > 3:
            insights.append("Multiple symptoms with fatigue may indicate systemic illness")
        
        return insights
    
    def _send_consultation_notifications(self, consultation):
        """Send consultation scheduled notifications"""
        # Patient notification
        TelemedicineNotification.objects.create(
            user=consultation.patient.user,
            notification_type='consultation_scheduled',
            title='Consultation Scheduled',
            message=f'Your consultation with Dr. {consultation.doctor.user.get_full_name()} has been scheduled for {consultation.scheduled_at.strftime("%B %d, %Y at %I:%M %p")}.',
            consultation=consultation,
            action_url=f'/hms/telemedicine/consultation/{consultation.id}/'
        )
        
        # Doctor notification
        TelemedicineNotification.objects.create(
            user=consultation.doctor.user,
            notification_type='consultation_scheduled',
            title='New Consultation Scheduled',
            message=f'You have a consultation scheduled with {consultation.patient.full_name} for {consultation.scheduled_at.strftime("%B %d, %Y at %I:%M %p")}.',
            consultation=consultation,
            action_url=f'/hms/telemedicine/consultation/{consultation.id}/'
        )
    
    def _send_consultation_started_notifications(self, consultation):
        """Send consultation started notifications"""
        TelemedicineNotification.objects.create(
            user=consultation.patient.user,
            notification_type='consultation_starting',
            title='Consultation Started',
            message=f'Your consultation with Dr. {consultation.doctor.user.get_full_name()} has started.',
            consultation=consultation,
            action_url=f'/hms/telemedicine/consultation/{consultation.id}/'
        )
    
    def _send_consultation_completed_notifications(self, consultation):
        """Send consultation completed notifications"""
        TelemedicineNotification.objects.create(
            user=consultation.patient.user,
            notification_type='consultation_completed',
            title='Consultation Completed',
            message=f'Your consultation with Dr. {consultation.doctor.user.get_full_name()} has been completed.',
            consultation=consultation,
            action_url=f'/hms/telemedicine/consultation/{consultation.id}/'
        )
    
    def _send_message_notification(self, consultation, message):
        """Send message notification"""
        # Determine recipient
        recipient = consultation.patient.user if message.sender == consultation.doctor.user else consultation.doctor.user
        
        TelemedicineNotification.objects.create(
            user=recipient,
            notification_type='message_received',
            title='New Message',
            message=f'You have a new message in consultation {consultation.consultation_id}',
            consultation=consultation,
            action_url=f'/hms/telemedicine/consultation/{consultation.id}/'
        )
    
    def _send_prescription_notification(self, consultation, prescription):
        """Send prescription notification"""
        TelemedicineNotification.objects.create(
            user=consultation.patient.user,
            notification_type='prescription_ready',
            title='Prescription Ready',
            message=f'Your prescription for {prescription.drug.name} is ready.',
            consultation=consultation,
            action_url=f'/hms/telemedicine/consultation/{consultation.id}/'
        )
    
    def _send_lab_order_notification(self, consultation, lab_order):
        """Send lab order notification"""
        TelemedicineNotification.objects.create(
            user=consultation.patient.user,
            notification_type='lab_order_created',
            title='Lab Order Created',
            message=f'Lab order for {lab_order.test.name} has been created.',
            consultation=consultation,
            action_url=f'/hms/telemedicine/consultation/{consultation.id}/'
        )
    
    def _send_vital_signs_notification(self, consultation, vital_signs):
        """Send vital signs notification"""
        TelemedicineNotification.objects.create(
            user=consultation.patient.user,
            notification_type='vital_signs_recorded',
            title='Vital Signs Recorded',
            message='Your vital signs have been recorded during the consultation.',
            consultation=consultation,
            action_url=f'/hms/telemedicine/consultation/{consultation.id}/'
        )


# Create service instance
telemedicine_service = TelemedicineService()




































