# Generated manually for AttendanceOvertimeConditionApproval

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("attendance", "0012_add_missing_punch_in"),
        ("employee", "0005_alter_employee_phone_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="AttendanceOvertimeConditionApproval",
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
                    "attendance_id",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ot_condition_approvals",
                        to="attendance.attendance",
                    ),
                ),
                (
                    "manager_id",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="employee.employee",
                    ),
                ),
            ],
            options={
                "ordering": ["sequence"],
            },
        ),
    ]
