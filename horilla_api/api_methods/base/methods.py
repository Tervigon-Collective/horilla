from collections import Counter
from urllib.parse import urlparse

from django.conf import settings
from django.db.models import Q
from django.http import QueryDict
from rest_framework.pagination import PageNumberPagination

from employee.models import EmployeeWorkInformation


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

    if user.has_perm(perm):
        return queryset

    employee = user.employee_get
    is_manager = EmployeeWorkInformation.objects.filter(
        reporting_manager_id=employee
    ).exists()
    if is_manager:
        if user_obj:
            return queryset.filter(
                Q(employee_id=employee)
                | Q(employee_id__employee_work_info__reporting_manager_id=employee)
            )
        manager_filter = Q(employee_id=employee)
        subordinates_filter = Q(
            employee_id__employee_work_info__reporting_manager_id=employee
        )
        merged_filter = manager_filter | subordinates_filter
        merged_queryset = queryset.filter(merged_filter)
        return merged_queryset

    return queryset.filter(employee_id=employee)
