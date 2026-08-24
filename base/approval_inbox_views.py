"""Web unified approval inbox."""

import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_http_methods
from rest_framework.parsers import FormParser, JSONParser
from rest_framework.request import Request

from horilla.decorators import hx_request_required


@login_required
def approval_inbox(request):
    from base.pending_approvals import get_pending_inbox

    type_filter = request.GET.get("type")
    try:
        page = int(request.GET.get("page", 1))
        page_size = int(request.GET.get("page_size", 25))
    except (TypeError, ValueError):
        page, page_size = 1, 25

    inbox = get_pending_inbox(request, type_filter, page, page_size)
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse(inbox)

    type_options = [
        ("", _("All")),
        ("leave", _("Leave")),
        ("attendance", _("Attendance")),
        ("asset", _("Assets")),
        ("shift", _("Shift")),
        ("work_type", _("Work Type")),
        ("reimbursement", _("Reimbursement")),
    ]

    return render(
        request,
        "base/approval_inbox.html",
        {
            "inbox": inbox,
            "type_filter": type_filter or "",
            "type_options": type_options,
            "page": page,
        },
    )


@login_required
@require_http_methods(["POST"])
def approval_inbox_action(request):
    from base.pending_approvals import execute_pending_action

    if request.content_type and "application/json" in request.content_type:
        try:
            body = json.loads(request.body.decode() or "{}")
        except json.JSONDecodeError:
            body = {}
    else:
        body = request.POST.dict()

    item_type = body.get("type")
    item_id = body.get("id")
    action = body.get("action")
    payload = body.get("payload") or {}

    if not item_type or item_id is None or not action:
        return JsonResponse({"error": _("type, id, and action are required.")}, status=400)

    drf_request = Request(request, parsers=[FormParser(), JSONParser()])
    response = execute_pending_action(
        drf_request, item_type, int(item_id), action, payload
    )
    if response.status_code >= 400:
        data = response.data if hasattr(response, "data") else {"error": _("Action failed.")}
        return JsonResponse(data, status=response.status_code)
    return JsonResponse({"status": "ok"})


@login_required
@hx_request_required
def approval_inbox_row(request, item_type, item_id):
    """Refresh a single inbox row after action (HTMX)."""
    from base.pending_approvals import INBOX_SOURCES, get_approval_context

    ctx = get_approval_context(request.user)
    for type_name, qs_fn, serialize_fn, *select_related in INBOX_SOURCES:
        if type_name != item_type:
            continue
        qs = qs_fn(request).filter(pk=item_id)
        rels = [r for r in select_related if r]
        if rels:
            qs = qs.select_related(*rels)
        obj = qs.first()
        if not obj:
            return JsonResponse({"removed": True})
        return render(
            request,
            "base/approval_inbox_row.html",
            {"item": serialize_fn(obj, ctx)},
        )
    return JsonResponse({"error": _("Not found.")}, status=404)


@login_required
def approval_inbox_export(request):
    from base.pending_approvals import export_pending_inbox_rows
    from payroll.methods.india_statutory_excel import rows_to_excel_response

    type_filter = request.GET.get("type") or "all"
    rows = export_pending_inbox_rows(request)
    fmt = (request.GET.get("format") or "csv").lower()
    filename_base = f"approval_inbox_{type_filter}"

    if fmt == "csv":
        import csv
        from io import StringIO

        from django.http import HttpResponse

        buffer = StringIO()
        writer = csv.writer(buffer)
        writer.writerows(rows)
        response = HttpResponse(buffer.getvalue(), content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="{filename_base}.csv"'
        return response

    return rows_to_excel_response(rows, f"{filename_base}.xlsx")
