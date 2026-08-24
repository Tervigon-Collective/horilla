from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("payroll", "0013_india_statutory_bsr_code"),
    ]

    operations = [
        migrations.AddField(
            model_name="indiastatutorysettings",
            name="enable_lwf",
            field=models.BooleanField(
                default=False, verbose_name="Labour Welfare Fund (LWF)"
            ),
        ),
        migrations.AddField(
            model_name="indiastatutorysettings",
            name="enable_bonus",
            field=models.BooleanField(
                default=False,
                verbose_name="Payment of Bonus Act (monthly provision)",
            ),
        ),
        migrations.AddField(
            model_name="indiastatutorysettings",
            name="enable_gratuity",
            field=models.BooleanField(
                default=True,
                verbose_name="Payment of Gratuity Act (F&F / register)",
            ),
        ),
        migrations.AddField(
            model_name="employeestatutoryprofile",
            name="lwf_applicable",
            field=models.BooleanField(default=True, verbose_name="LWF applicable"),
        ),
        migrations.AddField(
            model_name="employeestatutoryprofile",
            name="bonus_applicable",
            field=models.BooleanField(
                default=True, verbose_name="Bonus Act applicable"
            ),
        ),
        migrations.AddField(
            model_name="employeestatutoryprofile",
            name="gratuity_applicable",
            field=models.BooleanField(
                default=True, verbose_name="Gratuity applicable"
            ),
        ),
    ]
