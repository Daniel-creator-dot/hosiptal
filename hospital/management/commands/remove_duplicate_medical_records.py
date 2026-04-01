"""
Remove duplicate medical records
Identifies and removes duplicate records based on patient, encounter, record_type, title,
and same date+time (to the second).
"""
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.db.models import Count
from django.db import transaction
from django.db.models.functions import TruncSecond
from django.utils import timezone
from hospital.models import MedicalRecord


class Command(BaseCommand):
    help = 'Remove duplicate medical records and prevent future duplicates'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show duplicates without deleting them',
        )
        parser.add_argument(
            '--keep-oldest',
            action='store_true',
            help='Keep the oldest record, delete newer duplicates (default: keep newest)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        keep_oldest = options['keep_oldest']
        
        self.stdout.write(self.style.SUCCESS('\n=== Medical Records Duplicate Cleanup ===\n'))
        
        # 1) Find duplicates by same date+time (to the second): patient + encounter + type + title + created_second
        duplicates_same_time = list(
            MedicalRecord.objects.filter(is_deleted=False)
            .annotate(created_sec=TruncSecond('created'))
            .values('patient_id', 'encounter_id', 'record_type', 'title', 'created_sec')
            .annotate(count=Count('id'))
            .filter(count__gt=1)
        )
        n_same_time = len(duplicates_same_time)
        self.stdout.write(f'Found {n_same_time} duplicate groups (same patient+encounter+type+title+date+time)\n')
        
        # Find duplicates: same patient + encounter + record_type + title
        duplicates_by_all_fields = list(
            MedicalRecord.objects.filter(
                is_deleted=False
            ).values(
                'patient_id', 'encounter_id', 'record_type', 'title'
            ).annotate(
                count=Count('id')
            ).filter(
                count__gt=1
            ).order_by('-count')
        )
        
        # Also find duplicates: same patient + encounter + record_type (same record type for same encounter)
        duplicates_by_encounter = list(
            MedicalRecord.objects.filter(
                is_deleted=False
            ).values(
                'patient_id', 'encounter_id', 'record_type'
            ).annotate(
                count=Count('id')
            ).filter(
                count__gt=1
            ).order_by('-count')
        )
        
        # Count totals
        exact_dups = len(duplicates_by_all_fields)
        encounter_dups = len(duplicates_by_encounter)
        total_duplicate_groups = n_same_time + exact_dups + encounter_dups
        
        self.stdout.write(f'Found {exact_dups} exact duplicate groups (same patient+encounter+type+title)')
        self.stdout.write(f'Found {encounter_dups} potential duplicate groups (same patient+encounter+type, multiple records)')
        self.stdout.write(f'Total: {total_duplicate_groups} duplicate groups\n')
        
        if total_duplicate_groups == 0:
            self.stdout.write(self.style.SUCCESS('[OK] No duplicates found!'))
            return
        
        total_records_to_remove = 0
        removed_count = 0
        
        if dry_run:
            self.stdout.write(self.style.WARNING('[DRY RUN] DRY RUN MODE - No records will be deleted\n'))
        
        with transaction.atomic():
            # Process same-date+time duplicates first (same patient + encounter + type + title + created to the second)
            for dup_group in duplicates_same_time:
                patient_id = dup_group['patient_id']
                encounter_id = dup_group['encounter_id']
                record_type = dup_group['record_type']
                title = dup_group['title']
                created_sec = dup_group['created_sec']
                count = dup_group['count']
                if timezone.is_naive(created_sec):
                    end_sec = created_sec + timedelta(seconds=1)
                else:
                    end_sec = created_sec + timedelta(seconds=1)
                records = MedicalRecord.objects.filter(
                    patient_id=patient_id,
                    encounter_id=encounter_id,
                    record_type=record_type,
                    title=title,
                    is_deleted=False,
                    created__gte=created_sec,
                    created__lt=end_sec,
                ).order_by('created' if keep_oldest else '-created')
                keep_record = records.first()
                records_to_delete = records.exclude(id=keep_record.id)
                delete_count = records_to_delete.count()
                total_records_to_remove += delete_count
                patient_name = keep_record.patient.full_name if keep_record.patient else f'Patient {patient_id}'
                self.stdout.write(
                    f"Same date+time: {record_type} - {title[:50]}... @ {created_sec}\n"
                    f"  Patient: {patient_name}\n  Will remove: {delete_count}\n"
                )
                if not dry_run:
                    deleted = records_to_delete.update(is_deleted=True)
                    removed_count += deleted
                    self.stdout.write(self.style.SUCCESS(f"  [OK] Removed {deleted}\n"))
                else:
                    self.stdout.write(self.style.WARNING(f"  [WARNING] Would remove {delete_count}\n"))
            
            # Process exact duplicates (same patient + encounter + type + title)
            for dup_group in duplicates_by_all_fields:
                patient_id = dup_group['patient_id']
                encounter_id = dup_group['encounter_id']
                record_type = dup_group['record_type']
                title = dup_group['title']
                count = dup_group['count']
                
                # Get all records in this duplicate group
                records = MedicalRecord.objects.filter(
                    patient_id=patient_id,
                    encounter_id=encounter_id,
                    record_type=record_type,
                    title=title,
                    is_deleted=False
                ).order_by('created' if keep_oldest else '-created')
                
                # Keep the first one (oldest if keep_oldest, newest otherwise)
                keep_record = records.first()
                records_to_delete = records.exclude(id=keep_record.id)
                
                delete_count = records_to_delete.count()
                total_records_to_remove += delete_count
                
                # Get patient name for display
                patient_name = keep_record.patient.full_name if keep_record.patient else f'Patient {patient_id}'
                
                self.stdout.write(
                    f"Exact Duplicate Group: {record_type} - {title[:50]}...\n"
                    f"  Patient: {patient_name} (ID: {patient_id})\n"
                    f"  Encounter: {encounter_id}\n"
                    f"  Total duplicates: {count}, Will remove: {delete_count}\n"
                    f"  Keeping: Record ID {keep_record.id} (created: {keep_record.created})\n"
                )
                
                if not dry_run:
                    deleted = records_to_delete.update(is_deleted=True)
                    removed_count += deleted
                    self.stdout.write(self.style.SUCCESS(f"  [OK] Removed {deleted} duplicate(s)\n"))
                else:
                    self.stdout.write(self.style.WARNING(f"  [WARNING] Would remove {delete_count} duplicate(s)\n"))
            
            # Process encounter-level duplicates (same patient + encounter + type, different titles)
            # Only process if there are more than 1 record of same type for same encounter
            processed_encounters = set()
            for dup_group in duplicates_by_encounter:
                patient_id = dup_group['patient_id']
                encounter_id = dup_group['encounter_id']
                record_type = dup_group['record_type']
                
                # Skip if we already processed this as exact duplicate
                if (patient_id, encounter_id, record_type) in processed_encounters:
                    continue
                
                # Check if this was already handled as exact duplicate
                exact_dup_check = any(
                    g['patient_id'] == patient_id and g['encounter_id'] == encounter_id and g['record_type'] == record_type
                    for g in duplicates_by_all_fields
                )
                
                if exact_dup_check:
                    processed_encounters.add((patient_id, encounter_id, record_type))
                    continue
                
                # Get all records of this type for this encounter
                records = list(MedicalRecord.objects.filter(
                    patient_id=patient_id,
                    encounter_id=encounter_id,
                    record_type=record_type,
                    is_deleted=False
                ).order_by('created' if keep_oldest else '-created'))
                
                if len(records) <= 1:
                    continue
                
                # Sort by created time and content length (keep the one with most info)
                if not keep_oldest:
                    records = sorted(
                        records,
                        key=lambda r: (r.created, len(r.content or '')),
                        reverse=True
                    )
                else:
                    records = sorted(
                        records,
                        key=lambda r: (r.created, len(r.content or ''))
                    )
                
                keep_record = records[0]
                records_to_delete = records[1:]
                
                delete_count = len(records_to_delete)
                total_records_to_remove += delete_count
                
                # Get patient name for display
                patient_name = keep_record.patient.full_name if keep_record.patient else f'Patient {patient_id}'
                
                self.stdout.write(
                    f"Encounter Duplicate Group: {record_type}\n"
                    f"  Patient: {patient_name} (ID: {patient_id})\n"
                    f"  Encounter: {encounter_id}\n"
                    f"  Total records: {len(records)}, Will remove: {delete_count}\n"
                    f"  Keeping: Record ID {keep_record.id} - {keep_record.title[:50]}... (created: {keep_record.created})\n"
                )
                
                if not dry_run:
                    delete_ids = [r.id for r in records_to_delete]
                    deleted = MedicalRecord.objects.filter(id__in=delete_ids).update(is_deleted=True)
                    removed_count += deleted
                    self.stdout.write(self.style.SUCCESS(f"  [OK] Removed {deleted} duplicate(s)\n"))
                else:
                    self.stdout.write(self.style.WARNING(f"  [WARNING] Would remove {delete_count} duplicate(s)\n"))
                
                processed_encounters.add((patient_id, encounter_id, record_type))
        
        # Summary
        self.stdout.write(self.style.SUCCESS('\n=== Summary ==='))
        self.stdout.write(f'Total duplicate groups: {total_duplicate_groups}')
        self.stdout.write(f'Total records to remove: {total_records_to_remove}')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('\n[DRY RUN] DRY RUN - No records were actually deleted'))
            self.stdout.write(self.style.WARNING('Run without --dry-run to actually remove duplicates'))
        else:
            self.stdout.write(self.style.SUCCESS(f'\n[SUCCESS] Successfully removed {removed_count} duplicate record(s)'))
            self.stdout.write(self.style.SUCCESS('[SUCCESS] Medical records are now duplicate-free!'))
        
        # Verify
        remaining_exact = MedicalRecord.objects.filter(
            is_deleted=False
        ).values(
            'patient_id', 'encounter_id', 'record_type', 'title'
        ).annotate(
            count=Count('id')
        ).filter(
            count__gt=1
        ).count()
        
        remaining_encounter = MedicalRecord.objects.filter(
            is_deleted=False
        ).values(
            'patient_id', 'encounter_id', 'record_type'
        ).annotate(
            count=Count('id')
        ).filter(
            count__gt=1
        ).count()
        
        remaining_duplicates = remaining_exact + remaining_encounter
        
        if remaining_duplicates == 0:
            self.stdout.write(self.style.SUCCESS('\n[OK] Verification: No duplicates remaining!'))
        else:
            self.stdout.write(self.style.WARNING(f'\n[WARNING] Warning: {remaining_duplicates} duplicate groups still exist'))
