from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("base", "0012_remove_companyleaves_company_id_and_more"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name="company",
                    name="registration_number",
                    field=models.CharField(
                        blank=True,
                        max_length=50,
                        null=True,
                        verbose_name="Registration Number",
                    ),
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql="ALTER TABLE base_company ADD COLUMN IF NOT EXISTS registration_number varchar(50) NULL;",
                    reverse_sql=migrations.RunSQL.noop,
                ),
            ],
        ),
    ]
