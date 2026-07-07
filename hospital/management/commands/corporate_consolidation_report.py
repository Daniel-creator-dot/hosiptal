"""
List corporate Payer records that collapse to the same consolidation group_key
(duplicate spellings merged on company bills). Use after adding aliases in utils_billing.
"""
from collections import defaultdict

from django.core.management.base import BaseCommand

from hospital.models import Payer
from hospital.utils_billing import consolidated_corporate_company_group


class Command(BaseCommand):
    help = 'Show corporate payers grouped by consolidation key (merged duplicates)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--min-size',
            type=int,
            default=2,
            metavar='N',
            help='Only print groups with at least N payer rows (default: 2)',
        )

    def handle(self, *args, **options):
        min_size = max(1, options['min_size'])
        qs = Payer.objects.filter(payer_type='corporate', is_deleted=False).order_by('name').only(
            'id', 'name'
        )
        by_key = defaultdict(list)
        for p in qs:
            gk, disp = consolidated_corporate_company_group(p.name)
            by_key[gk].append((str(p.pk), p.name, disp))

        shown = 0
        for gk in sorted(by_key.keys(), key=lambda x: (x or '').lower()):
            rows = by_key[gk]
            if len(rows) < min_size:
                continue
            shown += 1
            names = sorted({r[1] for r in rows})
            disp = rows[0][2]
            self.stdout.write(
                self.style.WARNING(f'\n[{gk}] -> display: {disp!r}  ({len(rows)} payers)')
            )
            for _pid, name, _ in rows:
                self.stdout.write(f'   · {name}')

        self.stdout.write('')
        if shown == 0:
            self.stdout.write(self.style.SUCCESS(f'No groups with {min_size}+ payers (no merged duplicates).'))
        else:
            self.stdout.write(self.style.SUCCESS(f'{shown} consolidation group(s) with {min_size}+ payers.'))
