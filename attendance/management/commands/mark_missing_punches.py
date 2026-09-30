"""Backfill missing punch flags and sync work records."""

from django.core.management.base import BaseCommand
from django.db.models import Min, Q

from attendance.scheduler import mark_missing_punches


class Command(BaseCommand):
    help = (
        "Scan attendance for missing punch in/out, backfill work records "
        "for the last 7 days, clear stale missing punch in records, and "
        "refresh related work-record cells."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Only report stale missing punch in records.",
        )

    def handle(self, *args, **options):
        from attendance.models import Attendance

        cleared = self.clear_stale_missing_punch_in(options["dry_run"])
        if options["dry_run"]:
            self.stdout.write(f"[dry run] {cleared} stale missing punch in record(s).")
            return

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
                f"Missing punch scan completed. Cleared {cleared} stale record(s), "
                f"refreshed {refreshed} attendance row(s)."
            )
        )

    def clear_stale_missing_punch_in(self, dry_run):
        """
        Reset "Missing punch in" work records the nightly scan would no longer
        create: before the employee joined or first used attendance, or on a
        holiday / company leave.
        """
        from attendance.models import Attendance, WorkRecords
        from base.methods import get_working_days

        first_attendance = dict(
            Attendance.objects.values("employee_id")
            .annotate(first=Min("attendance_date"))
            .values_list("employee_id", "first")
        )
        records = WorkRecords.objects.filter(
            work_record_type="CONF", message="Missing punch in"
        ).select_related("employee_id__employee_work_info")

        cleared = 0
        for record in records:
            if Attendance.objects.filter(
                employee_id=record.employee_id_id,
                attendance_date=record.date,
                attendance_clock_in__isnull=False,
            ).exists():
                continue
            work_info = getattr(record.employee_id, "employee_work_info", None)
            started = first_attendance.get(record.employee_id_id)
            reason = None
            if work_info and work_info.date_joining and work_info.date_joining > record.date:
                reason = "before joining"
            elif not started:
                reason = "never used attendance"
            elif started > record.date:
                reason = "before first attendance"
            elif record.date not in get_working_days(
                record.date, record.date, record.employee_id
            )["working_days_on"]:
                reason = "non-working day"
            if not reason:
                continue
            cleared += 1
            self.stdout.write(f"{record.employee_id} {record.date}: {reason}")
            if not dry_run:
                WorkRecords.objects.filter(pk=record.pk).update(
                    work_record_type="DFT", message=""
                )
        return cleared
