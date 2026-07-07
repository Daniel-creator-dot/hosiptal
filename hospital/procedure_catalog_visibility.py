"""
ProcedureCatalog mixes hospital cash tariffs (e.g. PrimeCare) with legacy NHIS-style
rows whose names contain 'AS SOLE PROCEDURE' / 'AS AN ADDITIONAL PROCEDURE' and small
numeric values (tariff weights, not GHS). Those rows must not appear in cashier search
or clinical pickers when billing in GHS.
"""
from django.db.models import Q


def nhis_tariff_noise_q() -> Q:
    """Name patterns characteristic of NHIS tariff line text, not private cash fees."""
    return (
        Q(name__icontains='AS SOLE PROCEDURE')
        | Q(name__icontains='AS AN ADDITIONAL PROCEDURE')
        | Q(name__icontains='AS A COMBINED PROCEDURE')
    )


def billable_procedure_catalog_base_q() -> Q:
    """Active catalog rows excluding INVALID placeholder and NHIS noise."""
    return (
        Q(is_active=True)
        & Q(is_deleted=False)
        & Q(name__isnull=False)
        & ~Q(name__iexact='')
        & ~Q(name__icontains='INVALID')
        & ~nhis_tariff_noise_q()
    )
