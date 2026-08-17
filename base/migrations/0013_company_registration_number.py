from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("base", "0012_remove_companyleaves_company_id_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="company",
            name="registration_number",
            field=models.CharField(
                blank=True, max_length=50, null=True, verbose_name="Registration Number"
            ),
        ),
    ]
