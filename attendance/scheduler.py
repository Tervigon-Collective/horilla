import datetime
import fcntl
import os
import sys
import tempfile
from contextlib import contextmanager
from datetime import timedelta

import pytz
from horilla.db import SafeBackgroundScheduler
from django.conf import settings
from django.db import models
from django.utils import timezone

from base.backends import logger
from horilla.db import scheduled_job
from horilla.scheduling import register_job


@contextmanager
def _single_run(name):
    """
    Every gunicorn worker starts its own scheduler; hold a non-blocking file
    lock so a job never runs concurrently (concurrent attendance saves would
    apply the same Hours Balance diff more than once).
    """
    with open(os.path.join(tempfile.gettempdir(), f"horilla-{name}.lock"), "w") as fh:
        try:
            fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            yield False
            return
        try:
            yield True
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


def auto_punch_out_credit_until(shift_schedule, date):
    """
    Datetime up to which an auto check-out credits worked time: the shift end
    (the auto check-out time itself only decides when the punch gets closed).
    `date` is the day the auto check-out happens on (already night-shift adjusted).
    """
    end_time = shift_schedule.end_time or shift_schedule.auto_punch_out_time
    return datetime.datetime.combine(date, min(end_time, shift_schedule.auto_punch_out_time))


def flag_missing_punch_out(attendance_id):
    """
    Flag an auto checked-out attendance. Saved separately from the check-out
    so save() (which clears the flag when the check-out changes) keeps it, and
    the work record is refreshed to "Missing punch out".
    """
    from attendance.models import Attendance

    attendance = Attendance.objects.filter(pk=attendance_id).first()
    if attendance and not attendance.missing_punch_out:
        attendance.missing_punch_out = True
        attendance.save()


@scheduled_job
def auto_punch_out():
    with _single_run("auto_punch_out") as acquired:
        if acquired:
            _auto_punch_out()


def _auto_punch_out():
    from attendance.methods.utils import Request
    from attendance.models import Attendance, AttendanceActivity
    from attendance.views.clock_in_out import clock_out
    from base.models import EmployeeShiftSchedule

    automatic_check_out_shifts = EmployeeShiftSchedule.objects.filter(
        is_auto_punch_out_enabled=True
    )

    for shift_schedule in automatic_check_out_shifts:
        activities = AttendanceActivity.objects.filter(
            shift_day=shift_schedule.day,
            clock_out_date=None,
            clock_out=None,
        ).order_by("-created_at")

        for activity in activities:
            attendance = Attendance.objects.filter(
                employee_id=activity.employee_id,
                shift_id=shift_schedule.shift_id,
                attendance_day=shift_schedule.day,
                attendance_date=activity.attendance_date,
            ).first()
            if not attendance:
                continue

            date = activity.attendance_date
            if (
                shift_schedule.is_night_shift
                and shift_schedule.start_time
                and shift_schedule.end_time
                and shift_schedule.start_time > shift_schedule.end_time
            ):
                date += timedelta(days=1)

            cutoff = datetime.datetime.combine(date, shift_schedule.auto_punch_out_time)
            combined_datetime = timezone.make_aware(cutoff)
            if combined_datetime >= timezone.now():
                continue

            activity_in = datetime.datetime.combine(
                activity.clock_in_date, activity.clock_in
            )
            try:
                if attendance.attendance_clock_out is None and activity_in < cutoff:
                    # A forgotten check-out only earns time up to shift end;
                    # the flag lets the employee request a correction.
                    credited_out = max(
                        auto_punch_out_credit_until(shift_schedule, date), activity_in
                    )
                    clock_out(
                        Request(
                            user=attendance.employee_id.employee_user_id,
                            date=credited_out.date(),
                            time=credited_out.time(),
                            datetime=timezone.make_aware(credited_out),
                        )
                    )
                    flag_missing_punch_out(attendance.pk)
                    continue

                # Attendance already has a check-out (edited/approved while the
                # punch was still open) or the punch started after the cutoff:
                # close just the activity, never before it started.
                out = cutoff
                if attendance.attendance_clock_out and attendance.attendance_clock_out_date:
                    attendance_out = datetime.datetime.combine(
                        attendance.attendance_clock_out_date,
                        attendance.attendance_clock_out,
                    )
                    if attendance_out >= activity_in:
                        out = min(out, attendance_out)
                out = max(out, activity_in)
                activity.clock_out = out.time()
                activity.clock_out_date = out.date()
                activity.out_datetime = timezone.make_aware(out)
                activity.save()
            except Exception as e:
                logger.error(f"auto_punch_out error: {e}")


def _is_end_of_day_reached(target_date):
    """Only mark today's punches after 23:59 local time."""
    today = timezone.localdate()
    if target_date < today:
        return True
    if target_date > today:
        return False
    now = timezone.localtime()
    cutoff = now.replace(hour=23, minute=59, second=0, microsecond=0)
    return now >= cutoff


@scheduled_job
def mark_missing_punches():
    """
    At end of day (23:59), flag:
    - Missing punch OUT: checked in but no check-out
    - Missing punch IN: check-out without check-in on attendance rows
    - Missing punch IN: active employees on working days with no check-in
    """
    with _single_run("mark_missing_punches") as acquired:
        if acquired:
            _mark_missing_punches()


