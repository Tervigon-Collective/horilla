"""Probation confirmation list and actions."""

from __future__ import annotations

import contextlib

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from employee.methods.probation import (
    confirm_work_info,
    days_until_probation_end,
    probation_counts,
    probation_queryset,
)
from employee.models import EmployeeWorkInformation
from horilla.decorators import login_required, permission_required
from horilla.http import HorillaRedirect
from notifications.signals import notify


@login_required
@permission_required("employee.change_employee")
def probation_list(request):
    tab = (request.GET.get("tab") or "all").lower()
    if tab not in ("all", "due", "soon", "overdue"):
        tab = "all"
    rows = list(probation_queryset(request, tab=tab))
    today_counts = probation_counts(request)
    enriched = []
    for wi in rows:
        days = days_until_probation_end(wi)
        enriched.append(
            {
                "work_info": wi,
                "employee": wi.employee_id,
                "days": days,
                "status_label": (
                    _("Overdue")
                    if days is not None and days < 0
                    else (
                        _("Due soon")
                        if days is not None and days <= 7
                        else _("On probation")
                    )
                ),
            }
        )
    return render(
        request,
        "employee/probation/probation_list.html",
        {
            "rows": enriched,
            "tab": tab,
            "counts": today_counts,
        },
    )


@login_required
@permission_required("employee.change_employee")
def probation_confirm(request, pk):
    """Confirm a single employee (work info pk)."""
    work_info = get_object_or_404(
        EmployeeWorkInformation.objects.select_related("employee_id"),
        pk=pk,
    )
    employee = work_info.employee_id
    changed = confirm_work_info(
        work_info, actor=getattr(request.user, "employee_get", None)
    )
    if changed:
        messages.success(
            request,
            _("%(name)s confirmed successfully.")
            % {"name": employee.get_full_name()},
        )
        with contextlib.suppress(Exception):
            notify.send(
                request.user.employee_get,
                recipient=employee.employee_user_id,
                verb="Your employment has been confirmed.",
                verb_ar="تم تثبيت توظيفك.",
                verb_de="Ihre Anstellung wurde bestätigt.",
                verb_es="Su empleo ha sido confirmado.",
                verb_fr="Votre emploi a été confirmé.",
                redirect=reverse("employee-view") + f"?id={employee.id}",
                icon="checkmark",
            )
    else:
        messages.info(request, _("Employee is already confirmed."))
    return redirect(f"{reverse('probation-list')}?tab={request.GET.get('tab', 'all')}")


@login_required
@permission_required("employee.change_employee")
def probation_confirm_bulk(request):
    """Confirm multiple work-info IDs from POST/GET ids."""
    ids = request.POST.getlist("ids") or request.GET.getlist("ids")
    if not ids:
        messages.error(request, _("No employees selected."))
        return HorillaRedirect(request)
    confirmed = 0
    for pk in ids:
        try:
            work_info = EmployeeWorkInformation.objects.select_related(
                "employee_id"
            ).get(pk=pk)
        except (EmployeeWorkInformation.DoesNotExist, ValueError):
            continue
        if confirm_work_info(work_info):
            confirmed += 1
            employee = work_info.employee_id
            with contextlib.suppress(Exception):
                notify.send(
                    request.user.employee_get,
                    recipient=employee.employee_user_id,
                    verb="Your employment has been confirmed.",
                    redirect=reverse("employee-view") + f"?id={employee.id}",
                    icon="checkmark",
                )
    if confirmed:
        messages.success(
            request,
            _("%(count)s employee(s) confirmed.") % {"count": confirmed},
        )
    else:
        messages.info(request, _("No probation employees were confirmed."))
    return redirect(f"{reverse('probation-list')}?tab={request.GET.get('tab', 'all')}")
