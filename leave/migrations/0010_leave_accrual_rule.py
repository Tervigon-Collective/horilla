# Generated for leave accrual rules by grade/position

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("base", "0001_initial"),
        ("leave", "0009_leavetype_accrual_sandwich"),
    ]

    operations = [
        migrations.CreateModel(
            name="LeaveAccrualRule",
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
                (
                    "job_grade",
                    models.CharField(
                        blank=True,
                        help_text="Match employee work info job grade (blank = any grade)",
                        max_length=50,
                        null=True,
                        verbose_name="Job Grade",
                    ),
                ),
                (
                    "annual_days",
                    models.FloatField(
                        help_text="Yearly entitlement for employees matching this rule",
                        verbose_name="Annual days",
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
                    "job_position_id",
                    models.ForeignKey(
                        blank=True,
                        help_text="Match employee job position (blank = any position)",
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="leave_accrual_rules",
                        to="base.jobposition",
                        verbose_name="Job Position",
                    ),
                ),
                (
                    "leave_type_id",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="accrual_rules",
                        to="leave.leavetype",
                        verbose_name="Leave Type",
                    ),
                ),
                (
                    "modified_by",
                    models.ForeignKey(
                        blank=True,
                        editable=False,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="leaveaccrualrule_modified_by",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Modified By",
                    ),
                ),
            ],
            options={
                "verbose_name": "Leave Accrual Rule",
                "verbose_name_plural": "Leave Accrual Rules",
                "ordering": ["-id"],
            },
        ),
    ]
