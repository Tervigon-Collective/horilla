"""
Indian statutory payroll calculation engine (PF, ESI, PT, TDS).

Rates and slabs follow common Indian payroll practice (FY 2025-26 baseline).
Configure per company via IndiaStatutorySettings.
"""

from __future__ import annotations

import calendar
import csv
import io
import zipfile
from datetime import date, datetime
from typing import Any

from django.apps import apps

# New regime slabs (FY 2025-26 style) — (upper_limit, rate%)
NEW_REGIME_SLABS = [
    (400_000, 0),
    (800_000, 5),
    (1_200_000, 10),
    (1_600_000, 15),
    (2_000_000, 20),
    (2_400_000, 25),
    (float("inf"), 30),
]

OLD_REGIME_SLABS = [
    (250_000, 0),
    (500_000, 5),
    (1_000_000, 20),
    (float("inf"), 30),
]

SECTION_80C_LIMIT = 150_000
REBATE_87A_NEW_LIMIT = 700_000
REBATE_87A_OLD_LIMIT = 500_000
REBATE_87A_MAX = 25_000

# EPFO defaults (employer 12% splits into EPS 8.33% + EPF remainder)
EPS_RATE = 8.33
EDLI_RATE = 0.50
EPS_WAGE_CEILING = 15_000.0


def financial_year_bounds(for_date: date) -> tuple[date, date, int, int]:
    """Return (fy_start, fy_end, start_year, end_year) for Indian FY Apr–Mar."""
    if for_date.month >= 4:
        start_year = for_date.year
    else:
        start_year = for_date.year - 1
    end_year = start_year + 1
    fy_start = date(start_year, 4, 1)
    fy_end = date(end_year, 3, 31)
    return fy_start, fy_end, start_year, end_year


def _round2(value: float) -> float:
    return round(float(value or 0), 2)


def _setting(settings, *names, default=None):
    """Read a settings attribute, accepting DummySettings or model field names."""
    for name in names:
        if hasattr(settings, name):
            return getattr(settings, name)
    return default


def _tax_from_slabs(taxable_income: float, slabs: list[tuple[float, float]]) -> float:
    if taxable_income <= 0:
        return 0.0
    tax = 0.0
    lower = 0.0
    for upper, rate in slabs:
        if taxable_income <= lower:
            break
        band = min(taxable_income, upper) - lower
        if band > 0:
            tax += band * rate / 100.0
        lower = upper
    return tax


def calculate_annual_tds(
    annual_gross: float,
    regime: str,
    standard_deduction: float,
    section_80c: float = 0,
    section_80d: float = 0,
    other_vi_a: float = 0,
    pf_employee_annual: float = 0,
) -> dict[str, Any]:
    """Compute annual income tax before monthly spread."""
    annual_gross = max(0.0, annual_gross)
    if regime == "old":
        # Employee PF is part of 80C; do not add it on top of declared 80C.
        section_80c_total = min(
            float(section_80c or 0) + float(pf_employee_annual or 0),
            SECTION_80C_LIMIT,
        )
        deductions = section_80c_total + section_80d + other_vi_a
        taxable = max(
            0.0, annual_gross - standard_deduction - deductions
        )
        tax = _tax_from_slabs(taxable, OLD_REGIME_SLABS)
        if taxable <= REBATE_87A_OLD_LIMIT:
            tax = max(0.0, tax - min(tax, REBATE_87A_MAX))
    else:
        taxable = max(0.0, annual_gross - standard_deduction)
        tax = _tax_from_slabs(taxable, NEW_REGIME_SLABS)
        if taxable <= REBATE_87A_NEW_LIMIT:
            tax = max(0.0, tax - min(tax, REBATE_87A_MAX))

    # Health & education cess 4%
    cess = tax * 0.04
    total = _round2(tax + cess)
    return {
        "annual_tax": total,
        "taxable_income": _round2(taxable),
        "base_tax": _round2(tax),
        "cess": _round2(cess),
        "regime": regime,
    }


def professional_tax_for_state(
    state_code: str, monthly_gross: float, for_date: date | None = None
) -> float:
    """Monthly professional tax by state (simplified common slabs)."""
    if monthly_gross <= 0:
        return 0.0
    state = (state_code or "DL").upper()
    if state == "DL":
        return 0.0
    if state == "MH":
        if monthly_gross <= 7500:
            return 0.0
        if monthly_gross <= 10000:
            return 175.0
        # Maharashtra: remaining annual PT is collected in February (₹300 vs ₹200).
        if for_date and for_date.month == 2:
            return 300.0
        return 200.0
    if state == "KA":
        return 200.0 if monthly_gross >= 15000 else 0.0
    if state == "TS":
        if monthly_gross < 15000:
            return 0.0
        if monthly_gross <= 20000:
            return 150.0
        return 200.0
    if state == "TN":
        if monthly_gross <= 21000:
            return 0.0
        if monthly_gross <= 30000:
            return 135.0
        if monthly_gross <= 45000:
            return 315.0
        return 690.0
    if state == "WB":
        if monthly_gross <= 10000:
            return 0.0
        if monthly_gross <= 15000:
            return 110.0
        if monthly_gross <= 25000:
            return 130.0
        if monthly_gross <= 40000:
            return 150.0
        return 200.0
    if state in ("GJ", "AP", "KL"):
        if monthly_gross < 12000:
            return 0.0
        return 200.0
    return 200.0 if monthly_gross >= 15000 else 0.0


# LWF: (employee, employer, contribution months, wage ceiling; 0 = no ceiling)
# Amounts follow common payroll practice (half-yearly vs monthly by state).
LWF_BY_STATE = {
    "MH": (25.0, 75.0, (6, 12), 0),
    "KA": (20.0, 40.0, tuple(range(1, 13)), 0),
    "TN": (20.0, 40.0, tuple(range(1, 13)), 0),
    "KL": (20.0, 20.0, tuple(range(1, 13)), 0),
    "WB": (3.0, 15.0, tuple(range(1, 13)), 0),
    "GJ": (6.0, 12.0, tuple(range(1, 13)), 0),
    "HR": (31.0, 62.0, (6, 12), 0),
    "PB": (5.0, 20.0, tuple(range(1, 13)), 0),
    "DL": (0.75, 2.25, tuple(range(1, 13)), 0),
    "UP": (3.0, 6.0, (6, 12), 0),
    "MP": (10.0, 30.0, (6, 12), 0),
    "CH": (5.0, 20.0, tuple(range(1, 13)), 0),
    "OR": (10.0, 20.0, tuple(range(1, 13)), 0),
    "TS": (5.0, 10.0, tuple(range(1, 13)), 0),
    "AP": (5.0, 10.0, tuple(range(1, 13)), 0),
}

BONUS_ELIGIBILITY_CEILING = 21_000.0
BONUS_CALC_CEILING = 7_000.0
BONUS_MIN_RATE = 8.33
GRATUITY_MAX = 2_000_000.0


def calculate_lwf(
    monthly_gross: float,
    settings,
    profile,
    employee,
    for_date: date | None = None,
) -> dict[str, Any]:
    """State Labour Welfare Fund employee + employer contribution for the pay month."""
    empty = {"employee": 0.0, "employer": 0.0, "applicable": False, "state": ""}
    if not _setting(settings, "enable_lwf", default=False):
        return empty
    if profile and not getattr(profile, "lwf_applicable", True):
        return empty
    for_date = for_date or date.today()
    state = resolve_pt_state(settings, employee)
    spec = LWF_BY_STATE.get(state)
    if not spec:
        return {**empty, "state": state}
    ee, er, months, ceiling = spec
    if for_date.month not in months:
        return {**empty, "state": state}
    if ceiling and monthly_gross > ceiling:
        return {**empty, "state": state}
    return {
        "employee": _round2(ee),
        "employer": _round2(er),
        "applicable": True,
        "state": state,
    }


