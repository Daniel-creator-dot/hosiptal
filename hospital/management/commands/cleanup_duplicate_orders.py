"""
Management command to clean up duplicate orders
Removes duplicates, keeping only the most recent order per encounter+order_type
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from hospital.models import Order
from collections import defaultdict


class Command(BaseCommand):
    help = 'Clean up duplicate orders, keeping only the most recent per encounter+order_type'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting',
        )
        parser.add_argument(
            '--min-age-hours',
            type=int,
            default=1,
            help='Minimum age in hours for orders to be considered for cleanup (default: 1)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        min_age_hours = options['min_age_hours']
        min_age = timezone.now() - timezone.timedelta(hours=min_age_hours)
        
        self.stdout.write(self.style.SUCCESS('Starting duplicate order cleanup...'))
        
        # Get all non-deleted orders (if min_age_hours is 0, get all orders)
        if min_age_hours == 0:
            all_orders = Order.objects.filter(
                is_deleted=False
            ).select_related('encounter__patient', 'requested_by').order_by('encounter_id', 'order_type', '-requested_at', '-created')
        else:
            all_orders = Order.objects.filter(
                is_deleted=False,
                created__lt=min_age
            ).select_related('encounter__patient', 'requested_by').order_by('encounter_id', 'order_type', '-requested_at', '-created')
        
        # Group by encounter + order_type (primary key)
        order_groups = defaultdict(list)
        for order in all_orders:
            # Primary key: encounter + order_type
            key = (order.encounter_id, order.order_type)
            order_groups[key].append(order)
        
        # Find duplicates (groups with more than 1 order)
        duplicates_to_remove = []
        kept_orders = []
        seen_order_ids = set()  # Track which orders we're keeping
        
        # Status priority for keeping the best order
        status_priority = {
            'completed': 10, 'in_progress': 8, 'pending': 5, 'cancelled': 1
        }
        
        # Handle duplicates by encounter+order_type
        for key, orders in order_groups.items():
            if len(orders) > 1:
                # Sort by status priority and time
                orders_sorted = sorted(
                    orders,
                    key=lambda x: (
                        status_priority.get(x.status, 0),  # Higher status first
                        x.requested_at or x.created,  # Then by requested time or creation time
                    ),
                    reverse=True
                )
                
                # Keep the best one (highest status, most recent)
                kept = orders_sorted[0]
                if kept.id not in seen_order_ids:
                    kept_orders.append(kept)
                    seen_order_ids.add(kept.id)
                
                # Check if others are true duplicates (created within 2 hours and same type)
                for order in orders_sorted[1:]:
                    time_diff = abs((order.created - kept.created).total_seconds() / 3600)  # hours
                    
                    # If created within 2 hours, same order_type, same encounter - it's a duplicate
                    if time_diff < 2:
                        # Mark as duplicate
                        if order.id not in seen_order_ids and order.id not in [o.id for o in duplicates_to_remove]:
                            duplicates_to_remove.append(order)
                    # Also check if they have the same status and were created very close together (within 30 minutes)
                    elif time_diff < 0.5 and order.status == kept.status:
                        # Very recent duplicate with same status
                        if order.id not in seen_order_ids and order.id not in [o.id for o in duplicates_to_remove]:
                            duplicates_to_remove.append(order)
        
        if not duplicates_to_remove:
            self.stdout.write(self.style.SUCCESS('No duplicates found!'))
            return
        
        self.stdout.write(f'\nFound {len(duplicates_to_remove)} duplicate orders to remove')
        self.stdout.write(f'Keeping {len(kept_orders)} unique orders')
        
        # Show summary
        patient_counts = defaultdict(int)
        for order in duplicates_to_remove:
            patient_name = order.encounter.patient.full_name if order.encounter else "Unknown"
            patient_counts[patient_name] += 1
        
        self.stdout.write('\nDuplicates by patient:')
        for patient_name, count in sorted(patient_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
            self.stdout.write(f'  {patient_name}: {count} duplicates')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('\nDRY RUN - No orders were actually deleted'))
            self.stdout.write(f'Would delete {len(duplicates_to_remove)} duplicate orders')
        else:
            # Delete duplicates
            with transaction.atomic():
                deleted_count = 0
                for order in duplicates_to_remove:
                    # Soft delete by marking as deleted
                    order.is_deleted = True
                    order.save(update_fields=['is_deleted'])
                    deleted_count += 1
                
                self.stdout.write(self.style.SUCCESS(f'\nSuccessfully removed {deleted_count} duplicate orders!'))
        
        self.stdout.write(self.style.SUCCESS('\nCleanup complete!'))
