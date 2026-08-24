from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("payroll", "0011_tervigon_pt_state_delhi"),
    ]

    operations = [
        migrations.AddField(
            model_name="reimbursement",
            name="travel_from",
            field=models.CharField(
                blank=True, max_length=100, null=True, verbose_name="Travel From"
            ),
        ),
        migrations.AddField(
            model_name="reimbursement",
            name="travel_to",
            field=models.CharField(
                blank=True, max_length=100, null=True, verbose_name="Travel To"
            ),
        ),
        migrations.AddField(
            model_name="reimbursement",
            name="travel_date",
            field=models.DateField(blank=True, null=True, verbose_name="Travel Date"),
        ),
    ]
