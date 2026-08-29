"""Payroll run list / workflow views (create → calculate → validate → approve → lock)."""

from __future__ import annotations

from datetime import date

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_http_methods

from base.models import Company
from horilla.decorators import login_required, permission_required
from payroll.methods.payroll_run_engine import (
    PayrollRunLockedError,
    build_bank_transfer_rows,
    calculate_payroll_run,
    create_payroll_run,
    reopen_payroll_run,
    transition_run,
    validate_payroll_run,
)
from payroll.methods.payslip_override import apply_payslip_override, lock_run_attendance
from payroll.methods.attendance_arrear import create_attendance_arrear
from payroll.models.models import Payslip
from payroll.models.payroll_run import PAYROLL_RUN_STATUS, AttendanceArrear, PayrollRun


def _selected_company(request):
    selected = request.session.get("selected_company")
    if selected and selected != "all":
        return Company.objects.filter(pk=selected).first()
    return Company.objects.filter(hq=True).first() or Company.objects.first()


@login_required
@permission_required("payroll.view_payslip")
def payroll_run_list(request):
    company = _selected_company(request)
    runs = PayrollRun.objects.all()
    if company:
        runs = runs.filter(company_id=company)
    runs = runs.order_by("-year", "-month", "-version")[:100]
    return render(
        request,
        "payroll/payroll_run/list.html",
        {
            "runs": runs,
            "company": company,
            "statuses": PAYROLL_RUN_STATUS,
            "today": date.today(),
        },
    )


@login_required
@permission_required("payroll.add_payslip")
@require_http_methods(["GET", "POST"])
def payroll_run_create(request):
    company = _selected_company(request)
    if not company:
        messages.error(request, _("Select a company before creating a payroll run."))
        return redirect("payroll-run-list")

    if request.method == "POST":
        try:
            year = int(request.POST.get("year") or date.today().year)
            month = int(request.POST.get("month") or date.today().month)
        except (TypeError, ValueError):
            messages.error(request, _("Invalid year/month."))
            return redirect("payroll-run-create")
        if month < 1 or month > 12:
            messages.error(request, _("Month must be between 1 and 12."))
            return redirect("payroll-run-create")
        method = request.POST.get("proration_method") or "calendar"
        run = create_payroll_run(
            company,
            year=year,
            month=month,
            proration_method=method,
            notes=(request.POST.get("notes") or "").strip(),
        )
        messages.success(
            request,
            _("Payroll run %(label)s v%(ver)s ready (%(status)s).")
            % {"label": run.period_label, "ver": run.version, "status": run.status},
        )
        return redirect("payroll-run-detail", run_id=run.pk)

    today = date.today()
    return render(
        request,
        "payroll/payroll_run/create.html",
        {"company": company, "year": today.year, "month": today.month},
    )


@login_required
@permission_required("payroll.view_payslip")
def payroll_run_detail(request, run_id):
    run = get_object_or_404(PayrollRun, pk=run_id)
    payslips = Payslip.objects.filter(payroll_run=run).select_related("employee_id")
    return render(
        request,
        "payroll/payroll_run/detail.html",
        {
            "run": run,
            "payslips": payslips,
            "errors": (run.validation_report or {}).get("errors") or [],
            "warnings": (run.validation_report or {}).get("warnings") or [],
            "variance": run.variance_report or {},
        },
    )


@login_required
@permission_required("payroll.add_payslip")
@require_http_methods(["POST"])
def payroll_run_calculate(request, run_id):
    run = get_object_or_404(PayrollRun, pk=run_id)
    try:
        result = calculate_payroll_run(run)
        messages.success(
            request,
            _("Calculated %(created)s payslips (%(skipped)s skipped).")
            % {"created": result["created"], "skipped": result["skipped"]},
        )
        for err in result.get("errors") or []:
            if err.get("level") == "error":
                messages.error(request, err.get("message"))
            else:
                messages.warning(request, err.get("message"))
    except PayrollRunLockedError as exc:
        messages.error(request, str(exc))
    return redirect("payroll-run-detail", run_id=run.pk)


@login_required
@permission_required("payroll.change_payslip")
@require_http_methods(["POST"])
def payroll_run_validate(request, run_id):
    run = get_object_or_404(PayrollRun, pk=run_id)
    report = validate_payroll_run(run)
    if report.get("errors"):
        messages.error(
            request,
            _("Validation failed with %(n)s error(s).")
            % {"n": len(report["errors"])},
        )
    else:
        messages.success(
            request,
            _("Validation passed (%(n)s warning(s)).")
            % {"n": len(report.get("warnings") or [])},
        )
    return redirect("payroll-run-detail", run_id=run.pk)


@login_required
@permission_required("payroll.change_payslip")
@require_http_methods(["POST"])
def payroll_run_transition(request, run_id):
    run = get_object_or_404(PayrollRun, pk=run_id)
    new_status = request.POST.get("status")
    reason = (request.POST.get("reason") or "").strip()
    actor = getattr(request.user, "employee_get", None)
    try:
        transition_run(run, new_status, actor=actor, reason=reason)
        messages.success(
            request,
            _("Payroll run moved to %(status)s.") % {"status": new_status},
        )
    except (PayrollRunLockedError, ValueError) as exc:
        messages.error(request, str(exc))
    return redirect("payroll-run-detail", run_id=run.pk)


