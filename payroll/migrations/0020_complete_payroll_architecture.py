# Complete remaining payroll architecture gaps

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("employee", "0005_alter_employee_phone_and_more"),
        ("payroll", "0019_structure_override_rounding"),
    ]

    operations = [
        migrations.AddField(
            model_name="allowance",
            name="effective_from",
            field=models.DateField(blank=True, null=True, verbose_name="Effective from"),
        ),
        migrations.AddField(
            model_name="allowance",
            name="effective_to",
            field=models.DateField(blank=True, null=True, verbose_name="Effective to"),
        ),
        migrations.AddField(
            model_name="allowance",
            name="esi_applicable",
            field=models.BooleanField(default=False, verbose_name="ESI applicable component"),
        ),
        migrations.AddField(
            model_name="allowance",
            name="include_in_ctc",
            field=models.BooleanField(default=True, verbose_name="Included in CTC"),
        ),
        migrations.AddField(
            model_name="allowance",
            name="include_in_gross",
            field=models.BooleanField(default=True, verbose_name="Included in Gross"),
        ),
        migrations.AddField(
            model_name="allowance",
            name="include_in_wage_definition",
            field=models.BooleanField(
                default=False,
                help_text="Counts toward Code-on-Wages / PF wage components when set.",
                verbose_name="Included in statutory wage definition",
            ),
        ),
        migrations.AddField(
            model_name="allowance",
            name="is_excluded_allowance",
            field=models.BooleanField(
                default=False,
                help_text="HRA / special-style exclusions for statutory wage 50% rule.",
                verbose_name="Excluded allowance (CoW 50% test)",
            ),
        ),
        migrations.AddField(
            model_name="allowance",
            name="payslip_visible",
            field=models.BooleanField(default=True, verbose_name="Visible on payslip"),
        ),
        migrations.AddField(
            model_name="allowance",
            name="pf_applicable",
            field=models.BooleanField(default=False, verbose_name="PF applicable component"),
        ),
        migrations.AddField(
            model_name="allowance",
            name="proratable",
            field=models.BooleanField(default=True, verbose_name="Proratable"),
        ),
        migrations.AddField(
            model_name="employeestatutoryprofile",
            name="contribute_pf_on_actual_wage",
            field=models.BooleanField(
                default=False,
                verbose_name="Contribute PF on actual wage (ignore ceiling)",
            ),
        ),
        migrations.AddField(
            model_name="employeestatutoryprofile",
            name="other_income_annual",
            field=models.FloatField(
                default=0.0, verbose_name="Declared other income (annual, ₹)"
            ),
        ),
        migrations.AddField(
            model_name="employeestatutoryprofile",
            name="payroll_status",
            field=models.CharField(
                choices=[
                    ("included", "Included"),
                    ("on_hold", "On Hold"),
                    ("excluded", "Excluded"),
                ],
                default="included",
                max_length=20,
                verbose_name="Payroll status",
            ),
        ),
        migrations.AddField(
            model_name="employeestatutoryprofile",
            name="previous_employer_income",
            field=models.FloatField(
                default=0.0, verbose_name="Previous employer taxable income (FY, ₹)"
            ),
        ),
        migrations.AddField(
            model_name="employeestatutoryprofile",
            name="previous_employer_tds",
            field=models.FloatField(
                default=0.0,
                verbose_name="Previous employer TDS already deducted (FY, ₹)",
            ),
        ),
        migrations.AddField(
            model_name="employeestatutoryprofile",
            name="proof_submission_status",
            field=models.CharField(
                choices=[
                    ("pending", "Pending"),
                    ("submitted", "Submitted"),
                    ("verified", "Verified"),
                    ("rejected", "Rejected"),
                ],
                default="pending",
                max_length=20,
                verbose_name="Investment proof status",
            ),
        ),
        migrations.CreateModel(
            name="PayrollRunSnapshot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, blank=True, null=True, verbose_name="Created At")),
                ("is_active", models.BooleanField(default=True, verbose_name="Is Active")),
                ("payslip_id", models.PositiveIntegerField(blank=True, null=True)),
                ("payload", models.JSONField(default=dict)),
                ("gross_pay", models.FloatField(default=0)),
                ("net_pay", models.FloatField(default=0)),
                ("deduction", models.FloatField(default=0)),
                ("created_by", models.ForeignKey(blank=True, editable=False, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL, verbose_name="Created By")),
                ("employee_id", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="payroll_run_snapshots", to="employee.employee")),
                ("modified_by", models.ForeignKey(blank=True, editable=False, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="%(class)s_modified_by", to=settings.AUTH_USER_MODEL, verbose_name="Modified By")),
                ("payroll_run", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="snapshots", to="payroll.payrollrun")),
            ],
            options={
                "verbose_name": "Payroll Run Snapshot",
                "verbose_name_plural": "Payroll Run Snapshots",
                "unique_together": {("payroll_run", "employee_id")},
            },
        ),
        migrations.CreateModel(
            name="AttendanceArrear",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, blank=True, null=True, verbose_name="Created At")),
                ("is_active", models.BooleanField(default=True, verbose_name="Is Active")),
                ("source_period_start", models.DateField(verbose_name="Source period start")),
                ("source_period_end", models.DateField(verbose_name="Source period end")),
                ("days", models.FloatField(default=0, help_text="Positive = additional paid days; negative = recovery.")),
                ("amount", models.FloatField(default=0)),
                ("reason", models.TextField(blank=True, null=True)),
                ("payout_month", models.DateField(blank=True, help_text="First day of the month this arrear should pay in.", null=True)),
                ("paid", models.BooleanField(default=False)),
                ("paid_on", models.DateField(blank=True, null=True)),
                ("allowance", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="attendance_arrears", to="payroll.allowance")),
                ("created_by", models.ForeignKey(blank=True, editable=False, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL, verbose_name="Created By")),
                ("employee_id", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="attendance_arrears", to="employee.employee")),
                ("modified_by", models.ForeignKey(blank=True, editable=False, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="%(class)s_modified_by", to=settings.AUTH_USER_MODEL, verbose_name="Modified By")),
                ("source_payroll_run", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="attendance_arrears", to="payroll.payrollrun")),
            ],
            options={
                "verbose_name": "Attendance Arrear",
                "verbose_name_plural": "Attendance Arrears",
                "ordering": ["-id"],
            },
        ),
    ]
