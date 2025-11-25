from django.core.management.base import BaseCommand
from hospital.models_auto_attendance import StaffAttendance
from hospital.signals_auto_attendance import sync_attendance_calendar_record


class Command(BaseCommand):
    help = "Sync StaffAttendance records into AttendanceCalendar for HR dashboards"

    def handle(self, *args, **options):
        attendances = StaffAttendance.objects.filter(is_deleted=False).select_related('staff').order_by('date')
        total = attendances.count()
        synced = 0

        for attendance in attendances:
            record = sync_attendance_calendar_record(attendance)
            if record:
                synced += 1

        self.stdout.write(self.style.SUCCESS(
            f"Attendance calendar sync complete: {synced}/{total} records processed."
        ))

