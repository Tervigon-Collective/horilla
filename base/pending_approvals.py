"""
Unified pending-approval helpers for web dashboard and mobile API.

Provides scoped querysets, inbox serialization, and a thin action dispatcher
that delegates to existing module-specific API views.
"""

from __future__ import annotations

from typing import Any

from django.utils.translation import gettext_lazy as _
from rest_framework import status
from rest_framework.response import Response

from base.dashboard import _is_manager, get_pending_approvals_counts


def get_approval_context(user) -> dict[str, Any]:
    """Shared permission/manager context for pending approval scoping."""
    has_leave_perm = user.has_perm("leave.change_leaverequest")
    has_attendance_perm = user.has_perm("attendance.change_validateattendance")
    has_asset_perm = user.has_perm("asset.change_assetrequest")
    has_shift_perm = user.has_perm("base.change_shiftrequest")
    has_wt_perm = user.has_perm("base.change_worktyperequest")
    has_reimb_perm = user.has_perm("payroll.change_reimbursement")
    is_mgr = _is_manager(user)

    can_approve = any(
        [
            has_leave_perm,
            has_attendance_perm,
            has_asset_perm,
            has_shift_perm,
            has_wt_perm,
            has_reimb_perm,
            is_mgr,
        ]
    )

    return {
        "can_approve": can_approve,
        "is_restricted": not can_approve,
        "employee": getattr(user, "employee_get", None),
        "has_leave_perm": has_leave_perm,
        "has_attendance_perm": has_attendance_perm,
        "has_asset_perm": has_asset_perm,
        "has_shift_perm": has_shift_perm,
        "has_wt_perm": has_wt_perm,
        "has_reimb_perm": has_reimb_perm,
        "is_mgr": is_mgr,
    }


def _employee_payload(employee) -> dict[str, Any]:
    if not employee:
        return {}
    return {
        "id": employee.id,
        "full_name": employee.get_full_name(),
        "badge_id": getattr(employee, "badge_id", "") or "",
    }


def _iso_date(value) -> str | None:
    if not value:
        return None
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def pending_leave_queryset(request):
    from leave.models import LeaveRequest

    ctx = get_approval_context(request.user)
    if ctx["can_approve"]:
        if ctx["has_leave_perm"]:
            return LeaveRequest.objects.filter(status="requested")
        from base.methods import filtersubordinates

        qs = LeaveRequest.objects.filter(status="requested")
        return filtersubordinates(request, qs, "leave.change_leaverequest")
    employee = ctx["employee"]
    if not employee:
        return LeaveRequest.objects.none()
    return LeaveRequest.objects.filter(employee_id=employee, status="requested")


def pending_attendance_queryset(request):
    from attendance.models import Attendance

    ctx = get_approval_context(request.user)
    base = Attendance.objects.filter(
        is_validate_request=True,
        is_validate_request_approved=False,
    )
    if ctx["can_approve"]:
        if ctx["has_attendance_perm"]:
            return base
        from base.methods import filtersubordinates

        return filtersubordinates(request, base, "attendance.change_validateattendance")
    employee = ctx["employee"]
    if not employee:
        return Attendance.objects.none()
    return base.filter(employee_id=employee)


def pending_asset_queryset(request):
    from asset.models import AssetRequest

    ctx = get_approval_context(request.user)
    if ctx["can_approve"] and ctx["has_asset_perm"]:
        return AssetRequest.objects.filter(asset_request_status="Requested")
    employee = ctx["employee"]
    if not employee:
        return AssetRequest.objects.none()
    return AssetRequest.objects.filter(
        requested_employee_id=employee,
        asset_request_status="Requested",
    )


def pending_shift_queryset(request):
    from base.models import ShiftRequest

    ctx = get_approval_context(request.user)
    base = ShiftRequest.objects.filter(approved=False, canceled=False)
    if ctx["can_approve"]:
        if ctx["has_shift_perm"]:
            return base
        from base.methods import filtersubordinates

        return filtersubordinates(request, base, "base.change_shiftrequest")
    employee = ctx["employee"]
    if not employee:
        return ShiftRequest.objects.none()
    return base.filter(employee_id=employee)


