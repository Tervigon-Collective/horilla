import random

from django.core.paginator import Paginator
from django.utils.translation import gettext_lazy as _

from base.methods import get_pagination, get_subordinates
from employee.models import Employee
from horilla.http import HorillaRedirect
from project.models import Project, Task, TimeSheet

decorator_with_arguments = (
    lambda decorator: lambda *args, **kwargs: lambda func: decorator(
        func, *args, **kwargs
    )
)


def strtime_seconds(time):
    """
    this method is used to reconvert time in H:M formate string back to seconds and return it
    args:
        time : time in H:M format
    """
    ftr = [3600, 60, 1]
    return sum(a * b for a, b in zip(ftr, map(int, time.split(":"))))


def paginator_qry(qryset, page_number):
    """
    This method is used to generate common paginator limit.
    """
    paginator = Paginator(qryset, get_pagination())
    qryset = paginator.get_page(page_number)
    return qryset


def random_color_generator():
    r = random.randint(0, 255)
    g = random.randint(0, 255)
    b = random.randint(0, 255)
    if r == g or g == b or b == r:
        random_color_generator()
    return f"rgba({r}, {g}, {b} , 0.7)"


# color_palette=[]
# Function to generate distinct colors for each project
def generate_colors(num_colors):
    # Define a color palette with distinct colors
    color_palette = [
        "rgba(255, 99, 132, 1)",  # Red
        "rgba(54, 162, 235, 1)",  # Blue
        "rgba(255, 206, 86, 1)",  # Yellow
        "rgba(75, 192, 192, 1)",  # Green
        "rgba(153, 102, 255, 1)",  # Purple
        "rgba(255, 159, 64, 1)",  # Orange
    ]

    if num_colors > len(color_palette):
        for i in range(num_colors - len(color_palette)):
            color_palette.append(random_color_generator())

    colors = []
    for i in range(num_colors):
        # color=random_color_generator()
        colors.append(color_palette[i % len(color_palette)])

    return colors


def any_project_manager(user):
    employee = user.employee_get
    if employee.project_managers.all().exists():
        return True
    else:
        return False


def any_project_member(user):
    employee = user.employee_get
    if employee.project_members.all().exists():
        return True
    else:
        return False


def any_task_manager(user):
    employee = user.employee_get
    if employee.task_set.all().exists():
        return True
    else:
        return False


def any_task_member(user):
    employee = user.employee_get
    if employee.tasks.all().exists():
        return True
    else:
        return False


@decorator_with_arguments
def is_projectmanager_or_member_or_perms(function, perm):
    def _function(request, *args, **kwargs):
        """
        This method is used to check the employee is project manager or not
        """
        user = request.user
        if (
            user.has_perm(perm)
            or any_project_manager(user)
            or any_project_member(user)
            or any_task_manager(user)
            or any_task_member(user)
        ):
            return function(request, *args, **kwargs)
        return HorillaRedirect(request, message=_("You don't have permission."))

    return _function


def is_task_member(request, task_id):
    """
    This method is used to check the employee is task member or not
    """
    task = Task.find(task_id)
    if not task:
        return False  # Task not found, treat as not a member
    if (
        request.user.has_perm("project.change_task")
        or request.user.employee_get in task.task_managers.all()
        or request.user.employee_get in task.task_members.all()
    ):
        return True
    return False


def is_task_manager(request, task_id):
    """
    This method is used to check the employee is task member or not
    """
    task = Task.find(task_id)
    if not task:
        return False  # Task not found, treat as not a manager
    if (
        request.user.has_perm("project.delete_task")
        or request.user.employee_get in task.task_managers.all()
    ):
        return True
    return False


def can_mutate_task(request, task) -> bool:
    """Edit / move / status-change this task (managers, members, or role perm)."""
    if not task or not getattr(request.user, "is_authenticated", False):
        return False
    if request.user.is_superuser or request.user.has_perm("project.change_task"):
        return True
    if request.user.has_perm("project.change_project"):
        return True
    employee = getattr(request.user, "employee_get", None)
    if not employee:
        return False
    project = getattr(task, "project", None)
    if employee in task.task_managers.all() or employee in task.task_members.all():
        return True
    if project is None:
        return False
    return employee in project.managers.all() or employee in project.members.all()


