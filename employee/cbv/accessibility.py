"""
Accessiblility
"""

from functools import wraps

from django.contrib import messages
from django.contrib.auth.context_processors import PermWrapper
from django.utils.translation import gettext_lazy as _

from base.methods import check_manager
from employee.models import Employee, EmployeeNote
from horilla.http.response import HorillaRedirect
from horilla_audit.models import AccountBlockUnblock


def is_hr_user(request) -> bool:
    """Admin or HR who may see confidential employee data."""
    if not request.user.is_authenticated:
        return False
    return bool(
        request.user.is_superuser
        or request.user.has_perm("employee.change_employee")
        or request.user.has_perm("employee.add_employee")
    )


def can_access_employee_record(request, employee) -> bool:
    """Own profile, reporting manager of that employee, or HR/admin."""
    if not employee or not request.user.is_authenticated:
        return False
    if is_hr_user(request):
        return True
    if getattr(employee, "employee_user_id", None) == request.user:
        return True
    try:
        return check_manager(request.user.employee_get, employee)
    except Exception:
        return False


def accessible_employees_queryset(request, queryset):
    """
    HR/admin: all employees.
    Everyone else: themselves plus people who report to them.
    """
    from django.conf import settings
    from django.db.models import Q

    if not request or not getattr(request, "user", None) or not request.user.is_authenticated:
        return queryset.none()
    if is_hr_user(request):
        return queryset
    employee = getattr(request.user, "employee_get", None)
    if not employee:
        return queryset.none()
    q = Q(pk=employee.pk) | Q(employee_work_info__reporting_manager_id=employee)
    if getattr(settings, "NESTED_SUBORDINATE_VISIBILITY", False):
        current = [employee.pk]
        seen = {employee.pk}
        while current:
            sub_ids = list(
                Employee.objects.filter(
                    employee_work_info__reporting_manager_id__in=current
                ).values_list("id", flat=True)
            )
            new_ids = [pk for pk in sub_ids if pk not in seen]
            if not new_ids:
                break
            seen.update(new_ids)
            q |= Q(pk__in=new_ids)
            current = new_ids
    return queryset.filter(q).distinct()


def can_view_confidential_hr_data(request, employee=None) -> bool:
    """Salary, others' bank, mail logs — HR/admin only."""
    return is_hr_user(request)


def deny_without_employee_record_access(request, pk):
    """Redirect if the user may not open this employee's record."""
    employee = Employee.objects.entire().filter(id=pk).first() if pk else None
    if not can_access_employee_record(request, employee):
        messages.info(request, _("You dont have access to the feature"))
        return HorillaRedirect(request)
    return None


class EmployeeRecordAccessDispatchMixin:
    """CBV dispatch guard: own profile, reporting manager, or HR."""

    def dispatch(self, request, *args, **kwargs):
        blocked = deny_without_employee_record_access(request, kwargs.get("pk"))
        if blocked:
            return blocked
        return super().dispatch(request, *args, **kwargs)


def employee_record_access_required(view_func):
    """Function-view guard: own profile, reporting manager, or HR."""

    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        pk = kwargs.get("pk") or kwargs.get("obj_id") or kwargs.get("emp_id")
        blocked = deny_without_employee_record_access(request, pk)
        if blocked:
            return blocked
        return view_func(request, *args, **kwargs)

    return _wrapped


def hr_user_required(view_func):
    """Function-view guard: HR/admin only."""

    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not is_hr_user(request):
            messages.info(request, _("You dont have access to the feature"))
            return HorillaRedirect(request)
        return view_func(request, *args, **kwargs)

    return _wrapped


def edit_accessibility(
    request, instance: object = None, user_perms: PermWrapper = [], *args, **kwargs
) -> bool:
    """
    To access edit
    """
    if request.user == getattr(instance, "employee_user_id", None):
        return True
    if request.user.has_perm("employee.change_employee"):
        return True
    return False


def password_reset_accessibility(
    request, instance: object = None, user_perms: PermWrapper = [], *args, **kwargs
) -> bool:
    """
    To password  reset
    """
    if request.user.has_perm("employee.add_employee") or check_manager(
        request.user.employee_get, instance
    ):
        return True
    return False


def block_account_accessibility(
    request, instance: object = None, user_perms: PermWrapper = [], *args, **kwargs
) -> bool:
    """
    To block  account
    """
    enabled_block_unblock = (
        AccountBlockUnblock.objects.exists()
        and AccountBlockUnblock.objects.first().is_enabled
    )
    if (
        enabled_block_unblock
        and request.user.has_perm("employee.change_employee")
        and instance.employee_user_id.is_active
    ):
        return True
    return False


