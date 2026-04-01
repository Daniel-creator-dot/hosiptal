"""
Management command to clean up duplicate imaging studies
Removes duplicates, keeping only the most recent study per patient+modality+study_type
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from hospital.models_advanced import ImagingStudy
from collections import defaultdict


class Command(BaseCommand):
    help = 'Clean up duplicate imaging studies, keeping only the most recent per patient+modality+study_type'

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
            help='Minimum age in hours for studies to be considered for cleanup (default: 1)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        min_age_hours = options['min_age_hours']
        min_age = timezone.now() - timezone.timedelta(hours=min_age_hours)
        
        self.stdout.write(self.style.SUCCESS('Starting duplicate imaging study cleanup...'))
        
        # Get all non-deleted studies (if min_age_hours is 0, get all studies)
        if min_age_hours == 0:
            all_studies = ImagingStudy.objects.filter(
                is_deleted=False
            ).select_related('patient', 'order', 'encounter').order_by('patient_id', 'modality', 'study_type', '-created', '-performed_at')
        else:
            all_studies = ImagingStudy.objects.filter(
                is_deleted=False,
                created__lt=min_age
            ).select_related('patient', 'order', 'encounter').order_by('patient_id', 'modality', 'study_type', '-created', '-performed_at')
        
        # Group by patient + modality + study_type
        study_groups = defaultdict(list)
        for study in all_studies:
            # Primary key: patient + modality + study_type
            key = (study.patient_id, study.modality, study.study_type or '')
            study_groups[key].append(study)
        
        # Also check for duplicates within same encounter (same patient, same encounter, same modality)
        # These are likely duplicates even if study_type is slightly different
        encounter_groups = defaultdict(list)
        for study in all_studies:
            if study.encounter_id:
                encounter_key = (study.patient_id, study.encounter_id, study.modality)
                encounter_groups[encounter_key].append(study)
        
        # Find duplicates (groups with more than 1 study)
        duplicates_to_remove = []
        kept_studies = []
        seen_study_ids = set()  # Track which studies we're keeping
        
        # Status priority for keeping the best study
        status_priority = {
            'verified': 10, 'reported': 9, 'completed': 8, 'awaiting_report': 7,
            'reporting': 6, 'in_progress': 5, 'quality_check': 4, 'arrived': 3,
            'scheduled': 2, 'cancelled': 1
        }
        
        # First, handle duplicates by patient+modality+study_type
        for key, studies in study_groups.items():
            if len(studies) > 1:
                # Sort by status priority and time
                studies_sorted = sorted(
                    studies,
                    key=lambda x: (
                        status_priority.get(x.status, 0),  # Higher status first
                        x.performed_at or x.created,  # Then by time
                    ),
                    reverse=True
                )
                
                # Keep the best one (highest status, most recent)
                kept = studies_sorted[0]
                if kept.id not in seen_study_ids:
                    kept_studies.append(kept)
                    seen_study_ids.add(kept.id)
                
                # Mark others for deletion
                for study in studies_sorted[1:]:
                    if study.id not in seen_study_ids:  # Don't add if already marked
                        duplicates_to_remove.append(study)
        
        # Also check for duplicates within same encounter (same patient, same encounter, same modality)
        # These are likely duplicates even if study_type is slightly different
        for key, studies in encounter_groups.items():
            if len(studies) > 1:
                # Sort by status and time
                studies_sorted = sorted(
                    studies,
                    key=lambda x: (
                        status_priority.get(x.status, 0),
                        x.performed_at or x.created,
                    ),
                    reverse=True
                )
                
                # Keep the best one
                kept = studies_sorted[0]
                if kept.id not in seen_study_ids:
                    if kept.id not in [s.id for s in kept_studies]:
                        kept_studies.append(kept)
                    seen_study_ids.add(kept.id)
                
                # Check if others are true duplicates (created within 24 hours and same modality)
                # For same encounter, any duplicate modality within 24 hours is likely a duplicate
                for study in studies_sorted[1:]:
                    time_diff = abs((study.created - kept.created).total_seconds() / 3600)  # hours
                    
                    # If created within 24 hours, same modality, same encounter - it's a duplicate
                    if time_diff < 24 and study.modality == kept.modality:
                        # Mark as duplicate
                        if study.id not in seen_study_ids and study.id not in [s.id for s in duplicates_to_remove]:
                            duplicates_to_remove.append(study)
        
        if not duplicates_to_remove:
            self.stdout.write(self.style.SUCCESS('No duplicates found!'))
            return
        
        self.stdout.write(f'\nFound {len(duplicates_to_remove)} duplicate studies to remove')
        self.stdout.write(f'Keeping {len(kept_studies)} unique studies')
        
        # Show summary
        patient_counts = defaultdict(int)
        for study in duplicates_to_remove:
            patient_counts[study.patient.full_name] += 1
        
        self.stdout.write('\nDuplicates by patient:')
        for patient_name, count in sorted(patient_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
            self.stdout.write(f'  {patient_name}: {count} duplicates')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('\nDRY RUN - No studies were actually deleted'))
            self.stdout.write(f'Would delete {len(duplicates_to_remove)} duplicate studies')
        else:
            # Delete duplicates
            with transaction.atomic():
                deleted_count = 0
                for study in duplicates_to_remove:
                    # Soft delete by marking as deleted
                    study.is_deleted = True
                    study.save(update_fields=['is_deleted'])
                    deleted_count += 1
                
                self.stdout.write(self.style.SUCCESS(f'\nSuccessfully removed {deleted_count} duplicate studies!'))
        
        self.stdout.write(self.style.SUCCESS('\nCleanup complete!'))
