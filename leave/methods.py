import calendar
from datetime import date, datetime, timedelta

import pandas as pd
from django.apps import apps
from django.db.models import Q

from employee.models import Employee
from horilla.methods import get_horilla_model_class


def overlapping_date_q(start_date, end_date):
    """Match leave rows that overlap [start_date, end_date]. Null end_date is open-ended."""
    if start_date is None:
        return Q(pk__in=[])
    end = end_date or start_date
    return Q(start_date__lte=end) & (
        Q(end_date__gte=start_date) | Q(end_date__isnull=True)
    )


def calculate_requested_days(
    start_date, end_date, start_date_breakdown, end_date_breakdown
):
    if start_date is None:
        return 0
    if end_date is None:
        end_date = start_date
    if start_date == end_date:
        return (
            1
            if start_date_breakdown == "full_day" and end_date_breakdown == "full_day"
            else 0.5
        )

    # Count full days between the two dates, excluding start and end
    middle_days = (end_date - start_date).days - 1

    # Count start and end days
    start_day_value = 1 if start_date_breakdown == "full_day" else 0.5
    end_day_value = 1 if end_date_breakdown == "full_day" else 0.5

    return middle_days + start_day_value + end_day_value


def holiday_dates_list(holidays, range_start=None, range_end=None):
    """
    :return: This function returns a list of all holiday dates.
    Recurring holidays expand to the month/day within ``range_start``–``range_end``
    (or the holiday's own year plus the current year when no range is given).
    """
    if range_start is not None and hasattr(range_start, "date"):
        range_start = range_start.date()
    if range_end is not None and hasattr(range_end, "date"):
        range_end = range_end.date()
    holiday_dates = []
    for holiday in holidays:
        holiday_start_date = holiday.start_date
        if not holiday_start_date:
            continue
        holiday_end_date = holiday.end_date or holiday_start_date
        if getattr(holiday, "recurring", False):
            years = set()
            if range_start and range_end:
                years.update(range(range_start.year, range_end.year + 1))
            else:
                years.update(
                    {
                        holiday_start_date.year,
                        date.today().year,
                        date.today().year + 1,
                    }
                )
            for year in years:
                try:
                    occ = date(
                        year, holiday_start_date.month, holiday_start_date.day
                    )
                except ValueError:
                    continue
                if range_start and range_end and not (range_start <= occ <= range_end):
                    continue
                holiday_dates.append(occ)
            continue
        holiday_dates.extend(
            holiday_start_date + timedelta(i)
            for i in range((holiday_end_date - holiday_start_date).days + 1)
        )
    return holiday_dates


def company_leave_dates_list(company_leaves, start_date):
    """
    :return: This function returns a list of all company leave dates
    """
    company_leave_dates = set()
    year = start_date.year
    for company_leave in company_leaves:
        based_on_week = company_leave.based_on_week
        based_on_week_day = company_leave.based_on_week_day

        for month in range(1, 13):
            month_calendar = calendar.monthcalendar(year, month)

            if based_on_week is not None:
                # Set Sunday as the first day of the week
                calendar.setfirstweekday(6)
                try:
                    week_days = [
                        day for day in month_calendar[int(based_on_week)] if day != 0
                    ]
                    for day in week_days:
                        date = datetime(year, month, day)
                        if date.weekday() == int(based_on_week_day):
                            company_leave_dates.add(date.date())
                except IndexError:
                    pass
            else:
                # Set Monday as the first day of the week
                calendar.setfirstweekday(0)
                for week in month_calendar:
                    if week[int(based_on_week_day)] != 0:
                        date = datetime(year, month, week[int(based_on_week_day)])
                        company_leave_dates.add(date.date())

    return list(company_leave_dates)


