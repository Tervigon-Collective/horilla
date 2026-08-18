"""
Accessibility page for card functions
"""

from django.contrib.auth.context_processors import PermWrapper

from base.methods import check_manager
from employee.models import Employee
from leave.models import LeaveType


def assign_leave(request, instance, user_perm):
    if request.user.has_perm("leave.add_availableleave"):
        if not instance.is_compensatory_leave:
            return True
    return False


def leave_accessibility(
    request, instance: object = None, user_perms: PermWrapper = [], *args, **kwargs
) -> bool:
    """
    accessibility for leave tab in individual view
    """
    employee = Employee.objects.get(id=instance.pk)
    from employee.cbv.accessibility import can_access_employee_record

    return can_access_employee_record(request, employee)