def un_block_account_accessibility(
    request, instance: object = None, user_perms: PermWrapper = [], *args, **kwargs
) -> bool:
    """
    To block  account
    """
    enabled_block_unblock = (
        AccountBlockUnblock.objects.exists()
        and AccountBlockUnblock.objects.first().is_enabled
    )
    if (
        enabled_block_unblock
        and request.user.has_perm("employee.change_employee")
        and not instance.employee_user_id.is_active
    ):
        return True
    return False


def action_accessible(request, instance, user_perms):
    """
    To access archive and delete functionalities

    """

    if request.user.has_perm("employee.change_employee"):
        return True


def can_view_employee_permissions(request, employee) -> bool:
    """
    Groups & Permissions visible to: the employee, their reporting manager,
    and superadmins.
    """
    if not employee or not request.user.is_authenticated:
        return False
    user = request.user
    if user.is_superuser:
        return True
    if getattr(employee, "employee_user_id", None) == user:
        return True
    try:
        return check_manager(user.employee_get, employee)
    except Exception:
        return False


def can_edit_employee_permissions(request, employee) -> bool:
    """
    Who may change an employee's groups/permissions from the profile:
    superadmin only. Reporting managers and the employee get view access.
    """
    if not employee or not request.user.is_authenticated:
        return False
    return bool(request.user.is_superuser)


def permission_accessibility(
    request, instance: object = None, user_perms: PermWrapper = [], *args, **kwargs
) -> bool:
    """
    Groups & Permissions tab: visible to the employee themselves,
    their reporting manager, and superadmins.
    """
    return can_view_employee_permissions(request, instance)


def note_accessibility(
    request, instance: object = None, user_perms: PermWrapper = [], *args, **kwargs
) -> bool:
    """
    Notes about an employee: HR or their reporting manager, not peers.
    """
    if instance.employee_user_id == request.user and not request.user.is_superuser:
        return False
    if is_hr_user(request):
        return True
    try:
        return check_manager(request.user.employee_get, instance)
    except Exception:
        return False


def deny_without_note_access(request, employee):
    """Notes are HR or reporting-manager only, not the employee themselves."""
    if not employee or not note_accessibility(
        request, employee, PermWrapper(request.user)
    ):
        messages.info(request, _("You dont have access to the feature"))
        return HorillaRedirect(request)
    return None


def note_access_required(view_func):
    """Function-view guard for employee notes and note files."""

    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        employee = None
        emp_id = kwargs.get("emp_id") or kwargs.get("pk")
        if emp_id:
            employee = Employee.objects.filter(id=emp_id).first()
        elif kwargs.get("note_id"):
            note = EmployeeNote.objects.filter(id=kwargs["note_id"]).first()
            employee = getattr(note, "employee_id", None)
        elif kwargs.get("note_file_id"):
            note = EmployeeNote.objects.filter(
                note_files=kwargs["note_file_id"]
            ).first()
            employee = getattr(note, "employee_id", None)
        blocked = deny_without_note_access(request, employee)
        if blocked:
            return blocked
        return view_func(request, *args, **kwargs)

    return _wrapped


def document_accessibility(
    request, instance: object = None, user_perms: PermWrapper = [], *args, **kwargs
) -> bool:
    """
    Documents: own files, reporting manager, or HR.
    """
    employee = Employee.objects.get(id=instance.pk)
    if can_access_employee_record(request, employee):
        return True
    return False


def workshift_accessibility(
    request, instance: object = None, user_perms: PermWrapper = [], *args, **kwargs
) -> bool:
    """
    permission for work type and shift tab in employee profile
    """
    employee = Employee.objects.get(id=instance.pk)
    return can_access_employee_record(request, employee)


def mail_log_accessibility(
    request, instance: object = None, user_perms: PermWrapper = [], *args, **kwargs
) -> bool:
    """Mail log is HR/admin only."""
    return is_hr_user(request)


def history_accessibility(
    request, instance: object = None, user_perms: PermWrapper = [], *args, **kwargs
) -> bool:
    """Work-info history can include salary — HR/admin only."""
    return is_hr_user(request)


def project_accessibility(
    request, instance: object = None, user_perms: PermWrapper = [], *args, **kwargs
) -> bool:
    """
    permission for work type and shift tab in employee profile
    """
    employee = Employee.objects.get(id=instance.pk)
    return can_access_employee_record(request, employee)
