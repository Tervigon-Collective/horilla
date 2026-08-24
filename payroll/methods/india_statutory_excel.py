"""Excel import/export helpers for Indian statutory payroll."""

from __future__ import annotations

import math
from datetime import date
from typing import Any

import pandas as pd
from django.http import HttpResponse
from django.utils.translation import gettext_lazy as gettext

from employee.models import Employee, EmployeeBankDetails
from payroll.methods.ctc_wizard import apply_ctc_split_to_contract, split_monthly_ctc
from payroll.models.india_statutory import EmployeeStatutoryProfile, Form16Record
from payroll.models.models import Allowance, Contract

STATUTORY_EXCEL_COLUMNS = [
    "Badge ID",
    "Employee Name",
    "PAN",
    "UAN",
    "PF Number",
    "ESI Number",
    "PF Applicable",
    "ESI Applicable",
    "PT Applicable",
    "TDS Applicable",
    "TDS Regime",
    "Section 80C (Annual)",
    "Section 80D (Annual)",
    "Other Chapter VI-A",
    "VPF Rate (%)",
]


def _bool_cell(value) -> bool | None:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    text = str(value).strip().lower()
    if text in ("", "nan"):
        return None
    if text in ("yes", "y", "1", "true", "on"):
        return True
    if text in ("no", "n", "0", "false", "off"):
        return False
    return None


def _clean_str(value) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    return str(value).strip()


def _clean_float(value, default=0.0) -> float:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return default
    text = str(value).strip()
    if text in ("", "nan", "None"):
        return default
    try:
        return float(text)
    except (TypeError, ValueError):
        return default