def calculate_bonus_provision(
    basic_pay: float,
    gross_pay: float,
    settings,
    profile,
) -> dict[str, Any]:
    """Monthly Payment of Bonus Act provision (minimum 8.33% on capped wages)."""
    empty = {
        "provision": 0.0,
        "eligible": False,
        "bonus_wages": 0.0,
        "rate": BONUS_MIN_RATE,
    }
    if not _setting(settings, "enable_bonus", default=False):
        return empty
    if profile and not getattr(profile, "bonus_applicable", True):
        return empty
    if float(gross_pay or 0) > BONUS_ELIGIBILITY_CEILING:
        return empty
    bonus_wages = min(max(0.0, float(basic_pay or 0)), BONUS_CALC_CEILING)
    if bonus_wages <= 0:
        bonus_wages = min(max(0.0, float(gross_pay or 0)), BONUS_CALC_CEILING)
    provision = _round2(bonus_wages * BONUS_MIN_RATE / 100.0)
    return {
        "provision": provision,
        "eligible": provision > 0,
        "bonus_wages": _round2(bonus_wages),
        "rate": BONUS_MIN_RATE,
    }


def gratuity_completed_years(join_date: date | None, as_of: date) -> int:
    """Completed years under the Gratuity Act (6+ months rounds up)."""
    if not join_date or as_of < join_date:
        return 0
    days = (as_of - join_date).days
    years = days // 365
    if (days % 365) >= 182:
        years += 1
    return years


def calculate_gratuity(
    basic_pay: float,
    join_date: date | None,
    as_of: date | None = None,
    *,
    applicable: bool = True,
    death_or_disability: bool = False,
) -> dict[str, Any]:
    """Payment of Gratuity Act: last drawn basic × 15/26 × completed years, cap ₹20 lakh."""
    as_of = as_of or date.today()
    years = gratuity_completed_years(join_date, as_of)
    service_days = (as_of - join_date).days if join_date and as_of >= join_date else 0
    eligible = bool(applicable) and (
        death_or_disability or service_days >= 5 * 365
    ) and basic_pay > 0
    amount = 0.0
    if eligible and years > 0:
        amount = min(GRATUITY_MAX, _round2((15.0 / 26.0) * years * float(basic_pay)))
    return {
        "years": years,
        "eligible": eligible,
        "amount": amount,
        "capped": amount >= GRATUITY_MAX and amount > 0,
        "join_date": join_date,
        "as_of": as_of,
        "basic_pay": _round2(basic_pay),
    }


def calculate_bonus_fnf(
    basic_pay: float,
    gross_pay: float,
    join_date: date | None,
    last_working_day: date,
) -> dict[str, Any]:
    """Unpaid minimum bonus for months worked in the current FY (F&F estimate)."""
    if float(gross_pay or 0) > BONUS_ELIGIBILITY_CEILING:
        return {"amount": 0.0, "months": 0, "eligible": False}
    fy_start, _fy_end, _sy, _ey = financial_year_bounds(last_working_day)
    start = fy_start
    if join_date and join_date > fy_start:
        start = join_date
    if last_working_day < start:
        return {"amount": 0.0, "months": 0, "eligible": False}
    months = (
        (last_working_day.year - start.year) * 12
        + last_working_day.month
        - start.month
        + 1
    )
    months = max(0, min(12, months))
    bonus_wages = min(max(0.0, float(basic_pay or 0)), BONUS_CALC_CEILING)
    amount = _round2(bonus_wages * BONUS_MIN_RATE / 100.0 * months)
    return {
        "amount": amount,
        "months": months,
        "eligible": amount > 0,
        "bonus_wages": _round2(bonus_wages),
    }


def get_india_settings(employee):
    """Resolve IndiaStatutorySettings for employee's company."""
    from payroll.models.india_statutory import IndiaStatutorySettings

    company = employee.get_company()
    if not company:
        return None
    return IndiaStatutorySettings.objects.filter(
        company_id=company, is_enabled=True
    ).first()


def get_employee_statutory_profile(employee):
    from payroll.models.india_statutory import EmployeeStatutoryProfile

    return EmployeeStatutoryProfile.objects.filter(employee_id=employee).first()


def _state_name_to_code(state_value: str) -> str | None:
    """Map full state name or code to INDIAN_STATES code."""
    from payroll.models.india_statutory import INDIAN_STATES

    if not state_value:
        return None
    raw = str(state_value).strip()
    upper = raw.upper()
    codes = {code for code, _ in INDIAN_STATES}
    if upper in codes:
        return upper
    for code, label in INDIAN_STATES:
        if raw.lower() == str(label).lower():
            return code
    return None


def resolve_pt_state(settings, employee) -> str:
    """Use employee work state when set, else company PT state."""
    work_info = getattr(employee, "employee_work_info", None)
    work_state = getattr(work_info, "state", None) if work_info else None
    mapped = _state_name_to_code(work_state) if work_state else None
    if mapped:
        return mapped
    return (settings.pt_state or "DL").upper()


def _pf_wages(basic_pay: float, settings, profile=None) -> float:
    wage = max(0.0, float(basic_pay or 0))
    if profile and getattr(profile, "contribute_pf_on_actual_wage", False):
        return wage
    ceiling = float(
        _setting(settings, "pf_wage_ceiling", "pf_wage_ceiling", default=15000) or 15000
    )
    return min(wage, ceiling)


def _empty_pf() -> dict[str, float]:
    return {
        "pf_wages": 0.0,
        "employee": 0.0,
        "employer": 0.0,
        "vpf": 0.0,
        "eps": 0.0,
        "epf_employer": 0.0,
        "edli": 0.0,
    }


def calculate_pf(basic_pay: float, settings, profile) -> dict[str, float]:
    """Employee 12% EPF; employer 12% split into EPS (8.33%) + EPF remainder; EDLI extra."""
    if not _setting(settings, "enable_pf", "enable_pf", default=True) or (
        profile and not profile.pf_applicable
    ):
        return _empty_pf()
    pf_wages = _pf_wages(basic_pay, settings, profile)
    ee_rate = float(_setting(settings, "pf_employee_rate", "pf_employee_rate", default=12) or 12)
    er_rate = float(_setting(settings, "pf_employer_rate", "pf_employer_rate", default=12) or 12)
    employee_pf = pf_wages * ee_rate / 100.0
    employer_pf = pf_wages * er_rate / 100.0
    eps_wages = min(pf_wages, EPS_WAGE_CEILING)
    eps = min(employer_pf, eps_wages * EPS_RATE / 100.0)
    epf_employer = max(0.0, employer_pf - eps)
    edli = eps_wages * EDLI_RATE / 100.0
    vpf = 0.0
    if profile and profile.vpf_rate:
        vpf = pf_wages * profile.vpf_rate / 100.0
    return {
        "pf_wages": _round2(pf_wages),
        "employee": _round2(employee_pf + vpf),
        "employer": _round2(employer_pf),
        "vpf": _round2(vpf),
        "eps": _round2(eps),
        "epf_employer": _round2(epf_employer),
        "edli": _round2(edli),
    }


def pf_split_from_india(india: dict | None) -> dict[str, float]:
    """Read stored EPS/EDLI, or derive from employer PF on older payslips."""
    india = india or {}
    pf_wages = float(india.get("pf_wages") or 0)
    pf_employer = float(india.get("pf_employer") or 0)
    eps = india.get("eps")
    epf_employer = india.get("epf_employer")
    edli = india.get("edli")
    if eps is None or epf_employer is None:
        eps_wages = min(pf_wages, EPS_WAGE_CEILING)
        eps = min(pf_employer, _round2(eps_wages * EPS_RATE / 100.0))
        epf_employer = max(0.0, pf_employer - float(eps))
    if edli is None:
        edli = min(pf_wages, EPS_WAGE_CEILING) * EDLI_RATE / 100.0 if pf_wages else 0.0
    return {
        "eps": _round2(float(eps or 0)),
        "epf_employer": _round2(float(epf_employer or 0)),
        "edli": _round2(float(edli or 0)),
    }


def _esi_contribution_period(for_date: date) -> tuple[date, date]:
    """ESIC contribution periods: Apr–Sep and Oct–Mar."""
    if 4 <= for_date.month <= 9:
        return date(for_date.year, 4, 1), date(for_date.year, 9, 30)
    if for_date.month >= 10:
        return date(for_date.year, 10, 1), date(for_date.year + 1, 3, 31)
    return date(for_date.year - 1, 10, 1), date(for_date.year, 3, 31)


