"""
Views for Indian statutory payroll settings and Form 16.
"""

import calendar
from datetime import date

import pandas as pd
from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext_lazy as gettext

from base.models import Company
from employee.models import Employee
from horilla.decorators import login_required, permission_required
from horilla.http import HorillaRedirect
from payroll.forms.india_statutory_forms import (
    EmployeeStatutoryProfileForm,
    IndiaStatutorySettingsForm,
)
from payroll.methods.india_statutory import (
    aggregate_form16,
    aggregate_form16_bulk,
    aggregate_form24q,
    aggregate_gratuity_register,
    aggregate_statutory_challan,
    aggregate_tax_computation,
    build_epf_ecr_payload,
    challan_csv_rows,
    financial_year_bounds,
    form24q_csv_rows,
    generate_oltas_challan_text,
    generate_traces_zip,
    quarter_bounds,
    register_csv_rows,
)
from payroll.methods.accounting_export import (
    aggregate_payroll_journal,
    payroll_journal_csv_rows,
)
from payroll.methods.india_statutory_excel import (
    ctc_template_dataframe,
    dataframe_to_excel_response,
    export_ctc_structures,
    export_dataframe,
    export_fnf_estimates,
    export_rows,
    export_statutory_profiles,
    form16_import_template_dataframe,
    import_ctc_structures,
    import_form16_bulk_save,
    import_statutory_profiles,
    read_upload_dataframe,
    statutory_profiles_template_dataframe,
)
from payroll.models.india_statutory import (
    EmployeeStatutoryProfile,
    Form16Record,
    IndiaStatutorySettings,
)


def _company_slug(company) -> str:
    return (company.company if company else "company").replace(" ", "_")[:30]


def _file_response(rows: list[list], filename_base: str, fmt: str) -> HttpResponse:
    return export_rows(rows, filename_base, fmt)


IMPORT_REDIRECT_VIEWS = {
    "statutory-excel-hub",
    "form16-list",
    "challan-list",
    "form24q-list",
    "accounting-export-list",
    "india-statutory-settings",
    "statutory-register",
}


def _import_redirect(request, default: str = "statutory-excel-hub"):
    target = (request.POST.get("redirect_to") or default).strip()
    if target in IMPORT_REDIRECT_VIEWS:
        return redirect(target)
    return redirect(default)


def _export_pair(url_name: str, **query) -> dict[str, str]:
    from django.urls import reverse
    from urllib.parse import urlencode

    base = reverse(url_name)
    params = urlencode(query)
    prefix = f"{base}?{params}" if params else base
    join = "&" if params else "?"
    return {
        "excel": f"{prefix}{join}format=xlsx",
        "csv": f"{prefix}{join}format=csv",
    }


def _selected_company(request):
    selected = request.session.get("selected_company")
    if selected and selected != "all":
        return Company.objects.filter(id=selected).first()
    return Company.objects.filter(hq=True).first() or Company.objects.first()


def _require_selected_company(request):
    """Refuse settings writes when company filter is 'all' (would silently hit HQ)."""
    selected = request.session.get("selected_company")
    if selected and selected != "all":
        company = Company.objects.filter(id=selected).first()
        if company:
            return company
    messages.error(
        request,
        gettext("Select a specific company first (company filter cannot be All)."),
    )
    return None


@login_required
@permission_required("payroll.change_payslip")
def india_statutory_settings(request):
    company = _require_selected_company(request)
    if not company:
        return render(
            request,
            "payroll/india_statutory/settings.html",
            {"form": None, "company": None},
        )

    instance, _ = IndiaStatutorySettings.objects.get_or_create(
        company_id=company,
        defaults={"is_enabled": False},
    )
    if request.method == "POST":
        form = IndiaStatutorySettingsForm(request.POST, instance=instance)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.company_id = company
            obj.save()
            messages.success(request, gettext("India statutory settings saved."))
            form = IndiaStatutorySettingsForm(instance=obj)
    else:
        form = IndiaStatutorySettingsForm(instance=instance)

    profile_exports = _export_pair("statutory-profiles-export")
    ctc_exports = _export_pair("ctc-structure-export")

    return render(
        request,
        "payroll/india_statutory/settings.html",
        {
            "form": form,
            "company": company,
            "settings": instance,
            "profiles_export_csv_url": profile_exports["csv"],
            "ctc_export_csv_url": ctc_exports["csv"],
            "profiles_template_csv_url": f"{reverse('statutory-profiles-template')}?format=csv",
            "ctc_template_csv_url": f"{reverse('ctc-structure-template')}?format=csv",
            "redirect_view": "india-statutory-settings",
            "show_profiles_export": True,
            "show_ctc_export": True,
            "show_profiles_import": True,
            "show_ctc_import": True,
        },
    )


