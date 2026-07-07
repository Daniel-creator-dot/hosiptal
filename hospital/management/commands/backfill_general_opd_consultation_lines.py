"""
Recalculate general OPD consultation invoice lines (CON001, CONS-GEN, CONSULTATION_GENERAL, S00023)
to current policy: GHS 150 cash, GHS 160 corporate / corporate employee; insurance uses tiers.

Updates existing rows including paid invoices (recomputes line totals and invoice totals). Excludes
cancelled and soft-deleted invoices/lines and waived lines.

Always run with --dry-run first, then without.

Examples:
  python manage.py backfill_general_opd_consultation_lines --dry-run
  python manage.py backfill_general_opd_consultation_lines
  python manage.py backfill_general_opd_consultation_lines --only-open
  python manage.py backfill_general_opd_consultation_lines --invoice-id 12345 --dry-run
"""
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q

from hospital.models import InvoiceLine
from hospital.utils_billing import (
    GENERAL_OPD_LINE_SERVICE_CODES,
    get_corrected_general_opd_line_unit_price,
    is_review_visit,
)

OPEN_INVOICE_STATUSES = ('draft', 'issued', 'partially_paid', 'overdue')


class Command(BaseCommand):
    help = (
        'Backfill general OPD consultation line amounts (CON001 family, S00023) to 150/160 policy '
        'for all non-cancelled invoices, including paid.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show counts and sample changes without saving',
        )
        parser.add_argument(
            '--only-open',
            action='store_true',
            help='Only invoices in draft/issued/partially_paid/overdue (exclude paid)',
        )
        parser.add_argument(
            '--invoice-id',
            type=int,
            default=None,
            help='Restrict to a single invoice primary key',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=None,
            help='Max lines to process (after filters), for testing',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        only_open = options['only_open']
        invoice_id = options['invoice_id']
        limit = options['limit']

        code_q = Q()
        for code in sorted(GENERAL_OPD_LINE_SERVICE_CODES):
            code_q |= Q(service_code__code__iexact=code)

        lines_qs = (
            InvoiceLine.objects.filter(
                code_q,
                is_deleted=False,
                waived_at__isnull=True,
                invoice__is_deleted=False,
            )
            .exclude(invoice__status='cancelled')
            .select_related(
                'invoice',
                'invoice__patient',
                'invoice__payer',
                'invoice__encounter',
                'service_code',
            )
            .order_by('invoice_id', 'id')
        )

        if only_open:
            lines_qs = lines_qs.filter(invoice__status__in=OPEN_INVOICE_STATUSES)
        if invoice_id is not None:
            lines_qs = lines_qs.filter(invoice_id=invoice_id)

        stats = {
            'examined': 0,
            'updated': 0,
            'unchanged': 0,
            'skipped_none': 0,
            'skipped_review': 0,
            'sample': [],
        }

        for line in lines_qs.iterator(chunk_size=300):
            if limit is not None and stats['examined'] >= limit:
                break
            stats['examined'] += 1
            inv = line.invoice
            enc = inv.encounter
            if enc and is_review_visit(enc):
                stats['skipped_review'] += 1
                continue
            new_price = get_corrected_general_opd_line_unit_price(inv, line)
            if new_price is None:
                stats['skipped_none'] += 1
                continue

            qty = line.quantity or Decimal('1')
            new_total = new_price * qty
            if line.unit_price == new_price and line.line_total == new_total:
                stats['unchanged'] += 1
                continue

            if len(stats['sample']) < 15:
                stats['sample'].append(
                    f"  line id={line.pk} inv={inv.pk} "
                    f"{line.service_code.code}: {line.unit_price} -> {new_price}"
                )

            stats['updated'] += 1
            if dry_run:
                continue

            with transaction.atomic():
                line.unit_price = new_price
                line.line_total = new_total
                line.save(update_fields=['unit_price', 'line_total', 'modified'])
                inv.update_totals()

        self.stdout.write(self.style.SUCCESS('Backfill finished.'))
        self.stdout.write(f"  Lines examined: {stats['examined']}")
        self.stdout.write(f"  Would update / updated: {stats['updated']}")
        self.stdout.write(f"  Unchanged (already correct): {stats['unchanged']}")
        self.stdout.write(f"  Skipped (no target price): {stats['skipped_none']}")
        self.stdout.write(f"  Skipped (review / follow-up encounter): {stats['skipped_review']}")
        if stats['sample']:
            self.stdout.write('  Sample changes:')
            for s in stats['sample']:
                self.stdout.write(s)
        if dry_run:
            self.stdout.write(self.style.WARNING('Dry run — no database writes were performed.'))
