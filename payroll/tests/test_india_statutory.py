"""Tests for Indian statutory payroll calculations."""

from datetime import date

from django.test import TestCase

from payroll.methods.india_statutory import (
    calculate_annual_tds,
    calculate_esi,
    calculate_india_statutory,
    calculate_pf,
    financial_year_bounds,
    professional_tax_for_state,
)


class DummySettings:
    enable_pf = True
    enable_esi = True
    enable_pt = True
    enable_tds = True
    pf_wage_ceiling = 15000.0
    pf_employee_rate = 12.0
    pf_employer_rate = 12.0
    esi_gross_ceiling = 21000.0
    esi_employee_rate = 0.75
    esi_employer_rate = 3.25
    pt_state = "MH"
    default_tds_regime = "new"
    standard_deduction_annual = 75000.0
    standard_deduction_old_regime = 50000.0
    is_enabled = True


class IndiaStatutoryTests(TestCase):
    def test_pf_eps_edli_split_at_ceiling(self):
        pf = calculate_pf(25000, DummySettings(), None)
        self.assertEqual(pf["pf_wages"], 15000)
        self.assertEqual(pf["employee"], 1800.0)
        self.assertEqual(pf["employer"], 1800.0)
        self.assertEqual(pf["eps"], 1249.5)
        self.assertEqual(pf["epf_employer"], 550.5)
        self.assertEqual(pf["edli"], 75.0)

    def test_pf_split_from_legacy_payslip(self):
        from payroll.methods.india_statutory import pf_split_from_india

        split = pf_split_from_india({"pf_wages": 15000, "pf_employer": 1800})
        self.assertEqual(split["eps"], 1249.5)
        self.assertEqual(split["epf_employer"], 550.5)
        self.assertEqual(split["edli"], 75.0)

    def test_esi_not_applicable_above_ceiling(self):
        esi = calculate_esi(25000, DummySettings(), None)
        self.assertFalse(esi["applicable"])
        self.assertEqual(esi["employee"], 0)

    def test_esi_below_ceiling(self):
        esi = calculate_esi(20000, DummySettings(), None)
        self.assertTrue(esi["applicable"])
        self.assertEqual(esi["employee"], 150.0)

    def test_esi_once_covered_above_ceiling(self):
        esi = calculate_esi(25000, DummySettings(), None, once_covered=True)
        self.assertTrue(esi["applicable"])
        # Wage ceiling applies even when coverage continues.
        self.assertEqual(esi["employee"], 157.5)

    def test_professional_tax_maharashtra(self):
        self.assertEqual(professional_tax_for_state("MH", 7000), 0)
        self.assertEqual(professional_tax_for_state("MH", 9000), 175)
        self.assertEqual(professional_tax_for_state("MH", 15000), 200)
        self.assertEqual(
            professional_tax_for_state("MH", 15000, for_date=date(2026, 2, 28)),
            300,
        )

    def test_old_regime_80c_includes_pf_without_double_count(self):
        result = calculate_annual_tds(
            1_200_000,
            "old",
            standard_deduction=50000,
            section_80c=150000,
            pf_employee_annual=21600,
        )
        # Combined 80C is capped at 1.5L (declared 80C already at limit).
        uncapped = calculate_annual_tds(
            1_200_000,
            "old",
            standard_deduction=50000,
            section_80c=150000,
            pf_employee_annual=0,
        )
        self.assertEqual(result["taxable_income"], uncapped["taxable_income"])

    def test_new_regime_no_tax_low_income(self):
        result = calculate_annual_tds(
            600000, "new", standard_deduction=75000
        )
        self.assertEqual(result["annual_tax"], 0)

    def test_financial_year_bounds(self):
        start, end, sy, ey = financial_year_bounds(date(2026, 1, 15))
        self.assertEqual(sy, 2025)
        self.assertEqual(start, date(2025, 4, 1))
        self.assertEqual(end, date(2026, 3, 31))

    def test_calculate_india_disabled_without_settings(self):
        class Emp:
            def get_company(self):
                return None

        result = calculate_india_statutory(
            Emp(), 20000, 25000, date(2026, 1, 1), date(2026, 1, 31)
        )
        self.assertFalse(result["enabled"])

    def test_traces_24q_uses_section_192_and_challan_fields(self):
        from payroll.methods.india_statutory import generate_traces_text, generate_traces_zip

        class Emp:
            def get_full_name(self):
                return "Test | Employee"

        data = {
            "period_start": date(2026, 4, 1),
            "period_end": date(2026, 6, 30),
            "rows": [
                {
                    "employee": Emp(),
                    "pan": "ABCDE1234F",
                    "gross": 100000,
                    "tds": 5000,
                }
            ],
            "totals": {"gross": 100000, "tds": 5000},
        }
        text = generate_traces_text(
            data,
            tan="DELH12345A",
            bsr_code="1234567",
            challan_serial="00123",
            deposit_date="2026-07-07",
            company_name="Acme",
        )
        self.assertIn("|192|", text)
        self.assertNotIn("194P", text)
        self.assertIn("CD|1|192|200|1234567|07072026|00123|", text)
        self.assertIn("TEST   EMPLOYEE", text)
        blob = generate_traces_zip(data, tan="DELH12345A", filename_base="t")
        self.assertGreater(len(blob), 40)
        self.assertEqual(blob[:2], b"PK")

    def test_lwf_maharashtra_june_and_skip_other_months(self):
        from payroll.methods.india_statutory import calculate_lwf

        class Emp:
            employee_work_info = None

        settings = DummySettings()
        settings.enable_lwf = True
        settings.pt_state = "MH"
        june = calculate_lwf(25000, settings, None, Emp(), date(2026, 6, 30))
        self.assertTrue(june["applicable"])
        self.assertEqual(june["employee"], 25.0)
        self.assertEqual(june["employer"], 75.0)
        jan = calculate_lwf(25000, settings, None, Emp(), date(2026, 1, 31))
        self.assertFalse(jan["applicable"])
        self.assertEqual(jan["employee"], 0)

    def test_bonus_provision_capped_and_ineligible_above_wage(self):
        from payroll.methods.india_statutory import calculate_bonus_provision

        settings = DummySettings()
        settings.enable_bonus = True
        ok = calculate_bonus_provision(15000, 20000, settings, None)
        self.assertTrue(ok["eligible"])
        self.assertEqual(ok["bonus_wages"], 7000)
        self.assertAlmostEqual(ok["provision"], round(7000 * 8.33 / 100, 2))
        high = calculate_bonus_provision(25000, 25000, settings, None)
        self.assertFalse(high["eligible"])
        self.assertEqual(high["provision"], 0)

    def test_gratuity_five_years_and_six_month_roundup(self):
        from payroll.methods.india_statutory import calculate_gratuity

        join = date(2020, 1, 1)
        short = calculate_gratuity(26000, join, date(2024, 6, 1))
        self.assertFalse(short["eligible"])
        self.assertEqual(short["amount"], 0)
        eligible = calculate_gratuity(26000, join, date(2025, 1, 1))
        self.assertTrue(eligible["eligible"])
        self.assertEqual(eligible["years"], 5)
        self.assertAlmostEqual(eligible["amount"], round((15 / 26) * 5 * 26000, 2))
        rounded = calculate_gratuity(26000, join, date(2025, 8, 1))
        self.assertEqual(rounded["years"], 6)

    def test_ctc_split_and_increment_math(self):
        from payroll.methods.ctc_wizard import split_monthly_ctc

        split = split_monthly_ctc(100000, metro=True)
        self.assertEqual(split.basic, 40000)
        self.assertEqual(split.hra, 20000)
        self.assertEqual(split.special, 40000)
        old, new = 100000.0, 110000.0
        pct = round(((new - old) / old) * 100.0, 2)
        self.assertEqual(pct, 10.0)

    def test_salary_hold_status_query(self):
        from types import SimpleNamespace
        from unittest.mock import MagicMock, patch

        from payroll.methods.ctc_wizard import is_salary_on_hold

        employee = SimpleNamespace(id=1)
        with patch("payroll.models.salary_revision.SalaryHold.objects") as objects:
            objects.filter.return_value.exists.return_value = True
            self.assertTrue(is_salary_on_hold(employee))
            objects.filter.assert_called_with(
                employee_id=employee, is_active=True, released_on__isnull=True
            )
            objects.filter.return_value.exists.return_value = False
            self.assertFalse(is_salary_on_hold(employee))

    def test_pay_revision_arrears_creates_one_time_allowance(self):
        from datetime import date
        from types import SimpleNamespace
        from unittest.mock import MagicMock, patch

        from payroll.methods.ctc_wizard import pay_revision_arrears

        employee = SimpleNamespace(id=9)
        allowance = MagicMock()
        allowance.amount = 15000.0
        allowance.specific_employees = MagicMock()
        revision = SimpleNamespace(
            arrears_paid=False,
            arrears_amount=15000.0,
            effective_date=date(2026, 4, 1),
            employee_id=employee,
        )
        revision.save = MagicMock()
        with patch("payroll.models.models.Allowance.objects") as objects:
            objects.create.return_value = allowance
            result = pay_revision_arrears(revision, payment_date=date(2026, 8, 31))
        self.assertIs(result, allowance)
        objects.create.assert_called_once()
        kwargs = objects.create.call_args.kwargs
        self.assertEqual(kwargs["amount"], 15000.0)
        self.assertEqual(kwargs["one_time_date"], date(2026, 8, 31))
        self.assertTrue(kwargs["is_fixed"])
        allowance.specific_employees.add.assert_called_once_with(employee)
        self.assertTrue(revision.arrears_paid)
        self.assertEqual(revision.arrears_paid_on, date(2026, 8, 31))
        revision.save.assert_called_once()
        with self.assertRaises(ValueError):
            pay_revision_arrears(revision, payment_date=date(2026, 8, 31))
