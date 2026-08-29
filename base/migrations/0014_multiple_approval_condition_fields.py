# Generated manually for multi-level reimbursement / OT approval fields

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("base", "0013_company_registration_number"),
    ]

    operations = [
        migrations.AlterField(
            model_name="multipleapprovalcondition",
            name="condition_field",
            field=models.CharField(
                choices=[
                    ("", "---------"),
                    ("requested_days", "Leave Requested Days"),
                    ("reimbursement_amount", "Reimbursement Amount"),
                    ("overtime_hours", "Overtime Hours"),
                ],
                max_length=255,
                verbose_name="Condition Field",
            ),
        ),
    ]
