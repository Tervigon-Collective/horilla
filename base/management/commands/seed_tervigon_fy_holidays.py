"""
Seed Tervigon FY 2026–27 New Delhi holiday calendar and Eid religious leave.

Run: python manage.py seed_tervigon_fy_holidays
"""

from datetime import date

from django.core.management.base import BaseCommand
from django.db import transaction

from base.models import Company, Holidays
from employee.models import Employee
from horilla.horilla_middlewares import _thread_locals
from leave.models import AvailableLeave, LeaveType

COMPANY_NAME = "Tervigon Collective Private Limited"

# Company-wide holidays (not Eid — those are leave, not office-closed days).
# Recurring = same calendar date every year (national / fixed).
FY_HOLIDAYS = [
    ("Labour Day", date(2026, 5, 1), True),
    ("Independence Day", date(2026, 8, 15), True),
    ("Raksha Bandhan", date(2026, 8, 28), False),
    ("Gandhi Jayanti", date(2026, 10, 2), True),
    ("Dussehra (Vijayadashami)", date(2026, 10, 20), False),
    ("Govardhan Puja (Diwali)", date(2026, 11, 9), False),
    ("Bhai Dooj", date(2026, 11, 10), False),
    ("Christmas", date(2026, 12, 25), True),
    ("New Year's Day", date(2027, 1, 1), True),
    ("Republic Day", date(2026, 1, 26), True),
    ("Holi", date(2027, 3, 22), False),
]

# Dates from an earlier calendar that this FY list replaces.
SUPERSEDED = [
    (date(2026, 10, 21), "Dussehra"),
    (date(2026, 11, 8), "Diwali"),
]


def _get_mock_request():
    mock_user = type(
        "MockUser",
        (),
        {"is_authenticated": False, "is_anonymous": True},
    )()
    return type(
        "MockRequest",
        (),
        {"session": {"selected_company": "all"}, "user": mock_user},
    )()


class Command(BaseCommand):
    help = "Seed Tervigon FY 2026–27 holidays (New Delhi) and 2-day Eid leave type"

    def handle(self, *args, **options):
        _thread_locals.request = _get_mock_request()
        try:
            company = Company.objects.filter(company=COMPANY_NAME).first()
            if not company:
                self.stderr.write(self.style.ERROR(f"{COMPANY_NAME} not found"))
                return
            with transaction.atomic():
                self._seed_holidays(company)
                self._seed_eid_leave(company)
        finally:
            try:
                delattr(_thread_locals, "request")
            except AttributeError:
                pass

    def _seed_holidays(self, company):
        for d, name_part in SUPERSEDED:
            qs = Holidays.objects.filter(
                company_id=company, start_date=d, name__icontains=name_part
            )
            n, _ = qs.delete()
            if n:
                self.stdout.write(f"Removed superseded {name_part} on {d}")

        wanted_dates = {d for _n, d, _r in FY_HOLIDAYS}
        for name, start, recurring in FY_HOLIDAYS:
            existing = Holidays.objects.filter(
                company_id=company, start_date=start
            ).first()
            if not existing:
                existing = Holidays.objects.filter(
                    company_id=company, name=name, start_date__year=start.year
                ).first()
            if existing:
                existing.name = name
                existing.start_date = start
                existing.end_date = start
                existing.recurring = recurring
                existing.is_specific = False
                existing.save()
                self.stdout.write(f"Updated holiday: {name} {start}")
            else:
                Holidays.objects.create(
                    name=name,
                    start_date=start,
                    end_date=start,
                    recurring=recurring,
                    is_specific=False,
                    company_id=company,
                )
                self.stdout.write(self.style.SUCCESS(f"Added holiday: {name} {start}"))

        extra = Holidays.objects.filter(company_id=company).exclude(
            start_date__in=wanted_dates
        )
        for h in extra:
            self.stdout.write(
                self.style.WARNING(f"Left other holiday in place: {h.name} {h.start_date}")
            )

    def _seed_eid_leave(self, company):
        lt, created = LeaveType.objects.get_or_create(
            name="Eid Holiday",
            company_id=company,
            defaults={
                "payment": "paid",
                "payment_type": "paid",
                "count": 1,
                "period_in": "day",
                "limit_leave": True,
                "total_days": 2,
                "reset": True,
                "reset_based": "yearly",
                "reset_month": "4",
                "reset_day": "1",
                "carryforward_type": "no carryforward",
                "require_approval": "yes",
                "require_attachment": "no",
                "exclude_company_leave": "yes",
                "exclude_holiday": "yes",
                "is_encashable": False,
            },
        )
        if not created:
            lt.payment = "paid"
            lt.payment_type = "paid"
            lt.total_days = 2
            lt.reset = True
            lt.reset_based = "yearly"
            lt.reset_month = "4"
            lt.reset_day = "1"
            lt.carryforward_type = "no carryforward"
            lt.require_approval = "yes"
            lt.save()
            self.stdout.write("Updated leave type: Eid Holiday (2 days, FY reset)")
        else:
            self.stdout.write(self.style.SUCCESS("Created leave type: Eid Holiday (2 days)"))

        employees = Employee.objects.filter(
            is_active=True, employee_work_info__company_id=company
        )
        assigned = 0
        for emp in employees:
            _, was_new = AvailableLeave.objects.get_or_create(
                employee_id=emp,
                leave_type_id=lt,
                defaults={"available_days": 2, "carryforward_days": 0},
            )
            if was_new:
                assigned += 1
            else:
                av = AvailableLeave.objects.get(employee_id=emp, leave_type_id=lt)
                if av.available_days < 2 and av.total_leave_days < 2:
                    av.available_days = 2
                    av.save()
        self.stdout.write(
            f"Eid Holiday assigned to {assigned} new employee(s); "
            f"{employees.count()} active in company"
        )
