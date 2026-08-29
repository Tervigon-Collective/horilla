# Payroll run + payslip lock fields + Code on Wages toggle

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("base", "0001_initial"),
        ("employee", "0005_alter_employee_phone_and_more"),
        ("payroll", "0017_expense_mileage_policy"),
    ]

    operations = [
        migrations.CreateModel(
            name="PayrollRun",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(
                        auto_now_add=True,
                        blank=True,
                        null=True,
                        verbose_name="Created At",
                    ),
                ),
                ("is_active", models.BooleanField(default=True, verbose_name="Is Active")),
                ("year", models.PositiveIntegerField(verbose_name="Payroll year")),
                ("month", models.PositiveIntegerField(verbose_name="Payroll month")),
                ("period_start", models.DateField(verbose_name="Period start")),
                ("period_end", models.DateField(verbose_name="Period end")),
                (
                    "attendance_cutoff",
                    models.DateField(
                        blank=True, null=True, verbose_name="Attendance cut-off"
                    ),
                ),
                (
                    "variable_pay_cutoff",
                    models.DateField(
                        blank=True, null=True, verbose_name="Variable pay cut-off"
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("open", "Open"),
                            ("input_pending", "Input Pending"),
                            ("calculated", "Calculated"),
                            ("validation_failed", "Validation Failed"),
                            ("validation_passed", "Validation Passed"),
                            ("hr_approved", "HR Approved"),
                            ("finance_approved", "Finance Approved"),
                            ("locked", "Locked"),
                            ("paid", "Paid"),
                            ("published", "Published"),
                        ],
                        default="open",
                        max_length=32,
                        verbose_name="Status",
                    ),
                ),
                (
                    "version",
                    models.PositiveIntegerField(default=1, verbose_name="Version"),
                ),
                (
                    "group_name",
                    models.CharField(
                        blank=True,
                        max_length=80,
                        null=True,
                        verbose_name="Batch / group name",
                    ),
                ),
                (
                    "proration_method",
                    models.CharField(
                        choices=[
                            ("calendar", "Calendar-day method"),
                            ("working_day", "Working-day method"),
                        ],
                        default="calendar",
                        max_length=20,
                        verbose_name="Proration method",
                    ),
                ),
                ("validation_report", models.JSONField(blank=True, default=dict)),
                ("variance_report", models.JSONField(blank=True, default=dict)),
                (
                    "totals_snapshot",
                    models.JSONField(
                        blank=True,
                        default=dict,
                        help_text="Frozen headcount / gross / net / CTC totals at lock time.",
                    ),
                ),
                ("locked_at", models.DateTimeField(blank=True, null=True)),
                ("paid_at", models.DateTimeField(blank=True, null=True)),
                ("published_at", models.DateTimeField(blank=True, null=True)),
                ("reopen_reason", models.TextField(blank=True, null=True)),
                ("notes", models.TextField(blank=True, null=True)),
                (
                    "company_id",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="payroll_runs",
                        to="base.company",
                        verbose_name="Company",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        editable=False,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Created By",
                    ),
                ),
                (
                    "locked_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="payroll_runs_locked",
                        to="employee.employee",
                    ),
                ),
                (
                    "modified_by",
                    models.ForeignKey(
                        blank=True,
                        editable=False,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_modified_by",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Modified By",
                    ),
                ),
                (
                    "parent_run",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="revisions",
                        to="payroll.payrollrun",
                        verbose_name="Previous version",
                    ),
                ),
            ],
            options={
                "verbose_name": "Payroll Run",
                "verbose_name_plural": "Payroll Runs",
                "ordering": ["-year", "-month", "-version"],
            },
        ),
        migrations.AddField(
            model_name="payslip",
            name="payroll_run",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="payslips",
                to="payroll.payrollrun",
                verbose_name="Payroll run",
            ),
        ),
        migrations.AddField(
            model_name="payslip",
            name="published_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="payslip",
            name="snapshot_frozen",
            field=models.BooleanField(
                default=False,
                help_text="True when the parent payroll run is locked — do not recalculate.",
                verbose_name="Snapshot frozen",
            ),
        ),
        migrations.AddField(
            model_name="indiastatutorysettings",
            name="enable_code_on_wages_50pct",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "When enabled, excluded allowances above 50% of remuneration are "
                    "added back into the PF statutory wage base."
                ),
                verbose_name="Code on Wages 50% rule (statutory wage)",
            ),
        ),
        migrations.AddConstraint(
            model_name="payrollrun",
            constraint=models.UniqueConstraint(
                fields=("company_id", "year", "month", "version"),
                name="uniq_payroll_run_company_period_version",
            ),
        ),
    ]
