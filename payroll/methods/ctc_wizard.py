"""
CTC structure wizard — split monthly CTC into Basic, HRA, and Special allowance.

Standard Indian pattern (configurable ratios):
  Basic = 40% of CTC
  HRA = 50% of Basic (metro) or 40% of Basic (non-metro)
  Special = remainder
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any


@dataclass
class CtcSplit:
    monthly_ctc: float
    basic: float
    hra: float
    special: float
    metro: bool

    @property
    def annual_ctc(self) -> float:
        return round(self.monthly_ctc * 12, 2)

    @property
    def annual_basic(self) -> float:
        return round(self.basic * 12, 2)

    @property
    def annual_hra(self) -> float:
        return round(self.hra * 12, 2)

    @property
    def annual_special(self) -> float:
        return round(self.special * 12, 2)


def split_monthly_ctc(
    monthly_ctc: float,
    *,
    metro: bool = True,
    basic_ratio: float = 0.40,
    hra_ratio_of_basic: float | None = None,
) -> CtcSplit:
    """Split monthly CTC into Basic / HRA / Special components."""
    monthly_ctc = max(float(monthly_ctc or 0), 0.0)
    basic_ratio = min(max(basic_ratio, 0.1), 0.7)
    hra_pct = hra_ratio_of_basic if hra_ratio_of_basic is not None else (
        0.50 if metro else 0.40
    )

    basic = round(monthly_ctc * basic_ratio, 2)
    hra = round(basic * hra_pct, 2)
    special = round(max(monthly_ctc - basic - hra, 0.0), 2)

    return CtcSplit(
        monthly_ctc=round(monthly_ctc, 2),
        basic=basic,
        hra=hra,
        special=special,
        metro=metro,
    )


def apply_ctc_split_to_contract(
    contract,
    split: CtcSplit,
    *,
    create_allowances: bool = True,
) -> dict[str, Any]:
    """
    Set contract wage to basic and create/update HRA + Special allowances.
    """
    from payroll.models.models import Allowance

    contract.wage = split.basic
    contract.save(update_fields=["wage"])

    created = []
    if not create_allowances:
        return {"contract": contract, "allowances": created}

    employee = contract.employee_id
    specs = [
        ("HRA", split.hra),
        ("Special Allowance", split.special),
    ]
    for title, amount in specs:
        if amount <= 0:
            continue
        allowance = Allowance.objects.filter(
            title=title, specific_employees=employee
        ).first()
        if allowance:
            allowance.amount = amount
            allowance.is_fixed = True
            allowance.save()
        else:
            allowance = Allowance.objects.create(
                title=title,
                amount=amount,
                is_fixed=True,
                include_active_employees=False,
            )
            allowance.specific_employees.add(employee)
        created.append(allowance)

    return {"contract": contract, "allowances": created, "split": split}


def current_ctc_snapshot(contract) -> dict[str, float]:
    """Reconstruct monthly CTC from contract basic + HRA + Special allowances."""
    from payroll.models.models import Allowance

    employee = contract.employee_id
    basic = float(contract.wage or 0)
    hra = 0.0
    special = 0.0
    for allowance in Allowance.objects.filter(specific_employees=employee, is_fixed=True):
        title = (allowance.title or "").strip().lower()
        amount = float(allowance.amount or 0)
        if title in ("hra", "house rent allowance"):
            hra = amount
        elif title in ("special allowance", "special"):
            special = amount
    monthly = round(basic + hra + special, 2)
    return {
        "monthly_ctc": monthly,
        "basic": round(basic, 2),
        "hra": round(hra, 2),
        "special": round(special, 2),
    }


def record_salary_revision(
    contract,
    split: CtcSplit,
    *,
    previous: dict[str, float] | None = None,
    effective_date: date | None = None,
    note: str = "",
):
    """
    Persist a revision row, close the previous active structure version,
    and compute arrears if effective date is in the past.
    """
    from datetime import timedelta

    from django.db import transaction

    from payroll.models.salary_revision import SalaryRevision

    previous = previous or current_ctc_snapshot(contract)
    effective_date = effective_date or date.today()
    old_ctc = float(previous.get("monthly_ctc") or 0)
    new_ctc = float(split.monthly_ctc)
    increment = 0.0
    if old_ctc > 0:
        increment = round(((new_ctc - old_ctc) / old_ctc) * 100.0, 2)

    arrears_months = 0
    arrears_amount = 0.0
    today = date.today()
    if effective_date < date(today.year, today.month, 1) and new_ctc > old_ctc:
        arrears_months = (
            (today.year - effective_date.year) * 12
            + today.month
            - effective_date.month
        )
        arrears_months = max(0, arrears_months)
        arrears_amount = round((new_ctc - old_ctc) * arrears_months, 2)

    with transaction.atomic():
        active_qs = SalaryRevision.objects.filter(
            employee_id=contract.employee_id,
            status="active",
        ).order_by("-version", "-id")
        latest = active_qs.first()
        next_version = (latest.version + 1) if latest else 1
        # Close all currently active structures (should be one).
        close_to = effective_date - timedelta(days=1)
        for prior in active_qs:
            prior.status = "closed"
            if prior.effective_to is None:
                prior.effective_to = (
                    close_to if close_to >= prior.effective_date else prior.effective_date
                )
            prior.save(update_fields=["status", "effective_to"])

        return SalaryRevision.objects.create(
            employee_id=contract.employee_id,
            contract_id=contract,
            effective_date=effective_date,
            effective_to=None,
            version=next_version,
            status="active",
            previous_monthly_ctc=old_ctc,
            new_monthly_ctc=new_ctc,
            previous_basic=float(previous.get("basic") or 0),
            new_basic=split.basic,
            new_hra=split.hra,
            new_special=split.special,
            metro=split.metro,
            increment_percent=increment,
            arrears_months=arrears_months,
            arrears_amount=arrears_amount,
            note=note or "",
        )


def structure_as_of(employee, as_of: date | None = None) -> dict[str, float | int | str | None]:
    """
    Return the salary structure that applied on as_of (default today).

    Prefers versioned SalaryRevision history; falls back to live contract snapshot.
    """
    from payroll.models.salary_revision import SalaryRevision

    as_of = as_of or date.today()
    revision = (
        SalaryRevision.objects.filter(
            employee_id=employee,
            effective_date__lte=as_of,
        )
        .filter(models_q_effective_to(as_of))
        .order_by("-effective_date", "-version", "-id")
        .first()
    )
    if revision:
        return {
            "source": "revision",
            "revision_id": revision.pk,
            "version": revision.version,
            "status": revision.status,
            "effective_date": revision.effective_date.isoformat(),
            "effective_to": revision.effective_to.isoformat()
            if revision.effective_to
            else None,
            "monthly_ctc": float(revision.new_monthly_ctc or 0),
            "basic": float(revision.new_basic or 0),
            "hra": float(revision.new_hra or 0),
            "special": float(revision.new_special or 0),
        }

    from payroll.models.models import Contract

    contract = Contract.objects.filter(
        employee_id=employee, contract_status="active"
    ).first()
    if not contract:
        return {
            "source": "none",
            "monthly_ctc": 0.0,
            "basic": 0.0,
            "hra": 0.0,
            "special": 0.0,
        }
    snap = current_ctc_snapshot(contract)
    snap["source"] = "contract"
    snap["version"] = None
    return snap


def models_q_effective_to(as_of: date):
    """Q: effective_to is null OR effective_to >= as_of."""
    from django.db.models import Q

    return Q(effective_to__isnull=True) | Q(effective_to__gte=as_of)


def is_salary_on_hold(employee) -> bool:
    """True when the employee has an active, unreleased salary hold."""
    from payroll.models.salary_revision import SalaryHold

    return SalaryHold.objects.filter(
        employee_id=employee, is_active=True, released_on__isnull=True
    ).exists()


def hold_salary(employee, *, reason: str = "", held_by=None, held_on: date | None = None):
    """Place (or keep) an active salary hold on the employee."""
    from payroll.models.salary_revision import SalaryHold

    held_on = held_on or date.today()
    existing = SalaryHold.objects.filter(
        employee_id=employee, is_active=True, released_on__isnull=True
    ).first()
    if existing:
        if reason:
            existing.reason = reason
            existing.save(update_fields=["reason"])
        return existing
    return SalaryHold.objects.create(
        employee_id=employee,
        reason=reason or "",
        held_on=held_on,
        held_by=held_by,
        is_active=True,
    )


def release_salary(employee, *, released_by=None, released_on: date | None = None):
    """Release all active salary holds for the employee."""
    from payroll.models.salary_revision import SalaryHold

    released_on = released_on or date.today()
    holds = SalaryHold.objects.filter(
        employee_id=employee, is_active=True, released_on__isnull=True
    )
    count = 0
    for hold in holds:
        hold.released_on = released_on
        hold.released_by = released_by
        hold.is_active = False
        hold.save(update_fields=["released_on", "released_by", "is_active"])
        count += 1
    return count


def pay_revision_arrears(revision, *, payment_date: date | None = None):
    """
    Create a one-time taxable allowance for unpaid revision arrears.

    The allowance applies to the payslip period that contains payment_date.
    """
    from payroll.models.models import Allowance

    if revision.arrears_paid:
        raise ValueError("Arrears already paid for this revision.")
    amount = float(revision.arrears_amount or 0)
    if amount <= 0:
        raise ValueError("No arrears amount to pay.")

    payment_date = payment_date or date.today()
    title = f"Salary Arrears ({revision.effective_date.isoformat()})"
    allowance = Allowance.objects.create(
        title=title,
        amount=amount,
        is_fixed=True,
        include_active_employees=False,
        one_time_date=payment_date,
        only_show_under_employee=True,
        is_taxable=True,
    )
    allowance.specific_employees.add(revision.employee_id)

    revision.arrears_paid = True
    revision.arrears_paid_on = payment_date
    revision.arrears_allowance = allowance
    revision.save(
        update_fields=["arrears_paid", "arrears_paid_on", "arrears_allowance"]
    )
    return allowance
