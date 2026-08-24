from django.db import migrations


def set_delhi_pt_state(apps, schema_editor):
    Company = apps.get_model("base", "Company")
    IndiaStatutorySettings = apps.get_model("payroll", "IndiaStatutorySettings")
    company = Company.objects.filter(hq=True).first() or Company.objects.first()
    if not company:
        return
    IndiaStatutorySettings.objects.filter(company_id=company).update(pt_state="DL")


class Migration(migrations.Migration):

    dependencies = [
        ("payroll", "0010_enable_india_statutory_tervigon"),
    ]

    operations = [
        migrations.RunPython(set_delhi_pt_state, migrations.RunPython.noop),
    ]
