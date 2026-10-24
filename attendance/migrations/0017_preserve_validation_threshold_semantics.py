"""
Keep the Seleric auto-validation rule when moving to upstream 2.2.0.

The fork validates an attendance when worked time is AT LEAST ``validation_at_work``
(a minimum). Upstream 2.2.0 reads ``validation_at_work`` as a maximum ("auto approve
till") and adds ``minimum_at_work_to_validate``. Without this, an existing row such as
validation_at_work="23:59" would start auto-validating every attendance. Each existing
condition still on the default minimum gets its old value as the minimum and a very
large maximum, which reproduces the previous behaviour exactly.
"""

from django.db import migrations

NO_UPPER_LIMIT = "999:59"


def move_threshold_to_minimum(apps, schema_editor):
    Condition = apps.get_model("attendance", "AttendanceValidationCondition")
    for condition in Condition.objects.all():
        if (condition.minimum_at_work_to_validate or "00:00") != "00:00":
            continue
        condition.minimum_at_work_to_validate = condition.validation_at_work
        condition.validation_at_work = NO_UPPER_LIMIT
        condition.save(update_fields=["minimum_at_work_to_validate", "validation_at_work"])


class Migration(migrations.Migration):

    dependencies = [
        ("attendance", "0016_merge_20261024_1132"),
    ]

    operations = [
        migrations.RunPython(move_threshold_to_minimum, migrations.RunPython.noop),
    ]
