"""
Front Desk Report Generation Views
Allows front desk staff to generate reports with date filtering for:
- Visits
- Appointments
- Patient Registrations
- GP/General Practitioner Consultations
"""
import csv
import logging
from datetime import datetime, date, timedelta
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.db.models import Q, Count, Sum
from django.core.paginator import Paginator
from django.db import models

from .models import Patient, Appointment, Staff, Department
from .models_medical_records import VisitRecord
from .models import Encounter
from .decorators import role_required
from .utils_roles import get_user_role


logger = logging.getLogger(__name__)


@login_required
@role_required('receptionist', 'admin')
def frontdesk_reports_dashboard(request):
    """Main dashboard for front desk report generation"""
    today = timezone.now().date()
    
    # Get quick stats for today
    today_registrations = Patient.objects.filter(
        created__date=today,
        is_deleted=False
    ).count()
    
    today_appointments = Appointment.objects.filter(
        appointment_date__date=today,
        is_deleted=False
    ).count()
    
    today_visits = VisitRecord.objects.filter(
        visit_date=today,
        is_deleted=False
    ).count()
    
    # GP consultations (encounters with doctors)
    today_gp_consultations = Encounter.objects.filter(
        created__date=today,
        is_deleted=False,
        encounter_type='outpatient'
    ).select_related('provider').filter(
        provider__profession='doctor'
    ).count()
    
    context = {
        'title': 'Front Desk Reports',
        'today': today,
        'today_registrations': today_registrations,
        'today_appointments': today_appointments,
        'today_visits': today_visits,
        'today_gp_consultations': today_gp_consultations,
    }
    
    return render(request, 'hospital/frontdesk_reports/dashboard.html', context)


@login_required
@role_required('receptionist', 'admin')
def frontdesk_report_generate(request):
    """Generate reports based on selected criteria"""
    report_type = request.GET.get('report_type', 'visits')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    export_format = request.GET.get('export', None)
    
    # Parse dates
    try:
        if start_date:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        else:
            start_date = timezone.now().date() - timedelta(days=30)
        
        if end_date:
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        else:
            end_date = timezone.now().date()
    except (ValueError, TypeError):
        start_date = timezone.now().date() - timedelta(days=30)
        end_date = timezone.now().date()
    
    # Get data based on report type
    if report_type == 'visits':
        data = _get_visits_report(start_date, end_date)
        template = 'hospital/frontdesk_reports/visits_report.html'
        export_filename = f'visits_report_{start_date}_to_{end_date}.csv'
        
    elif report_type == 'appointments':
        data = _get_appointments_report(start_date, end_date)
        template = 'hospital/frontdesk_reports/appointments_report.html'
        export_filename = f'appointments_report_{start_date}_to_{end_date}.csv'
        
    elif report_type == 'registrations':
        data = _get_registrations_report(start_date, end_date)
        template = 'hospital/frontdesk_reports/registrations_report.html'
        export_filename = f'registrations_report_{start_date}_to_{end_date}.csv'
        
    elif report_type == 'gp_consultations':
        data = _get_gp_consultations_report(start_date, end_date)
        template = 'hospital/frontdesk_reports/gp_consultations_report.html'
        export_filename = f'gp_consultations_report_{start_date}_to_{end_date}.csv'
        
    else:
        return redirect('hospital:frontdesk_reports_dashboard')
    
    # Handle export
    if export_format == 'csv':
        return _export_to_csv(data, export_filename, report_type)
    elif export_format == 'pdf':
        # PDF export can be added later if needed
        return HttpResponse("PDF export coming soon", content_type='text/plain')
    
    # Pagination
    paginator = Paginator(data['items'], 50)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    context = {
        'title': f'{data["title"]} Report',
        'report_type': report_type,
        'start_date': start_date,
        'end_date': end_date,
        'data': data,
        'page_obj': page_obj,
        'summary': data.get('summary', {}),
    }
    
    return render(request, template, context)


def _get_visits_report(start_date, end_date):
    """Get visits report data"""
    visits = VisitRecord.objects.filter(
        visit_date__gte=start_date,
        visit_date__lte=end_date,
        is_deleted=False
    ).select_related('patient', 'provider', 'encounter').order_by('-visit_date', '-visit_time')
    
    total_visits = visits.count()
    visits_by_type = visits.values('visit_type').annotate(count=Count('id'))
    
    summary = {
        'total_visits': total_visits,
        'visits_by_type': list(visits_by_type),
    }
    
    items = []
    for visit in visits:
        items.append({
            'visit_number': visit.visit_number,
            'visit_date': visit.visit_date,
            'visit_time': visit.visit_time,
            'patient_name': visit.patient.full_name if visit.patient else 'N/A',
            'patient_mrn': visit.patient.mrn if visit.patient else 'N/A',
            'visit_type': visit.visit_type.title() if visit.visit_type else 'N/A',
            'provider': visit.provider.user.get_full_name() if visit.provider and visit.provider.user else 'N/A',
            'chief_complaint': visit.chief_complaint[:100] if visit.chief_complaint else '',
            'disposition': visit.get_disposition_display() if visit.disposition else 'N/A',
        })
    
    return {
        'title': 'Visits',
        'items': items,
        'summary': summary,
    }


