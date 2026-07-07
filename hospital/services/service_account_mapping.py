"""
Central service_type → Primecare revenue / cash account mapping.
Used by payment signals and accounting sync so P&L reads consistent account codes.
"""
from django.conf import settings

CASH_AND_EQUIVALENTS_CODE = '1010'
CASH_AND_EQUIVALENTS_NAME = 'Cash and Cash Equivalents'
CUSTOMER_DEPOSITS_CODE = '2110'
CUSTOMER_DEPOSITS_NAME = 'Customer Deposits'
TRADE_PAYABLES_CODE = '2100'
TRADE_RECEIVABLES_CODE = '1200'

# Primecare revenue accounts (4100–4180 series)
PRIMECARE_REVENUE_ACCOUNTS = {
    'registration': ('4100', 'Registration Revenue'),
    'consultation': ('4110', 'Consultation Revenue'),
    'lab': ('4120', 'Laboratory Revenue'),
    'lab_test': ('4120', 'Laboratory Revenue'),
    'lab_result': ('4120', 'Laboratory Revenue'),
    'laboratory': ('4120', 'Laboratory Revenue'),
    'laboratory_test': ('4120', 'Laboratory Revenue'),
    'blood_test': ('4120', 'Laboratory Revenue'),
    'pathology': ('4120', 'Laboratory Revenue'),
    'histology': ('4120', 'Laboratory Revenue'),
    'pharmacy': ('4130', 'Pharmacy Revenue'),
    'pharmacy_prescription': ('4130', 'Pharmacy Revenue'),
    'pharmacy_walkin': ('4130', 'Pharmacy Revenue'),
    'medication': ('4130', 'Pharmacy Revenue'),
    'surgeries': ('4140', 'Surgeries Revenue'),
    'surgery': ('4140', 'Surgeries Revenue'),
    'procedure': ('4140', 'Surgeries Revenue'),
    'admission': ('4150', 'Admissions Revenue'),
    'bed': ('4150', 'Admissions Revenue'),
    'detainment': ('4150', 'Admissions Revenue'),
    'imaging': ('4160', 'Radiology Revenue'),
    'imaging_study': ('4160', 'Radiology Revenue'),
    'radiology': ('4160', 'Radiology Revenue'),
    'dental': ('4170', 'Dental Revenue'),
    'physiotherapy': ('4180', 'Physiotherapy Revenue'),
    'consumables': ('4190', 'Consumables Revenue'),
    'consumable': ('4190', 'Consumables Revenue'),
    'gynecology': ('4110', 'Consultation Revenue'),
    'antenatal': ('4110', 'Consultation Revenue'),
    'combined': ('4110', 'Consultation Revenue'),
    'general': ('4110', 'Consultation Revenue'),
    'other': ('4200', 'Other Income'),
}

_CASH_EQUIVALENTS = (CASH_AND_EQUIVALENTS_CODE, CASH_AND_EQUIVALENTS_NAME)
_TRADE_RECEIVABLES = (TRADE_RECEIVABLES_CODE, 'Trade Receivables')

PAYMENT_METHOD_ACCOUNTS = {
    'cash': _CASH_EQUIVALENTS,
    'card': _CASH_EQUIVALENTS,
    'mobile_money': _CASH_EQUIVALENTS,
    'bank_transfer': _CASH_EQUIVALENTS,
    'cheque': _CASH_EQUIVALENTS,
    'insurance': _TRADE_RECEIVABLES,
    'corporate': _TRADE_RECEIVABLES,
}


def use_primecare_revenue_accounts():
    return getattr(settings, 'USE_PRIMECARE_REVENUE_ACCOUNTS', True)


def resolve_revenue_account_code(service_type):
    key = (service_type or 'other').lower().strip()
    if use_primecare_revenue_accounts():
        return PRIMECARE_REVENUE_ACCOUNTS.get(key, PRIMECARE_REVENUE_ACCOUNTS['other'])[0]
    # Legacy HMS fallback
    legacy = {
        'lab': '4010', 'lab_test': '4010', 'laboratory': '4010',
        'pharmacy': '4020', 'pharmacy_prescription': '4020', 'medication': '4020',
        'imaging': '4030', 'imaging_study': '4030',
        'consultation': '4040', 'gynecology': '4040',
        'procedure': '4050', 'admission': '4060',
    }
    return legacy.get(key, '4000')


def resolve_revenue_account_meta(service_type):
    key = (service_type or 'other').lower().strip()
    if use_primecare_revenue_accounts():
        code, name = PRIMECARE_REVENUE_ACCOUNTS.get(
            key, PRIMECARE_REVENUE_ACCOUNTS['other']
        )
        return code, name
    code = resolve_revenue_account_code(service_type)
    return code, f'Revenue ({service_type or "general"})'


def resolve_payment_account_code(payment_method):
    key = (payment_method or 'cash').lower().strip()
    return PAYMENT_METHOD_ACCOUNTS.get(key, PAYMENT_METHOD_ACCOUNTS['cash'])[0]


def resolve_payment_account_meta(payment_method):
    key = (payment_method or 'cash').lower().strip()
    return PAYMENT_METHOD_ACCOUNTS.get(key, PAYMENT_METHOD_ACCOUNTS['cash'])
