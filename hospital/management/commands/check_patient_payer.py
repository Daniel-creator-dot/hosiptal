"""
Check why a patient shows as cash on Payment Verification (pharmacy).
Prints primary_insurance, CorporateEmployee, PatientInsurance, and get_patient_payer_info result.

Usage:
  python manage.py check_patient_payer PMC2026009579
  python manage.py check_patient_payer PMC2026009579 PMC2026009570
  python manage.py check_patient_payer --all-pending   # run for all pending_payment prescriptions (first 20)
"""
from django.core.management.base import BaseCommand
from django.utils import timezone

from hospital.models import Patient
from hospital.models_payment_verification import PharmacyDispensing


class Command(BaseCommand):
    help = 'Check patient payer sources (primary_insurance, CorporateEmployee, PatientInsurance) for given MRN(s)'

    def add_arguments(self, parser):
        parser.add_argument(
            'mrn',
            nargs='*',
            help='One or more MRNs to check (e.g. PMC2026009579)',
        )
        parser.add_argument(
            '--all-pending',
            action='store_true',
            help='Check first 20 patients with pending_payment pharmacy prescriptions',
        )

    def handle(self, *args, **options):
        mrns = options.get('mrn') or []
        all_pending = options.get('all_pending', False)

        if all_pending:
            disp_qs = PharmacyDispensing.objects.filter(
                is_deleted=False,
                dispensing_status='pending_payment',
            ).select_related('patient', 'prescription__order__encounter')[:20]
            seen = set()
            for disp in disp_qs:
                p = disp.patient
                if p and p.id not in seen:
                    seen.add(p.id)
                    self._check_one(p, disp.prescription.order.encounter if getattr(disp.prescription, 'order', None) else None)
            if not seen:
                self.stdout.write(self.style.WARNING('No pending_payment pharmacy prescriptions found.'))
            return

        if not mrns:
            self.stdout.write(self.style.ERROR('Provide at least one MRN, e.g. check_patient_payer PMC2026009579'))
            return

        for mrn in mrns:
            patient = Patient.objects.filter(mrn__iexact=mrn.strip(), is_deleted=False).first()
            if not patient:
                self.stdout.write(self.style.ERROR(f'Patient not found: {mrn}'))
                continue
            encounter = None
            try:
                from hospital.models import Prescription
                rx = Prescription.objects.filter(
                    order__encounter__patient=patient,
                    is_deleted=False,
                ).select_related('order__encounter').order_by('-created').first()
                if rx and rx.order and rx.order.encounter:
                    encounter = rx.order.encounter
            except Exception:
                pass
            self._check_one(patient, encounter)

    def _check_one(self, patient, encounter=None):
        self.stdout.write('')
        self.stdout.write(self.style.HTTP_INFO(f'=== {patient.full_name} (MRN: {patient.mrn}) ==='))

        # 1. primary_insurance
        pi = getattr(patient, 'primary_insurance', None)
        if pi:
            self.stdout.write(
                self.style.SUCCESS(f'  primary_insurance: {pi.name} (payer_type={getattr(pi, "payer_type", "?")})')
            )
        else:
            self.stdout.write(self.style.WARNING('  primary_insurance: (not set)'))

        # 2. CorporateEmployee
        try:
            from hospital.models_enterprise_billing import CorporateEmployee
            emp = CorporateEmployee.objects.filter(
                patient=patient, is_active=True, is_deleted=False
            ).select_related('corporate_account').first()
            if emp:
                self.stdout.write(
                    self.style.SUCCESS(f'  CorporateEmployee: {emp.corporate_account.company_name}')
                )
            else:
                self.stdout.write(self.style.WARNING('  CorporateEmployee: (none)'))
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'  CorporateEmployee: (error: {e})'))

        # 3. PatientInsurance (models_insurance_companies)
        try:
            from hospital.models_insurance_companies import PatientInsurance
            pis = list(PatientInsurance.objects.filter(
                patient=patient,
                is_primary=True,
                status='active',
                is_deleted=False,
            ).select_related('insurance_company')[:5])
            if pis:
                for pi in pis:
                    name = pi.insurance_company.name if pi.insurance_company else '?'
                    self.stdout.write(self.style.SUCCESS(f'  PatientInsurance (primary): {name}'))
            else:
                self.stdout.write(self.style.WARNING('  PatientInsurance (primary, active): (none)'))
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'  PatientInsurance: (error: {e})'))

        # 4. get_patient_payer_info (what the app uses)
        try:
            from hospital.utils_billing import get_patient_payer_info
            info = get_patient_payer_info(patient, encounter)
            self.stdout.write(
                f'  get_patient_payer_info: type={info.get("type")} name={info.get("name")} '
                f'is_insurance_or_corporate={info.get("is_insurance_or_corporate")}'
            )
            if info.get('is_insurance_or_corporate'):
                self.stdout.write(self.style.SUCCESS('  → Will show as Paid (Corporate/Insurance) on Payment Verification'))
            else:
                self.stdout.write(self.style.WARNING('  → Will show as Not Paid (Collect Payment)'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'  get_patient_payer_info error: {e}'))
