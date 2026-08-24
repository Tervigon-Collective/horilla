from django.db import migrations


def enable_tervigon_statutory(apps, schema_editor):
    Company = apps.get_model("base", "Company")
    IndiaStatutorySettings = apps.get_model("payroll", "IndiaStatutorySettings")
    company = Company.objects.filter(hq=True).first() or Company.objects.first()
    if not company:
        return
    IndiaStatutorySettings.objects.update_or_create(
        company_id=company,
        defaults={
            "is_enabled": True,
            "enable_pf": True,
            "enable_esi": True,
            "enable_pt": True,
            "enable_tds": True,
            "pt_state": "DL",
            "default_tds_regime": "new",
            "pf_wage_ceiling": 15000.0,
            "pf_employee_rate": 12.0,
            "pf_employer_rate": 12.0,
            "esi_gross_ceiling": 21000.0,
            "esi_employee_rate": 0.75,
            "esi_employer_rate": 3.25,
            "standard_deduction_annual": 75000.0,
            "standard_deduction_old_regime": 50000.0,
            "is_active": True,
        },
    )


class Migration(migrations.Migration):

    dependencies = [
        ("payroll", "0009_india_statutory_horilla_fields"),
    ]

    operations = [
        migrations.RunPython(enable_tervigon_statutory, migrations.RunPython.noop),
    ]
