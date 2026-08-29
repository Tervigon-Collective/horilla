# Structure versioning, payslip overrides, rounding, attendance lock

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("employee", "0005_alter_employee_phone_and_more"),
        ("payroll", "0018_payroll_run_lock"),
    ]

    operations = [
        migrations.AddField(
            model_name="payrollgeneralsetting",
            name="component_decimals",
            field=models.PositiveSmallIntegerField(
                default=2, verbose_name="Component decimal places"
            ),
        ),
        migrations.AddField(
            model_name="payrollgeneralsetting",
            name="component_round_mode",
            field=models.CharField(
                choices=[
                    ("two_decimals", "Two decimals"),
                    ("nearest_rupee", "Nearest rupee"),
                    ("none", "No extra rounding"),
                ],
                default="two_decimals",
                max_length=20,
                verbose_name="Component rounding",
            ),
        ),
        migrations.AddField(
            model_name="payrollgeneralsetting",
            name="net_pay_round_mode",
            field=models.CharField(
                choices=[
                    ("two_decimals", "Two decimals"),
                    ("nearest_rupee", "Nearest rupee"),
                    ("none", "No extra rounding"),
                ],
                default="nearest_rupee",
                max_length=20,
                verbose_name="Net pay rounding",
            ),
        ),
        migrations.AddField(
            model_name="payrollgeneralsetting",
            name="statutory_round_mode",
            field=models.CharField(
                choices=[
                    ("two_decimals", "Two decimals"),
                    ("nearest_rupee", "Nearest rupee"),
                    ("none", "No extra rounding"),
                ],
                default="two_decimals",
                max_length=20,
                verbose_name="Statutory rounding",
            ),
        ),
        migrations.AddField(
            model_name="payrollrun",
            name="attendance_locked",
            field=models.BooleanField(
                default=False,
                help_text="When true, attendance for this period must not change payroll inputs.",
                verbose_name="Attendance locked",
            ),
        ),
        migrations.AddField(
            model_name="payrollrun",
            name="attendance_locked_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="salaryrevision",
            name="effective_to",
            field=models.DateField(
                blank=True,
                help_text="Set when a newer structure version closes this one.",
                null=True,
                verbose_name="Effective to",
            ),
        ),
        migrations.AddField(
            model_name="salaryrevision",
            name="status",
            field=models.CharField(
                choices=[
                    ("draft", "Draft"),
                    ("active", "Active"),
                    ("closed", "Closed"),
                ],
                default="active",
                max_length=16,
                verbose_name="Status",
            ),
        ),
        migrations.AddField(
            model_name="salaryrevision",
            name="version",
            field=models.PositiveIntegerField(
                default=1, verbose_name="Structure version"
            ),
        ),
        migrations.CreateModel(
            name="PayslipOverride",
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
                (
                    "is_active",
                    models.BooleanField(default=True, verbose_name="Is Active"),
                ),
                (
                    "field_name",
                    models.CharField(
                        choices=[
                            ("basic_pay", "Basic pay"),
                            ("gross_pay", "Gross pay"),
                            ("deduction", "Total deduction"),
                            ("net_pay", "Net pay"),
                            ("component", "Named component"),
                        ],
                        default="net_pay",
                        max_length=32,
                    ),
                ),
                (
                    "component_title",
                    models.CharField(
                        blank=True,
                        help_text="When field_name=component, the payslip line title.",
                        max_length=120,
                        null=True,
                    ),
                ),
                ("original_value", models.FloatField(verbose_name="Original value")),
                ("revised_value", models.FloatField(verbose_name="Revised value")),
                ("reason", models.TextField(verbose_name="Reason")),
                (
                    "attachment",
                    models.FileField(
                        blank=True,
                        null=True,
                        upload_to="payroll/overrides/",
                        verbose_name="Supporting attachment",
                    ),
                ),
                ("approved_at", models.DateTimeField(blank=True, null=True)),
                (
                    "approved_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="payslip_overrides_approved",
                        to="employee.employee",
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
                    "payslip",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="overrides",
                        to="payroll.payslip",
                        verbose_name="Payslip",
                    ),
                ),
                (
                    "requested_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="payslip_overrides_requested",
                        to="employee.employee",
                    ),
                ),
            ],
            options={
                "verbose_name": "Payslip Override",
                "verbose_name_plural": "Payslip Overrides",
                "ordering": ["-id"],
            },
        ),
        migrations.AlterModelOptions(
            name="salaryrevision",
            options={
                "ordering": ["-effective_date", "-version", "-id"],
                "verbose_name": "Salary Revision",
                "verbose_name_plural": "Salary Revisions",
            },
        ),
    ]
