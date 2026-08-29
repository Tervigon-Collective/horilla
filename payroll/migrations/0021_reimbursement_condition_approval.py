# Generated manually for ReimbursementConditionApproval

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("employee", "0005_alter_employee_phone_and_more"),
        ("payroll", "0020_complete_payroll_architecture"),
    ]

    operations = [
        migrations.CreateModel(
            name="ReimbursementConditionApproval",
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
                ("sequence", models.IntegerField()),
                ("is_approved", models.BooleanField(default=False)),
                ("is_rejected", models.BooleanField(default=False)),
                (
                    "manager_id",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="employee.employee",
                    ),
                ),
                (
                    "reimbursement_id",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="condition_approvals",
                        to="payroll.reimbursement",
                    ),
                ),
            ],
            options={
                "ordering": ["sequence"],
            },
        ),
    ]
