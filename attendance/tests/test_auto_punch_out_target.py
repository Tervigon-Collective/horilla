"""
Auto punch-out closes the punch it found open, not the employee's latest one.

2026-11-20: the server was down overnight; after the reboot the job closed
yesterday's forgotten punch through clock_out(), which closes the *latest* open
punch -- today's. Today's attendance got yesterday's 18:00 check-out and 0 hours.
"""

from datetime import date, datetime, time
from unittest import mock

from django.test import TestCase
from django.utils import timezone

from attendance.models import Attendance, AttendanceActivity
from attendance.scheduler import _auto_punch_out
from base.models import EmployeeShift, EmployeeShiftDay, EmployeeShiftSchedule
from horilla.testkit.factories import make_company, make_employee

YESTERDAY, TODAY = date(2026, 11, 2), date(2026, 11, 3)


class AutoPunchOutTargetTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        company = make_company("Punch Out Ltd")
        shift = EmployeeShift.objects.create(employee_shift="Day")
        shift.company_id.add(company)
        cls.employee = make_employee(
            company=company, email="worker@punch.test", first_name="Worker", shift=shift
        )
        for day in (YESTERDAY, TODAY):
            shift_day = EmployeeShiftDay.objects.get(day=day.strftime("%A").lower())
            EmployeeShiftSchedule.objects.create(
                shift_id=shift,
                day=shift_day,
                start_time=time(10, 0),
                end_time=time(18, 0),
                minimum_working_hour="08:00",
                is_auto_punch_out_enabled=True,
                auto_punch_out_time=time(18, 0),
            )
            Attendance.objects.create(
                employee_id=cls.employee,
                shift_id=shift,
                attendance_day=shift_day,
                attendance_date=day,
                attendance_clock_in_date=day,
                attendance_clock_in=time(10, 0),
                attendance_worked_hour="00:00",
                minimum_hour="08:00",
            )
            AttendanceActivity.objects.create(
                employee_id=cls.employee,
                shift_day=shift_day,
                attendance_date=day,
                clock_in_date=day,
                clock_in=time(10, 0),
                in_datetime=timezone.make_aware(datetime.combine(day, time(10, 0))),
            )

    def test_catch_up_closes_yesterday_and_leaves_today_open(self):
        noon_today = timezone.make_aware(datetime.combine(TODAY, time(12, 0)))
        with mock.patch("django.utils.timezone.now", return_value=noon_today):
            _auto_punch_out()

        yesterday = Attendance.objects.get(employee_id=self.employee, attendance_date=YESTERDAY)
        today = Attendance.objects.get(employee_id=self.employee, attendance_date=TODAY)
        self.assertEqual(
            (yesterday.attendance_clock_out_date, yesterday.attendance_clock_out),
            (YESTERDAY, time(18, 0)),
        )
        self.assertIsNone(today.attendance_clock_out)
        self.assertIsNone(
            AttendanceActivity.objects.get(
                employee_id=self.employee, attendance_date=TODAY
            ).clock_out
        )
        self.assertEqual(
            AttendanceActivity.objects.get(
                employee_id=self.employee, attendance_date=YESTERDAY
            ).clock_out,
            time(18, 0),
        )
