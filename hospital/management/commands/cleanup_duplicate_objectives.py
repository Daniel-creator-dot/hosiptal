"""
Management command to clean up duplicate marketing objectives
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from hospital.models_marketing import MarketingObjective
from django.db.models import Count
from django.utils import timezone


class Command(BaseCommand):
    help = 'Clean up duplicate marketing objectives, keeping the most recent one'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting',
        )
        parser.add_argument(
            '--keep-oldest',
            action='store_true',
            help='Keep the oldest objective instead of the newest',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        keep_oldest = options.get('keep_oldest', False)
        
        with transaction.atomic():
            # Find duplicates by title (case-insensitive)
            from django.db.models import Q
            duplicates = MarketingObjective.objects.values('title').annotate(
                count=Count('id')
            ).filter(count__gt=1)
            
            total_duplicates = 0
            deleted_count = 0
            
            for dup_group in duplicates:
                title = dup_group['title']
                count = dup_group['count']
                total_duplicates += (count - 1)  # All but one are duplicates
                
                # Get all objectives with this title
                objectives = MarketingObjective.objects.filter(
                    title__iexact=title
                ).order_by('created' if keep_oldest else '-created')
                
                # Keep the first one (oldest or newest based on flag)
                keep = objectives.first()
                to_delete = objectives.exclude(id=keep.id)
                
                self.stdout.write(f'\nFound {count} objectives with title "{title}":')
                self.stdout.write(f'  Keeping: {keep.id} (created: {keep.created})')
                
                for obj in to_delete:
                    obj_id = str(obj.id)
                    created_str = obj.created.strftime('%Y-%m-%d %H:%M:%S') if obj.created else 'Unknown'
                    if dry_run:
                        self.stdout.write(self.style.WARNING(f'  [DRY RUN] Would delete: {obj_id} (created: {created_str})'))
                    else:
                        obj.delete()
                        deleted_count += 1
                        self.stdout.write(self.style.SUCCESS(f'  ✅ Deleted: {obj_id}'))
            
            if total_duplicates == 0:
                self.stdout.write(self.style.SUCCESS('\n✅ No duplicates found!'))
            else:
                if dry_run:
                    self.stdout.write(self.style.WARNING(
                        f'\n[DRY RUN] Would delete {total_duplicates} duplicate objective(s)'
                    ))
                else:
                    self.stdout.write(self.style.SUCCESS(
                        f'\n✅ Deleted {deleted_count} duplicate objective(s)'
                    ))
                    self.stdout.write(f'   Kept {duplicates.count()} unique objective(s)')










