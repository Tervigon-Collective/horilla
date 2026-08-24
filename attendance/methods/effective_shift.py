"""Attendance helpers — effective shift at punch time."""

from __future__ import annotations

from datetime import date, datetime


def resolve_effective_shift(employee, at_dt=None):
    """
    Shift for clock-in: published roster for the date, else work_info.shift_id.

    Rotation already updates work_info asynchronously; roster is the day-level override.
    """
    work = getattr(employee, "employee_work_info", None)
    fallback = getattr(work, "shift_id", None) if work else None
    if at_dt is None:
        day = date.today()
    elif isinstance(at_dt, datetime):
        day = at_dt.date()
    else:
        day = at_dt

    try:
        from base.models import Roster

        entry = (
            Roster.objects.filter(
                employee=employee, date=day, is_published=True, is_off=False
            )
            .select_related("shift")
            .first()
        )
        if entry and entry.shift_id:
            return entry.shift
    except Exception:
        pass
    return fallback
