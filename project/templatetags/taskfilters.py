"""
This module is used to write custom template filters.
"""

from django.template.defaultfilters import register

from project.models import Project


@register.filter(name="task_crud_perm")
def task_crud_perm(user, task):
    """
    This method is used to check the requested user is task manager or project manager or has permission
    """
    try:
        employee = user.employee_get
        is_task_manager = employee in task.task_managers.all()
        is_project_manager = employee in task.project.managers.all()
        return is_task_manager or is_project_manager

    except Exception as _:
        return False


@register.filter(name="time_sheet_crud_perm")
def time_sheet_crud_perm(user, timesheet):
    """
    This method is used to check the requested user is task manager or project manager or has permission
    """
    try:
        employee = user.employee_get
        is_task_manager = employee in timesheet.task_id.task_managers.all()
        is_project_manager = employee in timesheet.project_id.managers.all()
        is_own_timesheet = timesheet.employee_id == employee

        return is_task_manager or is_project_manager or is_own_timesheet

    except Exception as _:
        return False


@register.filter(name="is_project_manager_or_member")
def is_project_manager_or_member(user, project):
    """
    This method will return true, if the user is manager of the project
    or a manager/member of any task under the project
    """
    employee = user.employee_get

    return (
        Project.objects.filter(id=project.id, managers=employee).exists()
        or Project.objects.filter(id=project.id, task__task_managers=employee).exists()
        or Project.objects.filter(id=project.id, task__task_members=employee).exists()
    )


@register.filter(name="is_project_manager")
def is_project_manager(user, project):
    """
    This method will return true, if the user is manager of the project
    """
    if user.is_superuser:
        return True
    employee = user.employee_get
    return Project.objects.filter(id=project.id, managers=employee).exists()


@register.filter(name="can_add_project_task")
def can_add_project_task(user, project):
    """
    True if the user may create tasks on this project (manager or member).
    """
    if user.is_superuser:
        return True
    try:
        from project.methods import can_view_all_projects

        # Build a minimal request-like object is awkward in filters; check groups/perms.
        if user.has_perm("project.change_project") or user.groups.filter(
            name__in=("Admin", "HR Manager", "Project Manager")
        ).exists():
            return True
        employee = user.employee_get
        return (
            Project.objects.filter(id=project.id, managers=employee).exists()
            or Project.objects.filter(id=project.id, members=employee).exists()
        )
    except Exception:
        return False


@register.filter(name="can_delete_this_task")
def can_delete_this_task(user, task):
    """
    True if the user may archive/delete this task (not plain project members).
    """
    if user.is_superuser or user.has_perm("project.delete_task"):
        return True
    try:
        employee = user.employee_get
        if employee in task.task_managers.all():
            return True
        return bool(task.project and employee in task.project.managers.all())
    except Exception:
        return False


@register.filter(name="is_task_manager")
def is_task_manager(user, task):
    """
    This method will return True if the user is a manager of the task.
    """
    try:
        employee = user.employee_get
        return employee in task.task_managers.all()
    except AttributeError:
        # Handle cases where user or task might not have the expected structure
        return False
