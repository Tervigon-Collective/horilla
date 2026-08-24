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
    Filters and returns LeaveRequest objects that have been conditionally approved by the previous sequence of approvals.
    """
    approval_manager = Employee.objects.filter(employee_user_id=request.user).first()
    leave_request_ids = []
    if apps.is_installed("leave"):
        from leave.models import LeaveRequest, LeaveRequestConditionApproval

        multiple_approval_requests = LeaveRequestConditionApproval.objects.filter(
            manager_id=approval_manager
        )

    else:
        multiple_approval_requests = None
    for instance in multiple_approval_requests:
        if instance.sequence > 1:
            pre_sequence = instance.sequence - 1
            leave_request_id = instance.leave_request_id
            instance = LeaveRequestConditionApproval.objects.filter(
                leave_request_id=leave_request_id, sequence=pre_sequence
            ).first()
            if instance and instance.is_approved:
                leave_request_ids.append(instance.leave_request_id.id)
        else:
            leave_request_ids.append(instance.leave_request_id.id)
    return LeaveRequest.objects.filter(pk__in=leave_request_ids)


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
