"""
Payroll run orchestration: create, calculate, validate, approve, lock, publish.

Guards locked periods so save_payslip / regenerate cannot silently overwrite.
"""

from __future__ import annotations

import calendar
import json
from datetime import date, datetime
from typing import Any

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from payroll.methods.ctc_wizard import is_salary_on_hold, structure_as_of
from payroll.methods.methods import calculate_employer_contribution, save_payslip
from payroll.methods.proration import eligible_for_period, payable_window
from payroll.models.models import Contract, Payslip
from payroll.models.payroll_run import (
    IMMUTABLE_RUN_STATUSES,
    PayrollRun,
)


class PayrollRunLockedError(Exception):
    """Raised when mutating a locked / paid / published payroll period."""


def period_bounds(year: int, month: int) -> tuple[date, date]:
    last = calendar.monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last)


def get_company_for_employee(employee):
    work = getattr(employee, "employee_work_info", None)
    return getattr(work, "company_id", None) if work else None


def find_immutable_run(company, start_date: date, end_date: date) -> PayrollRun | None:
    if not company:
        return None
    return (
        PayrollRun.objects.filter(
            company_id=company,
            period_start__lte=end_date,
            period_end__gte=start_date,
            status__in=IMMUTABLE_RUN_STATUSES,
        )
        .order_by("-version")
        .first()
    )


def assert_period_mutable(employee, start_date: date, end_date: date) -> None:
    """Block recalculation when a locked run covers this employee period."""
    company = get_company_for_employee(employee)
    locked = find_immutable_run(company, start_date, end_date)
    if locked:
        raise PayrollRunLockedError(
            f"Payroll {locked.period_label} v{locked.version} is {locked.status} "
            f"and cannot be recalculated. Reopen with a new version if correction is needed."
        )


def assert_payslip_mutable(payslip: Payslip) -> None:
    run = getattr(payslip, "payroll_run", None)
    if run and run.is_immutable:
        raise PayrollRunLockedError(
            f"Payslip belongs to locked payroll run {run} and cannot be changed."
        )
    assert_period_mutable(payslip.employee_id, payslip.start_date, payslip.end_date)


def create_payroll_run(
    company,
    *,
    year: int | None = None,
    month: int | None = None,
    period_start: date | None = None,
    period_end: date | None = None,
    proration_method: str = "calendar",
    notes: str = "",
    created_by=None,
) -> PayrollRun:
    today = date.today()
    year = year or today.year
    month = month or today.month
    if period_start is None or period_end is None:
        period_start, period_end = period_bounds(year, month)

    latest = (
        PayrollRun.objects.filter(company_id=company, year=year, month=month)
        .order_by("-version")
        .first()
    )
    # Reuse the active mutable version for this month.
    if latest and not latest.is_immutable:
        return latest

    version = (latest.version + 1) if latest else 1
    group_name = f"PR-{year}{month:02d}-v{version}"
    return PayrollRun.objects.create(
        company_id=company,
        year=year,
        month=month,
        period_start=period_start,
        period_end=period_end,
        status="open",
        version=version,
        parent_run=latest if latest else None,
        group_name=group_name,
        proration_method=proration_method or "calendar",
        notes=notes or "",
    )


def _employee_doj_lwd(employee) -> tuple[date | None, date | None]:
    work = getattr(employee, "employee_work_info", None)
    doj = getattr(work, "date_joining", None) if work else None
    lwd = getattr(work, "contract_end_date", None) if work else None
    return doj, lwd


def eligible_employees_for_run(run: PayrollRun):
    """Active employees in company with active contract, not exited before period."""
    from employee.models import Employee

    qs = Employee.objects.filter(
        is_active=True,
        employee_work_info__company_id=run.company_id,
        contract_set__contract_status="active",
    ).distinct()

    eligible = []
    for emp in qs:
        doj, lwd = _employee_doj_lwd(emp)
        if eligible_for_period(
            run.period_start, run.period_end, doj=doj, lwd=lwd
        ):
            eligible.append(emp)
    return eligible


