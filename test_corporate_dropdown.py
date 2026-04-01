"""
Test corporate dropdown in form
"""
import os
import sys
import django

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from hospital.forms import PatientForm

print('='*80)
print('TESTING CORPORATE DROPDOWN IN FORM')
print('='*80)

form = PatientForm()
queryset = form.fields['selected_corporate_company'].queryset

print(f'\n✅ Corporate companies in form: {queryset.count()}')
print('\nSample companies:')
for row in queryset[:15]:
    label = getattr(row, 'name', None) or getattr(row, 'company_name', None) or str(row)
    print(f'  - {label}')

print('\n' + '='*80)
print('✅ TEST COMPLETE')
print('='*80)
