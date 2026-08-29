"""Probation confirmation workflow helpers."""

from __future__ import annotations

from datetime import date, timedelta

from django.db.models import QuerySet


def _company_from_request(request):
    selected = request.session.get("selected_company") if request else None
    if not selected or selected == "all":
        return None
    from base.models import Company

    return Company.objects.filter(pk=selected).first()


def probation_queryset(request, *, tab: str = "all") -> QuerySet:
    """
    Active employees still on probation (or overdue confirmation).

    Tabs:
      - all: employment_status=probation
      - due: probation_end within next 30 days (inclusive)
      - overdue: probation_end before today
      - soon: probation_end within next 7 days
    """
    from employee.models import EmployeeWorkInformation

    today = date.today()
    qs = (
        EmployeeWorkInformation.objects.filter(
            employment_status="probation",
            employee_id__is_active=True,
        )
        .select_related(
            "employee_id",
            "department_id",
            "job_position_id",
            "company_id",
            "reporting_manager_id",
        )
        .order_by("probation_end", "employee_id__employee_first_name")
    )
    company = _company_from_request(request)
    if company:
        qs = qs.filter(company_id=company)

    if tab == "overdue":
        qs = qs.filter(probation_end__isnull=False, probation_end__lt=today)
    elif tab == "due":
        qs = qs.filter(
            probation_end__isnull=False,
            probation_end__gte=today,
            probation_end__lte=today + timedelta(days=30),
        )
    elif tab == "soon":
        qs = qs.filter(
            probation_end__isnull=False,
            probation_end__gte=today,
            probation_end__lte=today + timedelta(days=7),
        )
    return qs


def probation_counts(request) -> dict[str, int]:
    today = date.today()
    base = probation_queryset(request, tab="all")
    return {
        "all": base.count(),
        "due": base.filter(
            probation_end__isnull=False,
            probation_end__gte=today,
            probation_end__lte=today + timedelta(days=30),
        ).count(),
        "soon": base.filter(
            probation_end__isnull=False,
            probation_end__gte=today,
            probation_end__lte=today + timedelta(days=7),
        ).count(),
        "overdue": base.filter(
            probation_end__isnull=False, probation_end__lt=today
        ).count(),
    }


def confirm_work_info(work_info, *, actor=None) -> bool:
    """
    Set employment_status=confirmed. EmployeeWorkInformation.save() assigns Casual Leave.
    Returns True if status changed.
    """
    if not work_info or work_info.employment_status == "confirmed":
        return False
    work_info.employment_status = "confirmed"
    work_info.save()
    return True


def days_until_probation_end(work_info, today: date | None = None) -> int | None:
    today = today or date.today()
    if not work_info or not work_info.probation_end:
        return None
    return (work_info.probation_end - today).days