def calculate_payroll_run(
    run: PayrollRun,
    *,
    employee_ids: list[int] | None = None,
    require_attendance_lock: bool = True,
) -> dict[str, Any]:
    """Calculate (or recalculate) draft payslips for a mutable run."""
    if run.is_immutable:
        raise PayrollRunLockedError(f"Cannot calculate immutable run {run}")
    if require_attendance_lock and not run.attendance_locked:
        raise PayrollRunLockedError(
            "Lock attendance for this payroll period before calculating."
        )

    from payroll.methods.attendance_arrear import settle_attendance_arrears_for_period
    from payroll.views.component_views import payroll_calculation

    employees = eligible_employees_for_run(run)
    if employee_ids:
        id_set = set(employee_ids)
        employees = [e for e in employees if e.pk in id_set]

    created = 0
    skipped = 0
    errors: list[dict[str, Any]] = []

    for employee in employees:
        profile = None
        try:
            from payroll.methods.india_statutory import get_employee_statutory_profile

            profile = get_employee_statutory_profile(employee)
        except Exception:
            profile = None
        if profile and getattr(profile, "payroll_status", "included") == "excluded":
            skipped += 1
            errors.append(
                {
                    "employee_id": employee.pk,
                    "level": "warning",
                    "code": "payroll_excluded",
                    "message": f"{employee} payroll status is Excluded — skipped",
                }
            )
            continue
        if profile and getattr(profile, "payroll_status", "included") == "on_hold":
            skipped += 1
            errors.append(
                {
                    "employee_id": employee.pk,
                    "level": "warning",
                    "code": "payroll_on_hold",
                    "message": f"{employee} payroll status is On Hold — skipped",
                }
            )
            continue

        if is_salary_on_hold(employee):
            skipped += 1
            errors.append(
                {
                    "employee_id": employee.pk,
                    "level": "warning",
                    "code": "salary_hold",
                    "message": f"{employee} is on salary hold — skipped",
                }
            )
            continue

        contract = Contract.objects.filter(
            employee_id=employee, contract_status="active"
        ).first()
        if not contract:
            skipped += 1
            errors.append(
                {
                    "employee_id": employee.pk,
                    "level": "error",
                    "code": "missing_contract",
                    "message": f"{employee} has no active contract",
                }
            )
            continue

        doj, lwd = _employee_doj_lwd(employee)
        window = payable_window(
            run.period_start, run.period_end, doj=doj, lwd=lwd
        )
        if not window:
            skipped += 1
            continue
        start_date, end_date = window
        if contract.contract_start_date and start_date < contract.contract_start_date:
            start_date = contract.contract_start_date
        if end_date < start_date:
            skipped += 1
            errors.append(
                {
                    "employee_id": employee.pk,
                    "level": "error",
                    "code": "contract_not_started",
                    "message": f"{employee} contract has not started",
                }
            )
            continue

        try:
            with transaction.atomic():
                # Settle retro attendance arrears into this open month before calc
                try:
                    settle_attendance_arrears_for_period(employee, start_date, end_date)
                except Exception as exc:
                    errors.append(
                        {
                            "employee_id": employee.pk,
                            "level": "warning",
                            "code": "arrear_settle",
                            "message": f"{employee}: attendance arrear settle issue: {exc}",
                        }
                    )

                structure = structure_as_of(employee, end_date)
                payslip_data = payroll_calculation(
                    employee, start_date, end_date, structure_override=structure
                )
                if not payslip_data:
                    skipped += 1
                    errors.append(
                        {
                            "employee_id": employee.pk,
                            "level": "error",
                            "code": "calc_failed",
                            "message": f"Could not calculate payroll for {employee}",
                        }
                    )
                    continue

                pay_data = json.loads(payslip_data["json_data"])
                from payroll.methods.annual_ctc import annual_ctc_for_employee

                pay_data["structure_version"] = {
                    "source": structure.get("source"),
                    "version": structure.get("version"),
                    "revision_id": structure.get("revision_id"),
                    "basic": structure.get("basic"),
                    "hra": structure.get("hra"),
                    "special": structure.get("special"),
                    "proration_method": run.proration_method,
                    "payable_start": start_date.isoformat(),
                    "payable_end": end_date.isoformat(),
                    "attendance_locked": run.attendance_locked,
                }
                pay_data["annual_ctc"] = annual_ctc_for_employee(employee, as_of=end_date)

                data = {
                    "employee": employee,
                    "group_name": run.group_name,
                    "start_date": payslip_data["start_date"],
                    "end_date": payslip_data["end_date"],
                    "status": "draft",
                    "contract_wage": payslip_data["contract_wage"],
                    "basic_pay": payslip_data["basic_pay"],
                    "gross_pay": payslip_data["gross_pay"],
                    "deduction": payslip_data["total_deductions"],
                    "net_pay": payslip_data["net_pay"],
                    "pay_data": pay_data,
                    "installments": payslip_data["installments"],
                    "payroll_run": run,
                    "force": True,
                }
                calculate_employer_contribution(data)
                save_payslip(**data)
            created += 1
        except Exception as exc:
            skipped += 1
            errors.append(
                {
                    "employee_id": employee.pk,
                    "level": "error",
                    "code": "calc_exception",
                    "message": f"Payroll calculation failed for {employee}: {exc}",
                }
            )

    with transaction.atomic():
        run.status = "calculated"
        run.save(update_fields=["status"])
    return {"created": created, "skipped": skipped, "errors": errors}