def pending_work_type_queryset(request):
    from base.models import WorkTypeRequest

    ctx = get_approval_context(request.user)
    base = WorkTypeRequest.objects.filter(approved=False, canceled=False)
    if ctx["can_approve"]:
        if ctx["has_wt_perm"]:
            return base
        from base.methods import filtersubordinates

        return filtersubordinates(request, base, "base.change_worktyperequest")
    employee = ctx["employee"]
    if not employee:
        return WorkTypeRequest.objects.none()
    return base.filter(employee_id=employee)


def pending_reimbursement_queryset(request):
    from payroll.models.models import Reimbursement

    ctx = get_approval_context(request.user)
    if ctx["can_approve"] and ctx["has_reimb_perm"]:
        return Reimbursement.objects.filter(status="requested")
    employee = ctx["employee"]
    if not employee:
        return Reimbursement.objects.none()
    return Reimbursement.objects.filter(employee_id=employee, status="requested")


def _can_act_on_type(ctx: dict[str, Any], item_type: str) -> bool:
    if ctx["is_restricted"]:
        return False
    perm_map = {
        "leave": ctx["has_leave_perm"] or ctx["is_mgr"],
        "attendance": ctx["has_attendance_perm"] or ctx["is_mgr"],
        "asset": ctx["has_asset_perm"],
        "shift": ctx["has_shift_perm"] or ctx["is_mgr"],
        "work_type": ctx["has_wt_perm"] or ctx["is_mgr"],
        "reimbursement": ctx["has_reimb_perm"],
    }
    return perm_map.get(item_type, False)


def _inbox_item(
    item_type: str,
    obj,
    *,
    summary: str,
    requested_at,
    detail: dict[str, Any],
    ctx: dict[str, Any],
) -> dict[str, Any]:
    return {
        "type": item_type,
        "id": obj.pk,
        "employee": _employee_payload(getattr(obj, "employee_id", None) or getattr(obj, "requested_employee_id", None)),
        "summary": summary,
        "requested_at": _iso_date(requested_at),
        "can_act": _can_act_on_type(ctx, item_type),
        "detail": detail,
    }


def _serialize_leave(obj, ctx):
    leave_type = getattr(obj.leave_type_id, "name", str(obj.leave_type_id))
    return _inbox_item(
        "leave",
        obj,
        summary=f"{leave_type} · {obj.requested_days} days",
        requested_at=obj.requested_date or obj.start_date,
        detail={
            "leave_type": leave_type,
            "start_date": _iso_date(obj.start_date),
            "end_date": _iso_date(obj.end_date),
            "requested_days": obj.requested_days,
            "description": obj.description,
            "status": obj.status,
        },
        ctx=ctx,
    )


def _serialize_attendance(obj, ctx):
    return _inbox_item(
        "attendance",
        obj,
        summary=f"Attendance validation · {obj.attendance_date}",
        requested_at=obj.attendance_date,
        detail={
            "attendance_date": _iso_date(obj.attendance_date),
            "clock_in": str(obj.attendance_clock_in) if obj.attendance_clock_in else None,
            "clock_out": str(obj.attendance_clock_out) if obj.attendance_clock_out else None,
            "request_description": obj.request_description,
        },
        ctx=ctx,
    )


def _serialize_asset(obj, ctx):
    category = getattr(obj, "asset_category_id", None)
    asset_name = (
        getattr(category, "asset_category_name", None) if category else None
    ) or _("Asset request")
    return _inbox_item(
        "asset",
        obj,
        summary=str(asset_name),
        requested_at=getattr(obj, "created_at", None),
        detail={
            "asset_name": str(asset_name),
            "asset_request_status": obj.asset_request_status,
            "request_description": getattr(obj, "description", None),
        },
        ctx=ctx,
    )


