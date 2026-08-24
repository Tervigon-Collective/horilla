from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("payroll", "0012_reimbursement_travel"),
    ]

    operations = [
        migrations.AddField(
            model_name="indiastatutorysettings",
            name="bsr_code",
            field=models.CharField(
                blank=True,
                help_text="7-digit BSR code from the TDS challan (ITNS 281).",
                max_length=7,
                null=True,
                verbose_name="Bank BSR code",
            ),
        ),
    ]