def validate_payroll_run(run: PayrollRun) -> dict[str, Any]:
    """Flag critical errors and review warnings before approval."""
    slips = Payslip.objects.filter(payroll_run=run).select_related("employee_id")
    # Also pick up slips in the same period/group if not yet linked
    if not slips.exists():
        slips = Payslip.objects.filter(
            group_name=run.group_name,
            start_date__gte=run.period_start,
            end_date__lte=run.period_end,
            employee_id__employee_work_info__company_id=run.company_id,
        ).select_related("employee_id")

    errors: list[dict] = []
    warnings: list[dict] = []
    prev_start, prev_end = _previous_month_bounds(run.period_start)

    for slip in slips:
        emp = slip.employee_id
        contract = Contract.objects.filter(
            employee_id=emp, contract_status="active"
        ).first()
        if not contract:
            errors.append(
                {
                    "employee_id": emp.pk,
                    "code": "missing_salary_structure",
                    "message": f"{emp}: missing active contract / salary structure",
                }
            )
        work = getattr(emp, "employee_work_info", None)
        bank = getattr(work, "bank_account_number", None) or getattr(
            work, "account_number", None
        )
        if work and not bank:
            # bank field names vary; warn if joining date missing instead as critical
            pass
        if not getattr(work, "date_joining", None):
            errors.append(
                {
                    "employee_id": emp.pk,
                    "code": "missing_joining_date",
                    "message": f"{emp}: missing joining date",
                }
            )
        if float(slip.net_pay or 0) < 0:
            errors.append(
                {
                    "employee_id": emp.pk,
                    "code": "negative_net_pay",
                    "message": f"{emp}: negative net pay {slip.net_pay}",
                }
            )
        if float(slip.gross_pay or 0) == 0 and float(slip.net_pay or 0) == 0:
            warnings.append(
                {
                    "employee_id": emp.pk,
                    "code": "zero_salary",
                    "message": f"{emp}: unexpected zero salary",
                }
            )

        # MoM variance warnings
        prev = Payslip.objects.filter(
            employee_id=emp,
            start_date=prev_start,
            end_date=prev_end,
            status__in=["confirmed", "paid", "draft", "review_ongoing"],
        ).first()
        if prev and float(prev.gross_pay or 0) > 0:
            change = (
                (float(slip.gross_pay or 0) - float(prev.gross_pay or 0))
                / float(prev.gross_pay)
                * 100.0
            )
            if abs(change) >= 20:
                warnings.append(
                    {
                        "employee_id": emp.pk,
                        "code": "gross_changed",
                        "message": (
                            f"{emp}: gross changed {change:.1f}% "
                            f"({prev.gross_pay} → {slip.gross_pay})"
                        ),
                    }
                )

    report = {
        "errors": errors,
        "warnings": warnings,
        "payslip_count": slips.count(),
        "validated_at": timezone.now().isoformat(),
    }
    run.validation_report = report
    run.status = "validation_failed" if errors else "validation_passed"
    run.save(update_fields=["validation_report", "status"])

    # Link unlinked slips in this batch
    Payslip.objects.filter(
        group_name=run.group_name,
        payroll_run__isnull=True,
        start_date__gte=run.period_start,
        end_date__lte=run.period_end,
    ).update(payroll_run=run)

    variance = build_variance_report(run)
    run.variance_report = variance
    run.save(update_fields=["variance_report"])
    report["variance"] = variance
    return report


