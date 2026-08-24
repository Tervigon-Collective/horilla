"""CTC wizard, salary revision letters, arrears pay-out, and salary hold/release."""

from datetime import date

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_http_methods

from base.methods import template_pdf
from employee.models import Employee
from horilla.decorators import login_required, permission_required
from payroll.methods.ctc_wizard import (
    apply_ctc_split_to_contract,
    current_ctc_snapshot,
    hold_salary,
    is_salary_on_hold,
    pay_revision_arrears,
    record_salary_revision,
    release_salary,
    split_monthly_ctc,
)
from payroll.models.models import Contract
from payroll.models.salary_revision import SalaryHold, SalaryRevision


def _employee_in_selected_company(request, employee) -> bool:
    """True when session company is all, or employee belongs to selected company."""
    selected = request.session.get("selected_company")
    if not selected or selected == "all":
        return True
    work = getattr(employee, "employee_work_info", None)
    company = getattr(work, "company_id", None) if work else None
    if company is None:
        return False
    return str(getattr(company, "pk", company)) == str(selected)


@login_required
@permission_required("payroll.change_contract")
def ctc_wizard(request, contract_id):
    contract = get_object_or_404(Contract, pk=contract_id)
    metro = request.GET.get("metro", "1") != "0"
    snapshot = current_ctc_snapshot(contract)

    if request.method == "POST":
        try:
            monthly_ctc = float(request.POST.get("monthly_ctc", 0))
        except (TypeError, ValueError):
            monthly_ctc = 0
        metro = request.POST.get("metro") == "1"
        note = (request.POST.get("note") or "").strip()
        try:
            effective_date = date.fromisoformat(request.POST.get("effective_date"))
        except (TypeError, ValueError):
            effective_date = date.today()
        if monthly_ctc <= 0:
            messages.error(request, _("Enter a valid monthly CTC amount."))
        else:
            previous = current_ctc_snapshot(contract)
            split = split_monthly_ctc(monthly_ctc, metro=metro)
            apply_ctc_split_to_contract(contract, split)
            revision = record_salary_revision(
                contract,
                split,
                previous=previous,
                effective_date=effective_date,
                note=note,
            )
            messages.success(
                request,
                _(
                    "CTC applied: Basic %(basic)s, HRA %(hra)s, Special %(special)s"
                )
                % {"basic": split.basic, "hra": split.hra, "special": split.special},
            )
            return redirect("salary-revision-letter", revision_id=revision.pk)

    preview_ctc = snapshot["monthly_ctc"] or contract.wage or 0
    try:
        preview_ctc = float(request.GET.get("monthly_ctc", preview_ctc))
    except (TypeError, ValueError):
        pass
    split = split_monthly_ctc(preview_ctc, metro=metro) if preview_ctc else None
    revisions = SalaryRevision.objects.filter(contract_id=contract).order_by(
        "-effective_date", "-id"
    )[:10]

    return render(
        request,
        "payroll/contract/ctc_wizard.html",
        {
            "contract": contract,
            "split": split,
            "metro": metro,
            "preview_ctc": preview_ctc,
            "snapshot": snapshot,
            "revisions": revisions,
            "today": date.today().isoformat(),
        },
    )


@login_required
@permission_required("payroll.view_contract")
def salary_revision_list(request):
    qs = SalaryRevision.objects.select_related(
        "employee_id", "contract_id", "employee_id__employee_work_info__company_id"
    )
    selected = request.session.get("selected_company")
    if selected and selected != "all":
        qs = qs.filter(employee_id__employee_work_info__company_id=selected)
    qs = qs[:200]
    return render(
        request,
        "payroll/contract/salary_revision_list.html",
        {"revisions": qs},
    )


