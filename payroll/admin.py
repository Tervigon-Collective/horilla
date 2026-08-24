"""
admin.py

Used to register models on admin site
"""

from django.contrib import admin

from payroll.models.models import (
    Allowance,
    Contract,
    Deduction,
    FilingStatus,
    LoanAccount,
    MultipleCondition,
    Payslip,
    PayslipAutoGenerate,
    Reimbursement,
    ReimbursementrequestComment,
)
from payroll.models.tax_models import PayrollSettings, TaxBracket
from payroll.models.india_statutory import (
    EmployeeStatutoryProfile,
    Form16Record,
    IndiaStatutorySettings,
)

# Register your models here.
admin.site.register(FilingStatus)
admin.site.register(TaxBracket)
admin.site.register(Contract)
admin.site.register(Allowance)
admin.site.register(Deduction)
admin.site.register(Payslip)
admin.site.register(PayrollSettings)
admin.site.register(LoanAccount)
admin.site.register(Reimbursement)
admin.site.register(ReimbursementrequestComment)
admin.site.register(MultipleCondition)
admin.site.register(PayslipAutoGenerate)
admin.site.register(IndiaStatutorySettings)
admin.site.register(EmployeeStatutoryProfile)
admin.site.register(Form16Record)
