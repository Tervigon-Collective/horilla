from django.db import migrations, models


class Migration(migrations.Migration):
    """
    0009 added last_accrual_date on AvailableLeave but the simple_history
    table was not updated in some environments.
    """

    dependencies = [
        ("leave", "0010_leave_accrual_rule"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[],
            database_operations=[
                migrations.RunSQL(
                    sql=(
                        "ALTER TABLE leave_historicalavailableleave "
                        "ADD COLUMN IF NOT EXISTS last_accrual_date date NULL;"
                    ),
                    reverse_sql=(
                        "ALTER TABLE leave_historicalavailableleave "
                        "DROP COLUMN IF EXISTS last_accrual_date;"
                    ),
                ),
            ],
        ),
    ]
