"""Tests for grade-based leave accrual and service-duration eligibility."""

from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock

from django.test import TestCase

from leave.services import (
    employee_job_grade,
    employee_years_of_service,
    evaluate_leave_type_conditions,
    resolve_annual_leave_days,
)
from leave.tests.helpers import _make_employee, _make_leave_type


class GradeAccrualResolveTests(TestCase):
    def test_defaults_to_leave_type_total_days(self):
        lt = SimpleNamespace(total_days=24, accrual_rules=MagicMock())
        lt.accrual_rules.all.return_value = []
        employee = _make_employee()
        self.assertEqual(resolve_annual_leave_days(lt, employee), 24)

    def test_matches_job_grade_rule(self):
        rule = SimpleNamespace(
            job_grade="L2",
            job_position_id_id=None,
            annual_days=30,
        )
        lt = SimpleNamespace(total_days=18, accrual_rules=MagicMock())
        lt.accrual_rules.all.return_value = [rule]
        work = SimpleNamespace(job_grade="L2", job_position_id_id=5)
        employee = _make_employee()
        employee.employee_work_info = work
        self.assertEqual(resolve_annual_leave_days(lt, employee), 30)

    def test_prefers_grade_and_position_over_grade_only(self):
        grade_only = SimpleNamespace(
            job_grade="L2", job_position_id_id=None, annual_days=25
        )
        both = SimpleNamespace(job_grade="L2", job_position_id_id=9, annual_days=32)
        lt = SimpleNamespace(total_days=18, accrual_rules=MagicMock())
        lt.accrual_rules.all.return_value = [grade_only, both]
        work = SimpleNamespace(job_grade="L2", job_position_id_id=9)
        employee = _make_employee()
        employee.employee_work_info = work
        self.assertEqual(resolve_annual_leave_days(lt, employee), 32)

    def test_employee_job_grade_falls_back_to_position(self):
        work = SimpleNamespace(job_grade="", job_position_id="Engineer")
        employee = _make_employee()
        employee.employee_work_info = work
        self.assertEqual(employee_job_grade(employee), "engineer")


class ServiceDurationConditionTests(TestCase):
    def test_blocks_short_service(self):
        cond = MagicMock()
        cond.condition_type = "service_duration"
        cond.value = "5"
        lt = _make_leave_type()
        lt.conditions.all.return_value = [cond]
        work = SimpleNamespace(date_joining=date(2024, 1, 1), job_grade="L1")
        employee = _make_employee()
        employee.employee_work_info = work
        is_eligible, msg = evaluate_leave_type_conditions(lt, employee)
        self.assertFalse(is_eligible)
        self.assertIn("5", str(msg))

    def test_years_of_service_helper(self):
        work = SimpleNamespace(date_joining=date(2020, 1, 1))
        employee = _make_employee()
        employee.employee_work_info = work
        years = employee_years_of_service(employee, date(2025, 1, 1))
        self.assertAlmostEqual(years, 5.0, places=1)
