"""
Hand pending approvals over to an employee's new reporting manager.

Manager access is resolved from ``reporting_manager_id`` at request time, but
multi-level approval stages and PMS feedback store the manager on the row, so
a reporting-manager change would leave them with the previous manager.
"""

from django.apps import apps
from django.db import transaction

from base.backends import logger


def snapshot_reporting_managers(employee_ids=None):
    """{employee_id: reporting_manager_id} for later comparison."""
    from employee.models import EmployeeWorkInformation

    queryset = EmployeeWorkInformation.objects.all()
    if employee_ids is not None:
        queryset = queryset.filter(employee_id__in=list(employee_ids))
    return dict(queryset.values_list("employee_id", "reporting_manager_id"))


def transfer_changed_managers(before):
    """Transfer pending items for every employee whose manager changed since `before`."""
    after = snapshot_reporting_managers(before.keys())
    for employee_id, old_manager_id in before.items():
        new_manager_id = after.get(employee_id)
        if old_manager_id and new_manager_id and old_manager_id != new_manager_id:
            transfer_pending_to_new_manager(employee_id, old_manager_id, new_manager_id)


def _approval_stage_specs():
    """(stage model, parent fk name, filter keeping only still-pending parents)."""
    specs = []
    if apps.is_installed("leave"):
        from leave.models import LeaveRequestConditionApproval

        specs.append(
            (
                LeaveRequestConditionApproval,
                "leave_request_id",
                {"leave_request_id__status": "requested"},
            )
        )
    if apps.is_installed("attendance"):
        from attendance.models import AttendanceOvertimeConditionApproval

        specs.append(
            (
                AttendanceOvertimeConditionApproval,
                "attendance_id",
                {"attendance_id__attendance_overtime_approve": False},
            )
        )
    if apps.is_installed("payroll"):
        from payroll.models.models import ReimbursementConditionApproval

        specs.append(
            (
                ReimbursementConditionApproval,
                "reimbursement_id",
                {"reimbursement_id__status": "requested"},
            )
        )
    return specs


def transfer_pending_to_new_manager(employee_id, old_manager_id, new_manager_id):
    """
    Move the employee's pending approval stages and open PMS feedback from the
    old reporting manager to the new one. Returns {label: rows moved}.
    """
    from base.models import MultipleApprovalManagers

    moved = {}
    if not (old_manager_id and new_manager_id) or old_manager_id == new_manager_id:
        return moved
    if new_manager_id == employee_id:
        return moved

    with transaction.atomic():
        # A stage row does not record whether it came from the "reporting
        # manager" rule or from a fixed approver; if the old manager is also a
        # fixed approver, the stage may be theirs by name, so leave it.
        old_is_fixed_approver = MultipleApprovalManagers.objects.filter(
            employee_id=old_manager_id
        ).exists()
        if not old_is_fixed_approver:
            for stage_model, fk_name, pending_parent in _approval_stage_specs():
                count = stage_model.objects.filter(
                    **{f"{fk_name}__employee_id": employee_id},
                    **pending_parent,
                    manager_id=old_manager_id,
                    is_approved=False,
                    is_rejected=False,
                ).update(manager_id=new_manager_id)
                if count:
                    moved[stage_model._meta.verbose_name_plural] = count

        if apps.is_installed("pms"):
            from pms.models import Answer, Feedback

            answered = Answer.objects.filter(
                employee_id=old_manager_id,
                feedback_id__employee_id=employee_id,
            ).values_list("feedback_id", flat=True)
            count = (
                Feedback.objects.filter(employee_id=employee_id, manager_id=old_manager_id)
                .exclude(status="Closed")
                .exclude(id__in=answered)
                .update(manager_id=new_manager_id)
            )
            if count:
                moved["feedbacks"] = count

    if moved:
        logger.info(
            "Reporting manager change for employee_id=%s: moved %s from manager %s to %s",
            employee_id,
            moved,
            old_manager_id,
            new_manager_id,
        )
    return moved
