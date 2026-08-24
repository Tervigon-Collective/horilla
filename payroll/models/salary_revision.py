"""Salary revision records and salary hold/release."""

from django.db import models
from django.utils.translation import gettext_lazy as _

from base.horilla_company_manager import HorillaCompanyManager
from employee.models import Employee
from horilla.models import HorillaModel
from payroll.models.models import Allowance, Contract


class SalaryRevision(HorillaModel):
    """One CTC / compensation change for an employee contract."""

    employee_id = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name="salary_revisions",
        verbose_name=_("Employee"),
    )
    contract_id = models.ForeignKey(
        Contract,
        on_delete=models.CASCADE,
        related_name="salary_revisions",
        verbose_name=_("Contract"),
    )
    effective_date = models.DateField(verbose_name=_("Effective date"))
    previous_monthly_ctc = models.FloatField(default=0)
    new_monthly_ctc = models.FloatField(default=0)
    previous_basic = models.FloatField(default=0)
    new_basic = models.FloatField(default=0)
    new_hra = models.FloatField(default=0)
    new_special = models.FloatField(default=0)
    metro = models.BooleanField(default=True)
    increment_percent = models.FloatField(default=0)
    arrears_months = models.PositiveIntegerField(default=0)
    arrears_amount = models.FloatField(default=0)
    arrears_paid = models.BooleanField(default=False, verbose_name=_("Arrears paid"))
    arrears_paid_on = models.DateField(
        null=True, blank=True, verbose_name=_("Arrears paid on")
    )
    arrears_allowance = models.ForeignKey(
        Allowance,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="salary_revision_arrears",
        verbose_name=_("Arrears allowance"),
    )
    note = models.TextField(blank=True, null=True)

    objects = HorillaCompanyManager("employee_id__employee_work_info__company_id")

    class Meta:
        verbose_name = _("Salary Revision")
        verbose_name_plural = _("Salary Revisions")
        ordering = ["-effective_date", "-id"]

    def __str__(self):
        return f"{self.employee_id} @ {self.effective_date} ({self.new_monthly_ctc})"


class SalaryHold(HorillaModel):
    """Active salary hold blocks payslip generation until released."""

    employee_id = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name="salary_holds",
        verbose_name=_("Employee"),
    )
    reason = models.TextField(blank=True, null=True, verbose_name=_("Reason"))
    held_on = models.DateField(verbose_name=_("Held on"))
    released_on = models.DateField(
        null=True, blank=True, verbose_name=_("Released on")
    )
    held_by = models.ForeignKey(
        Employee,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="salary_holds_placed",
        verbose_name=_("Held by"),
    )
    released_by = models.ForeignKey(
        Employee,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="salary_holds_released",
        verbose_name=_("Released by"),
    )

    objects = HorillaCompanyManager("employee_id__employee_work_info__company_id")

    class Meta:
        verbose_name = _("Salary Hold")
        verbose_name_plural = _("Salary Holds")
        ordering = ["-held_on", "-id"]

    def __str__(self):
        status = "held" if self.is_active and not self.released_on else "released"
        return f"{self.employee_id} ({status})"