@login_required
@permission_required("payroll.view_contract")
def salary_revision_letter(request, revision_id):
    revision = get_object_or_404(
        SalaryRevision.objects.select_related(
            "employee_id",
            "contract_id",
            "employee_id__employee_work_info",
            "employee_id__employee_work_info__company_id",
            "employee_id__employee_work_info__job_position_id",
            "employee_id__employee_work_info__department_id",
            "arrears_allowance",
        ),
        pk=revision_id,
    )
    employee = revision.employee_id
    if not _employee_in_selected_company(request, employee):
        messages.error(request, _("You don't have permission for this company."))
        return redirect("salary-revision-list")
    work = getattr(employee, "employee_work_info", None)
    company = work.company_id if work else None
    context = {
        "revision": revision,
        "employee": employee,
        "work": work,
        "company": company,
        "contract": revision.contract_id,
        "on_hold": is_salary_on_hold(employee),
        "today": date.today().isoformat(),
    }
    if request.GET.get("format") == "pdf":
        html_content = render_to_string(
            "payroll/contract/salary_revision_letter_pdf.html", context
        )
        slug = (employee.get_full_name() or "employee").replace(" ", "_")[:30]
        return template_pdf(
            template=html_content,
            html=True,
            filename=f"Increment_Letter_{slug}_{revision.effective_date}",
        )
    return render(request, "payroll/contract/salary_revision_letter.html", context)


@login_required
@permission_required("payroll.change_contract")
@require_http_methods(["POST"])
def pay_salary_arrears(request, revision_id):
    revision = get_object_or_404(SalaryRevision, pk=revision_id)
    if not _employee_in_selected_company(request, revision.employee_id):
        messages.error(request, _("You don't have permission for this company."))
        return redirect("salary-revision-list")
    try:
        payment_date = date.fromisoformat(request.POST.get("payment_date"))
    except (TypeError, ValueError):
        payment_date = date.today()
    try:
        allowance = pay_revision_arrears(revision, payment_date=payment_date)
    except ValueError:
        if revision.arrears_paid:
            messages.error(request, _("Arrears are already scheduled for this revision."))
        else:
            messages.error(request, _("No arrears amount to pay for this revision."))
        return redirect("salary-revision-letter", revision_id=revision.pk)

    messages.success(
        request,
        _(
            "Arrears of %(amount)s scheduled as one-time allowance on %(date)s "
            "(will appear on the payslip covering that date)."
        )
        % {"amount": allowance.amount, "date": payment_date},
    )
    return redirect("salary-revision-letter", revision_id=revision.pk)


@login_required
@permission_required("payroll.view_contract")
def salary_hold_list(request):
    selected = request.session.get("selected_company")
    holds = SalaryHold.objects.select_related(
        "employee_id",
        "held_by",
        "released_by",
        "employee_id__employee_work_info__company_id",
    )
    if selected and selected != "all":
        holds = holds.filter(employee_id__employee_work_info__company_id=selected)

    active_holds = holds.filter(is_active=True, released_on__isnull=True)[:200]
    history = holds.filter(released_on__isnull=False).order_by("-released_on")[:50]

    employees = Employee.objects.filter(is_active=True).select_related(
        "employee_work_info__company_id"
    )
    if selected and selected != "all":
        employees = employees.filter(employee_work_info__company_id=selected)
    employees = employees.order_by("employee_first_name", "employee_last_name")[:500]

    return render(
        request,
        "payroll/contract/salary_hold_list.html",
        {
            "active_holds": active_holds,
            "history": history,
            "employees": employees,
            "today": date.today().isoformat(),
        },
    )


@login_required
@permission_required("payroll.change_contract")
@require_http_methods(["POST"])
def salary_hold_toggle(request):
    employee_id = request.POST.get("employee_id")
    action = (request.POST.get("action") or "").strip().lower()
    reason = (request.POST.get("reason") or "").strip()
    employee = get_object_or_404(Employee, pk=employee_id)
    if not _employee_in_selected_company(request, employee):
        messages.error(request, _("You don't have permission for this company."))
        return redirect("salary-hold-list")
    actor = getattr(request.user, "employee_get", None)

    if action == "hold":
        hold_salary(employee, reason=reason, held_by=actor)
        messages.success(
            request,
            _("Salary on hold for %(name)s. Payslips will not be generated.")
            % {"name": employee.get_full_name()},
        )
    elif action == "release":
        count = release_salary(employee, released_by=actor)
        if count:
            messages.success(
                request,
                _("Salary released for %(name)s.")
                % {"name": employee.get_full_name()},
            )
        else:
            messages.info(request, _("No active salary hold for this employee."))
    else:
        messages.error(request, _("Unknown action."))
    return redirect("salary-hold-list")
