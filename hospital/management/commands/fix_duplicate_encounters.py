"""
Management command to fix duplicate encounters
Marks older duplicate encounters as completed or deleted
"""
from django.core.management.base import BaseCommand
from django.db.models import Count, Max
from django.utils import timezone
from hospital.models import Encounter
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Fix duplicate encounters by keeping only the most recent per patient per day'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making changes',
        )
        parser.add_argument(
            '--mark-completed',
            action='store_true',
            help='Mark duplicates as completed instead of deleted',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        mark_completed = options['mark_completed']
        
        self.stdout.write("=" * 60)
        self.stdout.write("Fixing Duplicate Encounters")
        self.stdout.write("=" * 60)
        
        # Find duplicate encounters (same patient, same date)
        # This handles both same-type and different-type duplicates on same day
        # Note: Can't use Max('id') on UUID fields, so we'll find duplicates differently
        from django.db.models import OuterRef, Subquery
        
        # Get all encounters grouped by patient and date
        duplicates = Encounter.objects.filter(
            is_deleted=False
        ).values(
            'patient_id',
            'started_at__date'
        ).annotate(
            count=Count('id')
        ).filter(count__gt=1)
        
        total_duplicates = 0
        fixed = 0
        
        for dup in duplicates:
            patient_id = dup['patient_id']
            date = dup['started_at__date']
            count = dup['count']
            
            # Get all encounters for this patient/date (regardless of type)
            encounters = Encounter.objects.filter(
                patient_id=patient_id,
                started_at__date=date,
                is_deleted=False
            ).order_by('-started_at', '-id')
            
            # Keep the one with highest ID (most recent, breaks timestamp ties)
            keep_encounter = encounters.first()
            duplicates_to_fix = encounters.exclude(id=keep_encounter.id)
            
            dup_count = duplicates_to_fix.count()
            total_duplicates += dup_count
            
            if dup_count > 0:
                self.stdout.write(
                    f"\nPatient {patient_id}, {date}: "
                    f"{count} encounters found, keeping {keep_encounter.id}, "
                    f"fixing {dup_count}"
                )
                
                if not dry_run:
                    for enc in duplicates_to_fix:
                        if mark_completed:
                            enc.status = 'completed'
                            enc.ended_at = timezone.now()
                            enc.notes = (enc.notes or '') + f'\n[Auto-completed] Duplicate encounter, kept {keep_encounter.id}'
                            enc.save()
                            self.stdout.write(f"  [OK] Marked {enc.id} as completed")
                        else:
                            enc.is_deleted = True
                            enc.notes = (enc.notes or '') + f'\n[Auto-deleted] Duplicate encounter, kept {keep_encounter.id}'
                            enc.save()
                            self.stdout.write(f"  [OK] Deleted {enc.id}")
                    fixed += dup_count
                else:
                    self.stdout.write(f"  [DRY RUN] Would fix {dup_count} encounters")
        
        self.stdout.write("\n" + "=" * 60)
        if dry_run:
            self.stdout.write(f"DRY RUN: Found {total_duplicates} duplicate encounters")
        else:
            self.stdout.write(f"Fixed {fixed} duplicate encounters")
            self.stdout.write(f"Total duplicates found: {total_duplicates}")
        self.stdout.write("=" * 60)