@login_required
@permission_required("payroll.view_payslip")
def employee_statutory_profile(request, emp_id):
    from payroll.cbv.accessibility import can_view_all_payslips, is_payroll_admin

    employee = get_object_or_404(Employee, pk=emp_id)
    actor = getattr(request.user, "employee_get", None)
    if not (
        can_view_all_payslips(request)
        or (actor and actor == employee)
    ):
        messages.error(request, gettext("You don't have permission."))
        return HorillaRedirect(request)
    profile, _ = EmployeeStatutoryProfile.objects.get_or_create(employee_id=employee)
    if request.method == "POST":
        if not (is_payroll_admin(request) or request.user.has_perm("payroll.change_payslip")):
            messages.error(
                request,
                gettext("You do not have permission to update statutory profiles."),
            )
            form = EmployeeStatutoryProfileForm(instance=profile)
        else:
            form = EmployeeStatutoryProfileForm(request.POST, instance=profile)
            if form.is_valid():
                form.save()
                messages.success(request, gettext("Statutory profile updated."))
    else:
        form = EmployeeStatutoryProfileForm(instance=profile)
    return render(
        request,
        "payroll/india_statutory/employee_profile.html",
        {"form": form, "employee": employee},
    )


@login_required
@permission_required("payroll.view_payslip")
def form16_view(request, emp_id):
    from payroll.cbv.accessibility import can_view_all_payslips

    employee = get_object_or_404(Employee, pk=emp_id)
    actor = getattr(request.user, "employee_get", None)
    if not (
        can_view_all_payslips(request)
        or (actor and actor == employee)
    ):
        messages.error(request, gettext("You don't have permission."))
        return HorillaRedirect(request)
    fy_param = request.GET.get("fy")
    today = date.today()
    _, _, default_fy_start, _ = financial_year_bounds(today)
    try:
        fy_start = int(fy_param) if fy_param else default_fy_start
    except (TypeError, ValueError):
        fy_start = default_fy_start

    context = aggregate_form16(employee, fy_start)
    context["financial_year_start"] = fy_start

    if request.GET.get("save") == "1":
        if not context.get("payslip_count"):
            messages.error(
                request,
                gettext("No payslips found for this financial year. Form 16 was not saved."),
            )
        else:
            Form16Record.objects.update_or_create(
                employee_id=employee,
                financial_year_start=fy_start,
                defaults={
                    "financial_year_end": fy_start + 1,
                    "gross_salary": context["totals"]["gross_salary"],
                    "pf_employee_total": context["totals"]["pf_employee"],
                    "pf_employer_total": context["totals"]["pf_employer"],
                    "esi_employee_total": context["totals"]["esi_employee"],
                    "pt_total": context["totals"]["pt"],
                    "tds_total": context["totals"]["tds"],
                    "net_salary": context["totals"]["net_salary"],
                    "regime": context["regime"],
                    "summary_json": context["totals"],
                },
            )
            messages.success(request, gettext("Form 16 record saved."))

    if request.GET.get("format") == "pdf":
        from django.template.loader import render_to_string

        from base.methods import template_pdf

        if company := context.get("company"):
            context["statutory_settings"] = getattr(
                company, "india_statutory_settings", None
            )
        html_content = render_to_string(
            "payroll/india_statutory/form16_pdf.html", context
        )
        return template_pdf(
            template=html_content,
            html=True,
            filename=f"Form16_{employee.id}_FY{fy_start}",
        )

    return render(request, "payroll/india_statutory/form16.html", context)


@login_required
@permission_required("payroll.view_payslip")
def tax_computation_view(request, emp_id):
    """Income-tax computation sheet (HTML or PDF) for an employee FY."""
    employee = get_object_or_404(Employee, pk=emp_id)
    fy_param = request.GET.get("fy")
    today = date.today()
    _, _, default_fy_start, _ = financial_year_bounds(today)
    try:
        fy_start = int(fy_param) if fy_param else default_fy_start
    except (TypeError, ValueError):
        fy_start = default_fy_start

    context = aggregate_tax_computation(employee, fy_start)
    if company := context.get("company"):
        context["statutory_settings"] = getattr(
            company, "india_statutory_settings", None
        )

    if request.GET.get("format") == "pdf" or request.GET.get("pdf") == "1":
        from django.template.loader import render_to_string

        from base.methods import template_pdf

        html_content = render_to_string(
            "payroll/india_statutory/tax_computation_pdf.html", context
        )
        return template_pdf(
            template=html_content,
            html=True,
            filename=f"TaxComputation_{employee.id}_FY{fy_start}",
        )

    # Default: PDF download (computation sheet is a document, not a dashboard page)
    from django.template.loader import render_to_string

    from base.methods import template_pdf

    html_content = render_to_string(
        "payroll/india_statutory/tax_computation_pdf.html", context
    )
    return template_pdf(
        template=html_content,
        html=True,
        filename=f"TaxComputation_{employee.id}_FY{fy_start}",
    )


