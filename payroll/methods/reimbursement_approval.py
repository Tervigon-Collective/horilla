"""Multi-level sequential approval helpers for reimbursements."""

from __future__ import annotations


def reimbursement_stages(reimbursement):
    from payroll.models.models import ReimbursementConditionApproval

    return ReimbursementConditionApproval.objects.filter(
        reimbursement_id=reimbursement
    ).order_by("sequence")


def reimbursement_approval_progress(reimbursement) -> dict:
    from base.multiple_approval import approval_progress

    return approval_progress(reimbursement_stages(reimbursement))


def assert_can_approve_reimbursement_stage(
    reimbursement, employee, *, is_superuser=False
):
    from base.multiple_approval import assert_can_approve_stage

    return assert_can_approve_stage(
        reimbursement_stages(reimbursement),
        employee,
        is_superuser=is_superuser,
    )


def filter_conditional_reimbursements(request):
    from base.multiple_approval import current_stage_parent_ids
    from employee.models import Employee
    from payroll.models.models import Reimbursement, ReimbursementConditionApproval

    manager = Employee.objects.filter(employee_user_id=request.user).first()
    ids = current_stage_parent_ids(
        ReimbursementConditionApproval,
        manager=manager,
        fk_id_field="reimbursement_id_id",
        request_status_filter={"reimbursement_id__status": "requested"},
    )
    return Reimbursement.objects.filter(pk__in=ids)


def reimbursements_awaiting_approval(request):
    """
    Union of:
    - Org-wide payroll approvers: requested (excluding mid multi-chain) ∪ current stage
    - Stage managers: current-stage items
    - ESS: own requested items
    """
    from base.methods import has_org_wide_perm
    from base.multiple_approval import multi_ids_in_progress
    from payroll.models.models import Reimbursement, ReimbursementConditionApproval

    base_qs = Reimbursement.objects.filter(status="requested")
    multiple = filter_conditional_reimbursements(request).distinct()
    employee = getattr(request.user, "employee_get", None)

    if (
        has_org_wide_perm(request.user, "payroll.change_reimbursement")
        or request.user.is_superuser
    ):
        normal = base_qs
        if not request.user.is_superuser:
            multi_ids = multi_ids_in_progress(
                ReimbursementConditionApproval,
                fk_id_field="reimbursement_id_id",
                request_status_filter={"reimbursement_id__status": "requested"},
            )
            if multi_ids:
                normal = normal.exclude(id__in=multi_ids)
        return (normal | multiple).distinct()

    # ESS / non-payroll: own requests + any current-stage items for this manager
    own = (
        base_qs.filter(employee_id=employee) if employee else Reimbursement.objects.none()
    )
    return (own | multiple).distinct()
