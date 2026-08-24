from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("leave", "0008_leaverequest_balance_reservation"),
    ]

    operations = [
        migrations.AddField(
            model_name="leavetype",
            name="monthly_accrual",
            field=models.BooleanField(
                default=False,
                help_text="Accrue leave monthly (total_days ÷ 12) with DOJ pro-rata instead of lump reset",
                verbose_name="Monthly Accrual",
            ),
        ),
        migrations.AddField(
            model_name="leavetype",
            name="sandwich_policy",
            field=models.BooleanField(
                default=False,
                help_text="Count weekends/holidays between adjacent leave days as leave",
                verbose_name="Sandwich Policy",
            ),
        ),
        migrations.AddField(
            model_name="availableleave",
            name="last_accrual_date",
            field=models.DateField(
                blank=True, null=True, verbose_name="Last Accrual Date"
            ),
        ),
    ]
