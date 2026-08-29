"""
Payroll run — versioned period container with lock/publish workflow.

Statuses follow the org-wide blueprint:
OPEN → INPUT_PENDING → CALCULATED → VALIDATION_* → HR/FINANCE APPROVED
→ LOCKED → PAID → PUBLISHED

Locked (and later) runs must not be silently recalculated.
"""

from __future__ import annotations

from django.db import models
from django.utils.translation import gettext_lazy as _

from base.horilla_company_manager import HorillaCompanyManager
from base.models import Company
from employee.models import Employee
from horilla.models import HorillaModel


PAYROLL_RUN_STATUS = [
    ("open", _("Open")),
    ("input_pending", _("Input Pending")),
    ("calculated", _("Calculated")),
    ("validation_failed", _("Validation Failed")),
    ("validation_passed", _("Validation Passed")),
    ("hr_approved", _("HR Approved")),
    ("finance_approved", _("Finance Approved")),
    ("locked", _("Locked")),
    ("paid", _("Paid")),
    ("published", _("Published")),
]

# Periods in these statuses must not be overwritten by regenerate/save.
IMMUTABLE_RUN_STATUSES = frozenset({"locked", "paid", "published"})

PRORATION_METHODS = [
    ("calendar", _("Calendar-day method")),
    ("working_day", _("Working-day method")),
]


class PayrollRun(HorillaModel):
    """One payroll period calculation version for a company."""

    company_id = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="payroll_runs",
        verbose_name=_("Company"),
    )
    year = models.PositiveIntegerField(verbose_name=_("Payroll year"))
    month = models.PositiveIntegerField(verbose_name=_("Payroll month"))
    period_start = models.DateField(verbose_name=_("Period start"))
    period_end = models.DateField(verbose_name=_("Period end"))
    attendance_cutoff = models.DateField(
        null=True, blank=True, verbose_name=_("Attendance cut-off")
    )
    variable_pay_cutoff = models.DateField(
        null=True, blank=True, verbose_name=_("Variable pay cut-off")
    )
    status = models.CharField(
        max_length=32,
        choices=PAYROLL_RUN_STATUS,
        default="open",
        verbose_name=_("Status"),
    )
    version = models.PositiveIntegerField(default=1, verbose_name=_("Version"))
    parent_run = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="revisions",
        verbose_name=_("Previous version"),
    )
    group_name = models.CharField(
        max_length=80,
        blank=True,
        null=True,
        verbose_name=_("Batch / group name"),
    )
    proration_method = models.CharField(
        max_length=20,
        choices=PRORATION_METHODS,
        default="calendar",
        verbose_name=_("Proration method"),
    )
    attendance_locked = models.BooleanField(
        default=False,
        verbose_name=_("Attendance locked"),
        help_text=_("When true, attendance for this period must not change payroll inputs."),
    )
    attendance_locked_at = models.DateTimeField(null=True, blank=True)
    validation_report = models.JSONField(default=dict, blank=True)
    variance_report = models.JSONField(default=dict, blank=True)
    totals_snapshot = models.JSONField(
        default=dict,
        blank=True,
        help_text=_("Frozen headcount / gross / net / CTC totals at lock time."),
    )
    locked_at = models.DateTimeField(null=True, blank=True)
    locked_by = models.ForeignKey(
        Employee,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payroll_runs_locked",
    )
    paid_at = models.DateTimeField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    reopen_reason = models.TextField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)

    objects = HorillaCompanyManager("company_id")

    class Meta:
        verbose_name = _("Payroll Run")
        verbose_name_plural = _("Payroll Runs")
        ordering = ["-year", "-month", "-version"]
        constraints = [
            models.UniqueConstraint(
                fields=["company_id", "year", "month", "version"],
                name="uniq_payroll_run_company_period_version",
            )
        ]

    def __str__(self):
        return (
            f"{self.company_id} {self.year}-{self.month:02d} "
            f"v{self.version} ({self.status})"
        )

    @property
    def is_immutable(self) -> bool:
        return self.status in IMMUTABLE_RUN_STATUSES

    @property
    def period_label(self) -> str:
        return f"{self.year}-{self.month:02d}"

    def can_transition_to(self, new_status: str) -> bool:
        allowed = {
            "open": {"input_pending", "calculated"},
            "input_pending": {"calculated", "open"},
            "calculated": {"validation_failed", "validation_passed"},
            "validation_failed": {"calculated", "open"},
            "validation_passed": {"hr_approved", "calculated"},
            "hr_approved": {"finance_approved", "validation_passed"},
            "finance_approved": {"locked", "hr_approved"},
            "locked": {"paid"},
            "paid": {"published"},
            "published": set(),
        }
        return new_status in allowed.get(self.status, set())


class PayrollRunSnapshot(HorillaModel):
    """Immutable archive of a locked payroll run (employee payslip payloads)."""

    payroll_run = models.ForeignKey(
        PayrollRun,
        on_delete=models.CASCADE,
        related_name="snapshots",
    )
    employee_id = models.ForeignKey(
        Employee,
        on_delete=models.PROTECT,
        related_name="payroll_run_snapshots",
    )
    payslip_id = models.PositiveIntegerField(null=True, blank=True)
    payload = models.JSONField(default=dict)
    gross_pay = models.FloatField(default=0)
    net_pay = models.FloatField(default=0)
    deduction = models.FloatField(default=0)

    objects = HorillaCompanyManager("employee_id__employee_work_info__company_id")

    class Meta:
        verbose_name = _("Payroll Run Snapshot")
        verbose_name_plural = _("Payroll Run Snapshots")
        unique_together = ("payroll_run", "employee_id")


class AttendanceArrear(HorillaModel):
    """
    Retro attendance adjustment after a payroll month was locked.
    Never mutates the locked month — pays as arrear in a later open month.
    """

    employee_id = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name="attendance_arrears",
    )
    source_period_start = models.DateField(verbose_name=_("Source period start"))
    source_period_end = models.DateField(verbose_name=_("Source period end"))
    days = models.FloatField(
        default=0,
        help_text=_("Positive = additional paid days; negative = recovery."),
    )
    amount = models.FloatField(default=0)
    reason = models.TextField(blank=True, null=True)
    payout_month = models.DateField(
        null=True,
        blank=True,
        help_text=_("First day of the month this arrear should pay in."),
    )
    paid = models.BooleanField(default=False)
    paid_on = models.DateField(null=True, blank=True)
    allowance = models.ForeignKey(
        "payroll.Allowance",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="attendance_arrears",
    )
    source_payroll_run = models.ForeignKey(
        PayrollRun,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="attendance_arrears",
    )

    objects = HorillaCompanyManager("employee_id__employee_work_info__company_id")

    class Meta:
        verbose_name = _("Attendance Arrear")
        verbose_name_plural = _("Attendance Arrears")
        ordering = ["-id"]

    def __str__(self):
        return f"{self.employee_id} {self.days}d @ {self.source_period_start}"
