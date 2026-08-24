"""Backfill missing punch flags and sync work records."""

from django.core.management.base import BaseCommand
from django.db.models import Q

from attendance.scheduler import mark_missing_punches


class Command(BaseCommand):
    help = (
        "Scan attendance for missing punch in/out, backfill work records "
        "for the last 7 days, and refresh related work-record cells."
    )

    def handle(self, *args, **options):
        from attendance.models import Attendance

        mark_missing_punches()

        flagged = Attendance.objects.filter(
            Q(missing_punch_in=True) | Q(missing_punch_out=True)
        )
        refreshed = 0
        for attendance in flagged.iterator():
            attendance.save()
            refreshed += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Missing punch scan completed. Refreshed {refreshed} attendance row(s)."
            )
        )
