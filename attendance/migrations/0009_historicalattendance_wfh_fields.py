from django.db import migrations, models
import django.db.models.deletion


HIST_SQL = """
ALTER TABLE attendance_historicalattendance
    ADD COLUMN IF NOT EXISTS is_work_from_home boolean DEFAULT false NOT NULL;
ALTER TABLE attendance_historicalattendance
    ADD COLUMN IF NOT EXISTS wfh_requested boolean DEFAULT false NOT NULL;
ALTER TABLE attendance_historicalattendance
    ADD COLUMN IF NOT EXISTS wfh_request_ip inet NULL;
ALTER TABLE attendance_historicalattendance
    ADD COLUMN IF NOT EXISTS wfh_approval_status varchar(20) NULL;
ALTER TABLE attendance_historicalattendance
    ADD COLUMN IF NOT EXISTS wfh_approved_by_id integer NULL;
"""


class Migration(migrations.Migration):

    dependencies = [
        ("attendance", "0008_add_wfh_fields"),
        ("employee", "0001_initial"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name="historicalattendance",
                    name="is_work_from_home",
                    field=models.BooleanField(default=False, verbose_name="Work From Home"),
                ),
                migrations.AddField(
                    model_name="historicalattendance",
                    name="wfh_requested",
                    field=models.BooleanField(default=False, verbose_name="WFH Requested"),
                ),
                migrations.AddField(
                    model_name="historicalattendance",
                    name="wfh_request_ip",
                    field=models.GenericIPAddressField(
                        blank=True, null=True, verbose_name="WFH Request IP"
                    ),
                ),
                migrations.AddField(
                    model_name="historicalattendance",
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
                    model_name="historicalattendance",
                    name="wfh_approved_by",
                    field=models.ForeignKey(
                        blank=True,
                        db_constraint=False,
                        null=True,
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name="+",
                        to="employee.employee",
                        verbose_name="WFH Approved By",
                    ),
                ),
            ],
            database_operations=[
                migrations.RunSQL(sql=HIST_SQL, reverse_sql=migrations.RunSQL.noop),
            ],
        ),
    ]
