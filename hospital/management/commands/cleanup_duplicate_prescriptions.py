"""
Management command to clean up duplicate prescriptions
Removes duplicates, keeping only the most recent prescription per patient+drug+order
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from hospital.models import Prescription
from collections import defaultdict


class Command(BaseCommand):
    help = 'Clean up duplicate prescriptions, keeping only the most recent per patient+drug+order'

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
            help='Minimum age in hours for prescriptions to be considered for cleanup (default: 1)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        min_age_hours = options['min_age_hours']
        min_age = timezone.now() - timezone.timedelta(hours=min_age_hours)
        
        self.stdout.write(self.style.SUCCESS('Starting duplicate prescription cleanup...'))
        
        # Get all non-deleted prescriptions (if min_age_hours is 0, get all prescriptions)
        if min_age_hours == 0:
            all_prescriptions = Prescription.objects.filter(
                is_deleted=False
            ).select_related('order', 'order__encounter__patient', 'drug', 'prescribed_by').order_by('order__encounter__patient_id', 'drug_id', 'order_id', '-created')
        else:
            all_prescriptions = Prescription.objects.filter(
                is_deleted=False,
                created__lt=min_age
            ).select_related('order', 'order__encounter__patient', 'drug', 'prescribed_by').order_by('order__encounter__patient_id', 'drug_id', 'order_id', '-created')
        
        # Group by patient + drug + order (primary key)
        prescription_groups = defaultdict(list)
        for prescription in all_prescriptions:
            # Primary key: patient + drug + order
            key = (prescription.order.encounter.patient_id, prescription.drug_id, prescription.order_id)
            prescription_groups[key].append(prescription)
        
        # Also check for duplicates within same encounter (same patient, same encounter, same drug)
        encounter_groups = defaultdict(list)
        for prescription in all_prescriptions:
            if prescription.order.encounter_id:
                encounter_key = (prescription.order.encounter.patient_id, prescription.order.encounter_id, prescription.drug_id)
                encounter_groups[encounter_key].append(prescription)
        
        # Find duplicates (groups with more than 1 prescription)
        duplicates_to_remove = []
        kept_prescriptions = []
        seen_prescription_ids = set()  # Track which prescriptions we're keeping
        
        # First, handle duplicates by patient+drug+order
        for key, prescriptions in prescription_groups.items():
            if len(prescriptions) > 1:
                # Sort by creation time (most recent first)
                prescriptions_sorted = sorted(
                    prescriptions,
                    key=lambda x: x.created,
                    reverse=True
                )
                
                # Keep the most recent one
                kept = prescriptions_sorted[0]
                if kept.id not in seen_prescription_ids:
                    kept_prescriptions.append(kept)
                    seen_prescription_ids.add(kept.id)
                
                # Mark others for deletion
                for prescription in prescriptions_sorted[1:]:
                    if prescription.id not in seen_prescription_ids:  # Don't add if already marked
                        duplicates_to_remove.append(prescription)
        
        # Also check for duplicates within same encounter (same patient, same encounter, same drug)
        # These are likely duplicates even if order is different
        for key, prescriptions in encounter_groups.items():
            if len(prescriptions) > 1:
                # Sort by creation time
                prescriptions_sorted = sorted(
                    prescriptions,
                    key=lambda x: x.created,
                    reverse=True
                )
                
                # Keep the most recent one
                kept = prescriptions_sorted[0]
                if kept.id not in seen_prescription_ids:
                    if kept.id not in [p.id for p in kept_prescriptions]:
                        kept_prescriptions.append(kept)
                    seen_prescription_ids.add(kept.id)
                
                # Check if others are true duplicates (created within 24 hours and same drug)
                # For same encounter, any duplicate drug within 24 hours is likely a duplicate
                for prescription in prescriptions_sorted[1:]:
                    time_diff = abs((prescription.created - kept.created).total_seconds() / 3600)  # hours
                    
                    # If created within 24 hours, same drug, same encounter - it's a duplicate
                    if time_diff < 24 and prescription.drug_id == kept.drug_id:
                        # Mark as duplicate
                        if prescription.id not in seen_prescription_ids and prescription.id not in [p.id for p in duplicates_to_remove]:
                            duplicates_to_remove.append(prescription)
        
        if not duplicates_to_remove:
            self.stdout.write(self.style.SUCCESS('No duplicates found!'))
            return
        
        self.stdout.write(f'\nFound {len(duplicates_to_remove)} duplicate prescriptions to remove')
        self.stdout.write(f'Keeping {len(kept_prescriptions)} unique prescriptions')
        
        # Show summary
        patient_counts = defaultdict(int)
        for prescription in duplicates_to_remove:
            patient_name = prescription.order.encounter.patient.full_name if prescription.order.encounter else "Unknown"
            patient_counts[patient_name] += 1
        
        self.stdout.write('\nDuplicates by patient:')
        for patient_name, count in sorted(patient_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
            self.stdout.write(f'  {patient_name}: {count} duplicates')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('\nDRY RUN - No prescriptions were actually deleted'))
            self.stdout.write(f'Would delete {len(duplicates_to_remove)} duplicate prescriptions')
        else:
            # Delete duplicates
            with transaction.atomic():
                deleted_count = 0
                for prescription in duplicates_to_remove:
                    # Soft delete by marking as deleted
                    prescription.is_deleted = True
                    prescription.save(update_fields=['is_deleted'])
                    deleted_count += 1
                
                self.stdout.write(self.style.SUCCESS(f'\nSuccessfully removed {deleted_count} duplicate prescriptions!'))
        
        self.stdout.write(self.style.SUCCESS('\nCleanup complete!'))
