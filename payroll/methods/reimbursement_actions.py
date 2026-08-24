"""Reimbursement approve/reject helpers — must use model.save() for encashment logic."""


def apply_reimbursement_status(reimbursement, status: str, amount=None):
    """
    Update reimbursement status through the model save path so leave encashment
    balance deduction, allowance creation, and reject restore all run.
    """
    if amount is not None:
        reimbursement.amount = max(0, float(amount))
    reimbursement.status = status
    reimbursement.save()
    return reimbursement
