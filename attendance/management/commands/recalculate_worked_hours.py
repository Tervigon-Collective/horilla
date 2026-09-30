"""Repair punch activities, recalculate worked hours and rebuild Hours Balance."""

from collections import defaultdict
from datetime import datetime

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone


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
        from attendance.models import (
            Attendance,
            AttendanceActivity,
            AttendanceOverTime,
            default_shift_for,
        )

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

            capped = self.cap_auto_checkouts(dry_run)

            resaved = 0
            # Open attendances count up to "now", so they always look changed.
            closed = Attendance.objects.exclude(attendance_clock_out=None)
            for attendance in closed.select_related("employee_id"):
                old = attendance.attendance_worked_hour
                old_min = attendance.minimum_hour
                attendance.sync_worked_hours_from_clock_times()
                stale_ot = (attendance.approved_overtime_second or 0) > (
                    attendance.overtime_second or 0
                )
                # Requests/imports could store no shift or a 00:00 minimum on
                # a working day, which counted every worked minute as overtime.
                had_shift = bool(attendance.shift_id_id)
                if not had_shift:
                    attendance.shift_id = default_shift_for(attendance.employee_id)
                attendance.adjust_minimum_hour()
                missing_shift = not had_shift or attendance.minimum_hour != old_min
                if (
                    attendance.attendance_worked_hour == old
                    and not stale_ot
                    and not missing_shift
                ):
                    continue
                resaved += 1
                self.stdout.write(
                    f"attendance {attendance.pk} {attendance.employee_id} "
                    f"{attendance.attendance_date}: {old} -> "
                    f"{attendance.attendance_worked_hour}, minimum {old_min} -> "
                    f"{attendance.minimum_hour}, shift {attendance.shift_id}"
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
                f"{prefix}Fixed {fixed_activities} activities, capped {capped} auto "
                f"check-outs, recalculated {resaved} attendances, rebuilt "
                f"{rebuilt} hours balances."
            )
        )

    def cap_auto_checkouts(self, dry_run):
        """
        Past auto check-outs credited time up to the auto check-out time; move
        them back to shift end and flag them as missing punch out. They are
        recognised by the activity closing exactly on the auto check-out time
        (real punches always carry sub-second precision).
        """
        from attendance.models import Attendance, AttendanceActivity
        from attendance.scheduler import (
            auto_punch_out_credit_until,
            flag_missing_punch_out,
        )
        from base.models import EmployeeShiftSchedule

        capped = 0
        schedules = EmployeeShiftSchedule.objects.filter(
            is_auto_punch_out_enabled=True, auto_punch_out_time__isnull=False
        )
        for schedule in schedules:
            attendances = Attendance.objects.filter(
                shift_id=schedule.shift_id,
                attendance_day=schedule.day,
                attendance_clock_out=schedule.auto_punch_out_time,
            ).select_related("employee_id")
            for attendance in attendances:
                activity = (
                    AttendanceActivity.objects.filter(
                        employee_id=attendance.employee_id,
                        attendance_date=attendance.attendance_date,
                        clock_out_date=attendance.attendance_clock_out_date,
                        clock_out=schedule.auto_punch_out_time,
                    )
                    .order_by("clock_in_date", "clock_in")
                    .last()
                )
                if not activity:
                    continue
                activity_in = datetime.combine(activity.clock_in_date, activity.clock_in)
                credited_out = max(
                    auto_punch_out_credit_until(
                        schedule, attendance.attendance_clock_out_date
                    ),
                    activity_in,
                )
                capped += 1
                self.stdout.write(
                    f"auto check-out {attendance.pk} {attendance.employee_id} "
                    f"{attendance.attendance_date}: "
                    f"{attendance.attendance_clock_out} -> {credited_out.time():%H:%M}"
                )
                if dry_run:
                    continue
                AttendanceActivity.objects.filter(pk=activity.pk).update(
                    clock_out=credited_out.time(),
                    clock_out_date=credited_out.date(),
                    out_datetime=timezone.make_aware(credited_out),
                )
                attendance.attendance_clock_out = credited_out.time().replace(
                    second=0, microsecond=0
                )
                attendance.attendance_clock_out_date = credited_out.date()
                attendance.save()
                flag_missing_punch_out(attendance.pk)
        return capped
