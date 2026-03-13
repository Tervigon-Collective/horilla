"""
Management command to create or update Tervigon Collective Private Limited company.
"""

from django.core.management.base import BaseCommand

from base.models import Company


class Command(BaseCommand):
    help = "Create or update Tervigon Collective Private Limited company with registration and address."

    def handle(self, *args, **options):
        name = "Tervigon Collective Private Limited"
        registration_number = "07AATCS5069H1ZQ"
        address = (
            "B-1/D4, Mathura Road, Mohan Cooperative Industrial Estate, "
            "New Delhi, South East Delhi, Delhi 110044"
        )
        country = "India"
        state = "Delhi"
        city = "New Delhi"
        zip_code = "110044"

        company = Company.objects.filter(company=name).first()
        if company:
            company.registration_number = registration_number
            company.address = address
            company.country = country
            company.state = state
            company.city = city
            company.zip = zip_code
            company.hq = True
            company.save()
            created = False
        else:
            # Ensure only one HQ when creating
            Company.objects.filter(hq=True).update(hq=False)
            company = Company.objects.create(
                company=name,
                registration_number=registration_number,
                address=address,
                country=country,
                state=state,
                city=city,
                zip=zip_code,
                hq=True,
            )
            created = True
        if created:
            self.stdout.write(
                self.style.SUCCESS(f'Company "{company.company}" created (HQ).')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f'Company "{company.company}" updated (HQ).')
            )
