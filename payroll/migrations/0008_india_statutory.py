from django.db import migrations, models
import django.core.validators
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("base", "0001_initial"),
        ("employee", "0005_alter_employee_phone_and_more"),
        ("payroll", "0007_contract_deduct_attendance_absence_from_pay"),
    ]

    operations = [
        migrations.CreateModel(
            name="IndiaStatutorySettings",
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
                ("is_active", models.BooleanField(default=True)),
                (
                    "is_enabled",
                    models.BooleanField(
                        default=False, verbose_name="Enable Indian Statutory Payroll"
                    ),
                ),
                (
                    "enable_pf",
                    models.BooleanField(default=True, verbose_name="Provident Fund (EPF)"),
                ),
                (
                    "enable_esi",
                    models.BooleanField(default=True, verbose_name="ESI"),
                ),
                (
                    "enable_pt",
                    models.BooleanField(default=True, verbose_name="Professional Tax"),
                ),
                (
                    "enable_tds",
                    models.BooleanField(default=True, verbose_name="TDS (Income Tax)"),
                ),
                (
                    "pf_wage_ceiling",
                    models.FloatField(default=15000.0, verbose_name="PF wage ceiling (₹)"),
                ),
                (
                    "pf_employee_rate",
                    models.FloatField(
                        default=12.0,
                        validators=[
                            django.core.validators.MinValueValidator(0),
                            django.core.validators.MaxValueValidator(100),
                        ],
                        verbose_name="PF employee rate (%)",
                    ),
                ),
                (
                    "pf_employer_rate",
                    models.FloatField(
                        default=12.0,
                        validators=[
                            django.core.validators.MinValueValidator(0),
                            django.core.validators.MaxValueValidator(100),
                        ],
                        verbose_name="PF employer rate (%)",
                    ),
                ),
                (
                    "esi_gross_ceiling",
                    models.FloatField(default=21000.0, verbose_name="ESI gross ceiling (₹)"),
                ),
                (
                    "esi_employee_rate",
                    models.FloatField(
                        default=0.75,
                        validators=[
                            django.core.validators.MinValueValidator(0),
                            django.core.validators.MaxValueValidator(100),
                        ],
                        verbose_name="ESI employee rate (%)",
                    ),
                ),
                (
                    "esi_employer_rate",
                    models.FloatField(
                        default=3.25,
                        validators=[
                            django.core.validators.MinValueValidator(0),
                            django.core.validators.MaxValueValidator(100),
                        ],
                        verbose_name="ESI employer rate (%)",
                    ),
                ),
                (
                    "pt_state",
                    models.CharField(
                        choices=[
                            ("AN", "Andaman and Nicobar Islands"),
                            ("AP", "Andhra Pradesh"),
                            ("AR", "Arunachal Pradesh"),
                            ("AS", "Assam"),
                            ("BR", "Bihar"),
                            ("CH", "Chandigarh"),
                            ("CT", "Chhattisgarh"),
                            ("DL", "Delhi"),
                            ("GA", "Goa"),
                            ("GJ", "Gujarat"),
                            ("HR", "Haryana"),
                            ("HP", "Himachal Pradesh"),
                            ("JH", "Jharkhand"),
                            ("KA", "Karnataka"),
                            ("KL", "Kerala"),
                            ("LA", "Ladakh"),
                            ("LD", "Lakshadweep"),
                            ("MP", "Madhya Pradesh"),
                            ("MH", "Maharashtra"),
                            ("MN", "Manipur"),
                            ("ML", "Meghalaya"),
                            ("MZ", "Mizoram"),
                            ("NL", "Nagaland"),
                            ("OR", "Odisha"),
                            ("PY", "Puducherry"),
                            ("PB", "Punjab"),
                            ("RJ", "Rajasthan"),
                            ("SK", "Sikkim"),
                            ("TN", "Tamil Nadu"),
                            ("TS", "Telangana"),
                            ("TR", "Tripura"),
                            ("UP", "Uttar Pradesh"),
                            ("UK", "Uttarakhand"),
                            ("WB", "West Bengal"),
                        ],
                        default="MH",
                        max_length=5,
                        verbose_name="Professional Tax state",
                    ),
                ),
                (
                    "default_tds_regime",
                    models.CharField(
                        choices=[
                            ("new", "New Regime (default)"),
                            ("old", "Old Regime"),
                        ],
                        default="new",
                        max_length=10,
                        verbose_name="Default TDS regime",
                    ),
                ),
                (
                    "standard_deduction_annual",
                    models.FloatField(
                        default=75000.0,
                        verbose_name="Standard deduction (annual, ₹) — new regime",
                    ),
                ),
                (
                    "standard_deduction_old_regime",
                    models.FloatField(
                        default=50000.0,
                        verbose_name="Standard deduction (annual, ₹) — old regime",
                    ),
                ),
                (
                    "tan_number",
                    models.CharField(
                        blank=True, max_length=20, null=True, verbose_name="Employer TAN"
                    ),
                ),
                (
                    "pf_establishment_code",
                    models.CharField(
                        blank=True,
                        max_length=30,
                        null=True,
                        verbose_name="PF establishment code",
                    ),
                ),
                (
                    "esi_establishment_code",
                    models.CharField(
                        blank=True,
                        max_length=30,
                        null=True,
                        verbose_name="ESI establishment code",
                    ),
                ),
                (
                    "company_id",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="india_statutory_settings",
                        to="base.company",
                        verbose_name="Company",
                    ),
                ),
            ],
            options={
                "verbose_name": "India Statutory Settings",
                "verbose_name_plural": "India Statutory Settings",
            },
        ),
        migrations.CreateModel(
            name="EmployeeStatutoryProfile",
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
                ("is_active", models.BooleanField(default=True)),
                (
                    "pf_applicable",
                    models.BooleanField(default=True, verbose_name="PF applicable"),
                ),
                (
                    "esi_applicable",
                    models.BooleanField(default=True, verbose_name="ESI applicable"),
                ),
                (
                    "pt_applicable",
                    models.BooleanField(default=True, verbose_name="PT applicable"),
                ),
                (
                    "tds_applicable",
                    models.BooleanField(default=True, verbose_name="TDS applicable"),
                ),
                (
                    "tds_regime",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("new", "New Regime (default)"),
                            ("old", "Old Regime"),
                        ],
                        max_length=10,
                        null=True,
                        verbose_name="TDS regime override",
                    ),
                ),
                (
                    "section_80c_annual",
                    models.FloatField(
                        default=0.0,
                        verbose_name="Section 80C (annual, ₹) — old regime",
                    ),
                ),
                (
                    "section_80d_annual",
                    models.FloatField(
                        default=0.0,
                        verbose_name="Section 80D (annual, ₹) — old regime",
                    ),
                ),
                (
                    "other_chapter_vi_a",
                    models.FloatField(
                        default=0.0, verbose_name="Other Chapter VI-A (annual, ₹)"
                    ),
                ),
                (
                    "vpf_rate",
                    models.FloatField(
                        default=0.0,
                        validators=[
                            django.core.validators.MinValueValidator(0),
                            django.core.validators.MaxValueValidator(100),
                        ],
                        verbose_name="VPF extra (%) on PF wages",
                    ),
                ),
                (
                    "employee_id",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="statutory_profile",
                        to="employee.employee",
                        verbose_name="Employee",
                    ),
                ),
            ],
            options={
                "verbose_name": "Employee Statutory Profile",
                "verbose_name_plural": "Employee Statutory Profiles",
            },
        ),
        migrations.CreateModel(
            name="Form16Record",
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
                ("is_active", models.BooleanField(default=True)),
                (
                    "financial_year_start",
                    models.PositiveIntegerField(verbose_name="FY start year"),
                ),
                (
                    "financial_year_end",
                    models.PositiveIntegerField(verbose_name="FY end year"),
                ),
                ("gross_salary", models.FloatField(default=0)),
                ("pf_employee_total", models.FloatField(default=0)),
                ("pf_employer_total", models.FloatField(default=0)),
                ("esi_employee_total", models.FloatField(default=0)),
                ("pt_total", models.FloatField(default=0)),
                ("tds_total", models.FloatField(default=0)),
                ("net_salary", models.FloatField(default=0)),
                ("regime", models.CharField(default="new", max_length=10)),
                ("summary_json", models.JSONField(blank=True, default=dict)),
                ("generated_at", models.DateTimeField(auto_now=True)),
                (
                    "employee_id",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="form16_records",
                        to="employee.employee",
                        verbose_name="Employee",
                    ),
                ),
            ],
            options={
                "verbose_name": "Form 16 Record",
                "verbose_name_plural": "Form 16 Records",
                "unique_together": {("employee_id", "financial_year_start")},
            },
        ),
    ]
