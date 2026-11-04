from django.utils import timezone
from django.utils.translation import gettext_noop

from horilla.db import scheduled_job
from horilla.scheduling import register_job
from horilla.signals import post_scheduler, pre_scheduler


@scheduled_job
def leave_reset():
    pre_scheduler.send(sender=leave_reset)
    from leave.methods import run_missed_resets
    from leave.models import LeaveType

    today = timezone.localtime()
    today_date = timezone.localdate()
    leave_types = LeaveType.objects.filter(reset=True)
    for leave_type in leave_types:
        run_missed_resets(
            leave_type,
            reset_reason=gettext_noop("Leave reset"),
            expiry_reason=gettext_noop("Carryforward expired"),
            today_date=today_date,
        )
    post_scheduler.send(
        sender=leave_reset,
        **{
            "today": today,
            "today_date": today_date,
            "leave_types": leave_types,
        }
    )

    from leave.services import accrue_monthly_balances, expire_all_carryforward_balances

    # Bulk-expire any CF balances past their expiry date (catches anything the
    # per-record loop above may have missed due to missing expired_date setup).
    expire_all_carryforward_balances(today_date)
    accrue_monthly_balances(today_date)


register_job(leave_reset, "interval", hours=4)
