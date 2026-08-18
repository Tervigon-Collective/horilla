"""
Accessiblility for pms
"""

from django.contrib.auth.context_processors import PermWrapper

from base.methods import check_manager
from employee.models import Employee


def performance_accessibility(
    request, instance: object = None, user_perms: PermWrapper = [], *args, **kwargs
) -> bool:
    """
    permission for performance tab
    """
    employee = Employee.objects.get(id=instance.pk)
    from employee.cbv.accessibility import can_access_employee_record

    return can_access_employee_record(request, employee)


def create_objective_accessibility(
    request, instance: object = None, user_perms: PermWrapper = [], *args, **kwargs
) -> bool:
    """
    To check the user has permission to add objectives
    """
    return request.user.has_perm("pms.add_objective")
