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


def can_access_leave_request(request, leave_request) -> bool:
    """Own leave, team leave (reporting manager), or HR."""
    if not leave_request:
        return False
    from employee.cbv.accessibility import can_access_employee_record

    return can_access_employee_record(request, leave_request.employee_id)


def can_manage_leave_request(request, leave_request) -> bool:
    """
    Approve / reject / HR cancel for someone else's leave.

    Allowed: superuser, HR, Leave Manager (leave.change_leaverequest),
    reporting manager of that employee, or a multi-approval manager on
    this request. Never the leave owner (except superuser).
    """
    if not leave_request or not request.user.is_authenticated:
        return False
    actor = getattr(request.user, "employee_get", None)
    subject = leave_request.employee_id
    if not actor or not subject:
        return False
    if subject == actor and not request.user.is_superuser:
        return False
    from employee.cbv.accessibility import is_hr_user

    if request.user.is_superuser or is_hr_user(request):
        return True
    if request.user.has_perm("leave.change_leaverequest"):
        return True
    if check_manager(actor, subject):
        return True
    from leave.models import LeaveRequestConditionApproval

    return LeaveRequestConditionApproval.objects.filter(
        leave_request_id=leave_request, manager_id=actor
    ).exists()


def apply_leave_nav_filter_context(view, context):
    """Pass request into leave nav filters so employee dropdowns are scoped."""
    if not getattr(view, "filter_instance", None):
        return context
    filter_class = view.filter_instance.__class__
    filterset = filter_class(view.request.GET or None, request=view.request)
    context[view.filter_form_context_name] = filterset.form
    context[view.filter_instance_context_name] = filterset
    return context
