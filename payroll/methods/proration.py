"""
Proration helpers for join/exit and LOP paid-days math.
"""

from __future__ import annotations

from calendar import monthrange
from datetime import date
from typing import Literal


ProrationMethod = Literal["calendar", "working_day"]


def calendar_days_in_period(start: date, end: date) -> int:
    if end < start:
        return 0
    return (end - start).days + 1


def month_calendar_days(year: int, month: int) -> int:
    return monthrange(year, month)[1]


def prorate_amount(
    monthly_amount: float,
    *,
    paid_days: float,
    total_days: float,
    proratable: bool = True,
) -> float:
    """
    Prorated Component = Monthly × Paid Days ÷ Total Days.
    Non-proratable components return the full monthly amount.
    """
    amount = float(monthly_amount or 0)
    if not proratable:
        return round(amount, 2)
    total = float(total_days or 0)
    if total <= 0:
        return 0.0
    paid = max(0.0, float(paid_days or 0))
    return round(amount * paid / total, 2)


def payable_window(
    period_start: date,
    period_end: date,
    *,
    doj: date | None = None,
    lwd: date | None = None,
) -> tuple[date, date] | None:
    """
    Join/exit eligibility window inside a payroll period.
    Returns None when the employee is not eligible for any day.
    """
    start = period_start
    end = period_end
    if doj and doj > end:
        return None
    if lwd and lwd < start:
        return None
    if doj and doj > start:
        start = doj
    if lwd and lwd < end:
        end = lwd
    if end < start:
        return None
    return start, end


def eligible_for_period(
    period_start: date,
    period_end: date,
    *,
    doj: date | None = None,
    lwd: date | None = None,
    payroll_excluded: bool = False,
) -> bool:
    if payroll_excluded:
        return False
    return payable_window(period_start, period_end, doj=doj, lwd=lwd) is not None