def _serialize_shift(obj, ctx):
    shift = getattr(obj.shift_id, "employee_shift", str(obj.shift_id))
    return _inbox_item(
        "shift",
        obj,
        summary=f"Shift change · {shift}",
        requested_at=obj.requested_date,
        detail={
            "shift": str(shift),
            "requested_date": _iso_date(obj.requested_date),
            "requested_till": _iso_date(getattr(obj, "requested_till", None)),
            "description": getattr(obj, "description", None),
        },
        ctx=ctx,
    )


def _serialize_work_type(obj, ctx):
    work_type = getattr(obj.work_type_id, "work_type", str(obj.work_type_id))
    return _inbox_item(
        "work_type",
        obj,
        summary=f"Work type · {work_type}",
        requested_at=obj.requested_date,
        detail={
            "work_type": str(work_type),
            "requested_date": _iso_date(obj.requested_date),
            "requested_till": _iso_date(getattr(obj, "requested_till", None)),
            "description": getattr(obj, "description", None),
        },
        ctx=ctx,
    )


def _serialize_reimbursement(obj, ctx):
    return _inbox_item(
        "reimbursement",
        obj,
        summary=f"{obj.get_type_display()} · {obj.title}",
        requested_at=obj.allowance_on,
        detail={
            "title": obj.title,
            "type": obj.type,
            "amount": float(obj.amount or 0),
            "allowance_on": _iso_date(obj.allowance_on),
            "status": obj.status,
        },
        ctx=ctx,
    )


INBOX_SOURCES = [
    ("leave", pending_leave_queryset, _serialize_leave, "employee_id", "leave_type_id"),
    ("attendance", pending_attendance_queryset, _serialize_attendance, "employee_id", None),
    ("asset", pending_asset_queryset, _serialize_asset, "requested_employee_id", "asset_category_id"),
    ("shift", pending_shift_queryset, _serialize_shift, "employee_id", "shift_id"),
    ("work_type", pending_work_type_queryset, _serialize_work_type, "employee_id", "work_type_id"),
    ("reimbursement", pending_reimbursement_queryset, _serialize_reimbursement, "employee_id", None),
]

VALID_TYPES = {name for name, *_ in INBOX_SOURCES}
VALID_ACTIONS = {"approve", "reject"}


def get_pending_inbox(
    request,
    type_filter: str | None = None,
    page: int = 1,
    page_size: int = 20,
    max_per_type: int = 200,
) -> dict[str, Any]:
    if type_filter and type_filter not in VALID_TYPES:
        return {"error": _("Invalid type filter.")}

    page_size = min(max(int(page_size or 20), 1), 100)
    page = max(int(page or 1), 1)
    max_per_type = min(max(int(max_per_type or 200), 1), 10000)
    ctx = get_approval_context(request.user)
    items: list[dict[str, Any]] = []

    for type_name, qs_fn, serialize_fn, select_employee, select_extra in INBOX_SOURCES:
        if type_filter and type_filter != type_name:
            continue
        qs = qs_fn(request)
        rels = [select_employee]
        if select_extra:
            rels.append(select_extra)
        qs = qs.select_related(*rels).order_by("-id")[:max_per_type]
        for obj in qs:
            items.append(serialize_fn(obj, ctx))

    items.sort(key=lambda row: row.get("requested_at") or "", reverse=True)
    total = len(items)
    offset = (page - 1) * page_size
    counts_payload = get_pending_approvals_counts(request)

    return {
        "counts": counts_payload["pending"],
        "is_restricted": counts_payload["is_restricted"],
        "count": total,
        "page": page,
        "page_size": page_size,
        "results": items[offset : offset + page_size],
    }