def _esi_already_covered(employee, period_start: date) -> bool:
    """True if ESI applied on an earlier slip in the same contribution period."""
    if not getattr(employee, "pk", None):
        return False
    from payroll.models.models import Payslip

    start, end = _esi_contribution_period(period_start)
    slips = Payslip.objects.filter(
        employee_id=employee,
        start_date__lte=end,
        end_date__gte=start,
        start_date__lt=period_start,
        status__in=["confirmed", "paid"],
    )
    for slip in slips:
        india = (slip.pay_head_data or {}).get("india_statutory") or {}
        if india.get("esi_applicable") or float(india.get("esi_employee") or 0) > 0:
            return True
    return False


def calculate_esi(
    gross_pay: float,
    settings,
    profile,
    once_covered: bool = False,
) -> dict[str, float]:
    if not _setting(settings, "enable_esi", "enable_esi", default=True) or (
        profile and not profile.esi_applicable
    ):
        return {"employee": 0, "employer": 0, "applicable": False}
    ceiling = float(_setting(settings, "esi_gross_ceiling", "esi_gross_ceiling", default=21000) or 21000)
    if gross_pay > ceiling and not once_covered:
        return {"employee": 0, "employer": 0, "applicable": False}
    # ESIC wage ceiling caps the contribution base even when coverage continues
    # for once-covered employees.
    contribution_base = min(float(gross_pay or 0), ceiling)
    ee_rate = float(_setting(settings, "esi_employee_rate", "esi_employee_rate", default=0.75) or 0.75)
    er_rate = float(_setting(settings, "esi_employer_rate", "esi_employer_rate", default=3.25) or 3.25)
    return {
        "employee": _round2(contribution_base * ee_rate / 100.0),
        "employer": _round2(contribution_base * er_rate / 100.0),
        "applicable": True,
    }


def calculate_pt(
    gross_pay: float,
    settings,
    profile,
    employee,
    for_date: date | None = None,
) -> float:
    if not _setting(settings, "enable_pt", "enable_pt", default=True) or (
        profile and not profile.pt_applicable
    ):
        return 0.0
    state = resolve_pt_state(settings, employee)
    return _round2(professional_tax_for_state(state, gross_pay, for_date=for_date))


def _ytd_tds_from_payslips(employee, fy_start: date, before_date: date) -> float:
    from payroll.models.models import Payslip

    slips = Payslip.objects.filter(
        employee_id=employee,
        start_date__lt=before_date,
        end_date__gte=fy_start,
        status__in=["confirmed", "paid"],
    )
    total = 0.0
    for slip in slips:
        data = slip.pay_head_data or {}
        india = data.get("india_statutory") or {}
        total += float(india.get("tds") or data.get("federal_tax") or 0)
    return total


def calculate_monthly_tds(
    employee,
    gross_pay: float,
    period_start: date,
    period_end: date,
    settings,
    profile,
    pf_employee: float,
) -> dict[str, Any]:
    if not _setting(settings, "enable_tds", "enable_tds", default=True) or (
        profile and not profile.tds_applicable
    ):
        return {
            "tds": 0.0,
            "annual_tax": 0.0,
            "regime": _setting(
                settings, "default_tds_regime", "default_tds_regime", default="new"
            ),
            "remaining_months": 0,
            "remaining_tax": 0.0,
            "ytd_tds": 0.0,
            "previous_employer_tds": 0.0,
            "previous_employer_income": 0.0,
            "other_income": 0.0,
            "proof_status": getattr(profile, "proof_submission_status", None)
            if profile
            else None,
        }

    fy_start, fy_end, fy_sy, _fy_ey = financial_year_bounds(period_end)

    from payroll.models.models import Payslip

    ytd_gross = 0.0
    for slip in Payslip.objects.filter(
        employee_id=employee,
        start_date__lt=period_start,
        end_date__gte=fy_start,
        status__in=["confirmed", "paid"],
    ):
        ytd_gross += float(slip.gross_pay or 0)
    ytd_gross += float(gross_pay or 0)

    prev_income = float(getattr(profile, "previous_employer_income", 0) or 0) if profile else 0.0
    prev_tds = float(getattr(profile, "previous_employer_tds", 0) or 0) if profile else 0.0
    other_income = float(getattr(profile, "other_income_annual", 0) or 0) if profile else 0.0

    # Project annual current-employer income from YTD run-rate
    elapsed_days = (period_end - fy_start).days + 1
    days_in_fy = (fy_end - fy_start).days + 1
    if elapsed_days > 0 and ytd_gross > 0:
        annual_current = (ytd_gross / elapsed_days) * days_in_fy
    else:
        annual_current = float(gross_pay or 0) * 12

    annual_gross = annual_current + prev_income + other_income

    regime = _setting(settings, "default_tds_regime", "default_tds_regime", default="new")
    if profile and profile.tds_regime:
        regime = profile.tds_regime

    # Use declared deductions only when proofs verified/submitted; else conservative 0
    # for old-regime Chapter VI-A beyond standard deduction (except always-count PF).
    proof = getattr(profile, "proof_submission_status", "pending") if profile else "pending"
    allow_declared = proof in ("submitted", "verified")
    section_80c = float(profile.section_80c_annual or 0) if profile and allow_declared else 0.0
    section_80d = float(profile.section_80d_annual or 0) if profile and allow_declared else 0.0
    other_vi_a = float(profile.other_chapter_vi_a or 0) if profile and allow_declared else 0.0

    std_ded = (
        settings.standard_deduction_old_regime
        if regime == "old"
        else settings.standard_deduction_annual
    )
    months_left = max(
        1,
        (fy_end.year - period_end.year) * 12 + fy_end.month - period_end.month + 1,
    )
    pf_annual = float(pf_employee or 0) * months_left  # remaining PF estimate
    # Better PF annual: YTD PF + remaining months × current
    ytd_pf = 0.0
    for slip in Payslip.objects.filter(
        employee_id=employee,
        start_date__lt=period_start,
        end_date__gte=fy_start,
        status__in=["confirmed", "paid"],
    ):
        india = (slip.pay_head_data or {}).get("india_statutory") or {}
        ytd_pf += float(india.get("pf_employee") or 0)
    pf_annual = ytd_pf + float(pf_employee or 0) * months_left

    tax_info = calculate_annual_tds(
        annual_gross=annual_gross,
        regime=regime,
        standard_deduction=std_ded,
        section_80c=section_80c,
        section_80d=section_80d,
        other_vi_a=other_vi_a,
        pf_employee_annual=pf_annual if regime == "old" else 0,
    )
    annual_tax = tax_info["annual_tax"]
    ytd_tds = _ytd_tds_from_payslips(employee, fy_start, period_start)
    tax_already = ytd_tds + prev_tds
    remaining_tax = max(0.0, annual_tax - tax_already)
    monthly_tds = _round2(remaining_tax / months_left)

    return {
        "tds": monthly_tds,
        "annual_tax": annual_tax,
        "taxable_income": tax_info["taxable_income"],
        "regime": regime,
        "ytd_tds": _round2(ytd_tds),
        "annual_gross_projected": _round2(annual_gross),
        "annual_current_employer_projected": _round2(annual_current),
        "previous_employer_income": _round2(prev_income),
        "previous_employer_tds": _round2(prev_tds),
        "other_income": _round2(other_income),
        "tax_already_deducted": _round2(tax_already),
        "remaining_tax": _round2(remaining_tax),
        "remaining_months": months_left,
        "proof_status": proof,
        "declared_deductions_applied": allow_declared,
    }