@login_required
@permission_required("payroll.view_payslip")
def form16_list(request):
    from employee.models import Employee

    today = date.today()
    _, _, default_fy_start, _ = financial_year_bounds(today)
    fy_param = request.GET.get("fy")
    try:
        fy_start = int(fy_param) if fy_param else default_fy_start
    except (TypeError, ValueError):
        fy_start = default_fy_start

    company = _selected_company(request)
    saved_qs = Form16Record.objects.filter(financial_year_start=fy_start)
    if company:
        saved_qs = saved_qs.filter(
            employee_id__employee_work_info__company_id=company
        ).distinct()
    saved_records = {
        r.employee_id_id: r
        for r in saved_qs.select_related("employee_id")
    }

    employees = Employee.objects.all()
    if company:
        employees = employees.filter(
            employee_work_info__company_id=company
        ).distinct()

    employees = employees.order_by("employee_first_name", "employee_last_name")[:300]
    bulk_summaries = aggregate_form16_bulk(employees, fy_start)

    rows = []
    summary_gross = 0
    summary_tds = 0
    saved_count = 0
    for employee in employees:
        summary = bulk_summaries.get(employee.id, {"totals": {}, "payslip_count": 0})
        totals = summary["totals"]
        saved = saved_records.get(employee.id)
        if summary["payslip_count"] == 0 and not saved:
            continue
        if saved:
            saved_count += 1
            gross = float(getattr(saved, "gross_salary", 0) or 0)
            tds = float(getattr(saved, "tds_total", 0) or 0)
            pf = float(getattr(saved, "pf_employee_total", 0) or 0)
            if summary["payslip_count"] > 0:
                gross = float(totals.get("gross_salary", gross) or 0)
                tds = float(totals.get("tds", tds) or 0)
                pf = float(totals.get("pf_employee", pf) or 0)
        else:
            gross = float(totals.get("gross_salary", 0) or 0)
            tds = float(totals.get("tds", 0) or 0)
            pf = float(totals.get("pf_employee", 0) or 0)
        summary_gross += gross
        summary_tds += tds
        rows.append(
            {
                "employee": employee,
                "gross": gross,
                "tds": tds,
                "pf": pf,
                "payslip_count": summary["payslip_count"],
                "saved": bool(saved),
                "saved_at": saved.generated_at if saved else None,
            }
        )

    fy_options = [
        default_fy_start - 1,
        default_fy_start,
        default_fy_start + 1,
    ]

    settings = None
    if company:
        settings = IndiaStatutorySettings.objects.filter(company_id=company).first()

    exports = _export_pair("form16-excel-export", fy=fy_start)
    profile_exports = _export_pair("statutory-profiles-export")

    return render(
        request,
        "payroll/india_statutory/form16_list.html",
        {
            "rows": rows,
            "financial_year": f"{fy_start}-{fy_start + 1}",
            "financial_year_start": fy_start,
            "fy_options": fy_options,
            "company": company,
            "settings": settings,
            "total_employees": len(rows),
            "summary_gross": summary_gross,
            "summary_tds": summary_tds,
            "saved_count": saved_count,
            "export_csv_url": exports["csv"],
            "export_label": gettext("Form 16"),
            "profiles_export_csv_url": profile_exports["csv"],
            "show_profiles_export": True,
            "template_csv_url": f"{reverse('form16-import-template')}?fy={fy_start}&format=csv",
            "template_label": gettext("Form 16 import template"),
            "redirect_view": "form16-list",
            "import_fy": fy_start,
            "show_form16_import": True,
            "show_profiles_import": True,
        },
    )


