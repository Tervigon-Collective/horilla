"""
Payroll / attendance month: runs from PAYROLL_CYCLE_START_DAY of one month to
the day before it in the next (Seleric: the 26th to the 25th). Search screens
default to the current cycle, and overtime never carries across cycles.
"""

import datetime

from django.conf import settings


def cycle_start_day():
    day = int(getattr(settings, "PAYROLL_CYCLE_START_DAY", 1) or 1)
    return min(max(day, 1), 28)


def _add_months(day, months):
    month_index = day.month - 1 + months
    return day.replace(
        year=day.year + month_index // 12, month=month_index % 12 + 1, day=1
    )


def cycle_bounds(day=None):
    """(first, last) date of the payroll cycle containing ``day`` (default today)."""
    day = day or datetime.date.today()
    if isinstance(day, datetime.datetime):
        day = day.date()
    start_day = cycle_start_day()
    month_start = day.replace(day=1)
    if day.day >= start_day:
        first = month_start.replace(day=start_day)
    else:
        first = _add_months(month_start, -1).replace(day=start_day)
    last = _add_months(first.replace(day=1), 1).replace(day=start_day) - datetime.timedelta(
        days=1
    )
    return first, last


def cycle_key(day):
    """Identifies the cycle ``day`` belongs to (its first date)."""
    return cycle_bounds(day)[0]
