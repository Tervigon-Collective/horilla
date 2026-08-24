from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("leave", "0007_alter_historicalleaverequest_reject_reason_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="leaverequest",
            name="reserved_available_days",
            field=models.FloatField(default=0),
        ),
        migrations.AddField(
            model_name="leaverequest",
            name="reserved_carryforward_days",
            field=models.FloatField(default=0),
        ),
        migrations.AddField(
            model_name="historicalleaverequest",
            name="reserved_available_days",
            field=models.FloatField(default=0),
        ),
        migrations.AddField(
            model_name="historicalleaverequest",
            name="reserved_carryforward_days",
            field=models.FloatField(default=0),
        ),
    ]
