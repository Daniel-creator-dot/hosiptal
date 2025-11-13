"""
Set up sample corporate accounts and pricing for testing
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from hospital.models import ServiceCode, Department, Payer
from hospital.models_enterprise_billing import (
    CorporateAccount, ServicePricing
)


class Command(BaseCommand):
    help = 'Set up sample corporate accounts and multi-tier pricing'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS('\n🎯 Setting Up Sample Data\n'))
        
        # Create sample corporate account
        self.stdout.write('🏢 Creating sample corporate account...')
        
        try:
            corporate, created = CorporateAccount.objects.get_or_create(
                company_code='ABC001',
                defaults={
                    'company_name': 'ABC Corporation Ltd',
                    'registration_number': 'CR-12345678',
                    'tax_id': 'TIN-987654321',
                    'billing_contact_name': 'John Doe, CFO',
                    'billing_email': 'billing@abccorp.com',
                    'billing_phone': '0244123456',
                    'billing_address': '123 Business Street, Accra, Ghana',
                    'credit_limit': Decimal('100000.00'),
                    'payment_terms_days': 30,
                    'current_balance': Decimal('0.00'),
                    'credit_status': 'active',
                    'billing_cycle': 'monthly',
                    'billing_day_of_month': 1,
                    'next_billing_date': timezone.now().date() + timedelta(days=30),
                    'global_discount_percentage': Decimal('15.00'),
                    'contract_start_date': timezone.now().date(),
                    'send_statement_email': True,
                    'send_payment_reminders': True,
                }
            )
            
            if created:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'✅ Created: ABC Corporation Ltd (Credit: GHS 100,000, Discount: 15%)'
                    )
                )
            else:
                self.stdout.write(
                    self.style.WARNING('⚠️ ABC Corporation already exists')
                )
        
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Error creating corporate account: {str(e)}'))
        
        # Create sample service pricing
        self.stdout.write('\n💰 Setting up multi-tier pricing...')
        
        services_to_price = [
            ('CONSULT', 'General Consultation', Decimal('150.00'), Decimal('120.00'), Decimal('100.00')),
            ('CONSULT-SP', 'Specialist Consultation', Decimal('200.00'), Decimal('160.00'), Decimal('140.00')),
            ('LAB-CBC', 'Complete Blood Count', Decimal('250.00'), Decimal('200.00'), Decimal('180.00')),
            ('LAB-MAL', 'Malaria Test', Decimal('80.00'), Decimal('65.00'), Decimal('60.00')),
            ('XRAY-CHE', 'Chest X-Ray', Decimal('300.00'), Decimal('250.00'), Decimal('220.00')),
            ('ULTRA', 'Ultrasound', Decimal('500.00'), Decimal('400.00'), Decimal('350.00')),
        ]
        
        pricing_created = 0
        pricing_existing = 0
        
        for code, name, cash, corporate, insurance in services_to_price:
            try:
                # Get or create service code
                service_code, sc_created = ServiceCode.objects.get_or_create(
                    code=code,
                    defaults={
                        'description': name,
                        'category': 'Clinical Services',
                        'is_active': True,
                    }
                )
                
                # Create pricing
                pricing, p_created = ServicePricing.objects.get_or_create(
                    service_code=service_code,
                    payer__isnull=True,  # Standard pricing
                    is_active=True,
                    effective_from=timezone.now().date(),
                    defaults={
                        'cash_price': cash,
                        'corporate_price': corporate,
                        'insurance_price': insurance,
                    }
                )
                
                if p_created:
                    pricing_created += 1
                    self.stdout.write(
                        f'   ✅ {code}: Cash GHS {cash}, Corp GHS {corporate}, Ins GHS {insurance}'
                    )
                else:
                    pricing_existing += 1
            
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'   ❌ Error pricing {code}: {str(e)}'))
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\n📊 Pricing Summary: {pricing_created} created, {pricing_existing} existing'
            )
        )
        
        # Summary
        self.stdout.write(self.style.SUCCESS('\n✅ Sample Data Setup Complete!\n'))
        self.stdout.write('Next steps:')
        self.stdout.write('   1. Go to /admin/hospital/corporateaccount/')
        self.stdout.write('   2. View ABC Corporation Ltd')
        self.stdout.write('   3. Enroll employees using /admin/hospital/corporateemployee/')
        self.stdout.write('   4. Create visits and test multi-tier pricing')
        self.stdout.write('')

