"""
Merge duplicate pending medication orders per encounter.
Moves all prescriptions to the latest order (by id) and soft-deletes the rest.
Run after fixing code that used get_or_create (which caused "get() returned more than one Order").
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count
from hospital.models import Order, Prescription


class Command(BaseCommand):
    help = 'Merge duplicate pending medication orders per encounter; prescriptions go to pharmacy under one order'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be merged without changing data',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN - no changes will be made'))

        # Encounters that have more than one pending medication order
        dupes = (
            Order.objects.filter(
                order_type='medication',
                status='pending',
                is_deleted=False,
            )
            .values('encounter_id')
            .annotate(n=Count('id'))
            .filter(n__gt=1)
        )
        encounter_ids = [d['encounter_id'] for d in dupes]
        if not encounter_ids:
            self.stdout.write(self.style.SUCCESS('No duplicate pending medication orders found.'))
            return

        self.stdout.write(f'Found {len(encounter_ids)} encounter(s) with duplicate pending medication orders.')

        merged = 0
        prescriptions_moved = 0
        orders_soft_deleted = 0

        for encounter_id in encounter_ids:
            orders = (
                Order.objects.filter(
                    encounter_id=encounter_id,
                    order_type='medication',
                    status='pending',
                    is_deleted=False,
                )
                .order_by('-id')
            )
            keep = orders.first()
            to_merge = list(orders[1:])
            if not to_merge:
                continue

            with transaction.atomic():
                for order in to_merge:
                    rx_count = order.prescriptions.filter(is_deleted=False).count()
                    if rx_count:
                        if not dry_run:
                            order.prescriptions.filter(is_deleted=False).update(order_id=keep.id)
                        prescriptions_moved += rx_count
                        self.stdout.write(
                            f'  Encounter {encounter_id}: moved {rx_count} prescription(s) from order {order.id} -> {keep.id}'
                        )
                    if not dry_run:
                        order.is_deleted = True
                        order.save(update_fields=['is_deleted'])
                    orders_soft_deleted += 1
                merged += 1

        if dry_run:
            self.stdout.write(self.style.WARNING(f'Would merge {merged} encounter(s), move {prescriptions_moved} prescriptions, soft-delete {orders_soft_deleted} orders.'))
        else:
            self.stdout.write(self.style.SUCCESS(f'Merged {merged} encounter(s), moved {prescriptions_moved} prescriptions, soft-deleted {orders_soft_deleted} duplicate orders.'))
