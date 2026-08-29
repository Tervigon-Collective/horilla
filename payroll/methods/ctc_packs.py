"""
Reference CTC / salary structure packs (org samples).

Amounts are explicit monthly heads — not the default 40% CTC splitter —
so Pack A–D match Finance worksheets exactly.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class SalaryPack:
    code: str
    name: str
    basic: float
    hra: float
    special: float
    note: str = ""

    @property
    def gross(self) -> float:
        return round(self.basic + self.hra + self.special, 2)

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["gross"] = self.gross
        return data


# Sample packs from org payroll worksheets (Aug 2026).
SALARY_PACKS: dict[str, SalaryPack] = {
    "A": SalaryPack(
        code="A",
        name="Gross ₹60,000",
        basic=30000,
        hra=18000,
        special=12000,
        note="PF on ceiling wage; monthly CTC ≈ Gross + ER PF",
    ),
    "B": SalaryPack(
        code="B",
        name="Gross ₹45,000",
        basic=22500,
        hra=13500,
        special=9000,
        note="TDS may apply depending on annual projection",
    ),
    "C": SalaryPack(
        code="C",
        name="CTC ₹30,000 band",
        basic=14100,
        hra=8460,
        special=5640,
        note="≈50/30/20 of gross ₹28,200",
    ),
    "D": SalaryPack(
        code="D",
        name="Gross ₹20,000 + ESI",
        basic=20000,
        hra=0,
        special=0,
        note="ESI typically applicable when gross ≤ ceiling",
    ),
}


def list_salary_packs() -> list[dict[str, Any]]:
    return [p.as_dict() for p in SALARY_PACKS.values()]


def get_salary_pack(code: str) -> SalaryPack | None:
    return SALARY_PACKS.get((code or "").strip().upper())


def apply_salary_pack_to_contract(contract, pack: SalaryPack) -> dict[str, Any]:
    """Set basic wage and upsert HRA / Special Allowance amounts (zero clears)."""
    from payroll.models.models import Allowance
    from payroll.methods.ctc_wizard import CtcSplit, apply_ctc_split_to_contract

    split = CtcSplit(
        monthly_ctc=pack.gross,
        basic=pack.basic,
        hra=pack.hra,
        special=pack.special,
        metro=True,
    )
    result = apply_ctc_split_to_contract(contract, split, create_allowances=True)

    # Explicitly zero HRA/Special when pack has 0 (wizard skips amount<=0).
    employee = contract.employee_id
    for title, amount in (("HRA", pack.hra), ("Special Allowance", pack.special)):
        if amount > 0:
            continue
        allowance = Allowance.objects.filter(
            title=title, specific_employees=employee
        ).first()
        if allowance:
            allowance.amount = 0
            allowance.is_fixed = True
            allowance.is_active = False
            allowance.save(update_fields=["amount", "is_fixed", "is_active"])

    result["pack"] = pack.as_dict()
    return result
