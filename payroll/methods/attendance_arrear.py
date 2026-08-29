"""
Simplify settle: always create one-time allowance with absolute amount for
positive arrears; for recovery create one-time deduction.
"""

from __future__ import annotations

from calendar import monthrange
from datetime import date

from django.db import transaction


@transaction.atomic
def create_attendance_arrear(
    employee,
    *,
    source_period_start: date,
    source_period_end: date,
    days: float,
    reason: str = "",
    payout_month: date | None = None,
    source_payroll_run=None,
):
    from payroll.models.models import Contract
    from payroll.models.payroll_run import AttendanceArrear

    if not days:
        raise ValueError("days must be non-zero")

    contract = Contract.objects.filter(
        employee_id=employee, contract_status="active"
    ).first()
    basic = float(contract.wage or 0) if contract else 0.0
    cal_days = monthrange(source_period_start.year, source_period_start.month)[1] or 30
    per_day = basic / cal_days if cal_days else 0.0
    amount = round(per_day * float(days), 2)

    today = date.today()
    if payout_month is None:
        y, m = source_period_end.year, source_period_end.month
        if m == 12:
            payout_month = date(y + 1, 1, 1)
        else:
            payout_month = date(y, m + 1, 1)
        if payout_month < date(today.year, today.month, 1):
            payout_month = date(today.year, today.month, 1)

    return AttendanceArrear.objects.create(
        employee_id=employee,
        source_period_start=source_period_start,
        source_period_end=source_period_end,
        days=float(days),
        amount=amount,
        reason=reason or f"Attendance arrear {days} day(s)",
        payout_month=payout_month,
        source_payroll_run=source_payroll_run,
        paid=False,
    )


@transaction.atomic
def settle_attendance_arrears_for_period(
    employee,
    period_start: date,
    period_end: date,
) -> list[dict]:
    from payroll.models.models import Allowance, Deduction
    from payroll.models.payroll_run import AttendanceArrear

    month_start = date(period_start.year, period_start.month, 1)
    due = AttendanceArrear.objects.filter(
        employee_id=employee,
        paid=False,
        payout_month__lte=month_start,
        is_active=True,
    )
    lines = []
    for arrear in due:
        title = f"Attendance Arrear ({arrear.source_period_start:%b %Y})"
        amt = abs(float(arrear.amount))
        if float(arrear.amount) >= 0:
            allowance = Allowance.objects.create(
                title=title,
                amount=amt,
                is_fixed=True,
                is_taxable=True,
                include_active_employees=False,
                one_time_date=period_start,
                include_in_ctc=True,
                proratable=False,
            )
            allowance.specific_employees.add(employee)
            arrear.allowance = allowance
        else:
            ded = Deduction.objects.create(
                title=title,
                amount=amt,
                is_fixed=True,
                is_pretax=False,
                include_active_employees=False,
                one_time_date=period_start,
            )
            ded.specific_employees.add(employee)
            arrear.allowance = None
        arrear.paid = True
        arrear.paid_on = date.today()
        arrear.save()
        lines.append(
            {
                "arrear_id": arrear.pk,
                "title": title,
                "amount": float(arrear.amount),
                "days": float(arrear.days),
            }
        )
    return lines
