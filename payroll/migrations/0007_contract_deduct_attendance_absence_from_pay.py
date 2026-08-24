from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("payroll", "0006_payslip_unique_payslip_per_employee_period"),
    ]

    operations = [
        migrations.AddField(
            model_name="contract",
            name="deduct_attendance_absence_from_pay",
            field=models.BooleanField(
                default=True,
                help_text="Deduct salary for working days without validated attendance and without approved leave.",
                verbose_name="Deduct Attendance Absence (LOP)",
            ),
        ),
        migrations.AddField(
            model_name="historicalcontract",
            name="deduct_attendance_absence_from_pay",
            field=models.BooleanField(
                default=True,
                help_text="Deduct salary for working days without validated attendance and without approved leave.",
                verbose_name="Deduct Attendance Absence (LOP)",
            ),
        ),
    ]
