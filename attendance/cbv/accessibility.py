"""
Accessiblility
"""

from django.contrib.auth.context_processors import PermWrapper

from base.methods import check_manager
from employee.models import Employee


def attendance_accessibility(
    request, instance: object = None, user_perms: PermWrapper = [], *args, **kwargs
) -> bool:
    """
    permission for attendance tab
    """
    employee = Employee.objects.get(id=instance.pk)
    from employee.cbv.accessibility import can_access_employee_record

    return can_access_employee_record(request, employee)


def penalty_accessibility(
    request, instance: object = None, user_perms: PermWrapper = [], *args, **kwargs
) -> bool:
    """
    permission for penalty tab
    """
    employee = Employee.objects.get(id=instance.pk)
    from employee.cbv.accessibility import can_access_employee_record

    return can_access_employee_record(request, employee)


def create_attendance_request_accessibility(
    request, instance: object = None, user_perms: PermWrapper = [], *args, **kwargs
) -> bool:
    employee = Employee.objects.get(id=instance.pk)
    if request.user == employee.employee_user_id:
        return True
    return False
