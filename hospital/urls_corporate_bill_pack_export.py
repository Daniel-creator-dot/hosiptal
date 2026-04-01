"""
Corporate bill pack Excel/CSV export — included from hms.urls BEFORE hospital.urls so
/hms/accountant/billing/corporate-bills/payer/<uuid>/export/.../ resolves even when an
older hospital.urls on the server omits these routes.

Reverse as: corporate_bill_pack_export_excel, corporate_bill_pack_export_csv (no hospital: prefix).
"""
from django.urls import path

from . import views_billing_claims

urlpatterns = [
    path(
        'accountant/billing/corporate-bills/payer/<uuid:payer_id>/export/excel/',
        views_billing_claims.corporate_bill_pack_export_excel,
        name='corporate_bill_pack_export_excel',
    ),
    path(
        'accountant/billing/corporate-bills/payer/<uuid:payer_id>/export/csv/',
        views_billing_claims.corporate_bill_pack_export_csv,
        name='corporate_bill_pack_export_csv',
    ),
]