def _parse_period_month(request):
    today = date.today()
    year = request.GET.get("year")
    month = request.GET.get("month")
    try:
        y = int(year) if year else today.year
        m = int(month) if month else today.month
    except (TypeError, ValueError):
        y, m = today.year, today.month
    m = max(1, min(12, m))
    period_start = date(y, m, 1)
    last_day = calendar.monthrange(y, m)[1]
    period_end = date(y, m, last_day)
    return period_start, period_end, y, m


@login_required
@permission_required("payroll.view_payslip")
def challan_list(request):
    company = _selected_company(request)
    settings = None
    if company:
        settings = IndiaStatutorySettings.objects.filter(company_id=company).first()

    period_start, period_end, year, month = _parse_period_month(request)
    challan_data = aggregate_statutory_challan(company, period_start, period_end)

    month_options = []
    for m in range(1, 13):
        month_options.append({"value": m, "label": date(2000, m, 1).strftime("%B")})

    exports = _export_pair(
        "challan-export", year=year, month=month, type="all"
    )
    oltas_url = (
        f"{reverse('oltas-challan-download')}?year={year}&month={month}"
    )

    return render(
        request,
        "payroll/india_statutory/challan_list.html",
        {
            "company": company,
            "settings": settings,
            "challan_data": challan_data,
            "selected_year": year,
            "selected_month": month,
            "month_options": month_options,
            "year_options": [date.today().year - 1, date.today().year, date.today().year + 1],
            "export_csv_url": exports["csv"],
            "export_label": gettext("Challan"),
            "oltas_url": oltas_url,
        },
    )


@login_required
@permission_required("payroll.view_payslip")
def challan_export(request):
    company = _selected_company(request)
    period_start, period_end, year, month = _parse_period_month(request)
    export_type = request.GET.get("type", "all")
    fmt = (request.GET.get("format") or "csv").lower()
    challan_data = aggregate_statutory_challan(company, period_start, period_end)
    rows = challan_csv_rows(challan_data, export_type)

    company_slug = _company_slug(company)
    filename_base = f"challan_{export_type}_{year}_{month:02d}_{company_slug}"
    return _file_response(rows, filename_base, fmt)


REGISTER_TYPES = ("pf", "esi", "pt", "lwf", "bonus", "gratuity")


def _register_type(request) -> str:
    kind = (request.GET.get("type") or "pf").lower()
    return kind if kind in REGISTER_TYPES else "pf"


@login_required
@permission_required("payroll.view_payslip")
def statutory_register(request):
    company = _selected_company(request)
    settings = None
    if company:
        settings = IndiaStatutorySettings.objects.filter(company_id=company).first()

    period_start, period_end, year, month = _parse_period_month(request)
    register_type = _register_type(request)
    if register_type == "gratuity":
        challan_data = aggregate_gratuity_register(company, period_end)
    else:
        challan_data = aggregate_statutory_challan(company, period_start, period_end)

    month_options = []
    for m in range(1, 13):
        month_options.append({"value": m, "label": date(2000, m, 1).strftime("%B")})

    exports = _export_pair(
        "statutory-register-export", year=year, month=month, type=register_type
    )

    return render(
        request,
        "payroll/india_statutory/statutory_register.html",
        {
            "company": company,
            "settings": settings,
            "challan_data": challan_data,
            "register_type": register_type,
            "selected_year": year,
            "selected_month": month,
            "month_options": month_options,
            "year_options": [date.today().year - 1, date.today().year, date.today().year + 1],
            "export_csv_url": exports["csv"],
            "export_excel_url": exports["excel"],
            "export_label": gettext("Register"),
        },
    )


@login_required
@permission_required("payroll.view_payslip")
def statutory_register_export(request):
    company = _selected_company(request)
    period_start, period_end, year, month = _parse_period_month(request)
    register_type = _register_type(request)
    fmt = (request.GET.get("format") or "csv").lower()
    if register_type == "gratuity":
        challan_data = aggregate_gratuity_register(company, period_end)
    else:
        challan_data = aggregate_statutory_challan(company, period_start, period_end)
    rows = register_csv_rows(challan_data, register_type)
    company_slug = _company_slug(company)
    filename_base = f"{register_type}_register_{year}_{month:02d}_{company_slug}"
    return _file_response(rows, filename_base, fmt)


def _parse_quarter(request):
    today = date.today()
    _, _, fy_start, _ = financial_year_bounds(today)
    if today.month >= 4:
        default_quarter = (today.month - 4) // 3 + 1
    else:
        default_quarter = 4
    try:
        year = int(request.GET.get("year", fy_start))
        quarter = int(request.GET.get("quarter", default_quarter))
    except (TypeError, ValueError):
        year, quarter = fy_start, default_quarter
    quarter = max(1, min(4, quarter))
    period_start, period_end = quarter_bounds(year, quarter)
    return period_start, period_end, year, quarter


