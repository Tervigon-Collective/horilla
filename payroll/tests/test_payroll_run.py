"""Unit tests for payroll run lock, proration, statutory wage, CTC packs, rounding."""

from datetime import date

from django.test import SimpleTestCase

from payroll.methods.ctc_packs import SALARY_PACKS, get_salary_pack
from payroll.methods.proration import (
    eligible_for_period,
    payable_window,
    prorate_amount,
)
from payroll.methods.rounding import round_money
from payroll.methods.statutory_wage import compute_statutory_wage_base
from payroll.models.payroll_run import PayrollRun


class ProrationTests(SimpleTestCase):
    def test_prorate_calendar(self):
        self.assertEqual(prorate_amount(30000, paid_days=15, total_days=30), 15000.0)

    def test_non_proratable(self):
        self.assertEqual(
            prorate_amount(5000, paid_days=10, total_days=30, proratable=False), 5000.0
        )

    def test_join_mid_month(self):
        window = payable_window(
            date(2026, 8, 1),
            date(2026, 8, 31),
            doj=date(2026, 8, 16),
        )
        self.assertEqual(window, (date(2026, 8, 16), date(2026, 8, 31)))

    def test_exit_before_period(self):
        self.assertFalse(
            eligible_for_period(
                date(2026, 8, 1),
                date(2026, 8, 31),
                lwd=date(2026, 7, 31),
            )
        )


class StatutoryWageTests(SimpleTestCase):
    def test_50pct_add_back(self):
        result = compute_statutory_wage_base(
            basic_pay=20000,
            allowance_lines=[
                {"title": "HRA", "amount": 30000},
                {"title": "Special Allowance", "amount": 10000},
            ],
            apply_50pct_rule=True,
        )
        self.assertEqual(result["excess_allowance"], 10000.0)
        self.assertEqual(result["statutory_wage"], 30000.0)

    def test_no_excess_when_under_half(self):
        result = compute_statutory_wage_base(
            basic_pay=30000,
            allowance_lines=[
                {"title": "HRA", "amount": 18000},
                {"title": "Special Allowance", "amount": 12000},
            ],
            apply_50pct_rule=True,
        )
        self.assertEqual(result["excess_allowance"], 0.0)
        self.assertEqual(result["statutory_wage"], 30000.0)


class CtcPackTests(SimpleTestCase):
    def test_packs_a_to_d(self):
        self.assertEqual(set(SALARY_PACKS), {"A", "B", "C", "D"})
        self.assertEqual(get_salary_pack("A").gross, 60000)
        self.assertEqual(get_salary_pack("C").gross, 28200)
        self.assertEqual(get_salary_pack("D").hra, 0)


class PayrollRunTransitionTests(SimpleTestCase):
    def test_transition_matrix(self):
        run = PayrollRun(status="open")
        self.assertTrue(run.can_transition_to("calculated"))
        self.assertFalse(run.can_transition_to("locked"))
        run.status = "finance_approved"
        self.assertTrue(run.can_transition_to("locked"))
        run.status = "locked"
        self.assertTrue(run.is_immutable)
        self.assertTrue(run.can_transition_to("paid"))


class RoundingTests(SimpleTestCase):
    def test_nearest_rupee(self):
        self.assertEqual(round_money(18200.4, mode="nearest_rupee"), 18200.0)
        self.assertEqual(round_money(18200.5, mode="nearest_rupee"), 18201.0)

    def test_two_decimals(self):
        self.assertEqual(round_money(12.345, mode="two_decimals"), 12.35)
