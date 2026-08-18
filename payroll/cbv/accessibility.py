from django.contrib.auth.context_processors import PermWrapper

from base.methods import check_manager
from employee.models import Employee


def can_view_all_payslips(request) -> bool:
    """HR/admin or payroll staff — not every user with view_payslip."""
    if not request.user.is_authenticated:
        return False
    if request.user.is_superuser or request.user.has_perm("employee.change_employee"):
        return True
    return request.user.has_perm("payroll.view_payslip") and request.user.has_perm(
        "payroll.view_contract"
    )


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
    Own payslips, or HR/payroll staff — not every viewer of the profile.
    """
    employee = Employee.objects.get(id=instance.pk)
    if request.user == employee.employee_user_id:
        return True
    if request.user.has_perm("payroll.view_payslip") and (
        request.user.is_superuser
        or request.user.has_perm("employee.change_employee")
        or request.user.has_perm("payroll.view_contract")
    ):
        return True
    return False


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
    if request.user.has_perm("payroll.view_payslip") and (
        request.user.is_superuser
        or request.user.has_perm("employee.change_employee")
        or request.user.has_perm("payroll.view_contract")
    ):
        return True
    return False