def _previous_month_bounds(period_start: date) -> tuple[date, date]:
    if period_start.month == 1:
        y, m = period_start.year - 1, 12
    else:
        y, m = period_start.year, period_start.month - 1
    return period_bounds(y, m)


def build_variance_report(run: PayrollRun) -> dict[str, Any]:
    slips = Payslip.objects.filter(payroll_run=run)
    if not slips.exists():
        slips = Payslip.objects.filter(group_name=run.group_name)
    current_gross = slips.aggregate(s=Sum("gross_pay"))["s"] or 0
    current_net = slips.aggregate(s=Sum("net_pay"))["s"] or 0
    prev_start, prev_end = _previous_month_bounds(run.period_start)
    prev_slips = Payslip.objects.filter(
        start_date=prev_start,
        end_date=prev_end,
        employee_id__employee_work_info__company_id=run.company_id,
    )
    prev_gross = prev_slips.aggregate(s=Sum("gross_pay"))["s"] or 0
    prev_net = prev_slips.aggregate(s=Sum("net_pay"))["s"] or 0
    delta_gross = float(current_gross) - float(prev_gross)
    pct = (delta_gross / float(prev_gross) * 100.0) if prev_gross else None
    return {
        "previous_gross": round(float(prev_gross), 2),
        "current_gross": round(float(current_gross), 2),
        "gross_variance": round(delta_gross, 2),
        "gross_variance_pct": round(pct, 2) if pct is not None else None,
        "previous_net": round(float(prev_net), 2),
        "current_net": round(float(current_net), 2),
        "current_headcount": slips.count(),
        "previous_headcount": prev_slips.count(),
    }


def transition_run(run: PayrollRun, new_status: str, *, actor=None, reason: str = "") -> PayrollRun:
    if run.is_immutable and new_status not in ("paid", "published"):
        if run.status == "locked" and new_status == "paid":
            pass
        elif run.status == "paid" and new_status == "published":
            pass
        else:
            raise PayrollRunLockedError(f"Cannot move {run.status} → {new_status}")

    if not run.can_transition_to(new_status) and not (
        run.status == "locked" and new_status == "paid"
    ) and not (run.status == "paid" and new_status == "published"):
        raise ValueError(f"Invalid transition {run.status} → {new_status}")

    run.status = new_status
    now = timezone.now()
    update_fields = ["status"]
    if new_status == "locked":
        run.locked_at = now
        run.locked_by = actor
        run.totals_snapshot = {
            "gross": float(
                Payslip.objects.filter(payroll_run=run).aggregate(s=Sum("gross_pay"))["s"]
                or 0
            ),
            "net": float(
                Payslip.objects.filter(payroll_run=run).aggregate(s=Sum("net_pay"))["s"]
                or 0
            ),
            "count": Payslip.objects.filter(payroll_run=run).count(),
            "locked_at": now.isoformat(),
        }
        update_fields += ["locked_at", "locked_by", "totals_snapshot"]
        Payslip.objects.filter(payroll_run=run).update(
            status="confirmed", snapshot_frozen=True
        )
        archive_payroll_snapshots(run)
    elif new_status == "paid":
        run.paid_at = now
        update_fields.append("paid_at")
        Payslip.objects.filter(payroll_run=run).update(status="paid")
    elif new_status == "published":
        run.published_at = now
        update_fields.append("published_at")
        Payslip.objects.filter(payroll_run=run).update(
            sent_to_employee=True, published_at=now
        )
    if reason:
        run.notes = ((run.notes or "") + f"\n[{new_status}] {reason}").strip()
        update_fields.append("notes")
    run.save(update_fields=update_fields)
    return run


