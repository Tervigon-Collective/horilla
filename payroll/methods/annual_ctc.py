"""
Annual CTC composition and structure-aware payroll helpers.
"""

from __future__ import annotations

from datetime import date
from typing import Any


def annual_ctc_for_employee(employee, *, as_of: date | None = None) -> dict[str, Any]:
    """
    Annual CTC = recurring monthly × 12 + one-time / yearly CTC components.

    Recurring: basic + fixed allowances marked include_in_ctc (or all fixed if unset).
    Non-recurring: one_time_date allowances in the FY containing as_of.
    """
    from payroll.methods.ctc_wizard import structure_as_of
    from payroll.models.models import Allowance, Contract

    as_of = as_of or date.today()
    structure = structure_as_of(employee, as_of)
    monthly = float(structure.get("monthly_ctc") or 0)
    if monthly <= 0:
        contract = Contract.objects.filter(
            employee_id=employee, contract_status="active"
        ).first()
        if contract:
            from payroll.methods.ctc_wizard import current_ctc_snapshot

            monthly = float(current_ctc_snapshot(contract).get("monthly_ctc") or 0)

    recurring_annual = round(monthly * 12, 2)

    # FY Apr–Mar
    fy_start_year = as_of.year if as_of.month >= 4 else as_of.year - 1
    fy_start = date(fy_start_year, 4, 1)
    fy_end = date(fy_start_year + 1, 3, 31)

    one_time = 0.0
    one_time_lines = []
    for allowance in Allowance.objects.filter(
        specific_employees=employee,
        is_active=True,
        one_time_date__gte=fy_start,
        one_time_date__lte=fy_end,
    ):
        if getattr(allowance, "include_in_ctc", True) is False:
            continue
        amt = float(allowance.amount or 0)
        one_time += amt
        one_time_lines.append(
            {
                "title": allowance.title,
                "amount": amt,
                "date": allowance.one_time_date.isoformat(),
            }
        )

    return {
        "monthly_ctc": round(monthly, 2),
        "recurring_annual": recurring_annual,
        "non_recurring": round(one_time, 2),
        "annual_ctc": round(recurring_annual + one_time, 2),
        "one_time_lines": one_time_lines,
        "structure": structure,
        "as_of": as_of.isoformat(),
    }


def apply_structure_to_allowance_lines(
    allowances: list[dict],
    structure: dict[str, Any] | None,
) -> list[dict]:
    """Replace HRA / Special amounts with structure-as-of values when present."""
    if not structure or structure.get("source") not in ("revision", "contract"):
        return allowances
    hra = float(structure.get("hra") or 0)
    special = float(structure.get("special") or 0)
    for row in allowances:
        title = str(row.get("title") or "").strip().lower()
        if title in ("hra", "house rent allowance"):
            row["amount"] = hra
            row["structure_replayed"] = True
        elif title in ("special allowance", "special"):
            row["amount"] = special
            row["structure_replayed"] = True
    # Ensure HRA/Special exist when structure has them but allowance list does not
    titles = {str(r.get("title") or "").strip().lower() for r in allowances}
    if hra > 0 and not titles.intersection({"hra", "house rent allowance"}):
        allowances.append(
            {
                "title": "HRA",
                "amount": hra,
                "structure_replayed": True,
                "is_taxable": True,
            }
        )
    if special > 0 and not titles.intersection({"special allowance", "special"}):
        allowances.append(
            {
                "title": "Special Allowance",
                "amount": special,
                "structure_replayed": True,
                "is_taxable": True,
            }
        )
    return allowances
