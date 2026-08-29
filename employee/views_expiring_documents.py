"""Expiring documents list for HR."""

from __future__ import annotations

from django.contrib import messages
from django.shortcuts import redirect, render
from django.utils.translation import gettext_lazy as _

from base.templatetags.basefilters import is_reportingmanager
from employee.methods.expiring_documents import (
    days_until_expiry,
    expiring_documents_counts,
    expiring_documents_queryset,
)
from horilla.decorators import login_required


@login_required
def expiring_documents_list(request):
    if not (
        request.user.is_superuser
        or request.user.has_perm("horilla_documents.view_document")
        or request.user.has_perm("horilla_documents.view_documentrequest")
        or request.user.has_perm("employee.change_employee")
        or is_reportingmanager(request.user)
    ):
        messages.error(request, _("You don't have permission."))
        return redirect("/")

    tab = (request.GET.get("tab") or "due").lower()
    if tab not in ("all", "due", "soon", "overdue"):
        tab = "due"
    docs = list(expiring_documents_queryset(request, tab=tab)[:500])
    counts = expiring_documents_counts(request)
    rows = []
    for doc in docs:
        days = days_until_expiry(doc)
        if days is not None and days < 0:
            label = _("Expired")
        elif days is not None and days <= 7:
            label = _("Due soon")
        else:
            label = _("Expiring")
        rows.append({"document": doc, "days": days, "status_label": label})
    return render(
        request,
        "employee/documents/expiring_documents.html",
        {"rows": rows, "tab": tab, "counts": counts},
    )
