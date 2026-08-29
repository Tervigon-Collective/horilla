"""Expiring employee documents helpers."""

from __future__ import annotations

from datetime import date, timedelta

from django.db.models import QuerySet


def _company_from_request(request):
    selected = request.session.get("selected_company") if request else None
    if not selected or selected == "all":
        return None
    from base.models import Company

    return Company.objects.filter(pk=selected).first()


def _base_dated_documents(request):
    from horilla_documents.models import Document

    qs = Document.objects.filter(expiry_date__isnull=False).select_related(
        "employee_id",
        "employee_id__employee_work_info",
        "employee_id__employee_work_info__department_id",
        "document_request_id",
    )
    company = _company_from_request(request)
    if company:
        qs = qs.filter(employee_id__employee_work_info__company_id=company)
    return qs


def expiring_documents_queryset(request, *, tab: str = "due") -> QuerySet:
    """
    Documents with an expiry date.

    Tabs:
      - due: expires within next 30 days (active, not yet expired)
      - soon: expires within next 7 days
      - overdue: expiry_date < today
      - all: active dated + overdue
    """
    today = date.today()
    qs = _base_dated_documents(request)

    if tab == "overdue":
        return qs.filter(expiry_date__lt=today).order_by("expiry_date", "title")
    if tab == "soon":
        return qs.filter(
            is_active=True,
            expiry_date__gte=today,
            expiry_date__lte=today + timedelta(days=7),
        ).order_by("expiry_date", "title")
    if tab == "due":
        return qs.filter(
            is_active=True,
            expiry_date__gte=today,
            expiry_date__lte=today + timedelta(days=30),
        ).order_by("expiry_date", "title")
    # all
    return (
        qs.filter(is_active=True) | qs.filter(expiry_date__lt=today)
    ).distinct().order_by("expiry_date", "title")


def expiring_documents_counts(request) -> dict[str, int]:
    today = date.today()
    qs = _base_dated_documents(request)
    return {
        "all": (qs.filter(is_active=True) | qs.filter(expiry_date__lt=today))
        .distinct()
        .count(),
        "due": qs.filter(
            is_active=True,
            expiry_date__gte=today,
            expiry_date__lte=today + timedelta(days=30),
        ).count(),
        "soon": qs.filter(
            is_active=True,
            expiry_date__gte=today,
            expiry_date__lte=today + timedelta(days=7),
        ).count(),
        "overdue": qs.filter(expiry_date__lt=today).count(),
    }


def days_until_expiry(document, today: date | None = None) -> int | None:
    today = today or date.today()
    if not document or not document.expiry_date:
        return None
    return (document.expiry_date - today).days
