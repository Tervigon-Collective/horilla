import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("employee", "0005_alter_employee_phone_and_more"),
        ("payroll", "0014_lwf_bonus_gratuity"),
    ]

    operations = [
        migrations.CreateModel(
            name="SalaryRevision",
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
                        auto_now_add=True, blank=True, null=True, verbose_name="Created At"
                    ),
                ),
                ("is_active", models.BooleanField(default=True, verbose_name="Is Active")),
                ("effective_date", models.DateField(verbose_name="Effective date")),
                ("previous_monthly_ctc", models.FloatField(default=0)),
                ("new_monthly_ctc", models.FloatField(default=0)),
                ("previous_basic", models.FloatField(default=0)),
                ("new_basic", models.FloatField(default=0)),
                ("new_hra", models.FloatField(default=0)),
                ("new_special", models.FloatField(default=0)),
                ("metro", models.BooleanField(default=True)),
                ("increment_percent", models.FloatField(default=0)),
                ("arrears_months", models.PositiveIntegerField(default=0)),
                ("arrears_amount", models.FloatField(default=0)),
                ("note", models.TextField(blank=True, null=True)),
                (
                    "contract_id",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="salary_revisions",
                        to="payroll.contract",
                        verbose_name="Contract",
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
                    "employee_id",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="salary_revisions",
                        to="employee.employee",
                        verbose_name="Employee",
                    ),
                ),
                (
                    "modified_by",
                    models.ForeignKey(
                        blank=True,
                        editable=False,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="salaryrevision_modified_by",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Modified By",
                    ),
                ),
            ],
            options={
                "verbose_name": "Salary Revision",
                "verbose_name_plural": "Salary Revisions",
                "ordering": ["-effective_date", "-id"],
            },
        ),
    ]