@login_required
@permission_required("payroll.view_payslip")
def form24q_list(request):
    company = _selected_company(request)
    settings = None
    if company:
        settings = IndiaStatutorySettings.objects.filter(company_id=company).first()

    period_start, period_end, year, quarter = _parse_quarter(request)
    form24q_data = aggregate_form24q(company, period_start, period_end)
    today = date.today()
    _, _, default_fy_start, _ = financial_year_bounds(today)
    exports = _export_pair(
        "form24q-export", year=year, quarter=quarter
    )
    traces_url = (
        f"{reverse('traces-24q-download')}?year={year}&quarter={quarter}"
    )

    return render(
        request,
        "payroll/india_statutory/form24q_list.html",
        {
            "company": company,
            "settings": settings,
            "form24q_data": form24q_data,
            "selected_year": year,
            "selected_quarter": quarter,
            "fy_options": [default_fy_start - 1, default_fy_start, default_fy_start + 1],
            "quarter_options": [
                {"value": 1, "label": "Q1 (Apr–Jun)"},
                {"value": 2, "label": "Q2 (Jul–Sep)"},
                {"value": 3, "label": "Q3 (Oct–Dec)"},
                {"value": 4, "label": "Q4 (Jan–Mar)"},
            ],
            "export_csv_url": exports["csv"],
            "export_label": gettext("Form 24Q"),
            "traces_url": traces_url,
        },
    )


@login_required
@permission_required("payroll.view_payslip")
def form24q_export(request):
    company = _selected_company(request)
    period_start, period_end, year, quarter = _parse_quarter(request)
    form24q_data = aggregate_form24q(company, period_start, period_end)
    rows = form24q_csv_rows(form24q_data)
    fmt = (request.GET.get("format") or "csv").lower()

    company_slug = _company_slug(company)
    filename_base = f"form24q_Q{quarter}_FY{year}_{company_slug}"
    return _file_response(rows, filename_base, fmt)


@login_required
@permission_required("payroll.view_payslip")
def traces_efiling(request):
    """TRACES / OLTAS e-filing hub page."""
    company = _selected_company(request)
    settings = None
    if company:
        settings = IndiaStatutorySettings.objects.filter(company_id=company).first()

    today = date.today()
    _, _, default_fy_start, _ = financial_year_bounds(today)
    _, _, fy_year, quarter = _parse_quarter(request)
    _, _, calendar_year, month = _parse_period_month(request)

    return render(
        request,
        "payroll/india_statutory/traces_efiling.html",
        {
            "company": company,
            "settings": settings,
            "selected_fy_year": fy_year,
            "selected_quarter": quarter,
            "fy_options": [default_fy_start - 1, default_fy_start, default_fy_start + 1],
            "quarter_options": [
                {"value": 1, "label": "Q1 (Apr–Jun)"},
                {"value": 2, "label": "Q2 (Jul–Sep)"},
                {"value": 3, "label": "Q3 (Oct–Dec)"},
                {"value": 4, "label": "Q4 (Jan–Mar)"},
            ],
            "selected_month": month,
            "selected_calendar_year": calendar_year,
            "month_options": [
                {"value": m, "label": date(2000, m, 1).strftime("%B")} for m in range(1, 13)
            ],
            "year_options": [today.year - 1, today.year, today.year + 1],
            "default_bsr": getattr(settings, "bsr_code", "") or "",
            "default_tan": getattr(settings, "tan_number", "") or "",
            "default_deposit_date": today.isoformat(),
        },
    )


def _challan_meta(request, settings=None) -> dict:
    """BSR / challan serial / deposit date from query string or settings."""
    bsr = (request.GET.get("bsr") or "").strip()
    if not bsr and settings:
        bsr = getattr(settings, "bsr_code", "") or ""
    return {
        "bsr_code": bsr[:7],
        "challan_serial": (request.GET.get("challan_serial") or "").strip(),
        "deposit_date": (request.GET.get("deposit_date") or "").strip() or None,
    }


