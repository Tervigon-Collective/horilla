# leave/signals.py

import logging
import threading

from django.apps import apps
from django.db.models import Q
from django.db.models.signals import post_migrate, post_save, pre_delete, pre_save
from django.dispatch import receiver
from django.utils.translation import gettext_lazy as _

from horilla.methods import get_horilla_model_class
from leave.models import AvailableLeave, LeaveRequest, LeaveType

logger = logging.getLogger(__name__)

if apps.is_installed("attendance"):

    @receiver(post_save, sender=LeaveRequest)
    def leaverequest_pre_save(sender, instance, **_kwargs):
        """
        Overriding LeaveRequest model save method
        """
        WorkRecords = get_horilla_model_class(
            app_label="attendance", model="workrecords"
        )
        if (
            instance.start_date == instance.end_date
            and instance.end_date_breakdown != instance.start_date_breakdown
        ):
            instance.end_date_breakdown = instance.start_date_breakdown
            super(LeaveRequest, instance).save()

        period_dates = instance.requested_dates()
        if instance.status == "approved":
            for date in period_dates:
                try:
                    work_entry = (
                        WorkRecords.objects.filter(
                            date=date,
                            employee_id=instance.employee_id,
                        ).first()
                        if WorkRecords.objects.filter(
                            date=date,
                            employee_id=instance.employee_id,
                        ).exists()
                        else WorkRecords()
                    )
                    work_entry.employee_id = instance.employee_id
                    work_entry.is_leave_record = True
                    work_entry.leave_request_id = instance
                    work_entry.day_percentage = (
                        0.50
                        if instance.start_date == date
                        and instance.start_date_breakdown == "first_half"
                        or instance.end_date == date
                        and instance.end_date_breakdown == "second_half"
                        else 0.00
                    )
                    status = (
                        "CONF"
                        if instance.start_date == date
                        and instance.start_date_breakdown == "first_half"
                        or instance.end_date == date
                        and instance.end_date_breakdown == "second_half"
                        else "ABS"
                    )
                    work_entry.work_record_type = status
                    work_entry.date = date
                    work_entry.message = (
                        "Leave"
                        if status == "ABS"
                        else _("Half day Attendance need to validate")
                    )
                    work_entry.save()

                except Exception as e:
                    print(e)

        else:
            for date in period_dates:
                WorkRecords._base_manager.filter(
                    is_leave_record=True,
                    date=date,
                    employee_id=instance.employee_id,
                ).delete()

    @receiver(pre_delete, sender=LeaveRequest)
    def leaverequest_pre_delete(sender, instance, **kwargs):
        from attendance.models import WorkRecords

        work_records = WorkRecords._base_manager.filter(
            leave_request_id=instance
        ).delete()


# @receiver(post_migrate)
def add_missing_leave_to_workrecords(sender, **kwargs):
    if sender.label not in ["attendance", "leave"]:
        return

    if not apps.is_installed("attendance"):
        return
    try:
        from attendance.models import WorkRecords
        from leave.models import LeaveRequest

        work_records = WorkRecords.objects.filter(
            is_leave_record=True, leave_request_id__isnull=True
        )
        if not work_records.exists():
            return

        leave_requests = LeaveRequest.objects.all()
        date_leave_map = {}

        for leave in leave_requests:
            for date in leave.requested_dates():
                key = (leave.employee_id, date)
                date_leave_map[key] = leave

        records_to_update = []
        for record in work_records:
            leave_request = date_leave_map.get((record.employee_id, record.date))
            if leave_request:
                record.leave_request_id = leave_request
                records_to_update.append(record)

        if records_to_update:
            WorkRecords.objects.bulk_update(
                records_to_update, ["leave_request_id"], batch_size=500
            )
            print(
                f"Successfully updated {len(records_to_update)} work records with leave information"
            )

    except Exception as e:
        print(f"Error in leave/work records sync: {e}")


def _is_new_employee_type(employee_type):
    """Check if employee type is Full time or Intern (1 leave/month for first 6 months)."""
    if not employee_type:
        return False
    et_name = (getattr(employee_type, "employee_type", None) or "").strip().lower()
    return et_name in ("full time", "fulltime", "intern")


def _get_tenure_months(date_joining, today):
    """Return tenure in months; 0 if no joining date."""
    if not date_joining:
        return 0
    delta = today - date_joining
    return max(0, delta.days / 30.0)


def _get_leave_type_by_name(name, company):
    """Get leave type by name (case-insensitive) for the company or global."""
    return (
        LeaveType._default_manager.filter(name__iexact=name.strip())
        .filter(Q(company_id=company) | Q(company_id__isnull=True))
        .first()
    )


def _assign_leave_to_employee(employee, leave_type):
    """Create AvailableLeave for employee if not already assigned."""
    if not leave_type:
        return False
    if AvailableLeave._default_manager.filter(
        employee_id=employee, leave_type_id=leave_type
    ).exists():
        return False
    avail = AvailableLeave(
        leave_type_id=leave_type,
        employee_id=employee,
        available_days=leave_type.total_days or 1,
    )
    avail.pre_save_processing()
    avail.save()
    return True


