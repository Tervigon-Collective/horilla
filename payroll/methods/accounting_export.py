"""
Payroll journal export for accounting (Tally / Zoho Books import subset).
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any


def aggregate_payroll_journal(company, period_start, period_end) -> dict[str, Any]:
    """Aggregate payslip totals for journal entry export."""
    from payroll.models.models import Payslip

    slips = Payslip.objects.filter(
        start_date__lte=period_end,
        end_date__gte=period_start,
        status__in=["confirmed", "paid"],
    ).select_related("employee_id")
    if company:
        slips = slips.filter(employee_id__employee_work_info__company_id=company)

    totals = defaultdict(float)
    rows = []
    for slip in slips:
        india = (slip.pay_head_data or {}).get("india_statutory") or {}
        pf = float(india.get("pf_employee") or 0)
        esi = float(india.get("esi_employee") or 0)
        tds = float(india.get("tds") or 0) or float(
            (slip.pay_head_data or {}).get("federal_tax") or 0
        )
        pt = float(india.get("pt") or 0)
        gross = float(slip.gross_pay or 0)
        deduction = float(slip.deduction or 0)
        net = float(slip.net_pay or 0)
        other_ded = max(deduction - pf - esi - tds - pt, 0)

        totals["gross"] += gross
        totals["pf"] += pf
        totals["esi"] += esi
        totals["tds"] += tds
        totals["pt"] += pt
        totals["other_deductions"] += other_ded
        totals["net"] += net

        rows.append(
            {
                "employee": slip.employee_id,
                "badge_id": (slip.employee_id.badge_id or "") if slip.employee_id else "",
                "gross": round(gross, 2),
                "pf": round(pf, 2),
                "esi": round(esi, 2),
                "tds": round(tds, 2),
                "pt": round(pt, 2),
                "other_deductions": round(other_ded, 2),
                "net": round(net, 2),
            }
        )

    for key in totals:
        totals[key] = round(totals[key], 2)

    return {
        "rows": rows,
        "totals": dict(totals),
        "period_start": period_start,
        "period_end": period_end,
        "company": company,
        "employee_count": len(rows),
    }


def payroll_journal_csv_rows(journal_data: dict) -> list[list]:
    """Tally-friendly journal CSV: Voucher rows + employee detail."""
    headers = [
        "Employee",
        "Badge ID",
        "Gross (Dr Salary Expense)",
        "PF (Cr)",
        "ESI (Cr)",
        "TDS (Cr)",
        "PT (Cr)",
        "Other Deductions (Cr)",
        "Net Pay (Cr)",
    ]
    out = [headers]
    for row in journal_data["rows"]:
        emp = row["employee"]
        name = emp.get_full_name() if emp else ""
        out.append([
            name,
            row["badge_id"],
            row["gross"],
            row["pf"],
            row.get("esi", 0),
            row["tds"],
            row["pt"],
            row["other_deductions"],
            row["net"],
        ])

    t = journal_data["totals"]
    out.append([
        "TOTAL",
        "",
        t.get("gross", 0),
        t.get("pf", 0),
        t.get("esi", 0),
        t.get("tds", 0),
        t.get("pt", 0),
        t.get("other_deductions", 0),
        t.get("net", 0),
    ])
    out.append([])
    out.append(["Summary Journal Entry", "", "", "", "", "", "", "", ""])
    out.append(["Salary Expense", "Dr", t.get("gross", 0), "", "", "", "", "", ""])
    out.append(["PF Payable", "Cr", "", t.get("pf", 0), "", "", "", "", ""])
    out.append(["ESI Payable", "Cr", "", "", t.get("esi", 0), "", "", "", ""])
    out.append(["TDS Payable", "Cr", "", "", "", t.get("tds", 0), "", "", ""])
    out.append(["PT Payable", "Cr", "", "", "", "", t.get("pt", 0), "", ""])
    out.append(["Other Deductions Payable", "Cr", "", "", "", "", "", t.get("other_deductions", 0), ""])
    out.append(["Net Salary Payable", "Cr", "", "", "", "", "", "", t.get("net", 0)])
    return out
