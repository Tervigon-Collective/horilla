# Tervigon: work-from-home approval fields
# Columns already exist on production (old 0001_add_wfh_fields). This
# migration is idempotent so Horilla 2.0 can record the same schema.

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


WFH_SQL = """
ALTER TABLE attendance_attendance
    ADD COLUMN IF NOT EXISTS is_work_from_home boolean DEFAULT false NOT NULL;
ALTER TABLE attendance_attendance
    ADD COLUMN IF NOT EXISTS wfh_requested boolean DEFAULT false NOT NULL;
ALTER TABLE attendance_attendance
    ADD COLUMN IF NOT EXISTS wfh_request_ip inet NULL;
ALTER TABLE attendance_attendance
    ADD COLUMN IF NOT EXISTS wfh_approval_status varchar(20) NULL;
ALTER TABLE attendance_attendance
    ADD COLUMN IF NOT EXISTS wfh_approved_by_id integer NULL;
"""


class Migration(migrations.Migration):

    dependencies = [
        ("attendance", "0007_attendanceconflictresolution_attendancedailyhours_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("employee", "0001_initial"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
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
                    field=models.GenericIPAddressField(
                        blank=True, null=True, verbose_name="WFH Request IP"
                    ),
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
            ],
            database_operations=[
                migrations.RunSQL(sql=WFH_SQL, reverse_sql=migrations.RunSQL.noop),
            ],
        ),
    ]
