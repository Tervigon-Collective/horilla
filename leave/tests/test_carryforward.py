"""Tests for AvailableLeave carryforward / pre_save_processing and expiry."""

from datetime import date, timedelta

from django.test import TestCase


class AvailableLeaveCarryforwardTests(TestCase):
    def setUp(self):
        from horilla.testkit import make_company, make_employee
        from leave.models import AvailableLeave, LeaveType

        company = make_company("Leave Carry Co")
        self.employee = make_employee(company=company, email="carry@test.horilla")
        self.LeaveType = LeaveType
        self.AvailableLeave = AvailableLeave

    def test_carryforward_capped_at_max(self):
        lt = self.LeaveType.objects.create(
            name="Annual Carry Cap",
            total_days=12,
            carryforward_type="carryforward",
            carryforward_max=5,
        )
        avail = self.AvailableLeave.objects.create(
            employee_id=self.employee,
            leave_type_id=lt,
            available_days=10,
            carryforward_days=0,
            total_leave_days=10,
        )
        avail.total_leave_days = 10
        avail.update_carryforward()
        self.assertEqual(avail.carryforward_days, 5)
        self.assertEqual(avail.available_days, 12)

    def test_no_carryforward_zeroes_cf_on_reset(self):
        """update_carryforward must clear CF for 'no carryforward' types, not preserve old value."""
        lt = self.LeaveType.objects.create(
            name="Sick No Carry",
            total_days=8,
            carryforward_type="no carryforward",
        )
        avail = self.AvailableLeave.objects.create(
            employee_id=self.employee,
            leave_type_id=lt,
            available_days=2,
            carryforward_days=4,  # stale CF that should be wiped
            total_leave_days=6,
        )
        avail.update_carryforward()
        self.assertEqual(avail.carryforward_days, 0.0, "CF must be zeroed for no-CF types")
        self.assertEqual(avail.available_days, 8)

    def test_pre_save_processing_totals(self):
        lt = self.LeaveType.objects.create(
            name="Casual PreSave",
            total_days=10,
            carryforward_type="no carryforward",
            reset=False,
        )
        avail = self.AvailableLeave(
            employee_id=self.employee,
            leave_type_id=lt,
            available_days=10,
            carryforward_days=-2,
        )
        avail.pre_save_processing()
        self.assertEqual(avail.total_leave_days, 8.0)
        self.assertEqual(avail.carryforward_days, 0.0)

    def test_set_expired_date_only_zeroes_cf_not_available(self):
        """Expiry must zero carryforward_days but leave available_days untouched."""
        lt = self.LeaveType.objects.create(
            name="CF Expire Leave",
            total_days=10,
            carryforward_type="carryforward expire",
            carryforward_expire_in=1,
            carryforward_expire_period="month",
        )
        avail = self.AvailableLeave.objects.create(
            employee_id=self.employee,
            leave_type_id=lt,
            available_days=8,
            carryforward_days=3,
            total_leave_days=11,
        )
        today = date.today()
        avail.set_expired_date(available_leave=avail, assigned_date=today)
        self.assertEqual(avail.carryforward_days, 0, "CF should be zeroed on expiry")
        self.assertEqual(avail.available_days, 8, "available_days must NOT be reset by expiry")

    def test_expire_carryforward_days_helper(self):
        from leave.services import expire_carryforward_days

        lt = self.LeaveType.objects.create(
            name="CF Expire Helper",
            total_days=10,
            carryforward_type="carryforward expire",
            carryforward_expire_in=1,
            carryforward_expire_period="month",
        )
        yesterday = date.today() - timedelta(days=1)
        avail = self.AvailableLeave.objects.create(
            employee_id=self.employee,
            leave_type_id=lt,
            available_days=7,
            carryforward_days=5,
            total_leave_days=12,
            expired_date=yesterday,
        )
        result = expire_carryforward_days(avail, today_date=date.today())
        self.assertTrue(result)
        avail.refresh_from_db()
        self.assertEqual(avail.carryforward_days, 0)
        self.assertEqual(avail.available_days, 7, "current-year balance must survive CF expiry")
        self.assertIsNone(avail.expired_date)

    def test_expire_all_carryforward_balances(self):
        from leave.services import expire_all_carryforward_balances

        lt = self.LeaveType.objects.create(
            name="Bulk Expire",
            total_days=10,
            carryforward_type="carryforward expire",
            carryforward_expire_in=1,
            carryforward_expire_period="month",
        )
        past_date = date.today() - timedelta(days=2)
        avail = self.AvailableLeave.objects.create(
            employee_id=self.employee,
            leave_type_id=lt,
            available_days=9,
            carryforward_days=4,
            total_leave_days=13,
            expired_date=past_date,
        )
        count = expire_all_carryforward_balances(today_date=date.today())
        self.assertGreaterEqual(count, 1)
        avail.refresh_from_db()
        self.assertEqual(avail.carryforward_days, 0)
        self.assertEqual(avail.available_days, 9)
