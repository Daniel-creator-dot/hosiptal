"""
Verify corporate accounts fix
"""
import os
import sys
import django

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from hospital.models import Payer
from hospital.models_insurance_companies import InsuranceCompany

print('='*80)
print('CORPORATE ACCOUNTS FIX - VERIFICATION')
print('='*80)

corporate_payers = Payer.objects.filter(payer_type='corporate', is_deleted=False)
insurance_payers = Payer.objects.filter(payer_type__in=['insurance', 'private'], is_deleted=False)
active_insurance = InsuranceCompany.objects.filter(is_active=True, is_deleted=False)
inactive_insurance = InsuranceCompany.objects.filter(is_active=False, is_deleted=False)

print(f'\n✅ Corporate Payers: {corporate_payers.count()}')
print(f'✅ Insurance Payers: {insurance_payers.count()}')
print(f'✅ Active Insurance Companies: {active_insurance.count()}')
print(f'✅ Inactive Insurance Companies (corporate): {inactive_insurance.count()}')

print('\nSample Corporate Payers:')
for payer in corporate_payers[:10]:
    print(f'  - {payer.name}')

print('\n' + '='*80)
print('✅ VERIFICATION COMPLETE')
print('='*80)
