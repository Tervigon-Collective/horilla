"""
Accessibility
"""

from django.contrib.auth.context_processors import PermWrapper

from employee.models import Employee
from project.models import Project, Task


def task_crud_accessibility(
    request, instance: object = None, user_perms: PermWrapper = [], *args, **kwargs
) -> bool:
    """
    to access crud operations
    """
    from project.methods import can_delete_task, can_mutate_task

    return can_mutate_task(request, instance) or can_delete_task(request, instance)


def project_manager_accessibility(
    request, instance: object = None, user_perms: PermWrapper = [], *args, **kwargs
) -> bool:
    """
    to access edit Project
    """
    return (
        request.user.employee_get in instance.managers.all()
        or request.user.is_superuser
    )
