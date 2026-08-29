"""
Statutory wage base (Code on Wages — 50% excluded-allowance add-back).

Uses Allowance component flags when present; falls back to title heuristics.
"""

from __future__ import annotations

from typing import Any, Iterable


WAGE_COMPONENT_TITLES = {
    "basic",
    "basic pay",
    "basic salary",
    "dearness allowance",
    "da",
    "retaining allowance",
}

EXCLUDED_ALLOWANCE_HINTS = {
    "hra",
    "house rent allowance",
    "conveyance",
    "conveyance allowance",
    "travel",
    "travelling allowance",
    "special allowance",
    "special",
    "incentive",
    "bonus",
    "overtime",
    "reimbursement",
}


def _title_key(title: str) -> str:
    return (title or "").strip().lower()


def classify_component(title: str, *, flags: dict[str, Any] | None = None) -> str:
    """Return 'wage' | 'excluded' | 'other'."""
    flags = flags or {}
    if flags.get("include_in_wage_definition") or flags.get("pf_applicable"):
        return "wage"
    if flags.get("is_excluded_allowance"):
        return "excluded"
    key = _title_key(title)
    if key in WAGE_COMPONENT_TITLES:
        return "wage"
    if key in EXCLUDED_ALLOWANCE_HINTS or "allowance" in key:
        return "excluded"
    return "other"


def compute_statutory_wage_base(
    *,
    basic_pay: float,
    allowance_lines: Iterable[dict[str, Any]] | None = None,
    apply_50pct_rule: bool = True,
) -> dict[str, float]:
    """
    Derive statutory wage from basic + allowances.

    allowance_lines items: {"title": str, "amount": float, optional flags}
    """
    basic = max(0.0, float(basic_pay or 0))
    wage_components = basic
    excluded = 0.0
    other = 0.0

    for line in allowance_lines or []:
        amount = max(0.0, float(line.get("amount") or 0))
        flags = {
            "include_in_wage_definition": line.get("include_in_wage_definition"),
            "pf_applicable": line.get("pf_applicable"),
            "is_excluded_allowance": line.get("is_excluded_allowance"),
        }
        kind = classify_component(str(line.get("title") or ""), flags=flags)
        if kind == "wage":
            wage_components += amount
        elif kind == "excluded":
            excluded += amount
        else:
            other += amount

    total_remuneration = wage_components + excluded + other
    excess = 0.0
    if apply_50pct_rule and total_remuneration > 0:
        half = total_remuneration * 0.5
        if excluded > half:
            excess = excluded - half

    statutory_wage = wage_components + excess
    return {
        "total_remuneration": round(total_remuneration, 2),
        "wage_components": round(wage_components, 2),
        "excluded_allowances": round(excluded, 2),
        "other_components": round(other, 2),
        "excess_allowance": round(excess, 2),
        "statutory_wage": round(max(0.0, statutory_wage), 2),
    }