def _mark_missing_punches():
    from attendance.models import Attendance, WorkRecords
    from base.methods import get_working_days
    from employee.models import Employee
    from leave.models import LeaveRequest

    try:
        today = timezone.localdate()

        # --- Missing punch OUT ---
        missing_out = Attendance.objects.filter(
            attendance_clock_in__isnull=False,
            attendance_clock_out__isnull=True,
            missing_punch_out=False,
            attendance_date__lte=today,
        )
        for attendance in missing_out.iterator():
            if not _is_end_of_day_reached(attendance.attendance_date):
                continue
            try:
                attendance.missing_punch_out = True
                attendance.save()
            except Exception as exc:
                logger.error(
                    "mark_missing_punches missing_out id=%s: %s",
                    attendance.pk,
                    exc,
                )

        # --- Missing punch IN on attendance rows (out without in) ---
        missing_in_rows = Attendance.objects.filter(
            attendance_clock_in__isnull=True,
            attendance_clock_out__isnull=False,
            missing_punch_in=False,
            attendance_date__lte=today,
        )
        for attendance in missing_in_rows.iterator():
            if not _is_end_of_day_reached(attendance.attendance_date):
                continue
            try:
                attendance.missing_punch_in = True
                attendance.save()
            except Exception as exc:
                logger.error(
                    "mark_missing_punches missing_in row id=%s: %s",
                    attendance.pk,
                    exc,
                )

        # --- Missing punch IN: no check-in on working days (today only at EOD) ---
        # Employees are only expected to punch once they have started using
        # attendance; earlier days (and employees who never punched) are not
        # missing punches.
        first_attendance = dict(
            Attendance.objects.values("employee_id")
            .annotate(first=models.Min("attendance_date"))
            .values_list("employee_id", "first")
        )

        def _mark_no_check_in_for_date(target_date):
            if not _is_end_of_day_reached(target_date):
                return

            working_data = get_working_days(target_date, target_date)
            if target_date not in working_data["working_days_on"]:
                return

            employees = Employee.objects.filter(is_active=True).select_related(
                "employee_work_info"
            )
            for employee in employees.iterator():
                try:
                    work_info = getattr(employee, "employee_work_info", None)
                    if not work_info or not work_info.shift_id:
                        continue
                    if work_info.date_joining and work_info.date_joining > target_date:
                        continue
                    started = first_attendance.get(employee.pk)
                    if not started or started > target_date:
                        continue
                    if target_date not in get_working_days(
                        target_date, target_date, employee
                    )["working_days_on"]:
                        continue

                    on_leave = LeaveRequest.objects.filter(
                        employee_id=employee,
                        status="approved",
                        start_date__lte=target_date,
                        end_date__gte=target_date,
                    ).exists()
                    if on_leave:
                        continue

                    has_check_in = Attendance.objects.filter(
                        employee_id=employee,
                        attendance_date=target_date,
                        attendance_clock_in__isnull=False,
                    ).exists()
                    if has_check_in:
                        continue

                    work_record, _ = WorkRecords.objects.get_or_create(
                        employee_id=employee,
                        date=target_date,
                    )
                    if work_record.is_leave_record or work_record.work_record_type == "HD":
                        continue
                    if work_record.message in ("Missing punch in", "Missing punch out"):
                        continue
                    if (
                        work_record.work_record_type in ("FDP", "HDP")
                        and work_record.is_attendance_record
                        and work_record.attendance_id
                        and work_record.attendance_id.attendance_clock_in
                    ):
                        continue

                    work_record.work_record_type = "CONF"
                    work_record.message = "Missing punch in"
                    work_record.is_attendance_record = bool(work_record.attendance_id)
                    if not work_record.shift_id:
                        work_record.shift_id = work_info.shift_id
                    work_record.save()
                except Exception as exc:
                    logger.error(
                        "mark_missing_punches no_check_in emp=%s date=%s: %s",
                        employee.pk,
                        target_date,
                        exc,
                    )

        _mark_no_check_in_for_date(today)
        for days_ago in range(1, 8):
            _mark_no_check_in_for_date(today - timedelta(days=days_ago))

    except Exception as e:
        logger.error(f"mark_missing_punches error: {e}")


@scheduled_job
def create_work_record():
    from attendance.models import WorkRecords
    from employee.models import Employee

    date = datetime.date.today()
    work_records = WorkRecords.objects.filter(date=date).values_list(
        "employee_id", flat=True
    )
    employees = Employee.objects.exclude(id__in=work_records)
    records_to_create = []

    for employee in employees:
        try:
            shift_schedule = employee.get_shift_schedule()
            if shift_schedule is None:
                continue

            shift = employee.get_shift()
            record = WorkRecords(
                employee_id=employee,
                date=date,
                work_record_type="DFT",
                shift_id=shift,
                message="",
            )
            records_to_create.append(record)
        except Exception as e:
            logger.error(f"Error preparing work record for {employee}: {e}")

    if records_to_create:
        try:
            WorkRecords.objects.bulk_create(records_to_create, ignore_conflicts=True)
        except Exception as e:
            logger.error(f"Failed to bulk create work records: {e}")


register_job(create_work_record, "interval", minutes=30, misfire_grace_time=3600 * 3)
register_job(
    create_work_record,
    "cron",
    job_id="create_daily_work_record",
    hour=0,
    minute=30,
    misfire_grace_time=3600 * 9,
)
register_job(
    auto_punch_out,
    "interval",
    job_id="auto_punch_out",
    minutes=5,
    misfire_grace_time=600,
)
register_job(
    mark_missing_punches,
    "cron",
    job_id="mark_missing_punches",
    hour=23,
    minute=59,
    misfire_grace_time=3600,
)
