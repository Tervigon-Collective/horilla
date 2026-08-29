"""Multi-level sequential approval helpers for overtime."""

from __future__ import annotations


def overtime_stages(attendance):
    from attendance.models import AttendanceOvertimeConditionApproval

    return AttendanceOvertimeConditionApproval.objects.filter(
        attendance_id=attendance
    ).order_by("sequence")


def overtime_approval_progress(attendance) -> dict:
    from base.multiple_approval import approval_progress

    return approval_progress(overtime_stages(attendance))


def assert_can_approve_overtime_stage(attendance, employee, *, is_superuser=False):
    from base.multiple_approval import assert_can_approve_stage

    return assert_can_approve_stage(
        overtime_stages(attendance),
        employee,
        is_superuser=is_superuser,
    )


def filter_conditional_overtime(request):
    from attendance.models import Attendance, AttendanceOvertimeConditionApproval
    from base.multiple_approval import current_stage_parent_ids
    from employee.models import Employee

    manager = Employee.objects.filter(employee_user_id=request.user).first()
    ids = current_stage_parent_ids(
        AttendanceOvertimeConditionApproval,
        manager=manager,
        fk_id_field="attendance_id_id",
        request_status_filter={
            "attendance_id__attendance_overtime_approve": False,
            "attendance_id__overtime_second__gt": 0,
        },
    )
    return Attendance.objects.filter(pk__in=ids)


def overtime_awaiting_approval(request):
    from attendance.models import Attendance, AttendanceOvertimeConditionApproval
    from base.methods import filtersubordinates, has_org_wide_perm
    from base.multiple_approval import multi_ids_in_progress

    base_qs = Attendance.objects.filter(
        attendance_overtime_approve=False,
        overtime_second__gt=0,
    )
    multiple = filter_conditional_overtime(request).distinct()
    employee = getattr(request.user, "employee_get", None)

    if request.user.is_superuser or has_org_wide_perm(
        request.user, "attendance.change_attendance"
    ):
        normal = base_qs
    else:
        try:
            normal = filtersubordinates(
                request, base_qs, "attendance.change_attendance"
            )
        except Exception:
            normal = (
                base_qs.filter(employee_id=employee)
                if employee
                else Attendance.objects.none()
            )
        # Include own OT for ESS visibility when filtersubordinates returns empty
        if employee:
            normal = (normal | base_qs.filter(employee_id=employee)).distinct()

    if not request.user.is_superuser:
        multi_ids = multi_ids_in_progress(
            AttendanceOvertimeConditionApproval,
            fk_id_field="attendance_id_id",
            request_status_filter={
                "attendance_id__attendance_overtime_approve": False,
                "attendance_id__overtime_second__gt": 0,
            },
        )
        if multi_ids:
            # Keep own rows for ESS; strip mid-chain from manager/org buckets
            if employee:
                normal = normal.exclude(
                    id__in=multi_ids
                ) | base_qs.filter(employee_id=employee, id__in=multi_ids)
                normal = normal.distinct()
            else:
                normal = normal.exclude(id__in=multi_ids)

    return (normal | multiple).distinct()


def apply_overtime_approval(attendance, *, employee=None, is_superuser=False) -> bool:
    """
    Approve OT for one attendance. Returns True if fully approved (flag set).
    Mid-stage returns False (stages advanced, OT not yet approved).
    """
    from attendance.models import AttendanceOvertimeConditionApproval

    stages = list(overtime_stages(attendance))
    if not stages:
        attendance.attendance_overtime_approve = True
        attendance.save()
        return True

    if is_superuser:
        AttendanceOvertimeConditionApproval.objects.filter(
            attendance_id=attendance
        ).update(is_approved=True, is_rejected=False)
        attendance.attendance_overtime_approve = True
        attendance.save()
        return True

    stage = assert_can_approve_overtime_stage(
        attendance, employee, is_superuser=False
    )
    stage.is_approved = True
    stage.save()
    remaining = AttendanceOvertimeConditionApproval.objects.filter(
        attendance_id=attendance,
        is_approved=False,
        is_rejected=False,
    ).exists()
    if remaining:
        return False
    AttendanceOvertimeConditionApproval.objects.filter(
        attendance_id=attendance
    ).update(is_approved=True, is_rejected=False)
    attendance.attendance_overtime_approve = True
    attendance.save()
    return True


def apply_overtime_rejection(attendance, *, employee=None, is_superuser=False):
    """Reject current OT stage (or clear OT if single-level / superuser)."""
    from attendance.models import AttendanceOvertimeConditionApproval

    stages = list(overtime_stages(attendance))
    if stages and not is_superuser:
        stage = assert_can_approve_overtime_stage(
            attendance, employee, is_superuser=False
        )
        if stage is not None:
            stage.is_approved = False
            stage.is_rejected = True
            stage.save()

    attendance.overtime_second = 0
    attendance.attendance_overtime_approve = False
    attendance.save(update_fields=["overtime_second", "attendance_overtime_approve"])
    return attendance
