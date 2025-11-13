"""
Management command to export data in various formats.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import datetime, timedelta
from hospital.models import Patient, Encounter, Invoice, Admission
import csv
import json


class Command(BaseCommand):
    help = 'Export data to CSV or JSON format'

    def add_arguments(self, parser):
        parser.add_argument(
            '--format',
            type=str,
            choices=['csv', 'json'],
            default='csv',
            help='Export format (csv or json)'
        )
        parser.add_argument(
            '--model',
            type=str,
            choices=['patient', 'encounter', 'invoice', 'admission'],
            default='patient',
            help='Model to export'
        )
        parser.add_argument(
            '--output',
            type=str,
            help='Output file path'
        )
        parser.add_argument(
            '--date-from',
            type=str,
            help='Start date (YYYY-MM-DD)'
        )
        parser.add_argument(
            '--date-to',
            type=str,
            help='End date (YYYY-MM-DD)'
        )

    def handle(self, *args, **options):
        format_type = options['format']
        model_type = options['model']
        output_file = options['output'] or f'{model_type}_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.{format_type}'
        
        date_from = None
        date_to = None
        if options['date_from']:
            date_from = datetime.strptime(options['date_from'], '%Y-%m-%d').date()
        if options['date_to']:
            date_to = datetime.strptime(options['date_to'], '%Y-%m-%d').date()
        
        # Get data based on model
        if model_type == 'patient':
            queryset = Patient.objects.filter(is_deleted=False)
            if date_from:
                queryset = queryset.filter(created__date__gte=date_from)
            if date_to:
                queryset = queryset.filter(created__date__lte=date_to)
            data = self.export_patients(queryset, format_type)
        
        elif model_type == 'encounter':
            queryset = Encounter.objects.filter(is_deleted=False)
            if date_from:
                queryset = queryset.filter(started_at__date__gte=date_from)
            if date_to:
                queryset = queryset.filter(started_at__date__lte=date_to)
            data = self.export_encounters(queryset, format_type)
        
        elif model_type == 'invoice':
            queryset = Invoice.objects.filter(is_deleted=False)
            if date_from:
                queryset = queryset.filter(issued_at__date__gte=date_from)
            if date_to:
                queryset = queryset.filter(issued_at__date__lte=date_to)
            data = self.export_invoices(queryset, format_type)
        
        elif model_type == 'admission':
            queryset = Admission.objects.filter(is_deleted=False)
            if date_from:
                queryset = queryset.filter(admit_date__date__gte=date_from)
            if date_to:
                queryset = queryset.filter(admit_date__date__lte=date_to)
            data = self.export_admissions(queryset, format_type)
        
        # Write to file
        with open(output_file, 'w', encoding='utf-8') as f:
            if format_type == 'csv':
                writer = csv.writer(f)
                writer.writerow(data[0])  # Header
                writer.writerows(data[1:])  # Rows
            else:
                json.dump(data, f, indent=2, default=str)
        
        self.stdout.write(self.style.SUCCESS(f'Successfully exported {queryset.count()} records to {output_file}'))

    def export_patients(self, queryset, format_type):
        if format_type == 'csv':
            data = [['MRN', 'First Name', 'Last Name', 'Date of Birth', 'Gender', 'Blood Type', 'Phone', 'Email', 'Created']]
            for patient in queryset:
                data.append([
                    patient.mrn,
                    patient.first_name,
                    patient.last_name,
                    patient.date_of_birth,
                    patient.get_gender_display(),
                    patient.blood_type or '',
                    patient.phone_number or '',
                    patient.email or '',
                    patient.created.strftime('%Y-%m-%d %H:%M:%S'),
                ])
            return data
        else:
            return [
                {
                    'mrn': p.mrn,
                    'first_name': p.first_name,
                    'last_name': p.last_name,
                    'date_of_birth': str(p.date_of_birth),
                    'gender': p.get_gender_display(),
                    'blood_type': p.blood_type,
                    'phone': p.phone_number,
                    'email': p.email,
                    'created': p.created.isoformat(),
                }
                for p in queryset
            ]

    def export_encounters(self, queryset, format_type):
        if format_type == 'csv':
            data = [['Patient', 'MRN', 'Type', 'Status', 'Provider', 'Started At', 'Ended At']]
            for encounter in queryset.select_related('patient', 'provider'):
                data.append([
                    encounter.patient.full_name,
                    encounter.patient.mrn,
                    encounter.get_encounter_type_display(),
                    encounter.get_status_display(),
                    encounter.provider.user.get_full_name() if encounter.provider else '',
                    encounter.started_at.strftime('%Y-%m-%d %H:%M:%S'),
                    encounter.ended_at.strftime('%Y-%m-%d %H:%M:%S') if encounter.ended_at else '',
                ])
            return data
        else:
            return [
                {
                    'patient': e.patient.full_name,
                    'mrn': e.patient.mrn,
                    'type': e.get_encounter_type_display(),
                    'status': e.get_status_display(),
                    'provider': e.provider.user.get_full_name() if e.provider else None,
                    'started_at': e.started_at.isoformat(),
                    'ended_at': e.ended_at.isoformat() if e.ended_at else None,
                }
                for e in queryset.select_related('patient', 'provider')
            ]

    def export_invoices(self, queryset, format_type):
        if format_type == 'csv':
            data = [['Invoice #', 'Patient', 'Payer', 'Total Amount', 'Balance', 'Status', 'Issued At', 'Due At']]
            for invoice in queryset.select_related('patient', 'payer'):
                data.append([
                    invoice.invoice_number,
                    invoice.patient.full_name,
                    invoice.payer.name,
                    str(invoice.total_amount),
                    str(invoice.balance),
                    invoice.get_status_display(),
                    invoice.issued_at.strftime('%Y-%m-%d %H:%M:%S'),
                    invoice.due_at.strftime('%Y-%m-%d %H:%M:%S'),
                ])
            return data
        else:
            return [
                {
                    'invoice_number': i.invoice_number,
                    'patient': i.patient.full_name,
                    'payer': i.payer.name,
                    'total_amount': str(i.total_amount),
                    'balance': str(i.balance),
                    'status': i.get_status_display(),
                    'issued_at': i.issued_at.isoformat(),
                    'due_at': i.due_at.isoformat(),
                }
                for i in queryset.select_related('patient', 'payer')
            ]

    def export_admissions(self, queryset, format_type):
        if format_type == 'csv':
            data = [['Patient', 'MRN', 'Ward', 'Bed', 'Admit Date', 'Discharge Date', 'Status', 'Duration (days)']]
            for admission in queryset.select_related('encounter__patient', 'ward', 'bed'):
                data.append([
                    admission.encounter.patient.full_name,
                    admission.encounter.patient.mrn,
                    admission.ward.name if admission.ward else '',
                    admission.bed.bed_number if admission.bed else '',
                    admission.admit_date.strftime('%Y-%m-%d %H:%M:%S'),
                    admission.discharge_date.strftime('%Y-%m-%d %H:%M:%S') if admission.discharge_date else '',
                    admission.get_status_display(),
                    str(admission.get_duration_days()),
                ])
            return data
        else:
            return [
                {
                    'patient': a.encounter.patient.full_name,
                    'mrn': a.encounter.patient.mrn,
                    'ward': a.ward.name if a.ward else None,
                    'bed': a.bed.bed_number if a.bed else None,
                    'admit_date': a.admit_date.isoformat(),
                    'discharge_date': a.discharge_date.isoformat() if a.discharge_date else None,
                    'status': a.get_status_display(),
                    'duration_days': a.get_duration_days(),
                }
                for a in queryset.select_related('encounter__patient', 'ward', 'bed')
            ]