def calculate_india_statutory(
    employee,
    basic_pay: float,
    gross_pay: float,
    start_date: date,
    end_date: date,
) -> dict[str, Any]:
    """
    Full statutory breakdown for one pay period.
    Returns pretax lines, TDS, employer contributions, and metadata for Form 16.
    """
    empty = {
        "enabled": False,
        "pretax_deductions": [],
        "tds_amount": 0.0,
        "employer_contributions": [],
        "breakdown": {},
    }
    settings = get_india_settings(employee)
    if not settings:
        return empty

    profile = get_employee_statutory_profile(employee)
    allowance_lines = []
    # Prefer caller-provided allowance breakdown when present on employee cache;
    # otherwise PF wage base uses basic only unless CoW 50% is enabled with lines.
    cow_enabled = bool(
        _setting(settings, "enable_code_on_wages_50pct", "enable_code_on_wages_50pct", default=False)
    )
    pf_base = float(basic_pay or 0)
    statutory_wage_meta = {}
    if cow_enabled:
        from payroll.methods.statutory_wage import compute_statutory_wage_base
        from payroll.models.models import Allowance

        for allowance in Allowance.objects.filter(
            specific_employees=employee, is_fixed=True, is_active=True
        ):
            allowance_lines.append(
                {
                    "title": allowance.title,
                    "amount": float(allowance.amount or 0),
                    "include_in_wage_definition": getattr(
                        allowance, "include_in_wage_definition", False
                    ),
                    "pf_applicable": getattr(allowance, "pf_applicable", False),
                    "is_excluded_allowance": getattr(
                        allowance, "is_excluded_allowance", False
                    ),
                }
            )
        statutory_wage_meta = compute_statutory_wage_base(
            basic_pay=basic_pay,
            allowance_lines=allowance_lines,
            apply_50pct_rule=True,
        )
        pf_base = float(statutory_wage_meta.get("statutory_wage") or basic_pay)

    pf = calculate_pf(pf_base, settings, profile)
    esi = calculate_esi(
        gross_pay,
        settings,
        profile,
        once_covered=_esi_already_covered(employee, start_date),
    )
    pt = calculate_pt(gross_pay, settings, profile, employee, for_date=end_date)
    lwf = calculate_lwf(
        gross_pay, settings, profile, employee, for_date=end_date
    )
    bonus = calculate_bonus_provision(basic_pay, gross_pay, settings, profile)
    tds_info = calculate_monthly_tds(
        employee, gross_pay, start_date, end_date, settings, profile, pf["employee"]
    )

    pretax = []
    if pf["employee"] > 0:
        pretax.append(
            {
                "title": "Provident Fund (Employee)",
                "amount": pf["employee"],
                "statutory_code": "PF_EE",
                "employer_contribution_rate": _setting(
                    settings, "pf_employer_rate", "pf_employer_rate", default=12
                ),
                "employer_contribution_amount": pf["employer"],
            }
        )
    if esi["employee"] > 0:
        pretax.append(
            {
                "title": "ESI (Employee)",
                "amount": esi["employee"],
                "statutory_code": "ESI_EE",
                "employer_contribution_rate": _setting(
                    settings, "esi_employer_rate", "esi_employer_rate", default=3.25
                ),
                "employer_contribution_amount": esi["employer"],
            }
        )
    if pt > 0:
        pretax.append(
            {
                "title": "Professional Tax",
                "amount": pt,
                "statutory_code": "PT",
            }
        )
    if lwf["employee"] > 0:
        pretax.append(
            {
                "title": "Labour Welfare Fund (Employee)",
                "amount": lwf["employee"],
                "statutory_code": "LWF_EE",
                "employer_contribution_amount": lwf["employer"],
            }
        )

    employer = []
    if pf["epf_employer"] > 0:
        employer.append(
            {"code": "EPF_ER", "title": "EPF (Employer)", "amount": pf["epf_employer"]}
        )
    if pf["eps"] > 0:
        employer.append({"code": "EPS", "title": "EPS (Pension)", "amount": pf["eps"]})
    if pf["edli"] > 0:
        employer.append({"code": "EDLI", "title": "EDLI", "amount": pf["edli"]})
    if esi.get("employer", 0) > 0:
        employer.append({"code": "ESI_ER", "title": "ESI (Employer)", "amount": esi["employer"]})
    if lwf["employer"] > 0:
        employer.append(
            {"code": "LWF_ER", "title": "LWF (Employer)", "amount": lwf["employer"]}
        )
    if bonus["provision"] > 0:
        employer.append(
            {
                "code": "BONUS",
                "title": "Bonus Act provision",
                "amount": bonus["provision"],
            }
        )

    breakdown = {
        "pf_wages": pf["pf_wages"],
        "pf_employee": pf["employee"],
        "pf_employer": pf["employer"],
        "eps": pf["eps"],
        "epf_employer": pf["epf_employer"],
        "edli": pf["edli"],
        "vpf": pf["vpf"],
        "esi_employee": esi["employee"],
        "esi_employer": esi.get("employer", 0),
        "esi_applicable": esi.get("applicable", False),
        "pt": pt,
        "lwf_employee": lwf["employee"],
        "lwf_employer": lwf["employer"],
        "lwf_state": lwf.get("state") or "",
        "bonus_provision": bonus["provision"],
        "bonus_wages": bonus["bonus_wages"],
        "bonus_eligible": bonus["eligible"],
        "tds": tds_info["tds"],
        "tds_regime": tds_info.get("regime"),
        "annual_tax_projected": tds_info.get("annual_tax"),
        "taxable_income_projected": tds_info.get("taxable_income"),
        "tds_remaining_months": tds_info.get("remaining_months"),
        "tds_remaining_tax": tds_info.get("remaining_tax"),
        "tds_tax_already_deducted": tds_info.get("tax_already_deducted"),
        "tds_previous_employer_income": tds_info.get("previous_employer_income"),
        "tds_previous_employer_tds": tds_info.get("previous_employer_tds"),
        "tds_other_income": tds_info.get("other_income"),
        "tds_proof_status": tds_info.get("proof_status"),
        "pt_state": resolve_pt_state(settings, employee),
        "statutory_wage": statutory_wage_meta,
        "code_on_wages_50pct": cow_enabled,
    }

    return {
        "enabled": True,
        "pretax_deductions": pretax,
        "tds_amount": tds_info["tds"],
        "employer_contributions": employer,
        "breakdown": breakdown,
    }


def apply_india_statutory_to_payroll(
    employee,
    basic_pay: float,
    gross_pay: float,
    start_date: date,
    end_date: date,
    pretax_result: dict,
    federal_tax: float,
) -> dict[str, Any]:
    """Merge India statutory into payroll calculation result."""
    india = calculate_india_statutory(
        employee, basic_pay, gross_pay, start_date, end_date
    )
    if not india["enabled"]:
        return {
            "pretax_deductions": pretax_result,
            "federal_tax": federal_tax,
            "india_statutory": {},
        }

    pretax_list = list(pretax_result.get("pretax_deductions") or [])
    # Drop legacy PF/ESI/PT rows so India statutory lines are not double-counted.
    skipped = ("provident fund", "esi", "professional tax")
    cleaned = []
    for row in pretax_list:
        title = (row.get("title") or "").lower()
        if any(token in title for token in skipped):
            continue
        cleaned.append(row)
    cleaned.extend(india["pretax_deductions"])
    pretax_result["pretax_deductions"] = cleaned

    settings = get_india_settings(employee)
    if settings and _setting(settings, "enable_tds", "enable_tds"):
        federal_tax = india["tds_amount"]

    return {
        "pretax_deductions": pretax_result,
        "federal_tax": federal_tax,
        "india_statutory": india["breakdown"],
        "india_employer_contributions": india["employer_contributions"],
    }


def _format_payslip_period(start: date, end: date) -> str:
    """Compact month label for PDFs (e.g. Jul 2026), never a full date range."""
    if not start:
        return "—"
    if end and (start.year != end.year or start.month != end.month):
        if start.year == end.year:
            return f"{start.strftime('%b')}–{end.strftime('%b %Y')}"
        return f"{start.strftime('%b %Y')}–{end.strftime('%b %Y')}"
    return start.strftime("%b %Y")


