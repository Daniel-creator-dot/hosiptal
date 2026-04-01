"""
Management command to set up GCB PLC as a corporate payer and insurance company
with a default plan "GCB general".
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from decimal import Decimal

from hospital.models import Payer
from hospital.models_insurance_companies import InsuranceCompany, InsurancePlan


class Command(BaseCommand):
    help = 'Create GCB PLC corporate payer, insurance company and "GCB general" plan.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Setting up GCB PLC corporate payer and plan...'))

        # Create or get Payer
        payer, payer_created = Payer.objects.get_or_create(
            name='GCB PLC',
            defaults={
                'payer_type': 'corporate',
                'is_active': True,
            },
        )
        if not payer_created and payer.payer_type != 'corporate':
            payer.payer_type = 'corporate'
            payer.is_active = True
            payer.save(update_fields=['payer_type', 'is_active'])
        self.stdout.write(
            self.style.SUCCESS(
                f"{'Created' if payer_created else 'Updated'} payer: {payer.name} ({payer.payer_type})"
            )
        )

        # Create or get InsuranceCompany
        company, company_created = InsuranceCompany.objects.get_or_create(
            name='GCB PLC',
            defaults={
                'code': 'GCB',
                'payment_terms_days': 30,
                'status': 'active',
                'is_active': True,
                'contract_start_date': timezone.now().date(),
            },
        )
        if not company_created:
            # Ensure company is active and has code
            updated_fields = []
            if not company.code:
                company.code = 'GCB'
                updated_fields.append('code')
            if not company.is_active:
                company.is_active = True
                updated_fields.append('is_active')
            if company.status != 'active':
                company.status = 'active'
                updated_fields.append('status')
            if updated_fields:
                company.save(update_fields=updated_fields)
        self.stdout.write(
            self.style.SUCCESS(
                f"{'Created' if company_created else 'Verified'} insurance company: {company.name} ({company.code})"
            )
        )

        # Create or get InsurancePlan
        plan, plan_created = InsurancePlan.objects.get_or_create(
            insurance_company=company,
            plan_name='GCB general',
            defaults={
                'plan_code': 'GCB-GENERAL',
                'plan_type': 'corporate',
                'description': 'General corporate plan for GCB PLC.',
                'consultation_coverage': Decimal('100.00'),
                'lab_coverage': Decimal('100.00'),
                'imaging_coverage': Decimal('100.00'),
                'pharmacy_coverage': Decimal('80.00'),
                'surgery_coverage': Decimal('90.00'),
                'admission_coverage': Decimal('100.00'),
                'copay_amount': Decimal('0.00'),
                'effective_date': timezone.now().date(),
                'is_active': True,
            },
        )
        if not plan_created:
            updated_fields = []
            if not plan.is_active:
                plan.is_active = True
                updated_fields.append('is_active')
            if plan.plan_type != 'corporate':
                plan.plan_type = 'corporate'
                updated_fields.append('plan_type')
            if updated_fields:
                plan.save(update_fields=updated_fields)
        self.stdout.write(
            self.style.SUCCESS(
                f"{'Created' if plan_created else 'Verified'} plan: {plan.plan_name} ({plan.plan_code})"
            )
        )

        self.stdout.write(self.style.SUCCESS('✅ GCB PLC corporate setup complete.'))

