"""
Org-wide payroll rounding — single policy for components, net pay, and statutory.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Literal


RoundingMode = Literal["two_decimals", "nearest_rupee", "none"]


def _to_decimal(value) -> Decimal:
    return Decimal(str(value or 0))


def round_money(value, *, mode: RoundingMode = "two_decimals", decimals: int = 2) -> float:
    """
    Apply organization rounding policy.

    - two_decimals: banker's-style half-up to N decimals (default 2)
    - nearest_rupee: round half up to whole rupee
    - none: cast to float without extra rounding beyond float precision
    """
    amount = _to_decimal(value)
    if mode == "none":
        return float(amount)
    if mode == "nearest_rupee":
        quantized = amount.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        return float(quantized)
    places = max(0, int(decimals))
    step = Decimal("1").scaleb(-places)  # 10 ** -places
    quantized = amount.quantize(step, rounding=ROUND_HALF_UP)
    return float(quantized)


def get_rounding_settings(company=None) -> dict:
    """Load rounding settings from PayrollGeneralSetting (company or first)."""
    from payroll.models.models import PayrollGeneralSetting

    qs = PayrollGeneralSetting.objects.all()
    if company is not None:
        settings = qs.filter(company_id=company).first() or qs.first()
    else:
        settings = qs.first()
    if not settings:
        return {
            "component_mode": "two_decimals",
            "component_decimals": 2,
            "net_pay_mode": "nearest_rupee",
            "statutory_mode": "two_decimals",
        }
    return {
        "component_mode": getattr(settings, "component_round_mode", None) or "two_decimals",
        "component_decimals": int(getattr(settings, "component_decimals", 2) or 2),
        "net_pay_mode": getattr(settings, "net_pay_round_mode", None) or "nearest_rupee",
        "statutory_mode": getattr(settings, "statutory_round_mode", None) or "two_decimals",
    }


def apply_payslip_rounding(
    *,
    basic_pay: float,
    contract_wage: float,
    gross_pay: float,
    deduction: float,
    net_pay: float,
    company=None,
) -> dict[str, float]:
    cfg = get_rounding_settings(company)
    c_mode = cfg["component_mode"]
    c_dec = cfg["component_decimals"]
    return {
        "basic_pay": round_money(basic_pay, mode=c_mode, decimals=c_dec),
        "contract_wage": round_money(contract_wage, mode=c_mode, decimals=c_dec),
        "gross_pay": round_money(gross_pay, mode=c_mode, decimals=c_dec),
        "deduction": round_money(deduction, mode=c_mode, decimals=c_dec),
        "net_pay": round_money(net_pay, mode=cfg["net_pay_mode"], decimals=c_dec),
    }
