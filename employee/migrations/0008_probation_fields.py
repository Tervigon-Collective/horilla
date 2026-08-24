# Probation fields on work information

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("employee", "0007_job_grade"),
    ]

    operations = [
        migrations.AddField(
            model_name="employeeworkinformation",
            name="probation_end",
            field=models.DateField(
                blank=True, null=True, verbose_name="Probation end date"
            ),
        ),
        migrations.AddField(
            model_name="employeeworkinformation",
            name="employment_status",
            field=models.CharField(
                blank=True,
                choices=[
                    ("probation", "On probation"),
                    ("confirmed", "Confirmed"),
                    ("notice", "Notice period"),
                ],
                default="confirmed",
                max_length=20,
                verbose_name="Employment status",
            ),
        ),
        migrations.AddField(
            model_name="historicalemployeeworkinformation",
            name="probation_end",
            field=models.DateField(
                blank=True, null=True, verbose_name="Probation end date"
            ),
        ),
        migrations.AddField(
            model_name="historicalemployeeworkinformation",
            name="employment_status",
            field=models.CharField(
                blank=True,
                choices=[
                    ("probation", "On probation"),
                    ("confirmed", "Confirmed"),
                    ("notice", "Notice period"),
                ],
                default="confirmed",
                max_length=20,
                verbose_name="Employment status",
            ),
        ),
    ]
