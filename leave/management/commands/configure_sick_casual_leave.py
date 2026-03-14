"""
Configure Sick Leave and Casual Leave: 1/day per month, monthly reset, carry forward.
Run: python manage.py configure_sick_casual_leave
"""

from django.core.management.base import BaseCommand
from django.db.models import Q

from horilla.horilla_middlewares import _thread_locals
from leave.models import LeaveType


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
    help = (
        "Configures Sick Leave and Casual Leave: reset=monthly, "
        "carry forward, total_days=1"
    )

    def handle(self, *args, **options):
        names = ["Sick Leave", "Casual Leave"]
        updates = {
            "total_days": 1,
            "reset": True,
            "reset_based": "monthly",
            "reset_day": "1",
            "carryforward_type": "carryforward",
            "carryforward_max": 12,
        }
        _thread_locals.request = _get_mock_request()
        try:
            for name in names:
                lt = LeaveType._default_manager.filter(name__iexact=name).first()
                if not lt:
                    self.stdout.write(self.style.WARNING(f"{name} not found, skipped"))
                    continue
                for k, v in updates.items():
                    setattr(lt, k, v)
                lt.save()
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Configured {lt.name} (id={lt.id}): "
                        "1 day/month, monthly reset, carry forward up to 12 days"
                    )
                )
        finally:
            try:
                delattr(_thread_locals, "request")
            except AttributeError:
                pass