def can_delete_task(request, task) -> bool:
    """Archive/delete this task — managers or delete_task, not plain members."""
    if not task or not getattr(request.user, "is_authenticated", False):
        return False
    if request.user.is_superuser or request.user.has_perm("project.delete_task"):
        return True
    employee = getattr(request.user, "employee_get", None)
    if not employee:
        return False
    if employee in task.task_managers.all():
        return True
    project = getattr(task, "project", None)
    return bool(project and employee in project.managers.all())


def can_mutate_project(request, project) -> bool:
    """Update project status / stages (managers, members, or change_project)."""
    if not project or not getattr(request.user, "is_authenticated", False):
        return False
    if request.user.is_superuser or request.user.has_perm("project.change_project"):
        return True
    employee = getattr(request.user, "employee_get", None)
    if not employee:
        return False
    return employee in project.managers.all() or employee in project.members.all()


def can_add_task_to_project(request, project) -> bool:
    """Create a task on this project."""
    if not project or not getattr(request.user, "is_authenticated", False):
        return False
    if request.user.is_superuser or request.user.has_perm("project.add_task"):
        return True
    employee = getattr(request.user, "employee_get", None)
    if not employee:
        return False
    return employee in project.managers.all()


def can_view_project(request, project) -> bool:
    """View project details (member/manager or view_project)."""
    if not project or not getattr(request.user, "is_authenticated", False):
        return False
    if request.user.is_superuser or request.user.has_perm("project.view_project"):
        return True
    return can_mutate_project(request, project)


def can_view_task(request, task) -> bool:
    """View task details / timesheets list."""
    if not task or not getattr(request.user, "is_authenticated", False):
        return False
    if request.user.is_superuser or request.user.has_perm("project.view_task"):
        return True
    if request.user.has_perm("project.view_timesheet"):
        return True
    return can_mutate_task(request, task)


def can_view_employee_timesheet(request, employee) -> bool:
    """Self, reporting manager of that employee, or view_timesheet."""
    if not employee or not getattr(request.user, "is_authenticated", False):
        return False
    if request.user.is_superuser or request.user.has_perm("project.view_timesheet"):
        return True
    actor = getattr(request.user, "employee_get", None)
    if not actor:
        return False
    if employee == actor:
        return True
    try:
        from base.methods import check_manager

        return check_manager(actor, employee)
    except Exception:
        return False


def time_sheet_update_permissions(request, time_sheet_id):
    timesheet = TimeSheet.find(time_sheet_id)
    if not timesheet:
        return False  # Timesheet not found, treat as no permission
    if (
        request.user.has_perm("project.change_timesheet")
        or request.user.employee_get == timesheet.employee_id
        or timesheet.employee_id
        in Employee.objects.filter(
            employee_work_info__reporting_manager_id=request.user.employee_get
        )
    ):
        return True
    else:
        return False


def time_sheet_delete_permissions(request, time_sheet_id):
    employee = request.user.employee_get
    timesheet = TimeSheet.objects.filter(id=time_sheet_id).first()
    if not timesheet:
        return False
    if request.user.has_perm("project.delete_timesheet") or timesheet.employee_id == employee:
        return True
    task = timesheet.task_id
    if task is not None and employee in task.task_managers.all():
        return True
    project = timesheet.project_id or (task.project if task is not None else None)
    if project is not None and employee in project.managers.all():
        return True
    return False


def get_all_project_members_and_managers():
    all_projects = Project.objects.all()
    all_tasks = Task.objects.all()

    all_ids = set()

    for project in all_projects:
        all_ids.update(
            manager.id for manager in project.managers.all()
        )  # Add manager ID
        all_ids.update(member.id for member in project.members.all())  # Add member IDs

    for task in all_tasks:
        all_ids.update(
            task_manager.id for task_manager in task.task_managers.all()
        )  # Add task manager ID
        all_ids.update(
            task_member.id for task_member in task.task_members.all()
        )  # Add task member IDs

    # Return a single queryset for all employees
    return Employee.objects.filter(id__in=all_ids)


def has_subordinates(request):
    """
    used to check whether the project contain users subordinates or not
    """
    all_members_info = get_all_project_members_and_managers()
    subordinates = get_subordinates(request)

    member = {member for member in all_members_info}

    for subordinate in subordinates:
        if subordinate in member:
            return True

    return False


def is_project_manager_or_super_user(request, project):
    """
    Method to check whether user is a manager of project or
    user is a super user.
    """
    return (
        request.user.employee_get in project.managers.all() or request.user.is_superuser
    )