def _build_form16_totals_from_slips(slips) -> dict[str, Any]:
    """Aggregate Form 16 totals from an iterable of payslip instances."""
    totals = {
        "gross_salary": 0.0,
        "basic_salary": 0.0,
        "pf_employee": 0.0,
        "pf_employer": 0.0,
        "eps": 0.0,
        "epf_employer": 0.0,
        "edli": 0.0,
        "esi_employee": 0.0,
        "pt": 0.0,
        "tds": 0.0,
        "net_salary": 0.0,
        "months": [],
    }
    regime = "new"
    payslip_count = 0
    last_projection = {
        "taxable_income": 0.0,
        "annual_tax": 0.0,
    }
    for slip in slips:
        payslip_count += 1
        totals["gross_salary"] += float(slip.gross_pay or 0)
        totals["basic_salary"] += float(slip.basic_pay or 0)
        totals["net_salary"] += float(slip.net_pay or 0)
        pay_head = slip.pay_head_data or {}
        india = pay_head.get("india_statutory") or {}
        pf_emp = float(india.get("pf_employee") or 0)
        esi_emp = float(india.get("esi_employee") or 0)
        pt_amt = float(india.get("pt") or 0)
        tds_amt = float(india.get("tds") or pay_head.get("federal_tax") or 0)
        totals["pf_employee"] += pf_emp
        totals["pf_employer"] += float(india.get("pf_employer") or 0)
        split = pf_split_from_india(india)
        totals["eps"] = totals.get("eps", 0.0) + split["eps"]
        totals["epf_employer"] = totals.get("epf_employer", 0.0) + split["epf_employer"]
        totals["edli"] = totals.get("edli", 0.0) + split["edli"]
        totals["esi_employee"] += esi_emp
        totals["pt"] += pt_amt
        totals["tds"] += tds_amt
        if india.get("tds_regime"):
            regime = india["tds_regime"]
        if india.get("taxable_income_projected") is not None:
            last_projection["taxable_income"] = float(
                india.get("taxable_income_projected") or 0
            )
        if india.get("annual_tax_projected") is not None:
            last_projection["annual_tax"] = float(india.get("annual_tax_projected") or 0)
        totals["months"].append(
            {
                "period": _format_payslip_period(slip.start_date, slip.end_date),
                "gross": float(slip.gross_pay or 0),
                "basic": float(slip.basic_pay or 0),
                "pf": pf_emp,
                "esi": esi_emp,
                "pt": pt_amt,
                "tds": tds_amt,
                "net": float(slip.net_pay or 0),
            }
        )

    for key in totals:
        if key != "months":
            totals[key] = _round2(totals[key])

    balance = _round2(last_projection["annual_tax"] - totals["tds"])
    last_projection["taxable_income"] = _round2(last_projection["taxable_income"])
    last_projection["annual_tax"] = _round2(last_projection["annual_tax"])
    last_projection["balance_tax"] = balance

    return {
        "totals": totals,
        "regime": regime,
        "payslip_count": payslip_count,
        "projection": last_projection,
    }


def aggregate_form16(employee, financial_year_start: int) -> dict[str, Any]:
    """Build Form 16 Part B summary from confirmed payslips in the FY."""
    from payroll.models.models import Payslip

    fy_start = date(financial_year_start, 4, 1)
    fy_end = date(financial_year_start + 1, 3, 31)
    slips = Payslip.objects.filter(
        employee_id=employee,
        start_date__lte=fy_end,
        end_date__gte=fy_start,
        status__in=["confirmed", "paid", "draft"],
    ).order_by("start_date")

    summary = _build_form16_totals_from_slips(slips)
    totals = summary["totals"]
    regime = summary["regime"]
    payslip_count = summary["payslip_count"]

    bank = getattr(employee, "employee_bank_details", None)
    company = employee.get_company()

    return {
        "employee": employee,
        "company": company,
        "financial_year": f"{financial_year_start}-{financial_year_start + 1}",
        "financial_year_start": financial_year_start,
        "fy_start": fy_start,
        "fy_end": fy_end,
        "regime": regime,
        "pan": getattr(bank, "pan_number", None) if bank else None,
        "uan": getattr(bank, "uan_number", None) if bank else None,
        "totals": totals,
        "payslip_count": payslip_count,
        "projection": summary.get("projection")
        or {"taxable_income": 0.0, "annual_tax": 0.0, "balance_tax": 0.0},
        "months": totals.get("months") or [],
    }


def aggregate_tax_computation(employee, financial_year_start: int) -> dict[str, Any]:
    """Month-wise tax computation sheet for PDF download."""
    from datetime import datetime as dt

    context = aggregate_form16(employee, financial_year_start)
    context["generated_on"] = dt.now().strftime("%d %b %Y %H:%M")
    return context


def aggregate_form16_bulk(employees, financial_year_start: int) -> dict[int, dict[str, Any]]:
    """
    Bulk Form 16 aggregation for list views — one payslip query for all employees.
    Returns {employee_id: {"totals", "payslip_count", "regime"}}.
    """
    from collections import defaultdict

    from payroll.models.models import Payslip

    employee_list = list(employees)
    if not employee_list:
        return {}

    employee_ids = [emp.id for emp in employee_list]
    fy_start = date(financial_year_start, 4, 1)
    fy_end = date(financial_year_start + 1, 3, 31)
    slips = Payslip.objects.filter(
        employee_id__in=employee_ids,
        start_date__lte=fy_end,
        end_date__gte=fy_start,
        status__in=["confirmed", "paid"],
    ).order_by("employee_id", "start_date")

    slips_by_employee: dict[int, list] = defaultdict(list)
    for slip in slips:
        slips_by_employee[slip.employee_id_id].append(slip)

    result = {}
    for employee in employee_list:
        summary = _build_form16_totals_from_slips(slips_by_employee.get(employee.id, []))
        result[employee.id] = summary
    return result


def aggregate_statutory_challan(company, period_start: date, period_end: date) -> dict[str, Any]:
    """
    Aggregate PF/ESI/PT/TDS from confirmed payslips for challan filing export.
    """
    from collections import defaultdict

    from payroll.models.models import Payslip

    slips = Payslip.objects.filter(
        start_date__lte=period_end,
        end_date__gte=period_start,
        status__in=["confirmed", "paid"],
    ).select_related("employee_id", "employee_id__employee_bank_details")
    if company:
        slips = slips.filter(employee_id__employee_work_info__company_id=company)
    slips = slips.order_by("employee_id__employee_first_name", "start_date")

    by_employee: dict[int, dict] = defaultdict(
        lambda: {
            "employee": None,
            "badge_id": "",
            "pan": "",
            "uan": "",
            "payslip_count": 0,
            "gross": 0.0,
            "pf_wages": 0.0,
            "pf_employee": 0.0,
            "pf_employer": 0.0,
            "eps": 0.0,
            "epf_employer": 0.0,
            "edli": 0.0,
            "esi_employee": 0.0,
            "esi_employer": 0.0,
            "pt": 0.0,
            "lwf_employee": 0.0,
            "lwf_employer": 0.0,
            "bonus_provision": 0.0,
            "tds": 0.0,
            "ncp_days": 0.0,
        }
    )

    for slip in slips:
        india = (slip.pay_head_data or {}).get("india_statutory") or {}
        pay_head = slip.pay_head_data or {}
        has_statutory = any(
            float(india.get(key) or 0) > 0
            for key in (
                "pf_employee",
                "pf_employer",
                "esi_employee",
                "esi_employer",
                "pt",
                "lwf_employee",
                "lwf_employer",
                "bonus_provision",
                "tds",
            )
        )
        if not has_statutory and not pay_head.get("federal_tax"):
            continue
        emp = slip.employee_id
        row = by_employee[emp.id]
        row["employee"] = emp
        row["badge_id"] = emp.badge_id or ""
        bank = getattr(emp, "employee_bank_details", None)
        row["pan"] = getattr(bank, "pan_number", "") if bank else ""
        row["uan"] = getattr(bank, "uan_number", "") if bank else ""
        row["payslip_count"] += 1
        row["gross"] += float(slip.gross_pay or 0)
        row["pf_wages"] += float(india.get("pf_wages") or 0)
        row["pf_employee"] += float(india.get("pf_employee") or 0)
        row["pf_employer"] += float(india.get("pf_employer") or 0)
        split = pf_split_from_india(india)
        row["eps"] += split["eps"]
        row["epf_employer"] += split["epf_employer"]
        row["edli"] += split["edli"]
        row["esi_employee"] += float(india.get("esi_employee") or 0)
        row["esi_employer"] += float(india.get("esi_employer") or 0)
        row["pt"] += float(india.get("pt") or 0)
        row["lwf_employee"] += float(india.get("lwf_employee") or 0)
        row["lwf_employer"] += float(india.get("lwf_employer") or 0)
        row["bonus_provision"] += float(india.get("bonus_provision") or 0)
        row["tds"] += float(india.get("tds") or slip.pay_head_data.get("federal_tax") or 0)
        unpaid = pay_head.get("unpaid_days")
        if unpaid is None:
            unpaid = float(pay_head.get("leave_lop_days") or 0) + float(
                pay_head.get("attendance_lop_days") or 0
            )
        row["ncp_days"] += float(unpaid or 0)

    rows = []
    totals = {
        "gross": 0.0,
        "pf_wages": 0.0,
        "pf_employee": 0.0,
        "pf_employer": 0.0,
        "eps": 0.0,
        "epf_employer": 0.0,
        "edli": 0.0,
        "esi_employee": 0.0,
        "esi_employer": 0.0,
        "pt": 0.0,
        "lwf_employee": 0.0,
        "lwf_employer": 0.0,
        "bonus_provision": 0.0,
        "tds": 0.0,
        "ncp_days": 0.0,
        "employee_count": 0,
    }
    for row in sorted(by_employee.values(), key=lambda r: (r["employee"].get_full_name() if r["employee"] else "")):
        for key in totals:
            if key == "employee_count":
                continue
            totals[key] += row[key]
        totals["employee_count"] += 1
        for key in row:
            if key not in ("employee", "badge_id", "pan", "uan", "payslip_count") and isinstance(row[key], float):
                row[key] = _round2(row[key])
        rows.append(row)

    for key in totals:
        if key != "employee_count":
            totals[key] = _round2(totals[key])

    totals["pf_total"] = _round2(totals["pf_employee"] + totals["pf_employer"])
    totals["esi_total"] = _round2(totals["esi_employee"] + totals["esi_employer"])
    totals["lwf_total"] = _round2(
        totals.get("lwf_employee", 0) + totals.get("lwf_employer", 0)
    )

    return {
        "rows": rows,
        "totals": totals,
        "period_start": period_start,
        "period_end": period_end,
        "company": company,
    }


