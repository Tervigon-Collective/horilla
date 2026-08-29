"""
Indian statutory payroll configuration and Form 16 records.
"""

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from base.horilla_company_manager import HorillaCompanyManager
from base.models import Company
from employee.models import Employee
from horilla.models import HorillaModel

INDIAN_STATES = [
    ("AN", _("Andaman and Nicobar Islands")),
    ("AP", _("Andhra Pradesh")),
    ("AR", _("Arunachal Pradesh")),
    ("AS", _("Assam")),
    ("BR", _("Bihar")),
    ("CH", _("Chandigarh")),
    ("CT", _("Chhattisgarh")),
    ("DL", _("Delhi")),
    ("GA", _("Goa")),
    ("GJ", _("Gujarat")),
    ("HR", _("Haryana")),
    ("HP", _("Himachal Pradesh")),
    ("JH", _("Jharkhand")),
    ("KA", _("Karnataka")),
    ("KL", _("Kerala")),
    ("LA", _("Ladakh")),
    ("LD", _("Lakshadweep")),
    ("MP", _("Madhya Pradesh")),
    ("MH", _("Maharashtra")),
    ("MN", _("Manipur")),
    ("ML", _("Meghalaya")),
    ("MZ", _("Mizoram")),
    ("NL", _("Nagaland")),
    ("OR", _("Odisha")),
    ("PY", _("Puducherry")),
    ("PB", _("Punjab")),
    ("RJ", _("Rajasthan")),
    ("SK", _("Sikkim")),
    ("TN", _("Tamil Nadu")),
    ("TS", _("Telangana")),
    ("TR", _("Tripura")),
    ("UP", _("Uttar Pradesh")),
    ("UK", _("Uttarakhand")),
    ("WB", _("West Bengal")),
]

TDS_REGIME_CHOICES = [
    ("new", _("New Regime (default)")),
    ("old", _("Old Regime")),
]


class IndiaStatutorySettings(HorillaModel):
    """Company-level Indian statutory payroll configuration."""

    company_id = models.OneToOneField(
        Company,
        on_delete=models.CASCADE,
        related_name="india_statutory_settings",
        verbose_name=_("Company"),
    )
    is_enabled = models.BooleanField(
        default=False,
        verbose_name=_("Enable Indian Statutory Payroll"),
    )
    enable_pf = models.BooleanField(default=True, verbose_name=_("Provident Fund (EPF)"))
    enable_esi = models.BooleanField(default=True, verbose_name=_("ESI"))
    enable_pt = models.BooleanField(default=True, verbose_name=_("Professional Tax"))
    enable_tds = models.BooleanField(default=True, verbose_name=_("TDS (Income Tax)"))
    enable_lwf = models.BooleanField(
        default=False,
        verbose_name=_("Labour Welfare Fund (LWF)"),
    )
    enable_bonus = models.BooleanField(
        default=False,
        verbose_name=_("Payment of Bonus Act (monthly provision)"),
    )
    enable_gratuity = models.BooleanField(
        default=True,
        verbose_name=_("Payment of Gratuity Act (F&F / register)"),
    )
    enable_code_on_wages_50pct = models.BooleanField(
        default=False,
        verbose_name=_("Code on Wages 50% rule (statutory wage)"),
        help_text=_(
            "When enabled, excluded allowances above 50% of remuneration are "
            "added back into the PF statutory wage base."
        ),
    )
    pf_wage_ceiling = models.FloatField(
        default=15000.0,
        verbose_name=_("PF wage ceiling (₹)"),
    )
    pf_employee_rate = models.FloatField(
        default=12.0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name=_("PF employee rate (%)"),
    )
    pf_employer_rate = models.FloatField(
        default=12.0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name=_("PF employer rate (%)"),
    )
    esi_gross_ceiling = models.FloatField(
        default=21000.0,
        verbose_name=_("ESI gross ceiling (₹)"),
    )
    esi_employee_rate = models.FloatField(
        default=0.75,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name=_("ESI employee rate (%)"),
    )
    esi_employer_rate = models.FloatField(
        default=3.25,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name=_("ESI employer rate (%)"),
    )
    pt_state = models.CharField(
        max_length=5,
        choices=INDIAN_STATES,
        default="MH",
        verbose_name=_("Professional Tax state"),
    )
    default_tds_regime = models.CharField(
        max_length=10,
        choices=TDS_REGIME_CHOICES,
        default="new",
        verbose_name=_("Default TDS regime"),
    )
    standard_deduction_annual = models.FloatField(
        default=75000.0,
        verbose_name=_("Standard deduction (annual, ₹) — new regime"),
    )
    standard_deduction_old_regime = models.FloatField(
        default=50000.0,
        verbose_name=_("Standard deduction (annual, ₹) — old regime"),
    )
    tan_number = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name=_("Employer TAN"),
    )
    bsr_code = models.CharField(
        max_length=7,
        blank=True,
        null=True,
        verbose_name=_("Bank BSR code"),
        help_text=_("7-digit BSR code from the TDS challan (ITNS 281)."),
    )
    pf_establishment_code = models.CharField(
        max_length=30,
        blank=True,
        null=True,
        verbose_name=_("PF establishment code"),
    )
    esi_establishment_code = models.CharField(
        max_length=30,
        blank=True,
        null=True,
        verbose_name=_("ESI establishment code"),
    )

    objects = HorillaCompanyManager("company_id")

    class Meta:
        verbose_name = _("India Statutory Settings")
        verbose_name_plural = _("India Statutory Settings")

    def __str__(self):
        return f"India statutory — {self.company_id}"


