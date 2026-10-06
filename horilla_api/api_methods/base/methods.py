from collections import Counter
from urllib.parse import urlparse

from django.conf import settings
from django.db.models import Q
from django.http import QueryDict
from rest_framework.pagination import PageNumberPagination

from employee.models import Employee, EmployeeWorkInformation


def mobile_file_path(file_field):
    """
    Relative /media/... path. The official Horilla app always does
    ``serverUrl + path``, so an absolute http(s) URL would break images.
    """
    if not file_field:
        return None
    try:
        url = file_field.url
    except (ValueError, AttributeError):
        return None
    if not url:
        return None
    if url.startswith("http://") or url.startswith("https://"):
        url = urlparse(url).path or url
    if not url.startswith("/"):
        media = (getattr(settings, "MEDIA_URL", "/media/") or "/media/").rstrip("/")
        url = f"{media}/{url.lstrip('/')}"
    return url


def get_filter_url(current_url, request):
    url_parts = current_url.split("?")
    base_url = request.path
    query_params = QueryDict(url_parts[1], mutable=True)
    query_params.pop("groupby_field", None)
    return base_url + "?" + query_params.urlencode()


def groupby_queryset(request, url, field_name, queryset):
    queryset_with_counts = queryset.values(field_name)

    counts = Counter(item[field_name] for item in queryset_with_counts)

    result_list = []
    for i in counts:
        result_list.append({field_name: i, "count": counts[i]})

    counts_and_objects = []
    url = get_filter_url(url, request)
    for item in result_list:
        count = item["count"]
        related_fields = field_name.split("__")
        if item[field_name]:
            related_obj = queryset.filter(**{field_name: item[field_name]}).first()
            for field in related_fields:
                related_obj = getattr(related_obj, field)
            counts_and_objects.append(
                {
                    "count": count,
                    "name": str(related_obj),
                    "filter_url": f"{url}&{field_name}={item[field_name]}",
                }
            )
    pagination = PageNumberPagination()
    page = pagination.paginate_queryset(counts_and_objects, request)
    return pagination.get_paginated_response(page)


def permission_based_queryset(user, perm, queryset, user_obj=None):
    # Handle AnonymousUser during schema generation
    if not user.is_authenticated:
        return queryset.none()

    from base.methods import has_org_wide_perm

    if has_org_wide_perm(user, perm):
        return queryset

    employee = user.employee_get

    # Every narrowing branch below filters on employee_id, but 30 of the
    # models routed through this helper have no such field -- LinkedInAccount,
    # Recruitment, Objective, Project and the onboarding/offboarding stage
    # and task models among them. Those filters raise FieldError, so a user
    # *without* the permission got a 500 instead of a restricted list. There
    # is no per-employee predicate to apply on such a model, and returning
    # the unfiltered queryset would hand a permissionless caller everything,
    # so the correct answer is an empty queryset.
    field = next(
        (f for f in queryset.model._meta.fields if f.name == "employee_id"), None
    )
    if field is None:
        return queryset.none()
    # employee_id normally points at Employee, but on e.g. offboarding notes
    # and tasks it points at OffboardingEmployee (which has its own
    # employee_id); filtering those by an Employee raised ValueError (500).
    path = "employee_id"
    if field.related_model is not Employee:
        inner = next(
            (
                f
                for f in field.related_model._meta.fields
                if f.name == "employee_id" and f.related_model is Employee
            ),
            None,
        )
        if inner is None:
            return queryset.none()
        path = "employee_id__employee_id"

    own = Q(**{path: employee})
    reports = Q(**{f"{path}__employee_work_info__reporting_manager_id": employee})
    is_manager = EmployeeWorkInformation.objects.filter(
        reporting_manager_id=employee
    ).exists()
    if is_manager:
        return queryset.filter(own | reports)

    return queryset.filter(own)


def reject_reason_from(request):
    """
    The optional ``reason`` a reject call carries, trimmed, or None.

    Reject endpoints took no reason at all, so an employee learned only that
    a request was rejected, never why. Optional, so existing clients that
    send no body keep working unchanged.
    """
    reason = request.data.get("reason") if hasattr(request, "data") else None
    if not isinstance(reason, str):
        return None
    reason = reason.strip()
    return reason[:1000] or None
