"""Approve/reject reimbursements — respects multi-level stages when configured."""


def apply_reimbursement_status(
    reimbursement,
    status: str,
    amount=None,
    *,
    employee=None,
    is_superuser=False,
):
    """
    Update reimbursement status through the model save path so leave encashment
    balance deduction, allowance creation, and reject restore all run.

    For multi-level chains:
    - Intermediate approve only marks the stage; status stays ``requested``.
    - Final approve (or superuser) sets ``approved`` and triggers allowance.
    """
    if amount is not None:
        reimbursement.amount = max(0, float(amount))

    if status == "approved":
        from payroll.methods.reimbursement_approval import (
            assert_can_approve_reimbursement_stage,
            reimbursement_stages,
        )
        from payroll.models.models import ReimbursementConditionApproval

        stages = list(reimbursement_stages(reimbursement))
        if stages:
            if is_superuser:
                ReimbursementConditionApproval.objects.filter(
                    reimbursement_id=reimbursement
                ).update(is_approved=True, is_rejected=False)
            else:
                stage = assert_can_approve_reimbursement_stage(
                    reimbursement, employee, is_superuser=False
                )
                if stage is None:
                    pass
                else:
                    stage.is_approved = True
                    stage.save()
                    remaining = ReimbursementConditionApproval.objects.filter(
                        reimbursement_id=reimbursement,
                        is_approved=False,
                        is_rejected=False,
                    ).exists()
                    if remaining:
                        # Mid-stage — do not flip status / create allowance
                        return reimbursement
                    ReimbursementConditionApproval.objects.filter(
                        reimbursement_id=reimbursement
                    ).update(is_approved=True, is_rejected=False)

        reimbursement.status = "approved"
        reimbursement.save()
        return reimbursement

    if status == "rejected":
        from payroll.methods.reimbursement_approval import (
            assert_can_approve_reimbursement_stage,
        )
        from payroll.models.models import ReimbursementConditionApproval

        stages = list(
            ReimbursementConditionApproval.objects.filter(
                reimbursement_id=reimbursement
            )
        )
        if stages and not is_superuser:
            stage = assert_can_approve_reimbursement_stage(
                reimbursement, employee, is_superuser=False
            )
            if stage is not None:
                stage.is_approved = False
                stage.is_rejected = True
                stage.save()

        reimbursement.status = "rejected"
        reimbursement.save()
        return reimbursement

    reimbursement.status = status
    reimbursement.save()
    return reimbursement