def challan_csv_rows(challan_data: dict, export_type: str = "all") -> list[list]:
    """Build CSV rows for PF/ESI/PT/TDS/combined challan export."""
    headers_map = {
        "pf": [
            "Badge ID", "Employee", "UAN", "PAN", "PF Wages",
            "PF Employee", "EPS", "EPF Employer", "EDLI", "PF Employer Total",
        ],
        "esi": [
            "Badge ID", "Employee", "UAN", "Gross", "ESI Employee", "ESI Employer",
        ],
        "pt": ["Badge ID", "Employee", "PAN", "Gross", "Professional Tax"],
        "lwf": [
            "Badge ID", "Employee", "Gross", "LWF Employee", "LWF Employer", "LWF Total",
        ],
        "bonus": [
            "Badge ID", "Employee", "Gross", "Bonus Wages (stored)", "Bonus Provision",
        ],
        "tds": ["Badge ID", "Employee", "PAN", "Gross", "TDS Deducted"],
        "all": [
            "Badge ID", "Employee", "UAN", "PAN", "Payslips", "Gross",
            "PF Wages", "PF Employee", "EPS", "EPF Employer", "EDLI", "PF Employer Total",
            "ESI Employee", "ESI Employer",
            "PT", "LWF Employee", "LWF Employer", "Bonus Provision", "TDS",
        ],
    }
    export_type = (export_type or "all").lower()
    headers = headers_map.get(export_type, headers_map["all"])
    out = [headers]

    for row in challan_data["rows"]:
        emp = row["employee"]
        name = emp.get_full_name() if emp else ""
        if export_type == "pf":
            out.append([
                row["badge_id"], name, row["uan"], row["pan"],
                row["pf_wages"], row["pf_employee"],
                row.get("eps", 0), row.get("epf_employer", 0), row.get("edli", 0),
                row["pf_employer"],
            ])
        elif export_type == "esi":
            out.append([
                row["badge_id"], name, row["uan"],
                row["gross"], row["esi_employee"], row["esi_employer"],
            ])
        elif export_type == "pt":
            out.append([row["badge_id"], name, row["pan"], row["gross"], row["pt"]])
        elif export_type == "lwf":
            out.append([
                row["badge_id"], name, row["gross"],
                row.get("lwf_employee", 0), row.get("lwf_employer", 0),
                _round2(row.get("lwf_employee", 0) + row.get("lwf_employer", 0)),
            ])
        elif export_type == "bonus":
            out.append([
                row["badge_id"], name, row["gross"],
                row.get("bonus_wages", 0) if "bonus_wages" in row else "",
                row.get("bonus_provision", 0),
            ])
        elif export_type == "tds":
            out.append([row["badge_id"], name, row["pan"], row["gross"], row["tds"]])
        else:
            out.append([
                row["badge_id"], name, row["uan"], row["pan"], row["payslip_count"],
                row["gross"], row["pf_wages"], row["pf_employee"],
                row.get("eps", 0), row.get("epf_employer", 0), row.get("edli", 0),
                row["pf_employer"],
                row["esi_employee"], row["esi_employer"], row["pt"],
                row.get("lwf_employee", 0), row.get("lwf_employer", 0),
                row.get("bonus_provision", 0), row["tds"],
            ])

    totals = challan_data["totals"]
    if export_type == "pf":
        out.append([
            "", "TOTAL", "", "", totals["pf_wages"], totals["pf_employee"],
            totals.get("eps", 0), totals.get("epf_employer", 0), totals.get("edli", 0),
            totals["pf_employer"],
        ])
    elif export_type == "esi":
        out.append(["", "TOTAL", "", totals["gross"], totals["esi_employee"], totals["esi_employer"]])
    elif export_type == "pt":
        out.append(["", "TOTAL", "", totals["gross"], totals["pt"]])
    elif export_type == "lwf":
        out.append([
            "", "TOTAL", totals["gross"],
            totals.get("lwf_employee", 0), totals.get("lwf_employer", 0),
            _round2(totals.get("lwf_employee", 0) + totals.get("lwf_employer", 0)),
        ])
    elif export_type == "bonus":
        out.append(["", "TOTAL", totals["gross"], "", totals.get("bonus_provision", 0)])
    elif export_type == "tds":
        out.append(["", "TOTAL", "", totals["gross"], totals["tds"]])
    else:
        out.append([
            "", "TOTAL", "", "", "", totals["gross"], totals["pf_wages"],
            totals["pf_employee"],
            totals.get("eps", 0), totals.get("epf_employer", 0), totals.get("edli", 0),
            totals["pf_employer"], totals["esi_employee"],
            totals["esi_employer"], totals["pt"],
            totals.get("lwf_employee", 0), totals.get("lwf_employer", 0),
            totals.get("bonus_provision", 0), totals["tds"],
        ])
    return out


def quarter_bounds(year: int, quarter: int) -> tuple[date, date]:
    """Indian FY quarters: Q1 Apr–Jun, Q2 Jul–Sep, Q3 Oct–Dec, Q4 Jan–Mar."""
    quarter = max(1, min(4, quarter))
    if quarter == 1:
        return date(year, 4, 1), date(year, 6, 30)
    if quarter == 2:
        return date(year, 7, 1), date(year, 9, 30)
    if quarter == 3:
        return date(year, 10, 1), date(year, 12, 31)
    # Q4 spans calendar year boundary
    return date(year + 1, 1, 1), date(year + 1, 3, 31)


def aggregate_form24q(company, period_start: date, period_end: date) -> dict[str, Any]:
    """Quarterly TDS (Form 24Q) aggregation from confirmed payslips."""
    data = aggregate_statutory_challan(company, period_start, period_end)
    data["form"] = "24Q"
    data["quarter_label"] = f"{period_start} — {period_end}"
    return data


def form24q_csv_rows(form24q_data: dict) -> list[list]:
    """CSV rows for Form 24Q TDS quarterly statement (TRACES-ready subset)."""
    headers = [
        "PAN",
        "Employee Name",
        "Badge ID",
        "UAN",
        "Gross Salary",
        "TDS Deducted",
        "Period Start",
        "Period End",
    ]
    out = [headers]
    period_start = form24q_data["period_start"]
    period_end = form24q_data["period_end"]
    for row in form24q_data["rows"]:
        emp = row["employee"]
        name = emp.get_full_name() if emp else ""
        out.append([
            row["pan"],
            name,
            row["badge_id"],
            row["uan"],
            row["gross"],
            row["tds"],
            period_start.isoformat(),
            period_end.isoformat(),
        ])
    totals = form24q_data["totals"]
    out.append([
        "",
        "TOTAL",
        "",
        "",
        totals["gross"],
        totals["tds"],
        period_start.isoformat(),
        period_end.isoformat(),
    ])
    return out


def register_csv_rows(challan_data: dict, register_type: str = "pf") -> list[list]:
    """PF / ESI / PT / LWF / Bonus / Gratuity statutory register export."""
    kind = (register_type or "pf").lower()
    if kind == "gratuity":
        return challan_data.get("csv_rows") or [["Employee", "Join Date", "Years", "Basic", "Eligible", "Gratuity"]]
    if kind not in ("pf", "esi", "pt", "lwf", "bonus"):
        kind = "pf"
    return challan_csv_rows(challan_data, kind)


