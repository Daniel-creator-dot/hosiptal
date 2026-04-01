"""
Management command to clean up duplicate clinical notes
Removes duplicate notes that were created by auto-save before the fix
"""
from django.core.management.base import BaseCommand
from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta
from hospital.models_advanced import ClinicalNote


class Command(BaseCommand):
    help = 'Clean up duplicate clinical notes created by auto-save'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting',
        )
        parser.add_argument(
            '--time-window',
            type=int,
            default=10,
            help='Time window in seconds to consider notes as duplicates (default: 10)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        time_window = options['time_window']
        
        self.stdout.write(self.style.WARNING('Starting duplicate clinical notes cleanup...'))
        
        # Find duplicate notes by grouping on encounter, note_type, content, and time window
        duplicates_found = 0
        duplicates_deleted = 0
        
        # Get all notes grouped by encounter and note_type
        notes_by_encounter = ClinicalNote.objects.filter(
            is_deleted=False
        ).values('encounter', 'note_type', 'created_by').annotate(
            count=Count('id')
        ).filter(count__gt=1)
        
        for group in notes_by_encounter:
            encounter_id = group['encounter']
            note_type = group['note_type']
            created_by_id = group['created_by']
            
            # Get all notes in this group
            notes = ClinicalNote.objects.filter(
                encounter_id=encounter_id,
                note_type=note_type,
                created_by_id=created_by_id,
                is_deleted=False
            ).order_by('created')
            
            # Group notes by content and time window
            seen_notes = {}
            notes_to_delete = []
            
            for note in notes:
                # Create a key based on content (normalized)
                content_key = (
                    (note.subjective or '').strip().lower(),
                    (note.objective or '').strip().lower(),
                    (note.assessment or '').strip().lower(),
                    (note.plan or '').strip().lower(),
                )
                
                # Round timestamp to nearest time_window seconds
                timestamp_key = note.created.replace(
                    second=(note.created.second // time_window) * time_window,
                    microsecond=0
                )
                
                full_key = (content_key, timestamp_key)
                
                if full_key in seen_notes:
                    # This is a duplicate - mark for deletion
                    notes_to_delete.append(note)
                    duplicates_found += 1
                else:
                    # First occurrence - keep it
                    seen_notes[full_key] = note
            
            # Delete duplicates (keep the first one)
            for note in notes_to_delete:
                if dry_run:
                    self.stdout.write(
                        self.style.WARNING(
                            f'Would delete: {note.get_note_type_display()} note '
                            f'(ID: {note.id}) from encounter {encounter_id} '
                            f'created at {note.created}'
                        )
                    )
                else:
                    note.is_deleted = True
                    note.save(update_fields=['is_deleted', 'modified'])
                    duplicates_deleted += 1
        
        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f'DRY RUN: Found {duplicates_found} duplicate notes that would be deleted'
                )
            )
            self.stdout.write(
                self.style.WARNING('Run without --dry-run to actually delete duplicates')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully deleted {duplicates_deleted} duplicate clinical notes'
                )
            )
        
        self.stdout.write(self.style.SUCCESS('Cleanup complete!'))