def export_pending_inbox_rows(request) -> list[list]:
    """Build spreadsheet rows for pending approval inbox export."""
    type_filter = request.GET.get("type") or None
    if type_filter == "":
        type_filter = None
    inbox = get_pending_inbox(
        request, type_filter, page=1, page_size=10000, max_per_type=5000
    )
    rows = [
        [
            str(_("Type")),
            str(_("Employee")),
            str(_("Badge ID")),
            str(_("Summary")),
            str(_("Requested At")),
            str(_("Can Approve")),
        ]
    ]
    for item in inbox.get("results", []):
        employee = item.get("employee") or {}
        rows.append(
            [
                item.get("type", ""),
                employee.get("full_name", ""),
                employee.get("badge_id", ""),
                item.get("summary", ""),
                item.get("requested_at", ""),
                "Yes" if item.get("can_act") else "No",
            ]
        )
    return rows


def execute_pending_action(
    request,
    item_type: str,
    item_id: int,
    action: str,
    payload: dict | None = None,
) -> Response:
    if item_type not in VALID_TYPES:
        return Response({"error": _("Invalid type.")}, status=status.HTTP_400_BAD_REQUEST)
    if action not in VALID_ACTIONS:
        return Response({"error": _("Invalid action.")}, status=status.HTTP_400_BAD_REQUEST)

    ctx = get_approval_context(request.user)
    if not _can_act_on_type(ctx, item_type):
        return Response({"error": _("You do not have permission to act on this item.")}, status=status.HTTP_403_FORBIDDEN)

    payload = payload or {}

    if item_type == "leave":
        from horilla_api.api_views.leave.views import (
            LeaveRequestApproveAPIView,
            LeaveRequestRejectAPIView,
        )

        if action == "approve":
            return LeaveRequestApproveAPIView().put(request, pk=item_id)
        return LeaveRequestRejectAPIView().put(request, pk=item_id)

    if item_type == "attendance":
        from horilla_api.api_views.attendance.views import (
            AttendanceRequestApproveView,
            AttendanceRequestCancelView,
        )

        if action == "approve":
            return AttendanceRequestApproveView().put(request, pk=item_id)
        return AttendanceRequestCancelView().put(request, pk=item_id)

    if item_type == "reimbursement":
        from payroll.methods.reimbursement_actions import apply_reimbursement_status
        from payroll.models.models import Reimbursement

        if not request.user.has_perm("payroll.change_reimbursement"):
            return Response(
                {"error": _("You do not have permission to act on this item.")},
                status=status.HTTP_403_FORBIDDEN,
            )
        try:
            reimbursement = Reimbursement.objects.get(id=item_id)
        except Reimbursement.DoesNotExist:
            return Response({"error": _("Not found.")}, status=status.HTTP_404_NOT_FOUND)

        amount = payload.get("amount")
        status_val = "approved" if action == "approve" else "rejected"
        apply_reimbursement_status(reimbursement, status_val, amount=amount)
        return Response({"status": reimbursement.status}, status=status.HTTP_200_OK)

    if item_type == "shift":
        from horilla_api.api_views.base.views import (
            ShiftRequestApproveView,
            ShiftRequestCancelView,
        )

        if action == "approve":
            return ShiftRequestApproveView().put(request, pk=item_id)
        return ShiftRequestCancelView().post(request, pk=item_id)

    if item_type == "work_type":
        from horilla_api.api_views.base.views import (
            WorkRequestApproveView,
            WorkTypeRequestCancelView,
        )

        if action == "approve":
            return WorkRequestApproveView().put(request, pk=item_id)
        return WorkTypeRequestCancelView().put(request, pk=item_id)

    if item_type == "asset":
        from django.http import QueryDict

        from horilla_api.api_views.asset.views import (
            AssetApproveAPIView,
            AssetRejectAPIView,
        )

        if action == "approve":
            if not payload.get("asset_id"):
                return Response(
                    {"error": _("asset_id is required to approve an asset request.")},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            merged = QueryDict("", mutable=True)
            merged.update({k: str(v) for k, v in payload.items()})
            request._full_data = merged
            request._data = merged
            return AssetApproveAPIView().put(request, pk=item_id)
        return AssetRejectAPIView().put(request, pk=item_id)

    return Response({"error": _("Unsupported type.")}, status=status.HTTP_400_BAD_REQUEST)
