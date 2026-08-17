"""
Management command to create or update Tervigon Collective Private Limited company
and optionally delete all other companies (reassigning references first).
"""

from django.apps import apps
from django.core.management.base import BaseCommand
from django.db import models

from base.models import Company


COMPANY_NAME = "Tervigon Collective Private Limited"
REGISTRATION_NUMBER = "07AATCS5069H1ZQ"
ADDRESS = (
    "B-1/D4, Mathura Road, Mohan Cooperative Industrial Estate, "
    "New Delhi, South East Delhi, Delhi 110044"
)
COUNTRY = "India"
STATE = "Delhi"
CITY = "New Delhi"
ZIP_CODE = "110044"


def get_or_create_tervigon_company():
    """Ensure Tervigon Collective Private Limited exists and return it."""
    company = Company.objects.filter(company=COMPANY_NAME).first()
    if company:
        company.registration_number = REGISTRATION_NUMBER
        company.address = ADDRESS
        company.country = COUNTRY
        company.state = STATE
        company.city = CITY
        company.zip = ZIP_CODE
        company.hq = True
        company.save()
        return company
    Company.objects.filter(hq=True).update(hq=False)
    return Company.objects.create(
        company=COMPANY_NAME,
        registration_number=REGISTRATION_NUMBER,
        address=ADDRESS,
        country=COUNTRY,
        state=STATE,
        city=CITY,
        zip=ZIP_CODE,
        hq=True,
    )


def get_company_fk_models():
    """Return (model, field_name) for models that have FK or OneToOne to Company."""
    result = []
    for model in apps.get_models():
        for field in model._meta.get_fields():
            if not hasattr(field, "related_model") or field.related_model is not Company:
                continue
            if getattr(field, "many_to_many", False):
                continue
            # ForeignKey or OneToOneField to Company
            if hasattr(field, "column"):
                result.append((model, field.name))
    return result


def get_company_m2m_models():
    """Return (model, field_name) for models that have M2M to Company."""
    result = []
    for model in apps.get_models():
        for field in model._meta.get_fields():
            if getattr(field, "many_to_many", False) and hasattr(
                field, "related_model"
            ):
                if field.related_model is Company:
                    result.append((model, field.name))
    return result


class Command(BaseCommand):
    help = (
        "Create or update Tervigon Collective Private Limited. "
        "Use --delete-others to reassign all references to this company and delete other companies."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--delete-others",
            action="store_true",
            help="Reassign all company references to Tervigon and delete other companies.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Only show what would be done (with --delete-others).",
        )

    def handle(self, *args, **options):
        company = get_or_create_tervigon_company()
        if not options["delete_others"]:
            self.stdout.write(
                self.style.SUCCESS(f'Company "{company.company}" is set (HQ).')
            )
            return

        dry_run = options["dry_run"]
        other_ids = list(
            Company.objects.exclude(pk=company.pk).values_list("pk", flat=True)
        )
        if not other_ids:
            self.stdout.write(
                self.style.SUCCESS("No other companies to delete.")
            )
            return

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"DRY RUN: Would reassign references and delete {len(other_ids)} other company/companies."
                )
            )

        # 1. Reassign ForeignKey and OneToOneField
        for model, field_name in get_company_fk_models():
            try:
                qs = model.objects.filter(**{f"{field_name}__in": other_ids})
                count = qs.count()
                if count and not dry_run:
                    qs.update(**{field_name: company})
                if count:
                    self.stdout.write(
                        f"  {model._meta.label}.{field_name}: {count} updated"
                    )
            except Exception as e:
                self.stdout.write(
                    self.style.WARNING(
                        f"  Skip {model._meta.label}.{field_name}: {e}"
                    )
                )

        # 2. Reassign ManyToMany: set to only the keep company where others were present
        for model, field_name in get_company_m2m_models():
            try:
                qs = model.objects.filter(**{f"{field_name}__id__in": other_ids})
                count = qs.count()
                if count and not dry_run:
                    for obj in qs.iterator():
                        getattr(obj, field_name).set([company])
                if count:
                    self.stdout.write(
                        f"  {model._meta.label}.{field_name}: {count} instances updated"
                    )
            except Exception as e:
                self.stdout.write(
                    self.style.WARNING(
                        f"  Skip {model._meta.label}.{field_name}: {e}"
                    )
                )

        # 3. Delete other companies (CASCADE will remove dependent OneToOnes etc.)
        if not dry_run:
            deleted, _ = Company.objects.filter(pk__in=other_ids).delete()
            self.stdout.write(
                self.style.SUCCESS(
                    f'Deleted {deleted} other company/companies. Only "{company.company}" remains.'
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS("DRY RUN done. Run without --dry-run to apply.")
            )
