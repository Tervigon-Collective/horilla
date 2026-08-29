# Generated manually — LMS certificate id on enrollment

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("lms", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="courseenrollment",
            name="certificate_id",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Issued when the course is completed.",
                max_length=32,
                verbose_name="Certificate ID",
            ),
        ),
    ]
