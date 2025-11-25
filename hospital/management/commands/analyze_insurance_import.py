"""
Analyze insurance import data and show statistics
"""
import re
import os
from django.core.management.base import BaseCommand, CommandError
from collections import defaultdict
from hospital.models import Patient
from hospital.models_insurance_companies import InsuranceCompany, PatientInsurance


class Command(BaseCommand):
    help = 'Analyze insurance import data and show statistics'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--sql-dir',
            type=str,
            default=r'C:\Users\user\Videos\DS',
            help='Directory containing SQL files'
        )
    
    def handle(self, *args, **options):
        sql_dir = options['sql_dir']
        
        self.stdout.write(self.style.SUCCESS('=== Insurance Import Analysis ===\n'))
        
        # Current database state
        self.stdout.write(self.style.WARNING('Current Database State:'))
        self.stdout.write(f'  Patients: {Patient.objects.count()}')
        self.stdout.write(f'  Insurance Companies: {InsuranceCompany.objects.count()}')
        self.stdout.write(f'  Patient Insurance Enrollments: {PatientInsurance.objects.count()}\n')
        
        # Analyze SQL files
        insurance_data_file = os.path.join(sql_dir, 'insurance_data.sql')
        patient_data_file = os.path.join(sql_dir, 'patient_data.sql')
        
        if os.path.exists(insurance_data_file):
            self.analyze_insurance_data(insurance_data_file)
        
        if os.path.exists(patient_data_file):
            self.analyze_patient_data(patient_data_file)
        
        # Recommendations
        self.stdout.write(self.style.SUCCESS('\n=== Recommendations ==='))
        
        if Patient.objects.count() == 0:
            self.stdout.write(self.style.WARNING(
                '1. Import patients first: python manage.py import_legacy_patients --patients-only'
            ))
            self.stdout.write(self.style.WARNING(
                '2. Then link insurance: python manage.py import_legacy_patients --insurance-only'
            ))
        elif PatientInsurance.objects.count() == 0:
            self.stdout.write(self.style.WARNING(
                'Import insurance links: python manage.py import_legacy_patients --insurance-only'
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                '✓ Patients and insurance data already in database!'
            ))
    
    def analyze_insurance_data(self, file_path):
        """Analyze insurance_data.sql file"""
        self.stdout.write(self.style.WARNING('Analyzing insurance_data.sql...'))
        
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        # Count records
        insert_pattern = r'INSERT INTO insurance_data VALUES\((.*?)\);'
        matches = re.findall(insert_pattern, content, re.DOTALL)
        
        self.stdout.write(f'  Total insurance records: {len(matches)}')
        
        # Analyze by type
        type_counts = defaultdict(int)
        company_counts = defaultdict(int)
        with_policy = 0
        without_policy = 0
        
        for match in matches[:1000]:  # Sample first 1000
            try:
                import csv
                from io import StringIO
                reader = csv.reader(StringIO(match.strip()), delimiter=',', quotechar='"')
                values = list(reader)[0]
                
                if len(values) > 26:
                    ins_type = values[1] if values[1] else 'unknown'
                    provider = values[2] if values[2] else 'none'
                    policy = values[4] if values[4] else ''
                    
                    type_counts[ins_type] += 1
                    if provider not in ['', '0', 'NULL', ' ']:
                        company_counts[provider] += 1
                    
                    if policy and policy != 'NULL':
                        with_policy += 1
                    else:
                        without_policy += 1
            except:
                pass
        
        self.stdout.write(f'\n  By Type (sample of 1000):')
        for ins_type, count in sorted(type_counts.items()):
            self.stdout.write(f'    {ins_type}: {count}')
        
        self.stdout.write(f'\n  Top Insurance Companies (sample of 1000):')
        for company_id, count in sorted(company_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
            insurance = InsuranceCompany.objects.filter(code=f'INS{company_id}').first() or \
                       InsuranceCompany.objects.filter(code=company_id).first()
            company_name = insurance.name if insurance else f'Unknown ({company_id})'
            self.stdout.write(f'    {company_name}: {count} patients')
        
        self.stdout.write(f'\n  Policy Numbers:')
        self.stdout.write(f'    With policy number: {with_policy}')
        self.stdout.write(f'    Without policy number: {without_policy}\n')
    
    def analyze_patient_data(self, file_path):
        """Analyze patient_data.sql file"""
        self.stdout.write(self.style.WARNING('Analyzing patient_data.sql...'))
        
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        # Count records
        insert_pattern = r'INSERT INTO patient_data VALUES\((.*?)\);'
        matches = re.findall(insert_pattern, content, re.DOTALL)
        
        self.stdout.write(f'  Total patient records in SQL file: {len(matches)}\n')



















