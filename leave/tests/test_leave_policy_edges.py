"""Edge-case tests for Tervigon leave policy fixes."""

from datetime import date, timedelta
from unittest.mock import MagicMock

from django.core.exceptions import ValidationError
from django.test import TestCase


class LeavePolicyEdgeCaseTests(TestCase):
    def setUp(self):
        from horilla.testkit import make_company, make_employee
        from leave.models import AvailableLeave, LeaveType, LeaveTypeCondition

        self.company = make_company("Policy Edge Co")
        self.employee = make_employee(company=self.company, email="edge@test.horilla")
        self.LeaveType = LeaveType
        self.AvailableLeave = AvailableLeave
        self.LeaveTypeCondition = LeaveTypeCondition

    def test_once_per_employment_blocks_assign_not_request(self):
        from leave.services import evaluate_leave_type_conditions

        lt = self.LeaveType.objects.create(name="Maternity Edge", total_days=10)
        cond = self.LeaveTypeCondition.objects.create(
            condition_type="once_per_employment", value=""
        )
        lt.conditions.add(cond)
        self.AvailableLeave.objects.create(
            employee_id=self.employee, leave_type_id=lt, available_days=10
        )
        ok_req, _ = evaluate_leave_type_conditions(
            lt, self.employee, for_assignment=False
        )
        ok_asg, msg = evaluate_leave_type_conditions(
            lt, self.employee, for_assignment=True
        )
        self.assertTrue(ok_req)
        self.assertFalse(ok_asg)
        self.assertIn("once", str(msg).lower())

    def test_employment_status_condition(self):
        from leave.services import evaluate_leave_type_conditions

        lt = self.LeaveType.objects.create(name="CL Edge", total_days=12)
        cond = self.LeaveTypeCondition.objects.create(
            condition_type="employment_status", value="confirmed"
        )
        lt.conditions.add(cond)
        wi = self.employee.employee_work_info
        wi.employment_status = "probation"
        wi.save(update_fields=["employment_status"])
        ok, _ = evaluate_leave_type_conditions(lt, self.employee)
        self.assertFalse(ok)
        wi.employment_status = "confirmed"
        wi.save(update_fields=["employment_status"])
        ok, _ = evaluate_leave_type_conditions(lt, self.employee)
        self.assertTrue(ok)

    def test_monthly_accrual_fy_lapse_resets_to_zero(self):
        lt = self.LeaveType.objects.create(
            name="SL Accrue",
            total_days=12,
            carryforward_type="no carryforward",
            monthly_accrual=True,
        )
        avail = self.AvailableLeave.objects.create(
            employee_id=self.employee,
            leave_type_id=lt,
            available_days=5,
            carryforward_days=2,
            total_leave_days=7,
        )
        avail.update_carryforward()
        self.assertEqual(avail.carryforward_days, 0.0)
        self.assertEqual(avail.available_days, 0.0)

    def test_unlimited_lwp_has_sufficient_balance(self):
        from leave.services import has_sufficient_leave_balance

        lt = self.LeaveType.objects.create(
            name="LWP Edge", total_days=0, limit_leave=False, payment="unpaid"
        )
        avail = self.AvailableLeave.objects.create(
            employee_id=self.employee, leave_type_id=lt, available_days=0
        )
        self.assertTrue(has_sufficient_leave_balance(avail, 5, leave_type=lt))

    def test_months_accrued_math(self):
        from leave.management.commands.configure_tervigon_leave_policy import (
            _months_accrued_in_fy,
        )

        self.assertEqual(_months_accrued_in_fy(None, date(2026, 8, 25)), 4)
        self.assertEqual(_months_accrued_in_fy(date(2026, 6, 15), date(2026, 8, 25)), 1)
        self.assertEqual(_months_accrued_in_fy(date(2026, 8, 1), date(2026, 8, 25)), 0)
        self.assertEqual(_months_accrued_in_fy(date(2026, 4, 1), date(2026, 4, 1)), 0)