class EmployeeStatutoryProfile(HorillaModel):
    """Per-employee overrides for Indian statutory calculations."""

    employee_id = models.OneToOneField(
        Employee,
        on_delete=models.CASCADE,
        related_name="statutory_profile",
        verbose_name=_("Employee"),
    )
    pf_applicable = models.BooleanField(default=True, verbose_name=_("PF applicable"))
    esi_applicable = models.BooleanField(default=True, verbose_name=_("ESI applicable"))
    pt_applicable = models.BooleanField(default=True, verbose_name=_("PT applicable"))
    tds_applicable = models.BooleanField(default=True, verbose_name=_("TDS applicable"))
    lwf_applicable = models.BooleanField(default=True, verbose_name=_("LWF applicable"))
    bonus_applicable = models.BooleanField(
        default=True, verbose_name=_("Bonus Act applicable")
    )
    gratuity_applicable = models.BooleanField(
        default=True, verbose_name=_("Gratuity applicable")
    )
    tds_regime = models.CharField(
        max_length=10,
        choices=TDS_REGIME_CHOICES,
        blank=True,
        null=True,
        verbose_name=_("TDS regime override"),
    )
    section_80c_annual = models.FloatField(
        default=0.0,
        verbose_name=_("Section 80C (annual, ₹) — old regime"),
    )
    section_80d_annual = models.FloatField(
        default=0.0,
        verbose_name=_("Section 80D (annual, ₹) — old regime"),
    )
    other_chapter_vi_a = models.FloatField(
        default=0.0,
        verbose_name=_("Other Chapter VI-A (annual, ₹)"),
    )
    vpf_rate = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name=_("VPF extra (%) on PF wages"),
    )
    contribute_pf_on_actual_wage = models.BooleanField(
        default=False,
        verbose_name=_("Contribute PF on actual wage (ignore ceiling)"),
    )
    previous_employer_income = models.FloatField(
        default=0.0,
        verbose_name=_("Previous employer taxable income (FY, ₹)"),
    )
    previous_employer_tds = models.FloatField(
        default=0.0,
        verbose_name=_("Previous employer TDS already deducted (FY, ₹)"),
    )
    other_income_annual = models.FloatField(
        default=0.0,
        verbose_name=_("Declared other income (annual, ₹)"),
    )
    proof_submission_status = models.CharField(
        max_length=20,
        choices=[
            ("pending", _("Pending")),
            ("submitted", _("Submitted")),
            ("verified", _("Verified")),
            ("rejected", _("Rejected")),
        ],
        default="pending",
        verbose_name=_("Investment proof status"),
    )
    payroll_status = models.CharField(
        max_length=20,
        choices=[
            ("included", _("Included")),
            ("on_hold", _("On Hold")),
            ("excluded", _("Excluded")),
        ],
        default="included",
        verbose_name=_("Payroll status"),
    )

    objects = HorillaCompanyManager("employee_id__employee_work_info__company_id")

    class Meta:
        verbose_name = _("Employee Statutory Profile")
        verbose_name_plural = _("Employee Statutory Profiles")

    def __str__(self):
        return f"Statutory profile — {self.employee_id}"


class Form16Record(HorillaModel):
    """Generated Form 16 summary for an employee and financial year."""

    employee_id = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name="form16_records",
        verbose_name=_("Employee"),
    )
    financial_year_start = models.PositiveIntegerField(verbose_name=_("FY start year"))
    financial_year_end = models.PositiveIntegerField(verbose_name=_("FY end year"))
    gross_salary = models.FloatField(default=0)
    pf_employee_total = models.FloatField(default=0)
    pf_employer_total = models.FloatField(default=0)
    esi_employee_total = models.FloatField(default=0)
    pt_total = models.FloatField(default=0)
    tds_total = models.FloatField(default=0)
    net_salary = models.FloatField(default=0)
    regime = models.CharField(max_length=10, default="new")
    summary_json = models.JSONField(default=dict, blank=True)
    generated_at = models.DateTimeField(auto_now=True)

    objects = HorillaCompanyManager("employee_id__employee_work_info__company_id")

    class Meta:
        verbose_name = _("Form 16 Record")
        verbose_name_plural = _("Form 16 Records")
        unique_together = ("employee_id", "financial_year_start")

    def __str__(self):
        return f"Form 16 FY {self.financial_year_start}-{str(self.financial_year_end)[-2:]} — {self.employee_id}"

    @property
    def financial_year_label(self):
        return f"{self.financial_year_start}-{str(self.financial_year_end)[-2:]}"
