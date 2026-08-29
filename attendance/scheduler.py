import datetime
import sys
from datetime import timedelta

import pytz
from horilla.db import SafeBackgroundScheduler
from django.conf import settings
from django.db import models
from django.utils import timezone

from base.backends import logger


def auto_punch_out():
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
                attendance_clock_out=None,
                attendance_clock_out_date=None,
                shift_id=shift_schedule.shift_id,
                attendance_day=shift_schedule.day,
                attendance_date=activity.attendance_date,
            ).first()

            if attendance:
                date = activity.attendance_date
                if (
                    shift_schedule.is_night_shift
                    and shift_schedule.start_time
                    and shift_schedule.end_time
                    and shift_schedule.start_time > shift_schedule.end_time
                ):
                    date += timedelta(days=1)

                combined_datetime = timezone.make_aware(
                    datetime.datetime.combine(date, shift_schedule.auto_punch_out_time)
                )

                if combined_datetime < timezone.now():
                    try:
                        clock_out(
                            Request(
                                user=attendance.employee_id.employee_user_id,
                                date=date,
                                time=shift_schedule.auto_punch_out_time,
                                datetime=combined_datetime,
                            )
                        )
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


def mark_missing_punches():
    """
    At end of day (23:59), flag:
    - Missing punch OUT: checked in but no check-out
    - Missing punch IN: check-out without check-in on attendance rows
    - Missing punch IN: active employees on working days with no check-in
    """
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


if not any(
    cmd in sys.argv
    for cmd in ["makemigrations", "migrate", "compilemessages", "flush", "shell"]
):
    """
    Initializes and starts background tasks using APScheduler when the server is running.
    """
    scheduler = SafeBackgroundScheduler(timezone=pytz.timezone(settings.TIME_ZONE))

    scheduler.add_job(
        create_work_record, "interval", minutes=30, misfire_grace_time=3600 * 3
    )
    scheduler.add_job(
        create_work_record,
        "cron",
        hour=0,
        minute=30,
        misfire_grace_time=3600 * 9,
        id="create_daily_work_record",
        replace_existing=True,
    )
    scheduler.add_job(
        auto_punch_out,
        "interval",
        minutes=5,
        misfire_grace_time=600,
        id="auto_punch_out",
        replace_existing=True,
    )
    scheduler.add_job(
        mark_missing_punches,
        "cron",
        hour=23,
        minute=59,
        misfire_grace_time=3600,
        id="mark_missing_punches",
        replace_existing=True,
    )

    scheduler.start()
