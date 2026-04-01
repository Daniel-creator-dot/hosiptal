"""
Comprehensive duplicate removal for all record types
Removes duplicates from MedicalRecord, ClinicalNote, and other related models
"""
from django.core.management.base import BaseCommand
from django.db.models import Count
from django.db import transaction
from hospital.models import MedicalRecord
from hospital.models_advanced import ClinicalNote


class Command(BaseCommand):
    help = 'Remove ALL duplicate records from medical records and clinical notes'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show duplicates without deleting them',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        self.stdout.write(self.style.SUCCESS('\n=== Comprehensive Duplicate Record Cleanup ===\n'))
        
        removed_count = 0
        
        # 1. MedicalRecord duplicates
        self.stdout.write('[1/2] Checking MedicalRecord duplicates...')
        with transaction.atomic():
            # Method 1: Exact duplicates: same patient + encounter + record_type + title
            exact_dups = MedicalRecord.objects.filter(
                is_deleted=False
            ).values(
                'patient_id', 'encounter_id', 'record_type', 'title'
            ).annotate(
                count=Count('id')
            ).filter(
                count__gt=1
            )
            
            # Method 2: Same patient + record_type + title + same created date (within 1 minute)
            # This catches duplicates created at the same time
            from django.db.models import F
            from datetime import timedelta
            
            mr_removed = 0
            
            # Process exact duplicates
            for dup_group in exact_dups:
                patient_id = dup_group['patient_id']
                encounter_id = dup_group['encounter_id']
                record_type = dup_group['record_type']
                title = dup_group['title']
                
                # Get all duplicates, keep newest
                records = MedicalRecord.objects.filter(
                    patient_id=patient_id,
                    encounter_id=encounter_id,
                    record_type=record_type,
                    title=title,
                    is_deleted=False
                ).order_by('-created')
                
                keep_record = records.first()
                duplicates_to_remove = records.exclude(id=keep_record.id)
                
                if not dry_run:
                    deleted = duplicates_to_remove.update(is_deleted=True)
                    mr_removed += deleted
                else:
                    mr_removed += duplicates_to_remove.count()
            
            # Method 2: Find duplicates by patient + title + created time (within 1 minute)
            all_records = MedicalRecord.objects.filter(is_deleted=False).select_related('patient').order_by('patient_id', 'title', 'created')
            processed = set()
            
            for i, record in enumerate(all_records):
                if record.id in processed:
                    continue
                
                # Find records with same patient + title created within 1 minute
                dup_key = (record.patient_id, record.title)
                potential_dups = [
                    r for r in all_records[i+1:] 
                    if (r.patient_id, r.title) == dup_key 
                    and abs((r.created - record.created).total_seconds()) < 60
                    and r.id not in processed
                ]
                
                if potential_dups:
                    # Add current record to duplicates list
                    all_dups = [record] + potential_dups
                    # Keep the one with most content or newest
                    all_dups = sorted(
                        all_dups,
                        key=lambda r: (r.created, len(r.content or '')),
                        reverse=True
                    )
                    keep_record = all_dups[0]
                    duplicates_to_remove = all_dups[1:]
                    
                    for dup in duplicates_to_remove:
                        processed.add(dup.id)
                    
                    if not dry_run:
                        delete_ids = [d.id for d in duplicates_to_remove]
                        deleted = MedicalRecord.objects.filter(id__in=delete_ids).update(is_deleted=True)
                        mr_removed += deleted
                    else:
                        mr_removed += len(duplicates_to_remove)
            
            self.stdout.write(f'  Found {exact_dups.count()} exact duplicate groups')
            self.stdout.write(f'  {"Would remove" if dry_run else "Removed"} {mr_removed} duplicate MedicalRecord(s)')
            removed_count += mr_removed
        
        # 2. ClinicalNote duplicates
        self.stdout.write('\n[2/2] Checking ClinicalNote duplicates...')
        with transaction.atomic():
            # Find duplicates: same encounter + note_type + similar content
            clinical_note_dups = ClinicalNote.objects.filter(
                is_deleted=False
            ).values(
                'encounter_id', 'note_type', 'notes'
            ).annotate(
                count=Count('id')
            ).filter(
                count__gt=1
            )
            
            cn_removed = 0
            for dup_group in clinical_note_dups:
                encounter_id = dup_group['encounter_id']
                note_type = dup_group['note_type']
                notes = dup_group['notes']
                
                # Get all duplicates, keep newest
                notes_list = ClinicalNote.objects.filter(
                    encounter_id=encounter_id,
                    note_type=note_type,
                    notes=notes,
                    is_deleted=False
                ).order_by('-created')
                
                keep_note = notes_list.first()
                duplicates_to_remove = notes_list.exclude(id=keep_note.id)
                
                if not dry_run:
                    deleted = duplicates_to_remove.update(is_deleted=True)
                    cn_removed += deleted
                else:
                    cn_removed += duplicates_to_remove.count()
            
            self.stdout.write(f'  Found {clinical_note_dups.count()} duplicate groups')
            self.stdout.write(f'  {"Would remove" if dry_run else "Removed"} {cn_removed} duplicate ClinicalNote(s)')
            removed_count += cn_removed
        
        # Summary
        self.stdout.write(self.style.SUCCESS('\n=== Summary ==='))
        self.stdout.write(f'Total duplicates {"found" if dry_run else "removed"}: {removed_count}')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('\n[DRY RUN] No records were actually deleted'))
            self.stdout.write('Run without --dry-run to actually remove duplicates')
        else:
            self.stdout.write(self.style.SUCCESS('\n[SUCCESS] All duplicates removed!'))
            self.stdout.write(self.style.SUCCESS('System is now duplicate-free!'))