def _get_appointments_report(start_date, end_date):
    """Get appointments report data"""
    appointments = Appointment.objects.filter(
        appointment_date__date__gte=start_date,
        appointment_date__date__lte=end_date,
        is_deleted=False
    ).select_related('patient', 'provider', 'department').order_by('-appointment_date')
    
    total_appointments = appointments.count()
    appointments_by_status = appointments.values('status').annotate(count=Count('id'))
    appointments_by_department = appointments.values('department__name').annotate(count=Count('id'))
    
    summary = {
        'total_appointments': total_appointments,
        'by_status': list(appointments_by_status),
        'by_department': list(appointments_by_department),
    }
    
    items = []
    for appointment in appointments:
        items.append({
            'appointment_date': appointment.appointment_date.date(),
            'appointment_time': appointment.appointment_date.time(),
            'patient_name': appointment.patient.full_name if appointment.patient else 'N/A',
            'patient_mrn': appointment.patient.mrn if appointment.patient else 'N/A',
            'provider': appointment.provider.user.get_full_name() if appointment.provider and appointment.provider.user else 'N/A',
            'department': appointment.department.name if appointment.department else 'N/A',
            'status': appointment.get_status_display(),
            'reason': appointment.reason[:100] if appointment.reason else '',
            'duration': f"{appointment.duration_minutes} min",
        })
    
    return {
        'title': 'Appointments',
        'items': items,
        'summary': summary,
    }


def _get_registrations_report(start_date, end_date):
    """Get patient registrations report data"""
    registrations = Patient.objects.filter(
        created__date__gte=start_date,
        created__date__lte=end_date,
        is_deleted=False
    ).order_by('-created')
    
    total_registrations = registrations.count()
    registrations_by_gender = registrations.values('gender').annotate(count=Count('id'))
    
    summary = {
        'total_registrations': total_registrations,
        'by_gender': list(registrations_by_gender),
    }
    
    items = []
    for patient in registrations:
        items.append({
            'registration_date': patient.created.date(),
            'registration_time': patient.created.time(),
            'mrn': patient.mrn,
            'full_name': patient.full_name,
            'gender': patient.get_gender_display(),
            'date_of_birth': patient.date_of_birth,
            'phone_number': patient.phone_number or 'N/A',
            'email': patient.email or 'N/A',
            'address': patient.address[:100] if patient.address else 'N/A',
        })
    
    return {
        'title': 'Patient Registrations',
        'items': items,
        'summary': summary,
    }


def _get_gp_consultations_report(start_date, end_date):
    """Get GP/General Practitioner consultations report data"""
    # GP consultations are outpatient encounters with doctors
    consultations = Encounter.objects.filter(
        created__date__gte=start_date,
        created__date__lte=end_date,
        is_deleted=False,
        encounter_type='outpatient',
        provider__profession='doctor'
    ).select_related('patient', 'provider', 'provider__department').order_by('-created')
    
    total_consultations = consultations.count()
    consultations_by_department = consultations.values('provider__department__name').annotate(count=Count('id'))
    consultations_by_provider = consultations.values('provider__user__first_name', 'provider__user__last_name').annotate(count=Count('id'))
    
    summary = {
        'total_consultations': total_consultations,
        'by_department': list(consultations_by_department),
        'by_provider': list(consultations_by_provider),
    }
    
    items = []
    for consultation in consultations:
        # Get department through provider
        department_name = 'N/A'
        if consultation.provider and consultation.provider.department:
            department_name = consultation.provider.department.name
        
        items.append({
            'consultation_date': consultation.created.date(),
            'consultation_time': consultation.created.time(),
            'patient_name': consultation.patient.full_name if consultation.patient else 'N/A',
            'patient_mrn': consultation.patient.mrn if consultation.patient else 'N/A',
            'provider': consultation.provider.user.get_full_name() if consultation.provider and consultation.provider.user else 'N/A',
            'department': department_name,
            'status': consultation.get_status_display() if hasattr(consultation, 'get_status_display') else consultation.status,
        })
    
    return {
        'title': 'GP Consultations',
        'items': items,
        'summary': summary,
    }


def _export_to_csv(data, filename, report_type):
    """Export report data to CSV"""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    writer = csv.writer(response)
    
    # Write header based on report type
    if report_type == 'visits':
        writer.writerow(['Visit Number', 'Visit Date', 'Visit Time', 'Patient Name', 'MRN', 'Visit Type', 'Provider', 'Chief Complaint', 'Disposition'])
        for item in data['items']:
            writer.writerow([
                item['visit_number'],
                item['visit_date'],
                item['visit_time'],
                item['patient_name'],
                item['patient_mrn'],
                item['visit_type'],
                item['provider'],
                item['chief_complaint'],
                item['disposition'],
            ])
            
    elif report_type == 'appointments':
        writer.writerow(['Appointment Date', 'Time', 'Patient Name', 'MRN', 'Provider', 'Department', 'Status', 'Reason', 'Duration'])
        for item in data['items']:
            writer.writerow([
                item['appointment_date'],
                item['appointment_time'],
                item['patient_name'],
                item['patient_mrn'],
                item['provider'],
                item['department'],
                item['status'],
                item['reason'],
                item['duration'],
            ])
            
    elif report_type == 'registrations':
        writer.writerow(['Registration Date', 'Time', 'MRN', 'Full Name', 'Gender', 'Date of Birth', 'Phone', 'Email', 'Address'])
        for item in data['items']:
            writer.writerow([
                item['registration_date'],
                item['registration_time'],
                item['mrn'],
                item['full_name'],
                item['gender'],
                item['date_of_birth'],
                item['phone_number'],
                item['email'],
                item['address'],
            ])
            
    elif report_type == 'gp_consultations':
        writer.writerow(['Consultation Date', 'Time', 'Patient Name', 'MRN', 'Provider', 'Department', 'Status'])
        for item in data['items']:
            writer.writerow([
                item['consultation_date'],
                item['consultation_time'],
                item['patient_name'],
                item['patient_mrn'],
                item['provider'],
                item['department'],
                item['status'],
            ])
    
    return response

