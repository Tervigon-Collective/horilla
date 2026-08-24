"""Full & Final settlement calculation and workflow helpers."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any


def _years_of_service(join_date: date | None, last_working_day: date) -> float:
    if not join_date:
        return 0.0
    days = (last_working_day - join_date).days
    return max(days / 365.25, 0.0)


def loan_outstanding_amount(loan) -> float:
    """Unpaid principal remaining on a loan / advance / fine."""
    if getattr(loan, "settled", False):
        return 0.0
    total = int(loan.installments or 0)
    amount = float(loan.loan_amount or 0)
    if total <= 0:
        return round(amount, 2)
    paid = int(loan.installment_paid() or 0)
    remaining = max(total - paid, 0)
    return round(amount * remaining / total, 2)


def compute_fnf_totals(
    *,
    gratuity: float = 0,
    bonus_unpaid: float = 0,
    leave_encashment: float = 0,
    notice_period_pay: float = 0,
    other_additions: float = 0,
    loan_recovery: float = 0,
    other_deductions: float = 0,
) -> dict[str, float]:
    earnings = round(
        float(gratuity or 0)
        + float(bonus_unpaid or 0)
        + float(leave_encashment or 0)
        + float(notice_period_pay or 0)
        + float(other_additions or 0),
        2,
    )
    recoveries = round(float(loan_recovery or 0) + float(other_deductions or 0), 2)
    return {
        "total_earnings": earnings,
        "total_recoveries": recoveries,
        "net_payable": round(earnings - recoveries, 2),
        "total_settlement": round(earnings - recoveries, 2),
    }


def calculate_fnf_settlement(employee, last_working_day: date | None = None) -> dict[str, Any]:
    """
    Estimate F&F components for an exiting employee.

    Includes gratuity, unpaid bonus, leave encashment, notice stub, and recoveries
    (outstanding loans and pending claims).
    """
    from django.apps import apps

    from employee.models import EmployeeWorkInformation
    from leave.models import AvailableLeave
    from payroll.models.models import Contract, LoanAccount, Reimbursement

    last_working_day = last_working_day or date.today()
    work = EmployeeWorkInformation.objects.filter(employee_id=employee).first()
    join_date = getattr(work, "date_joining", None) if work else None
    years = _years_of_service(join_date, last_working_day)

    contract = (
        Contract.objects.filter(employee_id=employee, contract_status="active")
        .order_by("-contract_start_date")
        .first()
    )
    if contract is None:
        contract = (
            Contract.objects.filter(employee_id=employee)
            .order_by("-contract_start_date")
            .first()
        )
    basic_pay = float(getattr(contract, "wage", 0) or 0) if contract else 0.0
    gross_pay = basic_pay
    if contract:
        try:
            from payroll.methods.ctc_wizard import current_ctc_snapshot

            snap = current_ctc_snapshot(contract)
            gross_pay = float(snap.get("monthly_ctc") or basic_pay)
        except Exception:
            gross_pay = basic_pay
    daily_rate = gross_pay / 30.0 if gross_pay else 0.0

    gratuity = 0.0
    bonus_unpaid = 0.0
    gratuity_years = 0
    gratuity_eligible = False
    if contract:
        from payroll.methods.india_statutory import calculate_bonus_fnf, calculate_gratuity

        g = calculate_gratuity(basic_pay, join_date, last_working_day)
        gratuity = g["amount"]
        gratuity_eligible = g["eligible"]
        gratuity_years = g["years"]
        b = calculate_bonus_fnf(basic_pay, gross_pay, join_date, last_working_day)
        bonus_unpaid = b["amount"]

    unused_leave_days = 0.0
    encashable = AvailableLeave.objects.filter(
        employee_id=employee,
        leave_type_id__is_encashable=True,
    )
    for row in encashable:
        unused_leave_days += float(row.available_days or 0) + float(
            row.carryforward_days or 0
        )
    leave_encashment = round(unused_leave_days * daily_rate, 2)

    notice_period_pay = 0.0
    notice_days = 0
    try:
        from offboarding.models import OffboardingEmployee

        ob = OffboardingEmployee.objects.filter(employee_id=employee).first()
        if ob and ob.notice_period:
            notice_end = ob.notice_period_ends
            if not notice_end:
                start = ob.notice_period_starts or last_working_day
                extra_days = (
                    int(ob.notice_period)
                    if ob.unit == "day"
                    else int(ob.notice_period) * 30
                )
                notice_end = start + timedelta(days=extra_days)
            remaining_notice_days = max(0, (notice_end - last_working_day).days)
            if remaining_notice_days > 0:
                notice_days = remaining_notice_days
                notice_period_pay = round(notice_days * daily_rate, 2)
    except Exception:
        pass

    loan_recovery = 0.0
    loan_lines = []
    for loan in LoanAccount.objects.filter(employee_id=employee, settled=False):
        outstanding = loan_outstanding_amount(loan)
        if outstanding <= 0:
            continue
        loan_recovery += outstanding
        loan_lines.append(
            {
                "title": loan.title,
                "type": loan.type,
                "amount": outstanding,
            }
        )
    loan_recovery = round(loan_recovery, 2)

    pending_claims = 0.0
    claim_lines = []
    for claim in Reimbursement.objects.filter(
        employee_id=employee, status="requested"
    ):
        amount = float(claim.amount or 0)
        pending_claims += amount
        claim_lines.append({"title": claim.title, "amount": amount})
    pending_claims = round(pending_claims, 2)

    outstanding_assets = 0
    asset_lines = []
    if apps.is_installed("asset"):
        from asset.models import AssetAssignment

        open_assets = AssetAssignment.objects.filter(
            assigned_to_employee_id=employee, return_status__isnull=True
        ).select_related("asset_id")
        outstanding_assets = open_assets.count()
        for row in open_assets[:20]:
            asset_lines.append(str(row.asset_id))

    totals = compute_fnf_totals(
        gratuity=gratuity,
        bonus_unpaid=bonus_unpaid,
        leave_encashment=leave_encashment,
        notice_period_pay=notice_period_pay,
        loan_recovery=loan_recovery,
    )

    return {
        "employee": employee,
        "last_working_day": last_working_day,
        "join_date": join_date,
        "years_of_service": round(years, 2),
        "gratuity_years": gratuity_years,
        "basic_pay": basic_pay,
        "gross_pay": gross_pay,
        "daily_rate": round(daily_rate, 2),
        "gratuity": gratuity,
        "gratuity_eligible": gratuity_eligible,
        "bonus_unpaid": bonus_unpaid,
        "unused_leave_days": round(unused_leave_days, 2),
        "leave_encashment": leave_encashment,
        "notice_days": notice_days,
        "notice_period_pay": notice_period_pay,
        "loan_recovery": loan_recovery,
        "loan_lines": loan_lines,
        "pending_claims": pending_claims,
        "claim_lines": claim_lines,
        "outstanding_assets": outstanding_assets,
        "asset_lines": asset_lines,
        "other_additions": 0.0,
        "other_deductions": 0.0,
        **totals,
    }


def apply_estimate_to_settlement(record, estimate: dict[str, Any], *, keep_adjustments: bool = True):
    """Copy live estimate fields onto a persisted F&F record."""
    record.last_working_day = estimate.get("last_working_day")
    record.years_of_service = estimate.get("years_of_service") or 0
    record.gratuity = estimate.get("gratuity") or 0
    record.gratuity_eligible = bool(estimate.get("gratuity_eligible"))
    record.bonus_unpaid = estimate.get("bonus_unpaid") or 0
    record.leave_encashment = estimate.get("leave_encashment") or 0
    record.unused_leave_days = estimate.get("unused_leave_days") or 0
    record.notice_period_pay = estimate.get("notice_period_pay") or 0
    record.notice_days = estimate.get("notice_days") or 0
    record.outstanding_assets = estimate.get("outstanding_assets") or 0
    if not keep_adjustments or not record.pk:
        record.loan_recovery = estimate.get("loan_recovery") or 0
    record.recompute_totals()
    return record
