# Tervigon: work-from-home approval fields

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("attendance", "0007_attendanceconflictresolution_attendancedailyhours_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("employee", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="attendance",
            name="is_work_from_home",
            field=models.BooleanField(default=False, verbose_name="Work From Home"),
        ),
        migrations.AddField(
            model_name="attendance",
            name="wfh_requested",
            field=models.BooleanField(default=False, verbose_name="WFH Requested"),
        ),
        migrations.AddField(
            model_name="attendance",
            name="wfh_request_ip",
            field=models.GenericIPAddressField(blank=True, null=True, verbose_name="WFH Request IP"),
        ),
        migrations.AddField(
            model_name="attendance",
            name="wfh_approval_status",
            field=models.CharField(
                blank=True,
                choices=[
                    ("pending", "Pending"),
                    ("approved", "Approved"),
                    ("rejected", "Rejected"),
                ],
                max_length=20,
                null=True,
                verbose_name="WFH Approval Status",
            ),
        ),
        migrations.AddField(
            model_name="attendance",
            name="wfh_approved_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="wfh_approvals",
                to="employee.employee",
                verbose_name="WFH Approved By",
            ),
        ),
    ]
