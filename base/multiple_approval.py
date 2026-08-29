"""
Shared multi-level approval helpers for leave / reimbursement / overtime.

Config lives on MultipleApprovalCondition + MultipleApprovalManagers.
Per-request stage rows are module-specific (LeaveRequestConditionApproval, etc.).
"""

from __future__ import annotations

import operator
from typing import Any, Optional

OPERATOR_MAPPING = {
    "equal": operator.eq,
    "notequal": operator.ne,
    "lt": operator.lt,
    "gt": operator.gt,
    "le": operator.le,
    "ge": operator.ge,
    "icontains": operator.contains,
}


def find_applicable_condition(*, department, company, condition_field: str, value):
    """Return the first matching MultipleApprovalCondition for a numeric field value."""
    from base.models import MultipleApprovalCondition

    if department is None or company is None or not condition_field:
        return None
    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        return None

    conditions = MultipleApprovalCondition.objects.filter(
        department=department,
        company_id=company,
        condition_field=condition_field,
    ).order_by("condition_value")

    for condition in conditions:
        if condition.condition_operator == "range":
            try:
                start_value = float(condition.condition_start_value)
                end_value = float(condition.condition_end_value)
            except (TypeError, ValueError):
                continue
            if start_value <= numeric_value <= end_value:
                return condition
            continue
        operator_func = OPERATOR_MAPPING.get(condition.condition_operator)
        if not operator_func:
            continue
        try:
            condition_value = type(numeric_value)(condition.condition_value)
        except (TypeError, ValueError):
            continue
        if operator_func(numeric_value, condition_value):
            return condition
    return None


def sync_approval_stages(
    *,
    stage_model,
    fk_name: str,
    request_obj,
    employee,
    condition,
):
    """
    Create ordered stage rows for a request. Never wipe once any stage is approved.
    Rebuild only when no approvals have started yet (condition/managers may have changed).
    """
    from employee.models import Employee

    if condition is None:
        return

    filter_kwargs = {fk_name: request_obj}
    existing = stage_model.objects.filter(**filter_kwargs)
    if existing.filter(is_approved=True).exists():
        return
    if existing.exists():
        existing.delete()

    sequence = 0
    for manager in condition.approval_managers():
        if not isinstance(manager, Employee):
            work_info = getattr(employee, "employee_work_info", None)
            manager = getattr(work_info, manager, None) if work_info else None
        if manager:
            sequence += 1
            stage_model.objects.create(
                sequence=sequence,
                manager_id=manager,
                **{fk_name: request_obj},
            )


def approval_progress(stages) -> dict[str, Any]:
    stages = list(stages)
    if not stages:
        return {
            "is_multi_level": False,
            "approval_level": None,
            "approved_count": 0,
            "total_levels": 0,
            "your_turn": False,
            "pending_manager_id": None,
        }
    approved_count = sum(1 for s in stages if s.is_approved)
    pending = next((s for s in stages if not s.is_approved and not s.is_rejected), None)
    return {
        "is_multi_level": True,
        "approval_level": pending.sequence if pending else None,
        "approved_count": approved_count,
        "total_levels": len(stages),
        "your_turn": False,
        "pending_manager_id": pending.manager_id_id if pending else None,
    }


def assert_can_approve_stage(stages, employee, *, is_superuser=False):
    """
    Return the pending stage row to approve, or None when there are no stages
    (single-level flow). Raises ValueError if out of order / wrong approver.
    """
    stages = list(stages)
    if not stages:
        return None
    if is_superuser:
        return stages[-1]

    pending = next((s for s in stages if not s.is_approved and not s.is_rejected), None)
    if pending is None:
        raise ValueError("All approval stages are already complete.")
    if not employee or pending.manager_id_id != employee.id:
        raise ValueError("You are not the current-stage approver for this request.")
    if pending.sequence > 1:
        prev_ok = any(
            s.sequence == pending.sequence - 1 and s.is_approved for s in stages
        )
        if not prev_ok:
            raise ValueError("Previous approval stage is not complete yet.")
    return pending


def current_stage_parent_ids(
    stage_model,
    *,
    manager,
    fk_id_field: str,
    request_status_filter: Optional[dict] = None,
) -> list[int]:
    """Parent object IDs where `manager` is the current pending stage approver."""
    if not manager:
        return []
    pending_for_me = stage_model.objects.filter(
        manager_id=manager,
        is_approved=False,
        is_rejected=False,
    )
    if request_status_filter:
        pending_for_me = pending_for_me.filter(**request_status_filter)

    ids: list[int] = []
    for instance in pending_for_me:
        if instance.sequence > 1:
            prev_filter = {
                fk_id_field: getattr(instance, fk_id_field),
                "sequence": instance.sequence - 1,
                "is_approved": True,
            }
            if not stage_model.objects.filter(**prev_filter).exists():
                continue
        ids.append(getattr(instance, fk_id_field))
    return ids


def multi_ids_in_progress(
    stage_model,
    *,
    fk_id_field: str,
    request_status_filter: Optional[dict] = None,
) -> list[int]:
    """Parent IDs that still have an open multi-approval stage."""
    qs = stage_model.objects.filter(is_approved=False, is_rejected=False)
    if request_status_filter:
        qs = qs.filter(**request_status_filter)
    return list(qs.values_list(fk_id_field, flat=True))
