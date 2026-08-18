from django.db import migrations, models


SQL = """
ALTER TABLE attendance_attendance
    ADD COLUMN IF NOT EXISTS punch_location jsonb NULL;
ALTER TABLE attendance_attendanceactivity
    ADD COLUMN IF NOT EXISTS punch_location jsonb NULL;
ALTER TABLE attendance_historicalattendance
    ADD COLUMN IF NOT EXISTS punch_location jsonb NULL;
ALTER TABLE attendance_historicalattendanceactivity
    ADD COLUMN IF NOT EXISTS punch_location jsonb NULL;
"""


class Migration(migrations.Migration):

    dependencies = [
        ("attendance", "0009_historicalattendance_wfh_fields"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name="attendance",
                    name="punch_location",
                    field=models.JSONField(
                        blank=True,
                        default=dict,
                        null=True,
                        verbose_name="Punch location",
                    ),
                ),
                migrations.AddField(
                    model_name="attendanceactivity",
                    name="punch_location",
                    field=models.JSONField(
                        blank=True,
                        default=dict,
                        null=True,
                        verbose_name="Punch location",
                    ),
                ),
            ],
            database_operations=[
                migrations.RunSQL(sql=SQL, reverse_sql=migrations.RunSQL.noop),
            ],
        ),
    ]
