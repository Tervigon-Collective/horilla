"""
Helpers for missing punch detection and scoped queries.
"""

from datetime import timedelta

from django.utils import timezone

from base.methods import filtersubordinatesemployeemodel
from employee.models import Employee

MISSING_PUNCH_MESSAGES = ("Missing punch in", "Missing punch out")


def scoped_active_employees(request):
    """Employees visible to the current user for attendance operations."""
    return filtersubordinatesemployeemodel(
        request,
        Employee.objects.filter(is_active=True),
        "attendance.view_attendance",
    )


def missing_punch_work_records(request, days=30):
    """Work records flagged as missing punch in/out within the look-back window."""
    from attendance.models import WorkRecords

    since = timezone.localdate() - timedelta(days=days)
    employees = scoped_active_employees(request)
    return (
        WorkRecords.objects.filter(
            employee_id__in=employees,
            work_record_type="CONF",
            message__in=MISSING_PUNCH_MESSAGES,
            date__gte=since,
        )
        .select_related("employee_id", "attendance_id", "shift_id")
        .order_by("-date", "employee_id__employee_first_name")
    )


def missing_punch_count(request, days=30):
    return missing_punch_work_records(request, days=days).count()
