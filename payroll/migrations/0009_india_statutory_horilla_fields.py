import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    atomic = False

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("payroll", "0008_india_statutory"),
    ]

    operations = [
        migrations.AddField(
            model_name="indiastatutorysettings",
            name="created_at",
            field=models.DateTimeField(
                auto_now_add=True, blank=True, null=True, verbose_name="Created At"
            ),
        ),
        migrations.AddField(
            model_name="indiastatutorysettings",
            name="created_by",
            field=models.ForeignKey(
                blank=True,
                editable=False,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to=settings.AUTH_USER_MODEL,
                verbose_name="Created By",
            ),
        ),
        migrations.AddField(
            model_name="indiastatutorysettings",
            name="modified_by",
            field=models.ForeignKey(
                blank=True,
                editable=False,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="indiastatutorysettings_modified_by",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Modified By",
            ),
        ),
        migrations.AddField(
            model_name="employeestatutoryprofile",
            name="created_at",
            field=models.DateTimeField(
                auto_now_add=True, blank=True, null=True, verbose_name="Created At"
            ),
        ),
        migrations.AddField(
            model_name="employeestatutoryprofile",
            name="created_by",
            field=models.ForeignKey(
                blank=True,
                editable=False,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to=settings.AUTH_USER_MODEL,
                verbose_name="Created By",
            ),
        ),
        migrations.AddField(
            model_name="employeestatutoryprofile",
            name="modified_by",
            field=models.ForeignKey(
                blank=True,
                editable=False,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="employeestatutoryprofile_modified_by",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Modified By",
            ),
        ),
        migrations.AddField(
            model_name="form16record",
            name="created_at",
            field=models.DateTimeField(
                auto_now_add=True, blank=True, null=True, verbose_name="Created At"
            ),
        ),
        migrations.AddField(
            model_name="form16record",
            name="created_by",
            field=models.ForeignKey(
                blank=True,
                editable=False,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to=settings.AUTH_USER_MODEL,
                verbose_name="Created By",
            ),
        ),
        migrations.AddField(
            model_name="form16record",
            name="modified_by",
            field=models.ForeignKey(
                blank=True,
                editable=False,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="form16record_modified_by",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Modified By",
            ),
        ),
    ]
