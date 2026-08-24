from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("attendance", "0011_add_missing_punch_out"),
    ]

    operations = [
        migrations.AddField(
            model_name="attendance",
            name="missing_punch_in",
            field=models.BooleanField(
                default=False,
                help_text="Set when employee did not punch in by end of day.",
                verbose_name="Missing Punch In",
            ),
        ),
        migrations.AddField(
            model_name="historicalattendance",
            name="missing_punch_in",
            field=models.BooleanField(
                default=False,
                help_text="Set when employee did not punch in by end of day.",
                verbose_name="Missing Punch In",
            ),
        ),
    ]
