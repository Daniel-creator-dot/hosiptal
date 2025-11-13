"""
Django Management Command to Check Patient Insurance Enrollment Status
Shows detailed statistics about patient insurance coverage
"""
from django.core.management.base import BaseCommand
from django.db.models import Count, Q
from django.utils import timezone
from hospital.models import Patient
from hospital.models_insurance_companies import InsuranceCompany, PatientInsurance


class Command(BaseCommand):
    help = 'Check patient insurance enrollment status and statistics'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--detailed',
            action='store_true',
            help='Show detailed patient-by-patient breakdown'
        )
        parser.add_argument(
            '--company',
            type=str,
            help='Filter by insurance company name or code'
        )
    
    def handle(self, *args, **options):
        detailed = options['detailed']
        company_filter = options['company']
        
        self.stdout.write(self.style.SUCCESS('=== PATIENT INSURANCE ENROLLMENT CHECK ===\n'))
        
        # Overall statistics
        total_patients = Patient.objects.filter(is_deleted=False).count()
        enrolled_patients = Patient.objects.filter(
            insurances__isnull=False,
            insurances__is_deleted=False
        ).distinct().count()
        
        total_enrollments = PatientInsurance.objects.filter(is_deleted=False).count()
        active_enrollments = PatientInsurance.objects.filter(
            is_deleted=False,
            status='active'
        ).count()
        
        self.stdout.write(self.style.WARNING('OVERALL STATISTICS:'))
        self.stdout.write(f'  Total Patients: {total_patients}')
        self.stdout.write(f'  Patients with Insurance: {enrolled_patients}')
        self.stdout.write(f'  Patients without Insurance: {total_patients - enrolled_patients}')
        self.stdout.write(f'  Total Insurance Enrollments: {total_enrollments}')
        self.stdout.write(f'  Active Enrollments: {active_enrollments}\n')
        
        # Insurance companies
        total_companies = InsuranceCompany.objects.filter(is_deleted=False).count()
        active_companies = InsuranceCompany.objects.filter(
            is_deleted=False,
            is_active=True
        ).count()
        
        self.stdout.write(self.style.WARNING('INSURANCE COMPANIES:'))
        self.stdout.write(f'  Total Companies: {total_companies}')
        self.stdout.write(f'  Active Companies: {active_companies}\n')
        
        # Enrollment by company
        self.stdout.write(self.style.WARNING('ENROLLMENT BY INSURANCE COMPANY:'))
        
        enrollments_by_company = PatientInsurance.objects.filter(
            is_deleted=False,
            status='active'
        ).values(
            'insurance_company__name',
            'insurance_company__code'
        ).annotate(
            patient_count=Count('patient', distinct=True)
        ).order_by('-patient_count')
        
        if company_filter:
            enrollments_by_company = enrollments_by_company.filter(
                Q(insurance_company__name__icontains=company_filter) |
                Q(insurance_company__code__icontains=company_filter)
            )
        
        if enrollments_by_company.exists():
            for idx, enrollment in enumerate(enrollments_by_company[:20], 1):
                company_name = enrollment['insurance_company__name']
                company_code = enrollment['insurance_company__code']
                count = enrollment['patient_count']
                self.stdout.write(f'  {idx}. {company_name} ({company_code}): {count} patients')
        else:
            self.stdout.write(self.style.WARNING('  No active enrollments found'))
        
        # Companies with no enrollments
        self.stdout.write(self.style.WARNING('\nINSURANCE COMPANIES WITH NO ENROLLMENTS:'))
        companies_no_enrollment = InsuranceCompany.objects.filter(
            is_deleted=False,
            is_active=True
        ).annotate(
            enrollment_count=Count('patient_enrollments', filter=Q(
                patient_enrollments__is_deleted=False,
                patient_enrollments__status='active'
            ))
        ).filter(enrollment_count=0)
        
        if companies_no_enrollment.exists():
            self.stdout.write(f'  Total: {companies_no_enrollment.count()} companies')
            for company in companies_no_enrollment[:15]:
                self.stdout.write(f'    - {company.name} ({company.code})')
            if companies_no_enrollment.count() > 15:
                self.stdout.write(f'    ... and {companies_no_enrollment.count() - 15} more')
        else:
            self.stdout.write('  All active companies have at least one enrollment')
        
        # Patients with old insurance fields but no PatientInsurance record
        self.stdout.write(self.style.WARNING('\nPATIENTS WITH OLD INSURANCE FIELDS:'))
        patients_with_old_insurance = Patient.objects.filter(
            is_deleted=False
        ).exclude(
            Q(insurance_company='') & Q(insurance_id='')
        ).count()
        
        patients_with_new_insurance = Patient.objects.filter(
            is_deleted=False,
            insurances__isnull=False,
            insurances__is_deleted=False
        ).distinct().count()
        
        self.stdout.write(f'  Patients with old insurance_company field: {patients_with_old_insurance}')
        self.stdout.write(f'  Patients with new PatientInsurance records: {patients_with_new_insurance}')
        
        if patients_with_old_insurance > patients_with_new_insurance:
            self.stdout.write(self.style.WARNING(
                f'  WARNING: {patients_with_old_insurance - patients_with_new_insurance} patients need migration to new system'
            ))
        
        # Detailed patient breakdown
        if detailed:
            self.stdout.write(self.style.WARNING('\nDETAILED PATIENT BREAKDOWN:'))
            
            if company_filter:
                patients = Patient.objects.filter(
                    is_deleted=False,
                    insurances__insurance_company__name__icontains=company_filter,
                    insurances__is_deleted=False
                ).distinct()[:50]
            else:
                patients = Patient.objects.filter(
                    is_deleted=False
                ).prefetch_related('insurances')[:50]
            
            for patient in patients:
                enrollments = patient.insurances.filter(is_deleted=False)
                if enrollments.exists():
                    self.stdout.write(f'\n  Patient: {patient.full_name} (MRN: {patient.mrn})')
                    for enrollment in enrollments:
                        status_icon = '[Active]' if enrollment.status == 'active' else '[Inactive]'
                        primary_icon = '[PRIMARY]' if enrollment.is_primary else '[Secondary]'
                        self.stdout.write(
                            f'    {status_icon} {primary_icon} {enrollment.insurance_company.name} '
                            f'({enrollment.member_id}) - {enrollment.status}'
                        )
                else:
                    # Check old fields
                    if patient.insurance_company or patient.insurance_id:
                        self.stdout.write(
                            f'\n  Patient: {patient.full_name} (MRN: {patient.mrn}) '
                            f'- OLD FIELDS: {patient.insurance_company} / {patient.insurance_id}'
                        )
        
        # Recommendations
        self.stdout.write(self.style.SUCCESS('\n\n=== RECOMMENDATIONS ==='))
        
        if total_enrollments == 0:
            self.stdout.write(self.style.WARNING(
                'WARNING: No insurance enrollments found!'
            ))
            self.stdout.write('   Run one of these commands to import insurance data:')
            self.stdout.write('   1. python manage.py import_legacy_patients (full import)')
            self.stdout.write('   2. python manage.py link_patient_insurance (link only)')
        elif enrolled_patients < total_patients * 0.5:
            self.stdout.write(self.style.WARNING(
                f'WARNING: Only {(enrolled_patients/total_patients)*100:.1f}% of patients are enrolled in insurance'
            ))
            self.stdout.write('   Consider importing more insurance data')
        else:
            self.stdout.write(self.style.SUCCESS(
                f'OK: {(enrolled_patients/total_patients)*100:.1f}% of patients are enrolled in insurance'
            ))
        
        # Verification suggestions
        if active_enrollments > 0:
            self.stdout.write('\nVERIFICATION:')
            # Check for patients with multiple primary insurances
            patients_multiple_primary = Patient.objects.filter(
                is_deleted=False,
                insurances__is_deleted=False,
                insurances__is_primary=True
            ).annotate(
                primary_count=Count('insurances', filter=Q(
                    insurances__is_deleted=False,
                    insurances__is_primary=True
                ))
            ).filter(primary_count__gt=1)
            
            if patients_multiple_primary.exists():
                self.stdout.write(self.style.WARNING(
                    f'  WARNING: {patients_multiple_primary.count()} patients have multiple PRIMARY insurances'
                ))
            else:
                self.stdout.write('  OK: No patients with multiple primary insurances')
            
            # Check for invalid dates
            invalid_dates = PatientInsurance.objects.filter(
                is_deleted=False,
                effective_date__gt=timezone.now().date()
            ).count()
            
            if invalid_dates > 0:
                self.stdout.write(self.style.WARNING(
                    f'  WARNING: {invalid_dates} enrollments have future effective dates'
                ))
            else:
                self.stdout.write('  OK: All enrollment dates are valid')

