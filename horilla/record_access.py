"""
Per-record access for employee-owned data (attendance, leave, hours, work info).

A plain employee may see their own records and their direct reports'; anyone
holding the model's org-wide view permission (HR/admin) sees everything.
Detail views used to load any primary key from the URL, so an employee could
read a colleague's attendance, leave or hours by changing the number.
"""

from django.db.models import Q

from base.methods import has_org_wide_perm


def employee_scope_q(request, lookup="employee_id"):
    """Q() limiting rows to the requester and their direct reports.

    ``lookup`` is the path to the Employee on the model ("" for Employee itself).
    """
    me = getattr(request.user, "employee_get", None)
    if me is None:
        return Q(pk__in=[])
    if not lookup:
        return Q(pk=me.pk) | Q(employee_work_info__reporting_manager_id=me)
    return Q(**{lookup: me}) | Q(
        **{f"{lookup}__employee_work_info__reporting_manager_id": me}
    )


def can_see_all(request, perm):
    return has_org_wide_perm(request.user, perm)


class EmployeeRecordAccessMixin:
    """Restrict a detail/list view's queryset to records the requester may see."""

    access_perm = None
    employee_lookup = "employee_id"

    def get_queryset(self):
        queryset = super().get_queryset()
        if can_see_all(self.request, self.access_perm):
            return queryset
        return queryset.filter(employee_scope_q(self.request, self.employee_lookup))
