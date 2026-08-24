import sys
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler

from horilla.signals import post_scheduler, pre_scheduler


def leave_reset():
    pre_scheduler.send(sender=leave_reset)
    from leave.models import LeaveType

    today = datetime.now()
    today_date = today.date()
    leave_types = LeaveType.objects.filter(reset=True)
    # Looping through filtered leave types with reset is true
    for leave_type in leave_types:
        # Looping through all available leaves
        available_leaves = leave_type.employee_available_leave.all()

        for available_leave in available_leaves:
            reset_date = available_leave.reset_date
            expired_date = available_leave.expired_date
            if reset_date == today_date:
                available_leave.update_carryforward()
                # new_reset_date = available_leave.set_reset_date(assigned_date=today_date,available_leave = available_leave)
                new_reset_date = available_leave.set_reset_date(
                    assigned_date=today_date, available_leave=available_leave
                )
                available_leave.reset_date = new_reset_date
                available_leave.save()
            if expired_date and expired_date <= today_date:
                # Zero out the CF portion; keep expired_date so it isn't re-triggered
                available_leave.set_expired_date(
                    available_leave=available_leave, assigned_date=today_date
                )
                # Do NOT advance expired_date again — set it to None so it can be
                # reset fresh on the next reset cycle if needed.
                available_leave.expired_date = None
                available_leave.save()

        # Do NOT roll the LeaveType-level carryforward_expire_date forward here;
        # that date is an assignment-time snapshot, not a rolling trigger.
        # Rolling it caused CF to be expired repeatedly on every scheduler pass.
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


if not any(
    cmd in sys.argv
    for cmd in ["makemigrations", "migrate", "compilemessages", "flush", "shell"]
):
    """
    Initializes and starts background tasks using APScheduler when the server is running.
    """
    scheduler = BackgroundScheduler()
    scheduler.add_job(leave_reset, "interval", hours=4)

    scheduler.start()
