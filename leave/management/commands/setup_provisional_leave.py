"""
Create Provisional Leave type for new Full time/Intern employees (1/month, carry forward).
Run: python manage.py setup_provisional_leave
"""

from django.core.management.base import BaseCommand
from django.db.models import Q

from horilla.horilla_middlewares import _thread_locals
from leave.models import LeaveType


class Command(BaseCommand):
    help = "Creates 'Provisional Leave' type (1/month, carry forward) for new employees"

    def handle(self, *args, **options):
        existing = LeaveType._default_manager.filter(
            Q(name__iexact="Provisional Leave") | Q(name__iexact="New Employee Leave")
        ).first()
        if existing:
            self.stdout.write(
                self.style.WARNING(
                    f"Provisional Leave already exists: {existing.name} (id={existing.id})"
                )
            )
            return
        mock_user = type(
            "MockUser",
            (),
            {"is_authenticated": False, "is_anonymous": True},
        )()
        mock_request = type(
            "MockRequest",
            (),
            {"session": {"selected_company": "all"}, "user": mock_user},
        )()
        _thread_locals.request = mock_request
        try:
            lt = LeaveType._default_manager.create(
                name="Provisional Leave",
                color="#17a2b8",
                payment="paid",
                total_days=1,
                reset=True,
                reset_based="monthly",
                reset_day="1",
                carryforward_type="carryforward",
                carryforward_max=6,
                require_approval="yes",
            )
        finally:
            try:
                delattr(_thread_locals, "request")
            except AttributeError:
                pass
        self.stdout.write(
            self.style.SUCCESS(f"Created leave type: {lt.name} (id={lt.id})")
        )
        self.stdout.write(
            "  - 1 day/month, resets monthly, carry forward up to 6 days"
        )
