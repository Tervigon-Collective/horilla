"""Repair punch activities, recalculate worked hours and rebuild Hours Balance."""

from collections import defaultdict
from datetime import datetime

from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = (
        "Fix activities whose check-out is before check-in, re-save attendances "
        "whose worked hours no longer match their punches, and rebuild the "
        "monthly Hours Balance from validated attendances."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run", action="store_true", help="Report changes without saving."
        )

    def handle(self, *args, **options):
        from attendance.methods.utils import format_time, strtime_seconds
        from attendance.models import Attendance, AttendanceActivity, AttendanceOverTime

        dry_run = options["dry_run"]

        with transaction.atomic():
            fixed_activities = 0
            for activity in AttendanceActivity.objects.exclude(clock_out=None):
                start = datetime.combine(activity.clock_in_date, activity.clock_in)
                end = datetime.combine(activity.clock_out_date, activity.clock_out)
                if end < start:
                    fixed_activities += 1
                    self.stdout.write(
                        f"activity {activity.pk} {activity.employee_id} "
                        f"{activity.attendance_date}: out {end} before in {start}"
                    )
                    if not dry_run:
                        AttendanceActivity.objects.filter(pk=activity.pk).update(
                            clock_out=activity.clock_in,
                            clock_out_date=activity.clock_in_date,
                            out_datetime=activity.in_datetime,
                        )

            resaved = 0
            # Open attendances count up to "now", so they always look changed.
            closed = Attendance.objects.exclude(attendance_clock_out=None)
            for attendance in closed.select_related("employee_id"):
                old = attendance.attendance_worked_hour
                attendance.sync_worked_hours_from_clock_times()
                if attendance.attendance_worked_hour == old:
                    continue
                resaved += 1
                self.stdout.write(
                    f"attendance {attendance.pk} {attendance.employee_id} "
                    f"{attendance.attendance_date}: {old} -> "
                    f"{attendance.attendance_worked_hour}"
                )
                if not dry_run:
                    attendance.save()

            totals = defaultdict(lambda: [0, 0, 0])
            for attendance in Attendance.objects.filter(attendance_validated=True):
                key = (
                    attendance.employee_id_id,
                    attendance.attendance_date.strftime("%B").lower(),
                    str(attendance.attendance_date.year),
                )
                work = attendance.at_work_second or 0
                totals[key][0] += work
                totals[key][1] += attendance.approved_overtime_second or 0
                totals[key][2] += max(0, strtime_seconds(attendance.minimum_hour) - work)

            rebuilt = 0
            for ot in AttendanceOverTime.objects.select_related("employee_id"):
                work, overtime, pending = totals.pop(
                    (ot.employee_id_id, ot.month, str(ot.year)), (0, 0, 0)
                )
                if (ot.hour_account_second, ot.overtime_second, ot.hour_pending_second) == (
                    work,
                    overtime,
                    pending,
                ):
                    continue
                rebuilt += 1
                self.stdout.write(
                    f"hours balance {ot.employee_id} {ot.month} {ot.year}: "
                    f"worked {format_time(ot.hour_account_second or 0)} -> {format_time(work)}, "
                    f"pending {format_time(ot.hour_pending_second or 0)} -> {format_time(pending)}, "
                    f"overtime {format_time(ot.overtime_second or 0)} -> {format_time(overtime)}"
                )
                if not dry_run:
                    ot.hour_account_second = work
                    ot.overtime_second = overtime
                    ot.hour_pending_second = pending
                    ot.worked_hours = format_time(work)
                    ot.pending_hours = format_time(pending)
                    ot.overtime = format_time(overtime)
                    ot.save(
                        update_fields=[
                            "hour_account_second",
                            "overtime_second",
                            "hour_pending_second",
                            "worked_hours",
                            "pending_hours",
                            "overtime",
                        ]
                    )

            for (employee_id, month, year), (work, overtime, pending) in totals.items():
                rebuilt += 1
                self.stdout.write(f"hours balance employee {employee_id} {month} {year}: created")
                if not dry_run:
                    AttendanceOverTime.objects.create(
                        employee_id_id=employee_id,
                        month=month,
                        year=year,
                        hour_account_second=work,
                        overtime_second=overtime,
                        hour_pending_second=pending,
                        worked_hours=format_time(work),
                        pending_hours=format_time(pending),
                        overtime=format_time(overtime),
                    )

            if dry_run:
                transaction.set_rollback(True)

        prefix = "[dry run] " if dry_run else ""
        self.stdout.write(
            self.style.SUCCESS(
                f"{prefix}Fixed {fixed_activities} activities, recalculated "
                f"{resaved} attendances, rebuilt {rebuilt} hours balances."
            )
        )