def transition_employees_at_six_months():
    """
    - Employees < 6 months (Full time/Intern): only PL, remove SL and CL if present.
    - Employees >= 6 months (Full time/Intern): only SL+CL, remove PL if present.
    """
    from datetime import date

    from django.db.utils import InterfaceError, OperationalError, ProgrammingError

    from leave.models import AvailableLeave, LeaveType

    try:
        Employee = apps.get_model("employee", "Employee")
    except LookupError:
        return
    try:
        today = date.today()
        provisional_qs = LeaveType._default_manager.filter(
            Q(name__iexact="Provisional Leave") | Q(name__iexact="New Employee Leave")
        )

        for provisional_lt in provisional_qs:
            availables = list(
                AvailableLeave._default_manager.filter(
                    leave_type_id=provisional_lt
                ).select_related("employee_id__employee_work_info__employee_type_id")
            )
            for av in availables:
                emp = av.employee_id
                work_info = getattr(emp, "employee_work_info", None)
                if not work_info:
                    continue
                date_joining = getattr(work_info, "date_joining", None)
                if not date_joining:
                    continue
                tenure_months = _get_tenure_months(date_joining, today)
                if tenure_months < 6:
                    continue
                employee_type = getattr(work_info, "employee_type_id", None)
                if not _is_new_employee_type(employee_type):
                    continue
                company = getattr(work_info, "company_id", None)
                av.delete()
                added = []
                for name in ("Sick Leave", "Casual Leave"):
                    lt = _get_leave_type_by_name(name, company)
                    if lt and _assign_leave_to_employee(emp, lt):
                        added.append(name)
                if added:
                    logger.info(
                        "Transitioned %s (>=6 months): removed PL, added %s",
                        emp,
                        ", ".join(added),
                    )

        for emp in Employee.objects.all().select_related(
            "employee_work_info__employee_type_id", "employee_work_info__company_id"
        ):
            work_info = getattr(emp, "employee_work_info", None)
            if not work_info:
                continue
            date_joining = getattr(work_info, "date_joining", None)
            if not date_joining:
                continue
            tenure_months = _get_tenure_months(date_joining, today)
            employee_type = getattr(work_info, "employee_type_id", None)
            if not _is_new_employee_type(employee_type):
                continue

            if tenure_months < 6:
                to_remove = AvailableLeave._default_manager.filter(
                    employee_id=emp,
                    leave_type_id__name__in=["Sick Leave", "Casual Leave"],
                )
                removed_names = list(to_remove.values_list("leave_type_id__name", flat=True))
                to_remove.delete()
                if removed_names:
                    provisional = _get_leave_type_by_name(
                        "Provisional Leave",
                        getattr(work_info, "company_id", None),
                    )
                    if provisional:
                        _assign_leave_to_employee(emp, provisional)
                    logger.info(
                        "Corrected %s (<6 months): removed %s, kept only PL",
                        emp,
                        ", ".join(str(n) for n in removed_names if n),
                    )
    except (OperationalError, ProgrammingError, InterfaceError) as e:
        logger.warning("leave_six_month_transition failed: %s", e)


@receiver(post_save)
def auto_assign_leaves_to_new_employee(sender, instance, created, **kwargs):
    """
    Assign leaves based on tenure and employee type:
    - Full time/Intern, < 6 months: 1 Provisional Leave per month (carry forward)
    - Others or >= 6 months: 1 Sick + 1 Casual per month (carry forward)
    """
    if not created:
        return
    try:
        Employee = apps.get_model("employee", "Employee")
    except LookupError:
        return
    if sender is not Employee:
        return
    try:
        from datetime import date

        employee_work_info = getattr(instance, "employee_work_info", None)
        if not employee_work_info:
            return
        employee_company = getattr(employee_work_info, "company_id", None)
        date_joining = getattr(employee_work_info, "date_joining", None) or date.today()
        employee_type = getattr(employee_work_info, "employee_type_id", None)
        today = date.today()
        tenure_months = _get_tenure_months(date_joining, today)
        is_new_type = _is_new_employee_type(employee_type)

        assigned = []

        if is_new_type and tenure_months < 6:
            provisional = _get_leave_type_by_name("Provisional Leave", employee_company)
            if not provisional:
                provisional = _get_leave_type_by_name(
                    "New Employee Leave", employee_company
                )
            if provisional and _assign_leave_to_employee(instance, provisional):
                assigned.append(str(provisional))
            elif not provisional:
                sick = _get_leave_type_by_name("Sick Leave", employee_company)
                if sick and _assign_leave_to_employee(instance, sick):
                    assigned.append(str(sick))
                    logger.warning(
                        "Provisional Leave not found; assigned Sick Leave to %s. "
                        "Create 'Provisional Leave' (1/month, carry forward) for new employees.",
                        instance,
                    )
        else:
            for name in ("Sick Leave", "Casual Leave"):
                lt = _get_leave_type_by_name(name, employee_company)
                if lt and _assign_leave_to_employee(instance, lt):
                    assigned.append(str(lt))

        if assigned:
            logger.info(
                "Auto-assigned leave(s) to new employee %s: %s",
                instance,
                ", ".join(assigned),
            )
    except Exception as e:
        logger.warning(
            "Could not auto-assign leaves to new employee %s: %s", instance, e
        )