@login_required
@permission_required("payroll.change_payslip")
@require_http_methods(["POST"])
def payroll_run_reopen(request, run_id):
    run = get_object_or_404(PayrollRun, pk=run_id)
    reason = (request.POST.get("reason") or "").strip()
    actor = getattr(request.user, "employee_get", None)
    try:
        new_run = reopen_payroll_run(run, reason=reason, actor=actor)
        messages.success(
            request,
            _("Opened payroll version v%(ver)s. Recalculate before locking.")
            % {"ver": new_run.version},
        )
        return redirect("payroll-run-detail", run_id=new_run.pk)
    except (PayrollRunLockedError, ValueError) as exc:
        messages.error(request, str(exc))
        return redirect("payroll-run-detail", run_id=run.pk)


@login_required
@permission_required("payroll.change_payslip")
@require_http_methods(["POST"])
def payroll_run_lock_attendance(request, run_id):
    run = get_object_or_404(PayrollRun, pk=run_id)
    try:
        lock_run_attendance(run, actor=getattr(request.user, "employee_get", None))
        messages.success(request, _("Attendance locked for this payroll period."))
    except PayrollRunLockedError as exc:
        messages.error(request, str(exc))
    return redirect("payroll-run-detail", run_id=run.pk)


@login_required
@permission_required("payroll.change_payslip")
@require_http_methods(["POST"])
def payslip_override_create(request, payslip_id):
    payslip = get_object_or_404(Payslip, pk=payslip_id)
    field_name = request.POST.get("field_name") or "net_pay"
    reason = (request.POST.get("reason") or "").strip()
    component_title = (request.POST.get("component_title") or "").strip() or None
    try:
        revised_value = float(request.POST.get("revised_value"))
    except (TypeError, ValueError):
        messages.error(request, _("Enter a valid revised amount."))
        return redirect("view-created-payslip", payslip_id=payslip.pk)
    actor = getattr(request.user, "employee_get", None)
    try:
        apply_payslip_override(
            payslip,
            field_name=field_name,
            revised_value=revised_value,
            reason=reason,
            requested_by=actor,
            approved_by=actor,
            component_title=component_title,
            attachment=request.FILES.get("attachment"),
        )
        messages.success(request, _("Override applied and logged for audit."))
    except (PayrollRunLockedError, ValueError) as exc:
        messages.error(request, str(exc))
    return redirect("view-created-payslip", payslip_id=payslip.pk)


@login_required
@permission_required("payroll.view_payslip")
def payroll_run_bank_file(request, run_id):
    """Download bank transfer CSV for a locked/paid/published run."""
    import csv
    from django.http import HttpResponse

    run = get_object_or_404(PayrollRun, pk=run_id)
    if run.status not in ("locked", "paid", "published", "finance_approved"):
        messages.error(
            request,
            _("Bank file is available after Finance approval / lock."),
        )
        return redirect("payroll-run-detail", run_id=run.pk)

    rows = build_bank_transfer_rows(run)
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = (
        f'attachment; filename="bank_transfer_{run.period_label}_v{run.version}.csv"'
    )
    writer = csv.DictWriter(
        response,
        fieldnames=[
            "employee_id",
            "employee_name",
            "account_holder",
            "account_number",
            "ifsc",
            "bank_name",
            "amount",
            "payslip_id",
            "period",
        ],
    )
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return response


@login_required
@permission_required("payroll.add_payslip")
@require_http_methods(["GET", "POST"])
def attendance_arrear_create(request):
    """Create a retro attendance arrear (does not mutate locked months)."""
    from employee.models import Employee

    if request.method == "POST":
        try:
            emp_id = int(request.POST.get("employee_id"))
            days = float(request.POST.get("days"))
            source_start = date.fromisoformat(request.POST.get("source_period_start"))
            source_end = date.fromisoformat(request.POST.get("source_period_end"))
        except (TypeError, ValueError):
            messages.error(request, _("Invalid attendance arrear input."))
            return redirect("attendance-arrear-create")
        employee = get_object_or_404(Employee, pk=emp_id)
        reason = (request.POST.get("reason") or "").strip()
        try:
            arrear = create_attendance_arrear(
                employee,
                source_period_start=source_start,
                source_period_end=source_end,
                days=days,
                reason=reason,
            )
            messages.success(
                request,
                _("Attendance arrear created: %(days)s day(s), ₹%(amt)s for %(name)s")
                % {"days": arrear.days, "amt": arrear.amount, "name": employee},
            )
            return redirect("attendance-arrear-list")
        except ValueError as exc:
            messages.error(request, str(exc))

    employees = Employee.objects.filter(is_active=True).order_by("employee_first_name")[
        :500
    ]
    return render(
        request,
        "payroll/payroll_run/attendance_arrear_form.html",
        {"employees": employees, "today": date.today()},
    )


@login_required
@permission_required("payroll.view_payslip")
def attendance_arrear_list(request):
    arrears = AttendanceArrear.objects.select_related("employee_id").order_by("-id")[
        :200
    ]
    return render(
        request,
        "payroll/payroll_run/attendance_arrear_list.html",
        {"arrears": arrears},
    )