def get_leave_day_attendance(employee, comp_id=None):
    """
    This function returns a queryset of attendance on leave dates
    """
    Attendance = get_horilla_model_class(app_label="attendance", model="attendance")
    from leave.models import CompensatoryLeaveRequest

    attendances_to_exclude = Attendance.objects.none()  # Empty queryset to start with
    # Check for compensatory leave requests that are not rejected and not the current one
    if (
        CompensatoryLeaveRequest.objects.filter(employee_id=employee)
        .exclude(Q(id=comp_id) | Q(status="rejected"))
        .exists()
    ):
        comp_leave_reqs = CompensatoryLeaveRequest.objects.filter(
            employee_id=employee
        ).exclude(Q(id=comp_id) | Q(status="rejected"))
        for req in comp_leave_reqs:
            attendances_to_exclude |= req.attendance_id.all()
    # Filter holiday attendance excluding the attendances in attendances_to_exclude
    holiday_attendance = Attendance.objects.filter(
        is_holiday=True, employee_id=employee, attendance_validated=True
    ).exclude(id__in=attendances_to_exclude.values_list("id", flat=True))
    return holiday_attendance


def attendance_days(employee, attendances):
    """
    This function returns count of workrecord from the attendance
    """
    attendance_days = 0
    if apps.is_installed("attendance"):
        from attendance.models import WorkRecords

        for attendance in attendances:
            if WorkRecords.objects.filter(
                employee_id=employee, date=attendance.attendance_date
            ).exists():
                work_record_type = (
                    WorkRecords.objects.filter(
                        employee_id=employee, date=attendance.attendance_date
                    )
                    .first()
                    .work_record_type
                )
                if work_record_type == "HDP":
                    attendance_days += 0.5
                elif work_record_type == "FDP":
                    attendance_days += 1
    return attendance_days


def filter_conditional_leave_request(request):
    """
    Leave requests where the current user is the approver for the *current*
    pending stage (previous stage approved, this stage not yet approved/rejected).
    """
    approval_manager = Employee.objects.filter(employee_user_id=request.user).first()
    if not approval_manager or not apps.is_installed("leave"):
        from leave.models import LeaveRequest

        return LeaveRequest.objects.none()

    from leave.models import LeaveRequest, LeaveRequestConditionApproval

    pending_for_me = LeaveRequestConditionApproval.objects.filter(
        manager_id=approval_manager,
        is_approved=False,
        is_rejected=False,
        leave_request_id__status="requested",
    ).select_related("leave_request_id")

    leave_request_ids = []
    for instance in pending_for_me:
        if instance.sequence > 1:
            prev_ok = LeaveRequestConditionApproval.objects.filter(
                leave_request_id=instance.leave_request_id,
                sequence=instance.sequence - 1,
                is_approved=True,
            ).exists()
            if not prev_ok:
                continue
        leave_request_ids.append(instance.leave_request_id_id)

    return LeaveRequest.objects.filter(pk__in=leave_request_ids)


def leave_requests_awaiting_approval(request):
    """
    Union of:
    - Normal requested leaves in the user's subordinate scope (excluding
      those currently in a multi-approval chain), and
    - Multi-approval leaves that are at the user's current sequence.
    """
    from base.methods import filtersubordinates, has_org_wide_perm
    from leave.models import LeaveRequest, LeaveRequestConditionApproval

    base_qs = LeaveRequest.objects.filter(status="requested")
    multiple_approvals = filter_conditional_leave_request(request).distinct()

    if has_org_wide_perm(request.user, "leave.change_leaverequest") or request.user.is_superuser:
        normal_requests = base_qs
    else:
        normal_requests = filtersubordinates(
            request, base_qs, "leave.change_leaverequest"
        )

    if not request.user.is_superuser:
        # Exclude leaves stuck in a multi-approval chain from the "normal" bucket
        # so only the current-stage approver (via multiple_approvals) sees them.
        multi_ids = list(
            LeaveRequestConditionApproval.objects.filter(
                is_approved=False,
                is_rejected=False,
                leave_request_id__status="requested",
            ).values_list("leave_request_id_id", flat=True)
        )
        if multi_ids:
            normal_requests = normal_requests.exclude(id__in=multi_ids)

    return (normal_requests | multiple_approvals).distinct()


