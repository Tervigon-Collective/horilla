"""
Helpers for missing punch detection and scoped queries.
"""

from datetime import timedelta

from django.utils import timezone
from django.utils.http import urlencode

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


def can_regularize_missing_punch(request, record):
    """Employee, manager of that employee, or attendance change permission."""
    user = request.user
    if user.has_perm("attendance.change_attendance") or user.has_perm(
        "attendance.add_attendance"
    ):
        return True
    employee = getattr(user, "employee_get", None)
    if employee and record.employee_id_id == employee.pk:
        return True
    return filtersubordinatesemployeemodel(
        request,
        Employee.objects.filter(pk=record.employee_id_id),
        "attendance.change_attendance",
    ).exists()


def regularize_form_url(record):
    """CBV URL that opens the attendance request form for this missing punch."""
    from django.urls import reverse

    if record.attendance_id_id:
        return reverse("update-attendance-request", kwargs={"pk": record.attendance_id_id})
    params = {
        "employee_id": record.employee_id_id,
        "emp_id": record.employee_id_id,
        "attendance_date": record.date.isoformat() if record.date else "",
        "missing_punch": "1",
        "request_description": record.message or "Missing punch regularization",
    }
    if record.shift_id_id:
        params["shift_id"] = record.shift_id_id
    return reverse("request-new-attendance") + "?" + urlencode(params)


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