@login_required
@permission_required("payroll.view_payslip")
def traces_24q_download(request):
    """Download NSDL RPU pack (statement + annexure CSV + CSI challan)."""
    company = _selected_company(request)
    period_start, period_end, year, quarter = _parse_quarter(request)
    form24q_data = aggregate_form24q(company, period_start, period_end)

    tan = ""
    company_name = ""
    settings = None
    if company:
        company_name = getattr(company, "company", "") or str(company)
        settings = IndiaStatutorySettings.objects.filter(company_id=company).first()
        if settings:
            tan = getattr(settings, "tan_number", "") or ""
    meta = _challan_meta(request, settings)
    slug = _company_slug(company)
    filename_base = f"TRACES_24Q_Q{quarter}_FY{year}_{slug}"
    content = generate_traces_zip(
        form24q_data,
        tan=tan,
        company_name=company_name,
        filename_base=filename_base,
        **meta,
    )
    response = HttpResponse(content, content_type="application/zip")
    response["Content-Disposition"] = f'attachment; filename="{filename_base}.zip"'
    return response


@login_required
@permission_required("payroll.view_payslip")
def oltas_challan_download(request):
    """Download ITNS 281 / OLTAS challan working file."""
    company = _selected_company(request)
    period_start, period_end, year, month = _parse_period_month(request)
    challan_data = aggregate_statutory_challan(company, period_start, period_end)

    tan = ""
    settings = None
    if company:
        settings = IndiaStatutorySettings.objects.filter(company_id=company).first()
        if settings:
            tan = getattr(settings, "tan_number", "") or ""
    meta = _challan_meta(request, settings)
    content = generate_oltas_challan_text(challan_data, tan=tan, **meta)
    slug = _company_slug(company)
    filename = f"ITNS281_challan_{year}_{month:02d}_{slug}.txt"

    response = HttpResponse(content, content_type="text/plain; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@login_required
@permission_required("payroll.view_payslip")
def epf_ecr_list(request):
    """EPFO ECR 2.0 preview + validation for a wage month."""
    company = _selected_company(request)
    settings = None
    if company:
        settings = IndiaStatutorySettings.objects.filter(company_id=company).first()

    period_start, period_end, year, month = _parse_period_month(request)
    challan_data = aggregate_statutory_challan(company, period_start, period_end)
    ecr = build_epf_ecr_payload(challan_data)

    month_options = [
        {"value": m, "label": date(2000, m, 1).strftime("%B")} for m in range(1, 13)
    ]
    download_url = (
        f"{reverse('epf-ecr-download')}?year={year}&month={month}"
    )

    return render(
        request,
        "payroll/india_statutory/epf_ecr.html",
        {
            "company": company,
            "settings": settings,
            "ecr": ecr,
            "selected_year": year,
            "selected_month": month,
            "month_options": month_options,
            "year_options": [
                date.today().year - 1,
                date.today().year,
                date.today().year + 1,
            ],
            "download_url": download_url,
            "establishment_code": getattr(settings, "pf_establishment_code", "")
            if settings
            else "",
        },
    )


@login_required
@permission_required("payroll.view_payslip")
def epf_ecr_download(request):
    """Download EPFO ECR 2.0 text file (#~# delimited)."""
    company = _selected_company(request)
    period_start, period_end, year, month = _parse_period_month(request)
    challan_data = aggregate_statutory_challan(company, period_start, period_end)
    ecr = build_epf_ecr_payload(challan_data)
    if ecr["issues"] and request.GET.get("include_invalid") != "1":
        # Still download valid rows only; preview page lists issues
        pass
    content = ecr["text"]
    # EPFO expects ANSI/ASCII — strip non-ascii just in case
    content = content.encode("ascii", "ignore").decode("ascii")
    slug = _company_slug(company)
    filename = f"ECR_{year}_{month:02d}_{slug}.txt"
    response = HttpResponse(content, content_type="text/plain; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@login_required
@permission_required("payroll.view_payslip")
def accounting_export_list(request):
    company = _selected_company(request)
    settings = None
    if company:
        settings = IndiaStatutorySettings.objects.filter(company_id=company).first()
    period_start, period_end, year, month = _parse_period_month(request)
    journal_data = aggregate_payroll_journal(company, period_start, period_end)

    month_options = []
    for m in range(1, 13):
        month_options.append({"value": m, "label": date(2000, m, 1).strftime("%B")})

    exports = _export_pair(
        "accounting-export-download", year=year, month=month
    )

    return render(
        request,
        "payroll/india_statutory/accounting_export.html",
        {
            "company": company,
            "settings": settings,
            "journal_data": journal_data,
            "selected_year": year,
            "selected_month": month,
            "month_options": month_options,
            "year_options": [date.today().year - 1, date.today().year, date.today().year + 1],
            "export_csv_url": exports["csv"],
            "export_label": gettext("Payroll journal"),
        },
    )


@login_required
@permission_required("payroll.view_payslip")
def accounting_export_download(request):
    company = _selected_company(request)
    period_start, period_end, year, month = _parse_period_month(request)
    journal_data = aggregate_payroll_journal(company, period_start, period_end)
    rows = payroll_journal_csv_rows(journal_data)
    fmt = (request.GET.get("format") or "csv").lower()

    company_slug = _company_slug(company)
    filename_base = f"payroll_journal_{year}_{month:02d}_{company_slug}"
    return _file_response(rows, filename_base, fmt)


@login_required
@permission_required("payroll.view_payslip")
def statutory_excel_hub(request):
    company = _selected_company(request)
    settings = None
    if company:
        settings = IndiaStatutorySettings.objects.filter(company_id=company).first()
    today = date.today()
    _, _, default_fy_start, _ = financial_year_bounds(today)
    _, _, report_year, report_month = _parse_period_month(request)
    _, _, form24q_year, form24q_quarter = _parse_quarter(request)
    return render(
        request,
        "payroll/india_statutory/statutory_excel.html",
        {
            "company": company,
            "settings": settings,
            "financial_year_start": default_fy_start,
            "challan_export_url": (
                f"{reverse('challan-export')}?year={report_year}"
                f"&month={report_month}&format=csv"
            ),
            "form24q_export_url": (
                f"{reverse('form24q-export')}?year={form24q_year}"
                f"&quarter={form24q_quarter}&format=csv"
            ),
            "accounting_export_url": (
                f"{reverse('accounting-export-download')}?year={report_year}"
                f"&month={report_month}&format=csv"
            ),
            "register_export_url": (
                f"{reverse('statutory-register-export')}?year={report_year}"
                f"&month={report_month}&type=pf&format=csv"
            ),
        },
    )


@login_required
@permission_required("payroll.view_payslip")
def statutory_profiles_template(request):
    df = statutory_profiles_template_dataframe()
    fmt = (request.GET.get("format") or "csv").lower()
    return export_dataframe(df, "statutory_profiles_template", fmt)


@login_required
@permission_required("payroll.view_payslip")
def statutory_profiles_export(request):
    company = _selected_company(request)
    df = export_statutory_profiles(company)
    slug = _company_slug(company)
    fmt = (request.GET.get("format") or "csv").lower()
    return export_dataframe(df, f"statutory_profiles_{slug}", fmt)


@login_required
@permission_required("payroll.change_payslip")
def statutory_profiles_import(request):
    if request.method != "POST":
        return redirect("statutory-excel-hub")

    company = _selected_company(request)
    upload = request.FILES.get("statutory_excel_file")
    if not upload:
        messages.error(request, gettext("Please choose a file to upload."))
        return _import_redirect(request)

    try:
        dataframe = read_upload_dataframe(upload)
    except Exception as exc:
        messages.error(request, gettext("Could not read file: %(err)s") % {"err": exc})
        return _import_redirect(request)

    result = import_statutory_profiles(company, dataframe)
    if result["errors"]:
        err_df = pd.DataFrame(result["errors"])
        return export_dataframe(err_df, "statutory_import_errors", "csv")

    messages.success(
        request,
        gettext("Updated %(count)s employee statutory profiles.") % {"count": result["success"]},
    )
    return _import_redirect(request)


@login_required
@permission_required("payroll.view_payslip")
def form16_excel_export(request):
    company = _selected_company(request)
    today = date.today()
    _, _, default_fy_start, _ = financial_year_bounds(today)
    try:
        fy_start = int(request.GET.get("fy", default_fy_start))
    except (TypeError, ValueError):
        fy_start = default_fy_start

    employees = Employee.objects.all()
    if company:
        employees = employees.filter(
            employee_work_info__company_id=company
        ).distinct()
    employees = employees.order_by("employee_first_name", "employee_last_name")[:300]
    bulk_summaries = aggregate_form16_bulk(employees, fy_start)

    rows = [
        [
            "Badge ID",
            "Employee",
            "Payslips",
            "Gross Salary",
            "PF (Employee)",
            "TDS Deducted",
        ]
    ]
    for employee in employees:
        summary = bulk_summaries.get(employee.id, {"totals": {}, "payslip_count": 0})
        totals = summary["totals"]
        if summary["payslip_count"] == 0:
            continue
        rows.append(
            [
                employee.badge_id or "",
                employee.get_full_name(),
                summary["payslip_count"],
                totals.get("gross_salary", 0),
                totals.get("pf_employee", 0),
                totals.get("tds", 0),
            ]
        )

    slug = _company_slug(company)
    fmt = (request.GET.get("format") or "csv").lower()
    return export_rows(rows, f"form16_FY{fy_start}_{slug}", fmt)


def _handle_bulk_import(
    request,
    *,
    file_field: str,
    import_fn,
    success_message: str,
    error_filename: str,
):
    if request.method != "POST":
        return redirect("statutory-excel-hub")

    company = _selected_company(request)
    upload = request.FILES.get(file_field)
    if not upload:
        messages.error(request, gettext("Please choose a file to upload."))
        return _import_redirect(request)

    try:
        dataframe = read_upload_dataframe(upload)
    except Exception as exc:
        messages.error(request, gettext("Could not read file: %(err)s") % {"err": exc})
        return _import_redirect(request)

    result = import_fn(company, dataframe)
    if result["errors"]:
        err_df = pd.DataFrame(result["errors"])
        return export_dataframe(err_df, error_filename.replace(".xlsx", ""), "csv")

    messages.success(
        request,
        success_message % {"count": result["success"]},
    )
    return _import_redirect(request)


@login_required
@permission_required("payroll.view_payslip")
def ctc_template(request):
    fmt = (request.GET.get("format") or "csv").lower()
    return export_dataframe(ctc_template_dataframe(), "ctc_structure_template", fmt)


@login_required
@permission_required("payroll.view_payslip")
def ctc_export(request):
    company = _selected_company(request)
    df = export_ctc_structures(company)
    slug = _company_slug(company)
    fmt = (request.GET.get("format") or "csv").lower()
    return export_dataframe(df, f"ctc_structures_{slug}", fmt)


@login_required
@permission_required("payroll.change_payslip")
def ctc_import(request):
    return _handle_bulk_import(
        request,
        file_field="ctc_excel_file",
        import_fn=lambda company, df: import_ctc_structures(company, df),
        success_message=gettext("Updated CTC structure for %(count)s employees."),
        error_filename="ctc_import_errors.xlsx",
    )


@login_required
@permission_required("payroll.view_payslip")
def form16_import_template(request):
    today = date.today()
    _, _, default_fy_start, _ = financial_year_bounds(today)
    try:
        fy_start = int(request.GET.get("fy", default_fy_start))
    except (TypeError, ValueError):
        fy_start = default_fy_start
    return export_dataframe(
        form16_import_template_dataframe(fy_start),
        f"form16_bulk_save_template_FY{fy_start}",
        (request.GET.get("format") or "csv").lower(),
    )


@login_required
@permission_required("payroll.change_payslip")
def form16_bulk_import(request):
    today = date.today()
    _, _, default_fy_start, _ = financial_year_bounds(today)
    try:
        fy_start = int(request.POST.get("fy", default_fy_start))
    except (TypeError, ValueError):
        fy_start = default_fy_start

    def _import(company, dataframe):
        return import_form16_bulk_save(company, dataframe, fy_start)

    return _handle_bulk_import(
        request,
        file_field="form16_excel_file",
        import_fn=_import,
        success_message=gettext("Saved Form 16 records for %(count)s employees."),
        error_filename="form16_import_errors.xlsx",
    )


@login_required
@permission_required("payroll.view_payslip")
def fnf_excel_export(request):
    company = _selected_company(request)
    df = export_fnf_estimates(company)
    slug = _company_slug(company)
    fmt = (request.GET.get("format") or "csv").lower()
    return export_dataframe(df, f"fnf_estimates_{slug}", fmt)


# Aliases so URL modules can import snake_case names
form16_view = form16_view
form16_list = form16_list
tax_computation_view = tax_computation_view
challan_list = challan_list
challan_export = challan_export
form24q_list = form24q_list
form24q_export = form24q_export
accounting_export_list = accounting_export_list
accounting_export_download = accounting_export_download
statutory_excel_hub = statutory_excel_hub
statutory_profiles_template = statutory_profiles_template
statutory_profiles_export = statutory_profiles_export
statutory_profiles_import = statutory_profiles_import
form16_excel_export = form16_excel_export
ctc_template = ctc_template
ctc_export = ctc_export
ctc_import = ctc_import
form16_import_template = form16_import_template
form16_bulk_import = form16_bulk_import
fnf_excel_export = fnf_excel_export
employee_statutory_profile = employee_statutory_profile
india_statutory_settings = india_statutory_settings
statutory_register = statutory_register
statutory_register_export = statutory_register_export