def leave_approval_progress(leave_request) -> dict:
    """Progress payload for inbox / API: levels and whether it's the actor's turn."""
    from leave.models import LeaveRequestConditionApproval

    stages = list(
        LeaveRequestConditionApproval.objects.filter(
            leave_request_id=leave_request
        ).order_by("sequence")
    )
    if not stages:
        return {
            "is_multi_level": False,
            "approval_level": None,
            "approved_count": 0,
            "total_levels": 0,
            "your_turn": False,
        }
    approved_count = sum(1 for s in stages if s.is_approved)
    pending = next((s for s in stages if not s.is_approved and not s.is_rejected), None)
    return {
        "is_multi_level": True,
        "approval_level": pending.sequence if pending else None,
        "approved_count": approved_count,
        "total_levels": len(stages),
        "your_turn": False,  # filled by caller with actor
        "pending_manager_id": pending.manager_id_id if pending else None,
    }


def assert_can_approve_leave_stage(leave_request, employee, *, is_superuser=False):
    """
    Return the LeaveRequestConditionApproval row to approve, or None for
    single-level leave. Raises ValueError if out of order / wrong approver.
    """
    from leave.models import LeaveRequestConditionApproval

    stages = list(
        LeaveRequestConditionApproval.objects.filter(
            leave_request_id=leave_request
        ).order_by("sequence")
    )
    if not stages:
        return None
    if is_superuser:
        return stages[-1]

    pending = next((s for s in stages if not s.is_approved and not s.is_rejected), None)
    if pending is None:
        raise ValueError("All approval stages are already complete.")
    if not employee or pending.manager_id_id != employee.id:
        raise ValueError("You are not the current-stage approver for this leave request.")
    if pending.sequence > 1:
        prev_ok = LeaveRequestConditionApproval.objects.filter(
            leave_request_id=leave_request,
            sequence=pending.sequence - 1,
            is_approved=True,
        ).exists()
        if not prev_ok:
            raise ValueError("Previous approval stage is not complete yet.")
    return pending


def parse_excel_date(value):
    """
    Convert Excel date values into a valid Python date object.
    Supports multiple formats: YYYY-MM-DD, DD-MM-YYYY, DD Month YYYY, MM/DD/YYYY, etc.
    """
    if not value or pd.isna(value):
        return None

    if isinstance(value, date):
        # Already a date (from Excel or pandas)
        return value

    if isinstance(value, datetime):
        # Datetime object → convert to date
        return value.date()

    if isinstance(value, str):
        value = value.strip()
        # Try multiple formats
        date_formats = [
            "%Y-%m-%d",  # 2025-07-22
            "%d-%m-%Y",  # 22-07-2025
            "%d/%m/%Y",  # 22/07/2025
            "%m/%d/%Y",  # 07/22/2025
            "%d %B %Y",  # 22 July 2025
            "%d %B, %Y",  # 22 July, 2025
            "%d-%b-%Y",  # 22-Jul-2025
        ]
        for fmt in date_formats:
            try:
                return datetime.strptime(value, fmt).date()
            except ValueError:
                continue

    # If nothing matches, return None (caller should handle error)
    return None


def scope_leave_requests(request, queryset):
    """Own + direct/indirect reports, unless user has org-wide leave view."""
    from base.methods import filtersubordinates

    return filtersubordinates(request, queryset, "leave.view_leaverequest")


def scope_available_leave(request, queryset):
    """Own + team leave balances unless user has org-wide available-leave view."""
    from base.methods import filtersubordinates

    return filtersubordinates(request, queryset, "leave.view_availableleave")


def scope_leave_allocation_requests(request, queryset):
    from base.methods import filtersubordinates

    return filtersubordinates(
        request, queryset, "leave.view_leaveallocationrequest"
    )