def aggregate_gratuity_register(company, as_of: date | None = None) -> dict[str, Any]:
    """Projected gratuity liability for active employees (not from payslips)."""
    from employee.models import Employee
    from payroll.models.models import Contract

    as_of = as_of or date.today()
    employees = Employee.objects.filter(is_active=True).select_related(
        "employee_work_info"
    )
    if company:
        employees = employees.filter(employee_work_info__company_id=company)
    employees = employees.distinct().order_by(
        "employee_first_name", "employee_last_name"
    )

    contracts = {
        c.employee_id_id: c
        for c in Contract.objects.filter(
            employee_id__in=employees, contract_status="active"
        ).order_by("contract_start_date")
    }

    rows = []
    totals = {
        "employee_count": 0,
        "eligible_count": 0,
        "gratuity": 0.0,
        "gross": 0.0,
        "pt": 0.0,
        "lwf_employee": 0.0,
        "lwf_employer": 0.0,
        "bonus_provision": 0.0,
        "tds": 0.0,
        "pf_wages": 0.0,
        "pf_employee": 0.0,
        "pf_employer": 0.0,
        "eps": 0.0,
        "epf_employer": 0.0,
        "edli": 0.0,
        "esi_employee": 0.0,
        "esi_employer": 0.0,
    }
    csv_rows = [
        ["Badge ID", "Employee", "Join Date", "Completed Years", "Basic Pay", "Eligible", "Gratuity Liability"]
    ]
    for emp in employees:
        work = getattr(emp, "employee_work_info", None)
        join_date = getattr(work, "date_joining", None) if work else None
        contract = contracts.get(emp.id)
        basic = float(contract.basic_pay if contract else 0)
        profile = get_employee_statutory_profile(emp)
        applicable = True
        if profile and not getattr(profile, "gratuity_applicable", True):
            applicable = False
        info = calculate_gratuity(basic, join_date, as_of, applicable=applicable)
        row = {
            "employee": emp,
            "badge_id": emp.badge_id or "",
            "pan": "",
            "uan": "",
            "join_date": join_date,
            "years": info["years"],
            "basic_pay": info["basic_pay"],
            "eligible": info["eligible"],
            "gratuity": info["amount"],
            "capped": info["capped"],
            "gross": info["amount"],
            "pt": 0,
        }
        rows.append(row)
        totals["employee_count"] += 1
        if info["eligible"]:
            totals["eligible_count"] += 1
            totals["gratuity"] += info["amount"]
        csv_rows.append([
            row["badge_id"],
            emp.get_full_name(),
            join_date.isoformat() if join_date else "",
            info["years"],
            info["basic_pay"],
            "Yes" if info["eligible"] else "No",
            info["amount"],
        ])

    totals["gratuity"] = _round2(totals["gratuity"])
    csv_rows.append(["", "TOTAL", "", "", "", totals["eligible_count"], totals["gratuity"]])
    return {
        "rows": rows,
        "totals": totals,
        "period_start": as_of,
        "period_end": as_of,
        "company": company,
        "csv_rows": csv_rows,
        "form": "gratuity",
    }



# ---------------------------------------------------------------------------
# TRACES / NSDL RPU e-filing helpers
# ---------------------------------------------------------------------------

def _traces_pipe_safe(value) -> str:
    """Strip characters that would break pipe-delimited records."""
    return str(value or "").replace("|", " ").replace("\n", " ").strip()


def _traces_quarter_label(period_start: date) -> tuple[int, str]:
    fy_start = period_start.year if period_start.month >= 4 else period_start.year - 1
    month = period_start.month
    if month in (4, 5, 6):
        return fy_start, "Q1"
    if month in (7, 8, 9):
        return fy_start, "Q2"
    if month in (10, 11, 12):
        return fy_start, "Q3"
    return fy_start, "Q4"


def _parse_deposit_date(value, fallback: date) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    raw = str(value or "").strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d%m%Y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return fallback


def _tds_rate(gross: float, tds: float) -> str:
    if not gross:
        return "0.00"
    return f"{(float(tds) / float(gross)) * 100:.2f}"


def generate_traces_text(
    form24q_data: dict,
    tan: str = "",
    form: str = "24Q",
    *,
    bsr_code: str = "",
    challan_serial: str = "",
    deposit_date=None,
    company_name: str = "",
) -> str:
    """
    Build a 24Q working file for NSDL RPU (not a compiled FVU).

    Records: FH (file), BH (batch), CD (challan / ITNS 281), DD (deductee).
    Import the companion Annexure CSV into NSDL RPU, generate FVU, upload FVU
    on TRACES.
    """
    period_start = form24q_data["period_start"]
    period_end = form24q_data["period_end"]
    totals = form24q_data["totals"]
    tan = _traces_pipe_safe(tan).upper()
    bsr_code = _traces_pipe_safe(bsr_code)[:7]
    challan_serial = _traces_pipe_safe(challan_serial)
    company_name = _traces_pipe_safe(company_name).upper()
    deposited = _parse_deposit_date(deposit_date, period_end)
    fy_start, qtr = _traces_quarter_label(period_start)
    assessment_year = f"{fy_start + 1}-{str(fy_start + 2)[2:]}"
    tds_total = f"{totals.get('tds', 0):.2f}"
    deductee_count = str(len(form24q_data["rows"]))

    lines = [
        "|".join([
            "FH",
            form,
            str(fy_start),
            assessment_year,
            qtr,
            tan,
            company_name,
            date.today().strftime("%d%m%Y"),
            deductee_count,
            tds_total,
        ]),
        "|".join([
            "BH",
            "1",
            form,
            tan,
            qtr,
            str(fy_start),
            assessment_year,
            deductee_count,
            tds_total,
        ]),
        "|".join([
            "CD",
            "1",
            "192",
            "200",
            bsr_code,
            deposited.strftime("%d%m%Y"),
            challan_serial,
            tds_total,
            "0.00",
            "0.00",
            tds_total,
            deductee_count,
        ]),
    ]

    for idx, row in enumerate(form24q_data["rows"], start=1):
        emp = row.get("employee")
        name = _traces_pipe_safe(emp.get_full_name().upper() if emp else "")
        pan = _traces_pipe_safe(row.get("pan") or "PANNOTAVBL").upper()
        gross = float(row.get("gross", 0) or 0)
        tds = float(row.get("tds", 0) or 0)
        lines.append("|".join([
            "DD",
            str(idx),
            "01",
            pan,
            name,
            "192",
            period_end.strftime("%d%m%Y"),
            f"{gross:.2f}",
            f"{tds:.2f}",
            "0.00",
            "0.00",
            f"{tds:.2f}",
            f"{tds:.2f}",
            period_end.strftime("%d%m%Y"),
            _tds_rate(gross, tds),
            "",
            "",
        ]))

    lines.append("|".join([
        "FT",
        deductee_count,
        f"{totals.get('gross', 0):.2f}",
        tds_total,
    ]))
    return "\n".join(lines) + "\n"


def generate_rpu_annexure_csv(form24q_data: dict) -> str:
    """NSDL RPU Annexure I (deductee) import CSV for Form 24Q."""
    period_end = form24q_data["period_end"]
    payment_date = period_end.strftime("%d/%m/%Y")
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "Serial No",
        "Deductee Code",
        "PAN",
        "Name of Deductee",
        "Section Code",
        "Date of Payment/Credit",
        "Amount Paid/Credited",
        "TDS",
        "Surcharge",
        "Education Cess",
        "Total Tax Deducted",
        "Total Tax Deposited",
        "Date of Deduction",
        "Rate of TDS",
        "Reason for Non-deduction/Lower Deduction",
        "Certificate Number",
    ])
    for idx, row in enumerate(form24q_data["rows"], start=1):
        emp = row.get("employee")
        name = emp.get_full_name() if emp else ""
        pan = (row.get("pan") or "PANNOTAVBL").upper()
        gross = float(row.get("gross", 0) or 0)
        tds = float(row.get("tds", 0) or 0)
        writer.writerow([
            idx,
            "01",
            pan,
            name,
            "192",
            payment_date,
            f"{gross:.2f}",
            f"{tds:.2f}",
            "0.00",
            "0.00",
            f"{tds:.2f}",
            f"{tds:.2f}",
            payment_date,
            _tds_rate(gross, tds),
            "",
            "",
        ])
    return buf.getvalue()


