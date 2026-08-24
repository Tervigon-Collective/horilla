"""Unit tests for Full & Final settlement math."""

from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock

from django.test import TestCase

from offboarding.settlement import (
    compute_fnf_totals,
    loan_outstanding_amount,
    _years_of_service,
)


class FnFMathTests(TestCase):
    def test_years_of_service(self):
        self.assertEqual(_years_of_service(None, date.today()), 0.0)
        years = _years_of_service(date(2020, 1, 1), date(2025, 1, 1))
        self.assertAlmostEqual(years, 5.0, places=1)

    def test_net_payable_subtracts_recoveries(self):
        totals = compute_fnf_totals(
            gratuity=100000,
            bonus_unpaid=5000,
            leave_encashment=10000,
            notice_period_pay=0,
            other_additions=2000,
            loan_recovery=15000,
            other_deductions=1000,
        )
        self.assertEqual(totals["total_earnings"], 117000)
        self.assertEqual(totals["total_recoveries"], 16000)
        self.assertEqual(totals["net_payable"], 101000)
        self.assertEqual(totals["total_settlement"], 101000)

    def test_loan_outstanding_partially_paid(self):
        loan = SimpleNamespace(
            settled=False,
            installments=10,
            loan_amount=10000.0,
            installment_paid=MagicMock(return_value=4),
        )
        self.assertEqual(loan_outstanding_amount(loan), 6000.0)
        loan.settled = True
        self.assertEqual(loan_outstanding_amount(loan), 0.0)
