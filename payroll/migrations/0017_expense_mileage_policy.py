# Mileage + expense policy limits

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("payroll", "0016_salary_hold_arrears_paid"),
    ]

    operations = [
        migrations.AddField(
            model_name="reimbursement",
            name="mileage_km",
            field=models.FloatField(
                blank=True, default=0.0, null=True, verbose_name="Mileage (km)"
            ),
        ),
        migrations.AddField(
            model_name="reimbursement",
            name="mileage_rate",
            field=models.FloatField(
                blank=True,
                default=0.0,
                help_text="If set with mileage km, amount can be computed as km × rate",
                null=True,
                verbose_name="Mileage rate (₹/km)",
            ),
        ),
        migrations.AddField(
            model_name="encashmentgeneralsettings",
            name="max_claim_amount",
            field=models.FloatField(
                default=0,
                help_text="0 = no limit. Applies to reimbursement and travel claims.",
                verbose_name="Max reimbursement claim (₹)",
            ),
        ),
        migrations.AddField(
            model_name="encashmentgeneralsettings",
            name="default_mileage_rate",
            field=models.FloatField(
                default=0, verbose_name="Default mileage rate (₹/km)"
            ),
        ),
    ]