def archive_payroll_snapshots(run: PayrollRun) -> int:
    """Copy each payslip payload into PayrollRunSnapshot (immutable archive)."""
    from payroll.models.payroll_run import PayrollRunSnapshot

    count = 0
    for slip in Payslip.objects.filter(payroll_run=run).select_related("employee_id"):
        PayrollRunSnapshot.objects.update_or_create(
            payroll_run=run,
            employee_id=slip.employee_id,
            defaults={
                "payslip_id": slip.pk,
                "payload": {
                    "pay_head_data": slip.pay_head_data or {},
                    "employee_name": str(slip.employee_id),
                    "start_date": slip.start_date.isoformat(),
                    "end_date": slip.end_date.isoformat(),
                    "status": slip.status,
                    "group_name": slip.group_name,
                    "basic_pay": slip.basic_pay,
                    "gross_pay": slip.gross_pay,
                    "deduction": slip.deduction,
                    "net_pay": slip.net_pay,
                    "contract_wage": slip.contract_wage,
                },
                "gross_pay": float(slip.gross_pay or 0),
                "net_pay": float(slip.net_pay or 0),
                "deduction": float(slip.deduction or 0),
            },
        )
        count += 1
    return count


def build_bank_transfer_rows(run: PayrollRun) -> list[dict[str, Any]]:
    """Rows for bank payment file from locked/paid/published run."""
    rows = []
    slips = (
        Payslip.objects.filter(payroll_run=run)
        .select_related("employee_id", "employee_id__employee_work_info")
        .order_by("employee_id_id")
    )
    for slip in slips:
        emp = slip.employee_id
        work = getattr(emp, "employee_work_info", None)
        account = ""
        ifsc = ""
        bank_name = ""
        holder = str(emp)
        if work:
            account = (
                getattr(work, "account_number", None)
                or getattr(work, "bank_account_number", None)
                or ""
            )
            ifsc = getattr(work, "ifsc_code", None) or getattr(work, "bank_ifsc", None) or ""
            bank_name = getattr(work, "bank_name", None) or ""
            holder = getattr(work, "account_holder_name", None) or holder
        rows.append(
            {
                "employee_id": emp.pk,
                "employee_name": str(emp),
                "account_holder": holder,
                "account_number": account,
                "ifsc": ifsc,
                "bank_name": bank_name,
                "amount": float(slip.net_pay or 0),
                "payslip_id": slip.pk,
                "period": f"{slip.start_date} to {slip.end_date}",
            }
        )
    return rows


@transaction.atomic
def reopen_payroll_run(run: PayrollRun, *, reason: str, actor=None) -> PayrollRun:
    """Create a new version after a locked run; never mutate the locked row's calcs."""
    if not run.is_immutable:
        raise ValueError("Only locked/paid/published runs can be reopened into a new version")
    if not reason:
        raise ValueError("Reopen reason is required")

    new_version = run.version + 1
    # Ensure unique version slot
    while PayrollRun.objects.filter(
        company_id=run.company_id, year=run.year, month=run.month, version=new_version
    ).exists():
        new_version += 1

    new_run = PayrollRun.objects.create(
        company_id=run.company_id,
        year=run.year,
        month=run.month,
        period_start=run.period_start,
        period_end=run.period_end,
        attendance_cutoff=run.attendance_cutoff,
        variable_pay_cutoff=run.variable_pay_cutoff,
        status="open",
        version=new_version,
        parent_run=run,
        group_name=f"PR-{run.year}{run.month:02d}-v{new_version}",
        proration_method=run.proration_method,
        reopen_reason=reason,
        notes=f"Reopened from v{run.version} by {actor}: {reason}",
    )
    return new_run
