"""
Resync unpaid invoice line amounts from lab/imaging catalogs (and optional consultation rules).

Use after catalog price edits or fixing pricing logic so open bills match current rates.

Examples:
  python manage.py resync_open_invoice_lines_from_catalog --dry-run
  python manage.py resync_open_invoice_lines_from_catalog
  python manage.py resync_open_invoice_lines_from_catalog --include-consultation
"""
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db.models import Q

from hospital.models import InvoiceLine, LabTest
from hospital.models_advanced import ImagingCatalog
from hospital.services.auto_billing_service import AutoBillingService
from hospital.utils_billing import (
    CONSULTATION_LINE_SERVICE_CODES,
    get_consultation_price_for_encounter_and_payer,
    get_mat_anc_consultation_price,
)


OPEN_INVOICE_STATUSES = ('draft', 'issued', 'partially_paid', 'overdue')


class Command(BaseCommand):
    help = (
        'Update unpaid invoice lines to match current lab/imaging catalog prices (via AutoBillingService._resolve_price). '
        'Optionally refresh consultation lines from encounter + payer rules.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Print changes without saving',
        )
        parser.add_argument(
            '--include-consultation',
            action='store_true',
            help='Also update CON001/CON002/MAT-ANC lines from encounter and payer (not catalog-only)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        include_consultation = options['include_consultation']

        stats = {
            'lab_updated': 0,
            'lab_skipped_no_test': 0,
            'imaging_updated': 0,
            'imaging_skipped_no_catalog': 0,
            'consultation_updated': 0,
            'consultation_skipped': 0,
            'invoices_touched': set(),
        }

        q = Q(service_code__code__startswith='LAB-') | Q(service_code__code__startswith='IMG-')
        if include_consultation:
            q |= Q(service_code__code__in=list(CONSULTATION_LINE_SERVICE_CODES))

        lines = (
            InvoiceLine.objects.filter(
                q,
                is_deleted=False,
                waived_at__isnull=True,
                invoice__is_deleted=False,
                invoice__status__in=OPEN_INVOICE_STATUSES,
            )
            .select_related(
                'invoice',
                'invoice__patient',
                'invoice__payer',
                'invoice__encounter',
                'service_code',
            )
            .order_by('invoice_id', 'id')
        )

        for line in lines.iterator(chunk_size=500):
            inv = line.invoice
            patient = inv.patient
            payer = inv.payer
            code = (line.service_code.code or '').strip()

            if code.startswith('LAB-'):
                if self._sync_lab_line(line, inv, dry_run, stats):
                    stats['invoices_touched'].add(inv.pk)
                continue

            if code.startswith('IMG-'):
                if self._sync_imaging_line(line, inv, dry_run, stats):
                    stats['invoices_touched'].add(inv.pk)
                continue

            if include_consultation and code in CONSULTATION_LINE_SERVICE_CODES:
                if self._sync_consultation_line(line, inv, dry_run, stats):
                    stats['invoices_touched'].add(inv.pk)

        self.stdout.write(self.style.SUCCESS('Done.'))
        self.stdout.write(f"  Lab lines updated: {stats['lab_updated']}")
        self.stdout.write(f"  Lab skipped (no catalog match): {stats['lab_skipped_no_test']}")
        self.stdout.write(f"  Imaging lines updated: {stats['imaging_updated']}")
        self.stdout.write(f"  Imaging skipped (no catalog match): {stats['imaging_skipped_no_catalog']}")
        if include_consultation:
            self.stdout.write(f"  Consultation lines updated: {stats['consultation_updated']}")
            self.stdout.write(f"  Consultation skipped: {stats['consultation_skipped']}")
        self.stdout.write(f"  Invoices with at least one change: {len(stats['invoices_touched'])}")
        if dry_run:
            self.stdout.write(self.style.WARNING('Dry run — no database writes were performed.'))

    def _apply_price(self, line, invoice, unit_price, dry_run):
        qty = line.quantity or Decimal('1')
        new_total = unit_price * qty
        if line.unit_price == unit_price and line.line_total == new_total:
            return False
        if dry_run:
            return True
        line.unit_price = unit_price
        line.line_total = new_total
        line.save(update_fields=['unit_price', 'line_total', 'modified'])
        invoice.update_totals()
        return True

    def _sync_lab_line(self, line, invoice, dry_run, stats):
        suffix = (line.service_code.code or '')[4:]
        test = LabTest.objects.filter(code=suffix, is_deleted=False).first()
        if not test:
            try:
                test = LabTest.objects.filter(pk=suffix, is_deleted=False).first()
            except Exception:
                test = None
        if not test:
            stats['lab_skipped_no_test'] += 1
            return False

        default_price = test.price or Decimal('0.00')
        unit_price = AutoBillingService._resolve_price(
            invoice.patient, invoice.payer, line.service_code, default_price
        )
        if self._apply_price(line, invoice, unit_price, dry_run):
            stats['lab_updated'] += 1
            return True
        return False

    def _imaging_catalog_default_price(self, line, payer):
        """Mirror AutoBillingService.create_imaging_bill tier selection."""
        desc = (line.description or '').strip()
        catalog = None
        if desc:
            catalog = (
                ImagingCatalog.objects.filter(is_active=True, is_deleted=False)
                .filter(Q(code=desc) | Q(name__iexact=desc) | Q(study_type__iexact=desc))
                .first()
            )
        if not catalog and line.service_code:
            sc = line.service_code.code or ''
            if sc.startswith('IMG-'):
                rest = sc[4:]
                parts = rest.split('-', 1)
                if len(parts) == 2:
                    modality, study_tail = parts[0], parts[1]
                    catalog = (
                        ImagingCatalog.objects.filter(modality=modality, is_active=True, is_deleted=False)
                        .filter(
                            Q(code__iexact=study_tail)
                            | Q(name__iexact=study_tail)
                            | Q(study_type__iexact=study_tail)
                        )
                        .first()
                    )
        if not catalog:
            return Decimal('0.00')

        payer_type = (getattr(payer, 'payer_type', None) or 'cash')
        if isinstance(payer_type, str):
            payer_type = payer_type.lower()

        if payer_type == 'corporate' and catalog.corporate_price is not None:
            return Decimal(str(catalog.corporate_price))
        if payer_type in ('nhis', 'private') and catalog.insurance_price is not None:
            return Decimal(str(catalog.insurance_price))
        if catalog.price is not None:
            return Decimal(str(catalog.price))
        return Decimal('0.00')

    def _sync_imaging_line(self, line, invoice, dry_run, stats):
        default_price = self._imaging_catalog_default_price(line, invoice.payer)
        if default_price <= 0:
            stats['imaging_skipped_no_catalog'] += 1
            return False

        unit_price = AutoBillingService._resolve_price(
            invoice.patient, invoice.payer, line.service_code, default_price
        )
        if self._apply_price(line, invoice, unit_price, dry_run):
            stats['imaging_updated'] += 1
            return True
        return False

    def _sync_consultation_line(self, line, invoice, dry_run, stats):
        encounter = invoice.encounter
        if not encounter:
            stats['consultation_skipped'] += 1
            return False

        patient = encounter.patient
        payer = invoice.payer
        encounter_type_lower = (encounter.encounter_type or '').lower()
        doctor_staff = getattr(encounter, 'provider', None) or getattr(
            encounter, 'assigned_doctor', None
        )

        if 'antenatal' in encounter_type_lower:
            unit_price = get_mat_anc_consultation_price(patient, payer)
        else:
            consultation_type = 'general'
            if encounter_type_lower in ('specialist', 'gynae'):
                consultation_type = 'specialist'
            elif doctor_staff:
                from hospital.utils_doctor_pricing import DoctorPricingService

                info = DoctorPricingService.get_doctor_pricing_info(doctor_staff)
                if info.get('is_specialist'):
                    consultation_type = 'specialist'

            unit_price = get_consultation_price_for_encounter_and_payer(
                encounter, payer, consultation_type=consultation_type
            )

        if self._apply_price(line, invoice, unit_price, dry_run):
            stats['consultation_updated'] += 1
            return True
        return False
