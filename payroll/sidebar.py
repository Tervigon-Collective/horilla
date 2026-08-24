"""
payroll/sidebar.py

"""

from django.apps import apps
from django.urls import reverse, reverse_lazy
from django.utils.translation import gettext_lazy as _

from horilla.menu import settings_menu

MENU = _("Payroll")
IMG_SRC = "images/ui/wallet-outline.svg"

SUBMENUS = [
    {
        "menu": _("Dashboard"),
        "redirect": reverse("view-payroll-dashboard"),
        "accessibility": "payroll.sidebar.dasbhoard_accessibility",
    },
    {
        "menu": _("Payslips"),
        "redirect": reverse("view-payslip"),
    },
    # {
    #     "menu": _("Allowances"),
    #     "redirect": reverse("view-allowance"),
    #     "accessibility": "payroll.sidebar.allowance_accessibility",
    # },
    # {
    #     "menu": _("Deductions"),
    #     "redirect": reverse("view-deduction"),
    #     "accessibility": "payroll.sidebar.deduction_accessibility",
    # },
    {
        "menu": _("Loans & Salary Advances"),
        "redirect": reverse("view-loan"),
        "accessibility": "payroll.sidebar.loan_accessibility",
    },
    {
        "menu": _("Encashments & Reimbursements"),
        "redirect": reverse("view-reimbursement"),
    },
    {
        "menu": _("Contracts"),
        "redirect": reverse("view-contract"),
        "accessibility": "payroll.sidebar.dasbhoard_accessibility",
    },
    {
        "menu": _("Salary Revisions"),
        "redirect": reverse("salary-revision-list"),
        "accessibility": "payroll.sidebar.dasbhoard_accessibility",
    },
    {
        "menu": _("Salary Holds"),
        "redirect": reverse("salary-hold-list"),
        "accessibility": "payroll.sidebar.dasbhoard_accessibility",
    },
    {
        "menu": _("Income Tax"),
        "redirect": reverse("filing-status-view"),
        "accessibility": "payroll.sidebar.federal_tax_accessibility",
    },
    {
        "menu": _("India Statutory"),
        "redirect": reverse("india-statutory-settings"),
        "accessibility": "payroll.sidebar.india_statutory_accessibility",
    },
    {
        "menu": _("Form 16"),
        "redirect": reverse("form16-list"),
        "accessibility": "payroll.sidebar.india_statutory_accessibility",
    },
    {
        "menu": _("Statutory Challans"),
        "redirect": reverse("challan-list"),
        "accessibility": "payroll.sidebar.india_statutory_accessibility",
    },
    {
        "menu": _("Statutory Registers"),
        "redirect": reverse("statutory-register"),
        "accessibility": "payroll.sidebar.india_statutory_accessibility",
    },
    {
        "menu": _("Form 24Q"),
        "redirect": reverse("form24q-list"),
        "accessibility": "payroll.sidebar.india_statutory_accessibility",
    },
    {
        "menu": _("TRACES e-Filing"),
        "redirect": reverse("traces-efiling"),
        "accessibility": "payroll.sidebar.india_statutory_accessibility",
    },
    {
        "menu": _("Accounting Export"),
        "redirect": reverse("accounting-export-list"),
        "accessibility": "payroll.sidebar.india_statutory_accessibility",
    },
    {
        "menu": _("Statutory Excel"),
        "redirect": reverse("statutory-excel-hub"),
        "accessibility": "payroll.sidebar.india_statutory_accessibility",
    },
    {
        "menu": _("Configuration"),
        "redirect": reverse("payroll-settings-view"),
        "accessibility": "payroll.sidebar.payroll_settings_accessibility",
    },
]


def dasbhoard_accessibility(request, submenu, user_perms, *args, **kwargs):
    return request.user.has_perm("payroll.view_contract")


def allowance_accessibility(request, submenu, user_perms, *args, **kwargs):
    return request.user.has_perm("payroll.view_allowance")


def deduction_accessibility(request, submenu, user_perms, *args, **kwargs):
    return request.user.has_perm("payroll.view_deduction")


def loan_accessibility(request, submenu, user_perms, *args, **kwargs):
    return request.user.has_perm("payroll.view_loanaccount")


def federal_tax_accessibility(request, submenu, user_perms, *args, **kwargs):
    return request.user.has_perm("payroll.view_filingstatus")


def india_statutory_accessibility(request, submenu, user_perms, *args, **kwargs):
    return request.user.has_perm("payroll.change_payslip") or request.user.has_perm(
        "payroll.view_payslip"
    )


# ---------------------------------------------------------------------------
# Settings menu registrations
# ---------------------------------------------------------------------------


def payroll_settings_accessibility(request, submenu, user_perms, *args, **kwargs):
    return request.user.has_perm("payroll.view_payslipautogenerate")


def encashment_settings_accessibility(request, submenu, user_perms, *args, **kwargs):
    return request.user.has_perm("payroll.change_encashmentgeneralsettings")


@settings_menu.register
class PayrollSettings:
    title = _("Payroll")
    order = 7
    condition = lambda self, request: apps.is_installed("payroll")
    items = [
        {
            "label": _("Encashment Settings"),
            "url": reverse_lazy("encashment-settings-view"),
            "accessibility": encashment_settings_accessibility,
            "search_entries": [
                {
                    "text": _("Encashment"),
                    "description": _(
                        "Configure leave and bonus point encashment rules"
                    ),
                },
                {
                    "text": _("Bonus Unit"),
                    "description": _(
                        "Monetary value credited per bonus point redeemed"
                    ),
                },
                {
                    "text": _("Leave Unit Amount"),
                    "description": _("Monetary value credited per leave day encashed"),
                },
            ],
        },
        {
            "label": _("India Statutory Payroll"),
            "url": reverse_lazy("india-statutory-settings"),
            "accessibility": india_statutory_accessibility,
            "search_entries": [
                {
                    "text": _("PF"),
                    "description": _("Provident Fund settings for Indian payroll"),
                },
                {
                    "text": _("ESI"),
                    "description": _("Employee State Insurance settings"),
                },
                {
                    "text": _("TDS"),
                    "description": _("Tax deducted at source configuration"),
                },
                {
                    "text": _("Form 16"),
                    "description": _("Annual tax certificate records"),
                },
            ],
        },
    ]
