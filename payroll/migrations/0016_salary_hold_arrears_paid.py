# Generated manually for salary hold + arrears payout fields

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("employee", "0005_alter_employee_phone_and_more"),
        ("payroll", "0015_salary_revision"),
    ]

    operations = [
        migrations.AddField(
            model_name="salaryrevision",
            name="arrears_paid",
            field=models.BooleanField(default=False, verbose_name="Arrears paid"),
        ),
        migrations.AddField(
            model_name="salaryrevision",
            name="arrears_paid_on",
            field=models.DateField(
                blank=True, null=True, verbose_name="Arrears paid on"
            ),
        ),
        migrations.AddField(
            model_name="salaryrevision",
            name="arrears_allowance",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="salary_revision_arrears",
                to="payroll.allowance",
                verbose_name="Arrears allowance",
            ),
        ),
        migrations.CreateModel(
            name="SalaryHold",
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
                ("reason", models.TextField(blank=True, null=True, verbose_name="Reason")),
                ("held_on", models.DateField(verbose_name="Held on")),
                (
                    "released_on",
                    models.DateField(
                        blank=True, null=True, verbose_name="Released on"
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
                        related_name="salary_holds",
                        to="employee.employee",
                        verbose_name="Employee",
                    ),
                ),
                (
                    "held_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="salary_holds_placed",
                        to="employee.employee",
                        verbose_name="Held by",
                    ),
                ),
                (
                    "modified_by",
                    models.ForeignKey(
                        blank=True,
                        editable=False,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="salaryhold_modified_by",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Modified By",
                    ),
                ),
                (
                    "released_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="salary_holds_released",
                        to="employee.employee",
                        verbose_name="Released by",
                    ),
                ),
            ],
            options={
                "verbose_name": "Salary Hold",
                "verbose_name_plural": "Salary Holds",
                "ordering": ["-held_on", "-id"],
            },
        ),
    ]
