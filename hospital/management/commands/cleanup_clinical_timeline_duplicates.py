"""
Soft-delete clinical note rows that duplicate what dedupe_clinical_notes_timeline() would hide.
Aligns database with consultation / history timelines (double-submit, auto-save bursts).

Default: report only. Use --execute to set is_deleted=True on duplicates.
"""
from django.core.management.base import BaseCommand
from django.db.models import Count
from django.utils import timezone

from hospital.models_advanced import ClinicalNote
from hospital.utils_clinical_notes import dedupe_clinical_notes_timeline


class Command(BaseCommand):
    help = (
        "Soft-delete duplicate clinical notes (same rules as on-screen timeline dedupe). "
        "Default: dry-run. Pass --execute to apply."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--execute",
            action="store_true",
            help="Actually soft-delete duplicate notes (default is preview only)",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Max encounters to process (0 = all)",
        )

    def handle(self, *args, **options):
        execute = options["execute"]
        limit = options["limit"] or 0

        if not execute:
            self.stdout.write(
                self.style.WARNING("PREVIEW ONLY - no rows changed. Use --execute to soft-delete.\n")
            )
        else:
            self.stdout.write(self.style.SUCCESS("EXECUTE - soft-deleting duplicate notes.\n"))

        qs = (
            ClinicalNote.objects.filter(is_deleted=False)
            .values("encounter_id")
            .annotate(n=Count("id"))
            .filter(n__gt=1)
            .order_by("encounter_id")
        )
        if limit:
            qs = qs[:limit]

        encounter_ids = [row["encounter_id"] for row in qs]
        total_would_drop = 0
        total_updated = 0
        encounters_with_drops = 0

        for eid in encounter_ids:
            notes = list(
                ClinicalNote.objects.filter(encounter_id=eid, is_deleted=False).order_by("-created")
            )
            if len(notes) < 2:
                continue
            deduped = dedupe_clinical_notes_timeline(notes)
            keep_ids = {n.id for n in deduped}
            to_remove = [n for n in notes if n.id not in keep_ids]
            if not to_remove:
                continue
            encounters_with_drops += 1
            total_would_drop += len(to_remove)
            for n in to_remove:
                if execute:
                    n.is_deleted = True
                    n.modified = timezone.now()
                else:
                    self.stdout.write(
                        f"  would soft-delete note {n.pk} ({n.note_type}) "
                        f"encounter={eid} created={n.created}"
                    )
            if execute:
                ClinicalNote.objects.bulk_update(to_remove, ["is_deleted", "modified"])
                total_updated += len(to_remove)

        if execute:
            self.stdout.write(
                self.style.SUCCESS(f"Soft-deleted {total_updated} duplicate clinical note(s).")
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    f"Preview: {total_would_drop} duplicate note(s) in {encounters_with_drops} encounter(s) "
                    f"({len(encounter_ids)} encounter(s) had 2+ notes)."
                )
            )
        self.stdout.write(self.style.SUCCESS("Done."))
