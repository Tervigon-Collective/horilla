# Generated for employee job_grade

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("employee", "0006_add_pan_uan_pf_esi_ifsc"),
    ]

    operations = [
        migrations.AddField(
            model_name="employeeworkinformation",
            name="job_grade",
            field=models.CharField(
                blank=True,
                help_text="Grade band used for leave accrual rules (e.g. L1, M2)",
                max_length=50,
                null=True,
                verbose_name="Job Grade",
            ),
        ),
        migrations.AddField(
            model_name="historicalemployeeworkinformation",
            name="job_grade",
            field=models.CharField(
                blank=True,
                help_text="Grade band used for leave accrual rules (e.g. L1, M2)",
                max_length=50,
                null=True,
                verbose_name="Job Grade",
            ),
        ),
    ]
