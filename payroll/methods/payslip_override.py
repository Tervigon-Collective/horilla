"""Audited payslip component / net overrides."""

from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from payroll.methods.payroll_run_engine import PayrollRunLockedError, assert_payslip_mutable
from payroll.models.salary_revision import PayslipOverride


@transaction.atomic
def apply_payslip_override(
    payslip,
    *,
    field_name: str,
    revised_value: float,
    reason: str,
    requested_by=None,
    approved_by=None,
    component_title: str | None = None,
    attachment=None,
) -> PayslipOverride:
    """
    Apply a manual override and persist an audit row.

    Blocked when the payslip/run is locked. Visually identifiable via Overrides M2M.
    """
    if not reason or not str(reason).strip():
        raise ValueError("Override reason is required")

    assert_payslip_mutable(payslip)

    field_map = {
        "basic_pay": "basic_pay",
        "gross_pay": "gross_pay",
        "deduction": "deduction",
        "net_pay": "net_pay",
    }
    if field_name not in field_map and field_name != "component":
        raise ValueError(f"Unsupported override field: {field_name}")

    if field_name == "component":
        if not component_title:
            raise ValueError("component_title is required for component overrides")
        original = _find_component_amount(payslip, component_title)
        _set_component_amount(payslip, component_title, float(revised_value))
        payslip.save(update_fields=["pay_head_data"])
    else:
        attr = field_map[field_name]
        original = float(getattr(payslip, attr) or 0)
        setattr(payslip, attr, float(revised_value))
        # Keep JSON head in sync for net/gross display
        head = payslip.pay_head_data or {}
        if isinstance(head, dict):
            head[attr] = float(revised_value)
            head.setdefault("manual_overrides", [])
            if isinstance(head["manual_overrides"], list):
                head["manual_overrides"].append(
                    {
                        "field": field_name,
                        "original": original,
                        "revised": float(revised_value),
                        "reason": reason,
                    }
                )
            payslip.pay_head_data = head
        payslip.save(update_fields=[attr, "pay_head_data"])

    return PayslipOverride.objects.create(
        payslip=payslip,
        field_name=field_name,
        component_title=component_title or "",
        original_value=original,
        revised_value=float(revised_value),
        reason=reason.strip(),
        attachment=attachment,
        requested_by=requested_by,
        approved_by=approved_by or requested_by,
        approved_at=timezone.now(),
    )


def _find_component_amount(payslip, title: str) -> float:
    head = payslip.pay_head_data or {}
    title_l = title.strip().lower()
    for key in ("allowances", "pretax_deductions", "post_tax_deductions", "tax_deductions"):
        for row in head.get(key) or []:
            if str(row.get("title") or "").strip().lower() == title_l:
                return float(row.get("amount") or 0)
    return 0.0


def _set_component_amount(payslip, title: str, amount: float) -> None:
    head = payslip.pay_head_data or {}
    title_l = title.strip().lower()
    for key in ("allowances", "pretax_deductions", "post_tax_deductions", "tax_deductions"):
        for row in head.get(key) or []:
            if str(row.get("title") or "").strip().lower() == title_l:
                row["amount"] = amount
                row["manually_overridden"] = True
                payslip.pay_head_data = head
                return
    raise ValueError(f"Component '{title}' not found on payslip")


def lock_run_attendance(run, *, actor=None) -> None:
    """Mark attendance finalized for the payroll period."""
    from django.utils import timezone

    if run.is_immutable:
        raise PayrollRunLockedError("Cannot change attendance lock on an immutable run")
    run.attendance_locked = True
    run.attendance_locked_at = timezone.now()
    run.save(update_fields=["attendance_locked", "attendance_locked_at"])
