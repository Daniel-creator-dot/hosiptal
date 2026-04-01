"""
Management command to clean up duplicate lab results
Removes duplicates, keeping only the most recent result per patient+test+order
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from hospital.models import LabResult
from collections import defaultdict


class Command(BaseCommand):
    help = 'Clean up duplicate lab results, keeping only the most recent per patient+test+order'

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
            help='Minimum age in hours for results to be considered for cleanup (default: 1)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        min_age_hours = options['min_age_hours']
        min_age = timezone.now() - timezone.timedelta(hours=min_age_hours)
        
        self.stdout.write(self.style.SUCCESS('Starting duplicate lab result cleanup...'))
        
        # Get all non-deleted results (if min_age_hours is 0, get all results)
        if min_age_hours == 0:
            all_results = LabResult.objects.filter(
                is_deleted=False
            ).select_related('order', 'order__encounter__patient', 'test').order_by('order__encounter__patient_id', 'test_id', 'order_id', '-created')
        else:
            all_results = LabResult.objects.filter(
                is_deleted=False,
                created__lt=min_age
            ).select_related('order', 'order__encounter__patient', 'test').order_by('order__encounter__patient_id', 'test_id', 'order_id', '-created')
        
        # Group by patient + test + order (primary key)
        result_groups = defaultdict(list)
        for result in all_results:
            # Primary key: patient + test + order
            key = (result.order.encounter.patient_id, result.test_id, result.order_id)
            result_groups[key].append(result)
        
        # Also check for duplicates within same encounter (same patient, same encounter, same test)
        encounter_groups = defaultdict(list)
        for result in all_results:
            if result.order.encounter_id:
                encounter_key = (result.order.encounter.patient_id, result.order.encounter_id, result.test_id)
                encounter_groups[encounter_key].append(result)
        
        # Find duplicates (groups with more than 1 result)
        duplicates_to_remove = []
        kept_results = []
        seen_result_ids = set()  # Track which results we're keeping
        
        # Status priority for keeping the best result
        status_priority = {
            'completed': 10, 'in_progress': 5, 'pending': 3, 'cancelled': 1
        }
        
        # First, handle duplicates by patient+test+order
        for key, results in result_groups.items():
            if len(results) > 1:
                # Sort by status priority and time
                results_sorted = sorted(
                    results,
                    key=lambda x: (
                        status_priority.get(x.status, 0),  # Higher status first
                        x.verified_at or x.created,  # Then by verification time or creation time
                    ),
                    reverse=True
                )
                
                # Keep the best one (highest status, most recent)
                kept = results_sorted[0]
                if kept.id not in seen_result_ids:
                    kept_results.append(kept)
                    seen_result_ids.add(kept.id)
                
                # Mark others for deletion
                for result in results_sorted[1:]:
                    if result.id not in seen_result_ids:  # Don't add if already marked
                        duplicates_to_remove.append(result)
        
        # Also check for duplicates within same encounter (same patient, same encounter, same test)
        # These are likely duplicates even if order is different
        for key, results in encounter_groups.items():
            if len(results) > 1:
                # Sort by status and time
                results_sorted = sorted(
                    results,
                    key=lambda x: (
                        status_priority.get(x.status, 0),
                        x.verified_at or x.created,
                    ),
                    reverse=True
                )
                
                # Keep the best one
                kept = results_sorted[0]
                if kept.id not in seen_result_ids:
                    if kept.id not in [r.id for r in kept_results]:
                        kept_results.append(kept)
                    seen_result_ids.add(kept.id)
                
                # Check if others are true duplicates (created within 24 hours and same test)
                # For same encounter, any duplicate test within 24 hours is likely a duplicate
                for result in results_sorted[1:]:
                    time_diff = abs((result.created - kept.created).total_seconds() / 3600)  # hours
                    
                    # If created within 24 hours, same test, same encounter - it's a duplicate
                    if time_diff < 24 and result.test_id == kept.test_id:
                        # Mark as duplicate
                        if result.id not in seen_result_ids and result.id not in [r.id for r in duplicates_to_remove]:
                            duplicates_to_remove.append(result)
        
        if not duplicates_to_remove:
            self.stdout.write(self.style.SUCCESS('No duplicates found!'))
            return
        
        self.stdout.write(f'\nFound {len(duplicates_to_remove)} duplicate results to remove')
        self.stdout.write(f'Keeping {len(kept_results)} unique results')
        
        # Show summary
        patient_counts = defaultdict(int)
        for result in duplicates_to_remove:
            patient_name = result.order.encounter.patient.full_name if result.order.encounter else "Unknown"
            patient_counts[patient_name] += 1
        
        self.stdout.write('\nDuplicates by patient:')
        for patient_name, count in sorted(patient_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
            self.stdout.write(f'  {patient_name}: {count} duplicates')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('\nDRY RUN - No results were actually deleted'))
            self.stdout.write(f'Would delete {len(duplicates_to_remove)} duplicate results')
        else:
            # Delete duplicates
            with transaction.atomic():
                deleted_count = 0
                for result in duplicates_to_remove:
                    # Soft delete by marking as deleted
                    result.is_deleted = True
                    result.save(update_fields=['is_deleted'])
                    deleted_count += 1
                
                self.stdout.write(self.style.SUCCESS(f'\nSuccessfully removed {deleted_count} duplicate results!'))
        
        self.stdout.write(self.style.SUCCESS('\nCleanup complete!'))
