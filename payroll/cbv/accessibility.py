from django.contrib.auth.context_processors import PermWrapper

from base.methods import check_manager
from employee.models import Employee


def is_payroll_admin(request) -> bool:
    """HR/admin, or staff who can generate payslips — not view-only / managers."""
    from employee.cbv.accessibility import is_hr_user

    if not request.user.is_authenticated:
        return False
    if is_hr_user(request):
        return True
    return request.user.has_perm("payroll.add_payslip")


def can_view_all_payslips(request) -> bool:
    """Everyone's slips/contracts/wages — payroll admin only, not reporting managers."""
    return is_payroll_admin(request)


def can_view_payslip_record(request, payslip) -> bool:
    if not payslip:
        return False
    if payslip.employee_id and payslip.employee_id.employee_user_id == request.user:
        return True
    return can_view_all_payslips(request)


def payroll_accessibility(
    request, instance: object = None, user_perms: PermWrapper = [], *args, **kwargs
) -> bool:
    """
    Own payslips, or HR/payroll staff — not a reporting manager of someone else.
    """
    employee = Employee.objects.get(id=instance.pk)
    if request.user == employee.employee_user_id:
        return True
    return is_payroll_admin(request)


def bonus_accessibility(
    request, instance: object = None, user_perms: PermWrapper = [], *args, **kwargs
) -> bool:
    """
    Own bonus points, or HR — not a reporting manager of someone else.
    """
    from employee.cbv.accessibility import is_hr_user

    employee = Employee.objects.get(id=instance.pk)
    if request.user == employee.employee_user_id:
        return True
    return is_hr_user(request)


def allowance_and_deduction_accessibility(
    request, instance: object = None, user_perms: PermWrapper = [], *args, **kwargs
) -> bool:
    """
    Own allowances, or payroll/HR staff.
    """
    employee = Employee.objects.get(id=instance.pk)
    if request.user == employee.employee_user_id:
        return True
    return is_payroll_admin(request)
