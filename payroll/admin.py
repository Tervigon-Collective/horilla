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
from payroll.models.payroll_run import AttendanceArrear, PayrollRun, PayrollRunSnapshot
from payroll.models.salary_revision import PayslipOverride, SalaryHold, SalaryRevision

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
admin.site.register(PayrollRun)
admin.site.register(PayrollRunSnapshot)
admin.site.register(AttendanceArrear)
admin.site.register(SalaryRevision)
admin.site.register(SalaryHold)
admin.site.register(PayslipOverride)
