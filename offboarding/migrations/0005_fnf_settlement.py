# Generated for persisted F&F settlement workflow

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("employee", "0005_alter_employee_phone_and_more"),
        ("offboarding", "0004_historicalresignationletter"),
    ]

    operations = [
        migrations.CreateModel(
            name="FnFSettlement",
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
                ("last_working_day", models.DateField(blank=True, null=True)),
                ("years_of_service", models.FloatField(default=0)),
                ("gratuity", models.FloatField(default=0)),
                ("gratuity_eligible", models.BooleanField(default=False)),
                ("bonus_unpaid", models.FloatField(default=0)),
                ("leave_encashment", models.FloatField(default=0)),
                ("unused_leave_days", models.FloatField(default=0)),
                ("notice_period_pay", models.FloatField(default=0)),
                ("notice_days", models.PositiveIntegerField(default=0)),
                ("loan_recovery", models.FloatField(default=0)),
                ("other_additions", models.FloatField(default=0)),
                ("other_deductions", models.FloatField(default=0)),
                ("outstanding_assets", models.PositiveIntegerField(default=0)),
                ("total_earnings", models.FloatField(default=0)),
                ("total_recoveries", models.FloatField(default=0)),
                ("net_payable", models.FloatField(default=0)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("draft", "Draft"),
                            ("confirmed", "Confirmed"),
                            ("paid", "Paid"),
                        ],
                        default="draft",
                        max_length=12,
                    ),
                ),
                ("remarks", models.TextField(blank=True, null=True)),
                ("confirmed_on", models.DateField(blank=True, null=True)),
                ("paid_on", models.DateField(blank=True, null=True)),
                (
                    "confirmed_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="fnf_confirmed",
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
                    "employee_id",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="fnf_settlements",
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
                        related_name="fnfsettlement_modified_by",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Modified By",
                    ),
                ),
                (
                    "offboarding_employee",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="fnf_settlement",
                        to="offboarding.offboardingemployee",
                        verbose_name="Exit process",
                    ),
                ),
                (
                    "paid_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="fnf_paid",
                        to="employee.employee",
                    ),
                ),
            ],
            options={
                "verbose_name": "F&F Settlement",
                "verbose_name_plural": "F&F Settlements",
                "ordering": ["-id"],
            },
        ),
    ]