def generate_csi_challan_text(
    form24q_data: dict,
    tan: str = "",
    *,
    bsr_code: str = "",
    challan_serial: str = "",
    deposit_date=None,
) -> str:
    """CSI-style challan line for NSDL RPU challan matching (ITNS 281)."""
    period_end = form24q_data["period_end"]
    deposited = _parse_deposit_date(deposit_date, period_end)
    tds_total = f"{form24q_data['totals'].get('tds', 0):.2f}"
    return "|".join([
        _traces_pipe_safe(tan).upper(),
        "281",
        "200",
        _traces_pipe_safe(bsr_code)[:7],
        deposited.strftime("%d/%m/%Y"),
        _traces_pipe_safe(challan_serial),
        tds_total,
        "0.00",
        "0.00",
        tds_total,
    ]) + "\n"


def generate_traces_zip(
    form24q_data: dict,
    tan: str = "",
    *,
    bsr_code: str = "",
    challan_serial: str = "",
    deposit_date=None,
    company_name: str = "",
    filename_base: str = "TRACES_24Q",
) -> bytes:
    """Zip of statement TXT + RPU Annexure CSV + CSI challan line."""
    statement = generate_traces_text(
        form24q_data,
        tan=tan,
        bsr_code=bsr_code,
        challan_serial=challan_serial,
        deposit_date=deposit_date,
        company_name=company_name,
    )
    annexure = generate_rpu_annexure_csv(form24q_data)
    csi = generate_csi_challan_text(
        form24q_data,
        tan=tan,
        bsr_code=bsr_code,
        challan_serial=challan_serial,
        deposit_date=deposit_date,
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"{filename_base}_statement.txt", statement)
        zf.writestr(f"{filename_base}_rpu_annexure.csv", annexure)
        zf.writestr(f"{filename_base}_csi_challan.txt", csi)
        zf.writestr(
            "README.txt",
            "Import rpu_annexure.csv into NSDL RPU as Form 24Q Annexure I.\n"
            "Match CSI challan (BSR, serial, deposit date, amount) in RPU.\n"
            "Validate in RPU to produce the FVU file, then upload the FVU on TRACES.\n"
            "The statement.txt is a working copy — it is not an FVU.\n",
        )
    return buf.getvalue()


def generate_oltas_challan_text(
    challan_data: dict,
    tan: str = "",
    *,
    bsr_code: str = "",
    challan_serial: str = "",
    deposit_date=None,
) -> str:
    """ITNS 281 / OLTAS challan working file (TDS). PF/ESI remain in DETAIL rows."""
    totals = challan_data["totals"]
    period_start = challan_data["period_start"]
    period_end = challan_data["period_end"]
    tan = _traces_pipe_safe(tan).upper()
    deposited = _parse_deposit_date(deposit_date, period_end)

    lines = [
        "|".join([
            "CHALLAN",
            tan,
            "281",
            "200",
            _traces_pipe_safe(bsr_code)[:7],
            deposited.strftime("%d%m%Y"),
            _traces_pipe_safe(challan_serial),
            period_start.strftime("%d%m%Y"),
            period_end.strftime("%d%m%Y"),
            f"{totals.get('tds', 0):.2f}",
            f"{totals.get('pf_employee', 0) + totals.get('pf_employer', 0):.2f}",
            f"{totals.get('esi_employee', 0) + totals.get('esi_employer', 0):.2f}",
            f"{totals.get('pt', 0):.2f}",
        ])
    ]

    for row in challan_data["rows"]:
        emp = row.get("employee")
        name = _traces_pipe_safe(emp.get_full_name().upper() if emp else "")
        pan = _traces_pipe_safe(row.get("pan") or "").upper()
        lines.append("|".join([
            "DETAIL",
            pan,
            name,
            f"{row.get('gross', 0):.2f}",
            f"{row.get('tds', 0):.2f}",
            f"{row.get('pf_employee', 0):.2f}",
            f"{row.get('pf_employer', 0):.2f}",
            f"{row.get('esi_employee', 0):.2f}",
            f"{row.get('esi_employer', 0):.2f}",
            f"{row.get('pt', 0):.2f}",
        ]))

    return "\n".join(lines) + "\n"


ECR_DELIMITER = "#~#"


def _ecr_safe_name(name: str) -> str:
    """EPFO member name: letters, spaces, dots only."""
    cleaned = []
    for ch in (name or "").upper():
        if ch.isalpha() or ch in (" ", "."):
            cleaned.append(ch)
        elif ch in ("-", "_", "'", "|", ",", "/"):
            cleaned.append(" ")
    return " ".join("".join(cleaned).split())


def _ecr_uan(value) -> str:
    digits = "".join(ch for ch in str(value or "") if ch.isdigit())
    return digits[:12]


def _ecr_int(value) -> int:
    try:
        return int(round(float(value or 0)))
    except (TypeError, ValueError):
        return 0


def build_epf_ecr_payload(challan_data: dict) -> dict[str, Any]:
    """
    Build EPFO ECR 2.0 rows (#~# delimited) from aggregated challan data.

    Columns:
    UAN, Member Name, Gross Wages, EPF Wages, EPS Wages, EDLI Wages,
    EPF EE Share, EPS ER Share, EPF-EPS Diff (ER), NCP Days, Refund of Advances
    """
    lines: list[str] = []
    included: list[dict] = []
    issues: list[dict] = []

    for row in challan_data.get("rows") or []:
        pf_wages = float(row.get("pf_wages") or 0)
        pf_ee = float(row.get("pf_employee") or 0)
        pf_er = float(row.get("pf_employer") or 0)
        if pf_wages <= 0 and pf_ee <= 0 and pf_er <= 0:
            continue

        emp = row.get("employee")
        name = _ecr_safe_name(emp.get_full_name() if emp else "")
        uan = _ecr_uan(row.get("uan"))
        split = {
            "eps": float(row.get("eps") or 0),
            "epf_employer": float(row.get("epf_employer") or 0),
        }
        if not split["eps"] and not split["epf_employer"] and pf_er:
            derived = pf_split_from_india(
                {
                    "pf_wages": pf_wages,
                    "pf_employer": pf_er,
                    "eps": row.get("eps"),
                    "epf_employer": row.get("epf_employer"),
                    "edli": row.get("edli"),
                }
            )
            split = {
                "eps": float(derived.get("eps") or 0),
                "epf_employer": float(derived.get("epf_employer") or 0),
            }

        eps_wages = min(pf_wages, EPS_WAGE_CEILING) if pf_wages > 0 else 0.0
        edli_wages = eps_wages
        if float(split.get("eps") or 0) <= 0:
            eps_wages = 0.0

        ncp = _ecr_int(row.get("ncp_days") or 0)
        fields = [
            uan,
            name,
            str(_ecr_int(row.get("gross"))),
            str(_ecr_int(pf_wages)),
            str(_ecr_int(eps_wages)),
            str(_ecr_int(edli_wages)),
            str(_ecr_int(pf_ee)),
            str(_ecr_int(split.get("eps"))),
            str(_ecr_int(split.get("epf_employer"))),
            str(ncp),
            "0",
        ]
        line = ECR_DELIMITER.join(fields)
        record = {
            "uan": uan,
            "name": name,
            "line": line,
            "employee": emp,
            "badge_id": row.get("badge_id") or "",
            "pf_wages": _ecr_int(pf_wages),
            "pf_employee": _ecr_int(pf_ee),
        }

        if len(uan) != 12:
            issues.append(
                {
                    **record,
                    "issue": "Missing or invalid UAN (12 digits required)",
                }
            )
            continue
        if not name:
            issues.append({**record, "issue": "Missing member name"})
            continue

        lines.append(line)
        included.append(record)

    return {
        "lines": lines,
        "included": included,
        "issues": issues,
        "text": ("\n".join(lines) + ("\n" if lines else "")),
        "period_start": challan_data.get("period_start"),
        "period_end": challan_data.get("period_end"),
        "company": challan_data.get("company"),
    }


def generate_epf_ecr_text(challan_data: dict) -> str:
    """Return EPFO ECR 2.0 plain-text body (ANSI-safe ASCII)."""
    return build_epf_ecr_payload(challan_data)["text"]