def _optional_float(value):
    """Parse a number, or None when the cell is blank so imports do not wipe data."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    text = str(value).strip()
    if text in ("", "nan", "None"):
        return None
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def dataframe_to_excel_response(dataframe: pd.DataFrame, filename: str) -> HttpResponse:
    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    dataframe.to_excel(response, index=False, engine="openpyxl")
    return response


def dataframe_to_csv_response(dataframe: pd.DataFrame, filename: str) -> HttpResponse:
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    dataframe.to_csv(response, index=False)
    return response


def export_dataframe(dataframe: pd.DataFrame, filename_base: str, fmt: str) -> HttpResponse:
    fmt = (fmt or "csv").lower()
    if fmt == "csv":
        return dataframe_to_csv_response(dataframe, f"{filename_base}.csv")
    return dataframe_to_excel_response(dataframe, f"{filename_base}.xlsx")


def export_rows(rows: list[list], filename_base: str, fmt: str) -> HttpResponse:
    fmt = (fmt or "csv").lower()
    if not rows:
        return export_dataframe(pd.DataFrame(), filename_base, fmt)
    headers = rows[0]
    body = rows[1:]
    if not body:
        return export_dataframe(pd.DataFrame(columns=headers), filename_base, fmt)
    max_cols = len(headers)
    normalized = []
    for row in body:
        cells = list(row) if row is not None else []
        if len(cells) < max_cols:
            cells.extend([""] * (max_cols - len(cells)))
        elif len(cells) > max_cols:
            cells = cells[:max_cols]
        normalized.append(cells)
    return export_dataframe(pd.DataFrame(normalized, columns=headers), filename_base, fmt)


def rows_to_excel_response(rows: list[list], filename: str) -> HttpResponse:
    if not rows:
        return dataframe_to_excel_response(pd.DataFrame(), filename)
    headers = rows[0]
    body = rows[1:]
    if not body:
        return dataframe_to_excel_response(pd.DataFrame(columns=headers), filename)
    max_cols = len(headers)
    normalized = []
    for row in body:
        cells = list(row) if row is not None else []
        if len(cells) < max_cols:
            cells.extend([""] * (max_cols - len(cells)))
        elif len(cells) > max_cols:
            cells = cells[:max_cols]
        normalized.append(cells)
    return dataframe_to_excel_response(pd.DataFrame(normalized, columns=headers), filename)


def statutory_profiles_template_dataframe() -> pd.DataFrame:
    return pd.DataFrame(
        columns=STATUTORY_EXCEL_COLUMNS,
        data=[
            [
                "EMP001",
                "Sample Employee",
                "ABCDE1234F",
                "100012345678",
                "MH/BAN/12345/000/1234567",
                "1234567890123456",
                "Yes",
                "Yes",
                "Yes",
                "Yes",
                "new",
                150000,
                25000,
                0,
                0,
            ]
        ],
    )


def export_statutory_profiles(company) -> pd.DataFrame:
    # Include inactive/exited employees too (important for re-importing/updating
    # statutory profile values based on Badge ID).
    employees = Employee.objects.all().select_related(
        "employee_bank_details", "statutory_profile"
    )
    if company:
        employees = employees.filter(
            employee_work_info__company_id=company
        ).distinct()
    employees = employees.order_by("employee_first_name", "employee_last_name")

    rows = []
    for emp in employees:
        bank = getattr(emp, "employee_bank_details", None)
        profile = getattr(emp, "statutory_profile", None)
        if profile is None:
            profile, _ = EmployeeStatutoryProfile.objects.get_or_create(employee_id=emp)
        rows.append(
            {
                "Badge ID": emp.badge_id or "",
                "Employee Name": emp.get_full_name(),
                "PAN": getattr(bank, "pan_number", "") or "",
                "UAN": getattr(bank, "uan_number", "") or "",
                "PF Number": getattr(bank, "pf_number", "") or "",
                "ESI Number": getattr(bank, "esi_number", "") or "",
                "PF Applicable": "Yes" if profile.pf_applicable else "No",
                "ESI Applicable": "Yes" if profile.esi_applicable else "No",
                "PT Applicable": "Yes" if profile.pt_applicable else "No",
                "TDS Applicable": "Yes" if profile.tds_applicable else "No",
                "TDS Regime": profile.tds_regime or "",
                "Section 80C (Annual)": profile.section_80c_annual,
                "Section 80D (Annual)": profile.section_80d_annual,
                "Other Chapter VI-A": profile.other_chapter_vi_a,
                "VPF Rate (%)": profile.vpf_rate,
            }
        )
    return pd.DataFrame(rows, columns=STATUTORY_EXCEL_COLUMNS)


def import_statutory_profiles(company, dataframe: pd.DataFrame) -> dict[str, Any]:
    """Import statutory profiles from Excel. Returns success count and error rows."""
    employees_qs = Employee.objects.all()
    if company:
        employees_qs = employees_qs.filter(
            employee_work_info__company_id=company
        ).distinct()
    by_badge = {
        (emp.badge_id or "").strip().lower(): emp
        for emp in employees_qs
        if emp.badge_id
    }

    success = 0
    errors = []

    for _, row in dataframe.iterrows():
        badge = _clean_str(row.get("Badge ID")).lower()
        if not badge:
            continue

        error_row = row.to_dict()
        employee = by_badge.get(badge)
        if not employee:
            error_row["Error"] = str(gettext("Badge ID not found for this company."))
            errors.append(error_row)
            continue

        regime = _clean_str(row.get("TDS Regime")).lower()
        if regime and regime not in ("new", "old"):
            error_row["Error"] = str(gettext("TDS Regime must be 'new' or 'old'."))
            errors.append(error_row)
            continue

        bank, _ = EmployeeBankDetails.objects.get_or_create(employee_id=employee)
        pan = _clean_str(row.get("PAN"))
        uan = _clean_str(row.get("UAN"))
        pf_no = _clean_str(row.get("PF Number"))
        esi_no = _clean_str(row.get("ESI Number"))
        if pan:
            bank.pan_number = pan.upper()
        if uan:
            bank.uan_number = uan
        if pf_no:
            bank.pf_number = pf_no
        if esi_no:
            bank.esi_number = esi_no
        bank.save()

        profile, _ = EmployeeStatutoryProfile.objects.get_or_create(employee_id=employee)
        for field, col in (
            ("pf_applicable", "PF Applicable"),
            ("esi_applicable", "ESI Applicable"),
            ("pt_applicable", "PT Applicable"),
            ("tds_applicable", "TDS Applicable"),
        ):
            parsed = _bool_cell(row.get(col))
            if parsed is not None:
                setattr(profile, field, parsed)

        if regime:
            profile.tds_regime = regime
        for field, col in (
            ("section_80c_annual", "Section 80C (Annual)"),
            ("section_80d_annual", "Section 80D (Annual)"),
            ("other_chapter_vi_a", "Other Chapter VI-A"),
            ("vpf_rate", "VPF Rate (%)"),
        ):
            parsed = _optional_float(row.get(col))
            if parsed is not None:
                setattr(profile, field, parsed)
        profile.save()
        success += 1

    return {"success": success, "errors": errors}


CTC_EXCEL_COLUMNS = [
    "Badge ID",
    "Employee Name",
    "Monthly CTC",
    "Metro (Yes/No)",
    "Basic (Monthly)",
    "HRA (Monthly)",
    "Special Allowance (Monthly)",
]

FORM16_IMPORT_COLUMNS = [
    "Badge ID",
    "Financial Year Start",
]


def read_upload_dataframe(upload) -> pd.DataFrame:
    name = (getattr(upload, "name", "") or "").lower()
    if hasattr(upload, "seek"):
        upload.seek(0)
    if name.endswith(".csv"):
        df = pd.read_csv(upload, encoding="utf-8-sig")
    elif name.endswith(".tsv"):
        df = pd.read_csv(upload, sep="\t", encoding="utf-8-sig")
    elif name.endswith((".xlsx", ".xls")):
        df = pd.read_excel(upload)
    else:
        raise ValueError(
            str(gettext("Unsupported file type. Please upload CSV, TSV, XLSX, or XLS."))
        )
    df.columns = [str(col).strip() for col in df.columns]
    return df


def _employees_for_company(company):
    # Keep badge lookup compatible with Form16 bulk operations for exited staff.
    employees_qs = Employee.objects.all()
    if company:
        employees_qs = employees_qs.filter(
            employee_work_info__company_id=company
        ).distinct()
    return employees_qs


def _badge_index(company) -> dict[str, Employee]:
    return {
        (emp.badge_id or "").strip().lower(): emp
        for emp in _employees_for_company(company)
        if emp.badge_id
    }


def _allowance_amount(employee, title: str) -> float:
    allowance = Allowance.objects.filter(
        title=title, specific_employees=employee
    ).first()
    return float(allowance.amount or 0) if allowance else 0.0


def ctc_template_dataframe() -> pd.DataFrame:
    return pd.DataFrame(
        columns=CTC_EXCEL_COLUMNS,
        data=[
            ["EMP001", "Sample Employee", 50000, "Yes", "", "", ""],
        ],
    )


def export_ctc_structures(company) -> pd.DataFrame:
    rows = []
    employees = _employees_for_company(company).order_by(
        "employee_first_name", "employee_last_name"
    )
    for emp in employees:
        contract = (
            emp.contract_set.filter(contract_status="active")
            .order_by("-contract_start_date")
            .first()
        )
        if not contract:
            continue
        basic = float(contract.wage or 0)
        hra = _allowance_amount(emp, "HRA")
        special = _allowance_amount(emp, "Special Allowance")
        monthly_ctc = round(basic + hra + special, 2)
        rows.append(
            {
                "Badge ID": emp.badge_id or "",
                "Employee Name": emp.get_full_name(),
                "Monthly CTC": monthly_ctc,
                "Metro (Yes/No)": "",
                "Basic (Monthly)": basic,
                "HRA (Monthly)": hra,
                "Special Allowance (Monthly)": special,
            }
        )
    return pd.DataFrame(rows, columns=CTC_EXCEL_COLUMNS)


def import_ctc_structures(company, dataframe: pd.DataFrame) -> dict[str, Any]:
    by_badge = _badge_index(company)
    success = 0
    errors = []

    for _, row in dataframe.iterrows():
        badge = _clean_str(row.get("Badge ID")).lower()
        if not badge:
            continue

        error_row = row.to_dict()
        employee = by_badge.get(badge)
        if not employee:
            error_row["Error"] = str(gettext("Badge ID not found for this company."))
            errors.append(error_row)
            continue

        monthly_ctc = _clean_float(row.get("Monthly CTC"))
        if monthly_ctc <= 0:
            error_row["Error"] = str(gettext("Monthly CTC must be greater than zero."))
            errors.append(error_row)
            continue

        metro_cell = _bool_cell(row.get("Metro (Yes/No)"))
        metro = metro_cell if metro_cell is not None else True

        contract = (
            employee.contract_set.filter(contract_status="active")
            .order_by("-contract_start_date")
            .first()
        )
        if not contract:
            error_row["Error"] = str(gettext("No active contract for this employee."))
            errors.append(error_row)
            continue

        split = split_monthly_ctc(monthly_ctc, metro=metro)
        apply_ctc_split_to_contract(contract, split)
        success += 1

    return {"success": success, "errors": errors}


def form16_import_template_dataframe(fy_start: int) -> pd.DataFrame:
    return pd.DataFrame(
        columns=FORM16_IMPORT_COLUMNS,
        data=[["EMP001", fy_start]],
    )


def import_form16_bulk_save(
    company,
    dataframe: pd.DataFrame,
    default_fy_start: int,
) -> dict[str, Any]:
    from payroll.methods.india_statutory import aggregate_form16

    by_badge = _badge_index(company)
    success = 0
    errors = []

    for _, row in dataframe.iterrows():
        badge = _clean_str(row.get("Badge ID")).lower()
        if not badge:
            continue

        error_row = row.to_dict()
        employee = by_badge.get(badge)
        if not employee:
            error_row["Error"] = str(gettext("Badge ID not found for this company."))
            errors.append(error_row)
            continue

        fy_raw = row.get("Financial Year Start")
        if fy_raw is None or (isinstance(fy_raw, float) and math.isnan(fy_raw)):
            fy_start = default_fy_start
        else:
            try:
                fy_start = int(float(fy_raw))
            except (TypeError, ValueError):
                error_row["Error"] = str(gettext("Invalid financial year start."))
                errors.append(error_row)
                continue

        context = aggregate_form16(employee, fy_start)
        if context.get("payslip_count", 0) == 0:
            error_row["Error"] = str(gettext("No payslips found for this financial year."))
            errors.append(error_row)
            continue

        totals = context["totals"]
        Form16Record.objects.update_or_create(
            employee_id=employee,
            financial_year_start=fy_start,
            defaults={
                "financial_year_end": fy_start + 1,
                "gross_salary": totals["gross_salary"],
                "pf_employee_total": totals["pf_employee"],
                "pf_employer_total": totals["pf_employer"],
                "esi_employee_total": totals["esi_employee"],
                "pt_total": totals["pt"],
                "tds_total": totals["tds"],
                "net_salary": totals["net_salary"],
                "regime": context["regime"],
                "summary_json": totals,
            },
        )
        success += 1

    return {"success": success, "errors": errors}


def export_fnf_estimates(company) -> pd.DataFrame:
    from offboarding.models import OffboardingEmployee
    from offboarding.settlement import calculate_fnf_settlement

    qs = OffboardingEmployee.objects.select_related(
        "employee_id", "fnf_settlement"
    ).order_by("-id")
    if company:
        qs = qs.filter(
            employee_id__employee_work_info__company_id=company
        ).distinct()

    rows = []
    for ob in qs[:500]:
        employee = ob.employee_id
        last_day = ob.notice_period_ends or date.today()
        data = calculate_fnf_settlement(employee, last_day)
        try:
            status = ob.fnf_settlement.get_status_display()
            net = ob.fnf_settlement.net_payable
        except Exception:
            status = "Estimate"
            net = data.get("net_payable", data["total_settlement"])
        rows.append(
            {
                "Badge ID": employee.badge_id or "",
                "Employee Name": employee.get_full_name(),
                "Last Working Day": last_day.isoformat() if last_day else "",
                "Years of Service": data["years_of_service"],
                "Gratuity": data["gratuity"],
                "Unpaid Bonus": data.get("bonus_unpaid", 0),
                "Leave Encashment": data["leave_encashment"],
                "Notice Period Pay": data["notice_period_pay"],
                "Loan Recovery": data.get("loan_recovery", 0),
                "Net Payable": net,
                "Status": status,
            }
        )

    columns = [
        "Badge ID",
        "Employee Name",
        "Last Working Day",
        "Years of Service",
        "Gratuity",
        "Unpaid Bonus",
        "Leave Encashment",
        "Notice Period Pay",
        "Loan Recovery",
        "Net Payable",
        "Status",
    ]
    return pd.DataFrame(rows, columns=columns)
