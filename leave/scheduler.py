import sys
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler

from horilla.signals import post_scheduler, pre_scheduler


def leave_six_month_transition():
    """
    Transition Full time/Intern employees at 6 months: remove Provisional Leave,
    add Sick + Casual Leave. Runs once daily.
    """
    from leave.signals import transition_employees_at_six_months

    from django.db import connection

    connection.close()
    transition_employees_at_six_months()


def leave_reset():
    from django.db import connection
    from django.db.utils import (
        InterfaceError,
        OperationalError,
        ProgrammingError,
    )

    # Use a fresh DB connection (avoids "connection already closed" in background thread)
    connection.close()
    pre_scheduler.send(sender=leave_reset)
    from leave.models import LeaveType

    today = datetime.now()
    today_date = today.date()
    try:
        leave_types = LeaveType.objects.filter(reset=True)
    except (OperationalError, ProgrammingError, InterfaceError):
        return  # Migrations not applied or connection closed
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
                new_expired_date = available_leave.set_expired_date(
                    available_leave=available_leave, assigned_date=today_date
                )
                available_leave.expired_date = new_expired_date
                available_leave.save()

        if (
            leave_type.carryforward_expire_date
            and leave_type.carryforward_expire_date <= today_date
        ):
            leave_type.carryforward_expire_date = leave_type.set_expired_date(
                today_date
            )
            leave_type.save()
    post_scheduler.send(
        sender=leave_reset,
        **{
            "today": today,
            "today_date": today_date,
            "leave_types": leave_types,
        }
    )


if not any(
    cmd in sys.argv
    for cmd in ["makemigrations", "migrate", "compilemessages", "flush", "shell"]
):
    """
    Initializes and starts background tasks using APScheduler when the server is running.
    """
    scheduler = BackgroundScheduler()
    scheduler.add_job(leave_reset, "interval", seconds=20)
    scheduler.add_job(leave_six_month_transition, "cron", hour=1, minute=0)

    scheduler.start()
