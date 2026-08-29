"""
leave/services.py

Centralised business-logic helpers for the leave app.
"""

from django.db import transaction
from django.db.models import Q, Sum
from django.utils.translation import gettext_lazy as _


def evaluate_leave_type_conditions(leave_type, employee, *, for_assignment=True):
    """
    Evaluate all conditions configured on a LeaveType against an employee.

    Returns a (is_eligible, error_message) tuple.

    for_assignment=True (default): enforce once_per_employment for assignment flows.
    Leave requests must pass for_assignment=False so assigned maternity/etc. remain usable.
    """
    from datetime import date

    from leave.models import AvailableLeave

    for condition in leave_type.conditions.all():
        ctype = condition.condition_type

        if ctype == "gender":
            emp_gender = (getattr(employee, "gender", None) or "").lower()
            required_gender = (condition.value or "").lower()
            if emp_gender and required_gender and emp_gender != required_gender:
                return False, _(
                    "This leave type is restricted to {gender} employees only."
                ).format(gender=condition.value)

        elif ctype == "once_per_employment":
            if not for_assignment:
                continue
            already_assigned = AvailableLeave.objects.filter(
                employee_id=employee,
                leave_type_id=leave_type,
            ).exists()
            if already_assigned:
                return False, _(
                    "'{leave_type}' can only be assigned once per employment and has already been assigned to this employee."
                ).format(leave_type=leave_type.name)

        elif ctype == "marital_status":
            emp_status = (getattr(employee, "marital_status", None) or "").lower()
            required_status = (condition.value or "").lower()
            if emp_status and required_status and emp_status != required_status:
                return False, _(
                    "This leave type is restricted to employees with marital status: {status}."
                ).format(status=condition.value)

        elif ctype == "nationality":
            emp_country = (getattr(employee, "country", None) or "").lower()
            required_country = (condition.value or "").lower()
            if emp_country and required_country and emp_country != required_country:
                return False, _(
                    "This leave type is restricted to employees with nationality: {nationality}."
                ).format(nationality=condition.value)

        elif ctype == "department":
            dept = None
            work_info = getattr(employee, "employee_work_info", None)
            if work_info:
                dept_obj = getattr(work_info, "department_id", None)
                if dept_obj:
                    dept = str(dept_obj).lower()
            required_dept = (condition.value or "").lower()
            if dept and required_dept and dept != required_dept:
                return False, _(
                    "This leave type is restricted to employees in the {department} department."
                ).format(department=condition.value)

        elif ctype == "employment_type":
            emp_type = None
            work_info = getattr(employee, "employee_work_info", None)
            if work_info:
                emp_type_obj = getattr(work_info, "employee_type_id", None)
                if emp_type_obj:
                    emp_type = str(emp_type_obj).lower()
            required_type = (condition.value or "").lower()
            if emp_type and required_type and emp_type != required_type:
                return False, _(
                    "This leave type is restricted to employees with employment type: {emp_type}."
                ).format(emp_type=condition.value)

        elif ctype == "employment_status":
            work_info = getattr(employee, "employee_work_info", None)
            emp_status = (
                (getattr(work_info, "employment_status", None) or "").strip().lower()
                if work_info
                else ""
            )
            required_status = (condition.value or "").strip().lower()
            # Treat blank status as not meeting a required status (e.g. confirmed)
            if required_status and emp_status != required_status:
                return False, _(
                    "This leave type is available only when employment status is: {status}."
                ).format(status=condition.value)

        elif ctype == "grade":
            grade = employee_job_grade(employee)
            required_grade = (condition.value or "").strip().lower()
            if grade and required_grade and grade != required_grade:
                return False, _(
                    "This leave type is restricted to employees with grade: {grade}."
                ).format(grade=condition.value)

        elif ctype == "service_duration":
            try:
                required_years = float(condition.value)
            except (TypeError, ValueError):
                required_years = 0.0
            years = employee_years_of_service(employee, date.today())
            if years < required_years:
                return False, _(
                    "This leave type requires at least {years} years of service."
                ).format(years=condition.value)

    return True, None


def employee_job_grade(employee) -> str:
    """Normalized job grade from work info (falls back to job position name)."""
    work_info = getattr(employee, "employee_work_info", None)
    if not work_info:
        return ""
    grade = (getattr(work_info, "job_grade", None) or "").strip()
    if grade:
        return grade.lower()
    position = getattr(work_info, "job_position_id", None)
    return str(position).strip().lower() if position else ""


def employee_years_of_service(employee, as_of=None) -> float:
    from datetime import date

    as_of = as_of or date.today()
    work_info = getattr(employee, "employee_work_info", None)
    doj = getattr(work_info, "date_joining", None) if work_info else None
    if not doj:
        return 0.0
    return max((as_of - doj).days / 365.25, 0.0)


def resolve_annual_leave_days(leave_type, employee) -> float:
    """
    Annual entitlement for an employee: matching LeaveAccrualRule or leave_type.total_days.
    """
    default = float(getattr(leave_type, "total_days", 0) or 0)
    rules = getattr(leave_type, "accrual_rules", None)
    if rules is None:
        return default
    try:
        rule_list = list(rules.all())
    except Exception:
        return default
    if not rule_list:
        return default

    work_info = getattr(employee, "employee_work_info", None)
    grade = (getattr(work_info, "job_grade", None) or "").strip().lower() if work_info else ""
    position_id = getattr(work_info, "job_position_id_id", None) if work_info else None

    best = None
    best_score = -1
    for rule in rule_list:
        score = 0
        rule_grade = (rule.job_grade or "").strip().lower()
        rule_pos = getattr(rule, "job_position_id_id", None)
        if rule_grade:
            if not grade or grade != rule_grade:
                continue
            score += 2
        if rule_pos:
            if not position_id or int(position_id) != int(rule_pos):
                continue
            score += 1
        if score > best_score:
            best_score = score
            best = rule

    if best is not None:
        return float(best.annual_days or 0)
    return default


def deduct_leave_balance_fifo(available_leave, requested_days):
    """
    Deduct using carryforward-first FIFO policy.
    Returns (approved_available_days, approved_carryforward_days).
    Mutates available_leave in memory.
    """
    requested = float(requested_days or 0)
    carryforward = float(available_leave.carryforward_days or 0)
    available = float(available_leave.available_days or 0)

    if requested > carryforward:
        approved_carryforward = carryforward
        carryforward = 0.0
        remainder = requested - approved_carryforward
        approved_available = remainder
        available -= remainder
    else:
        approved_carryforward = requested
        carryforward -= requested
        approved_available = 0.0

    available_leave.carryforward_days = max(0.0, carryforward)
    available_leave.available_days = max(0.0, available)
    return approved_available, approved_carryforward


def restore_leave_balance(available_leave, approved_available, approved_carryforward):
    """Restore previously deducted balance."""
    available_leave.available_days = (available_leave.available_days or 0) + float(
        approved_available or 0
    )
    available_leave.carryforward_days = (available_leave.carryforward_days or 0) + float(
        approved_carryforward or 0
    )


def pending_requested_days(employee, leave_type, exclude_pk=None):
    """Sum requested days for other pending leave requests (pre-reservation check)."""
    from leave.models import LeaveRequest

    qs = LeaveRequest.objects.filter(
        employee_id=employee,
        leave_type_id=leave_type,
        status="requested",
    )
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    return float(qs.aggregate(total=Sum("requested_days"))["total"] or 0)


def has_sufficient_leave_balance(
    available_leave, requested_days, employee=None, leave_type=None, exclude_pk=None
) -> bool:
    """Check balance including other pending requests not yet reserved."""
    lt = leave_type or getattr(available_leave, "leave_type_id", None)
    if lt is not None and not getattr(lt, "limit_leave", True):
        return True
    total = float(available_leave.available_days or 0) + float(
        available_leave.carryforward_days or 0
    )
    if employee is not None and leave_type is not None:
        total -= pending_requested_days(employee, leave_type, exclude_pk)
    return total >= float(requested_days or 0)


def get_available_leave_record(leave_request, for_update=False):
    from leave.models import AvailableLeave

    qs = AvailableLeave.objects.filter(
        employee_id=leave_request.employee_id,
        leave_type_id=leave_request.leave_type_id,
    )
    if for_update:
        qs = qs.select_for_update()
    return qs.first()


def _reserved_total(leave_request):
    return float(leave_request.reserved_available_days or 0) + float(
        leave_request.reserved_carryforward_days or 0
    )


def _approved_total(leave_request):
    return float(leave_request.approved_available_days or 0) + float(
        leave_request.approved_carryforward_days or 0
    )


@transaction.atomic
def reserve_leave_balance(leave_request):
    """Hold balance when a leave request is submitted for approval."""
    from leave.models import LeaveRequest

    if leave_request.status != "requested":
        return
    if leave_request.leave_type_id.require_approval == "no":
        return
    # Unlimited types (e.g. LWP) have no balance to hold
    if not leave_request.leave_type_id.limit_leave:
        return
    if _reserved_total(leave_request) > 0:
        return

    available_leave = get_available_leave_record(leave_request, for_update=True)
    if not available_leave:
        return

    if not has_sufficient_leave_balance(
        available_leave,
        leave_request.requested_days,
        leave_request.employee_id,
        leave_request.leave_type_id,
        exclude_pk=leave_request.pk,
    ):
        return

    approved_available, approved_carryforward = deduct_leave_balance_fifo(
        available_leave, leave_request.requested_days
    )
    leave_request.reserved_available_days = approved_available
    leave_request.reserved_carryforward_days = approved_carryforward
    available_leave.save()
    LeaveRequest.objects.filter(pk=leave_request.pk).update(
        reserved_available_days=approved_available,
        reserved_carryforward_days=approved_carryforward,
    )


@transaction.atomic
def sync_leave_reservation(leave_request, previous_requested_days=0):
    """Re-reserve when requested days change on a pending request."""
    if _reserved_total(leave_request) > 0:
        release_leave_balance(leave_request, clear_status=False)
    if leave_request.status == "requested":
        reserve_leave_balance(leave_request)


@transaction.atomic
def confirm_leave_approval(leave_request, available_leave=None):
    """
    Finalize deduction on approval.
    Uses existing reservation when present, otherwise deducts now.
    """
    if available_leave is None:
        available_leave = get_available_leave_record(leave_request, for_update=True)

    if not leave_request.leave_type_id.limit_leave:
        leave_request.approved_available_days = 0
        leave_request.approved_carryforward_days = 0
        leave_request.reserved_available_days = 0
        leave_request.reserved_carryforward_days = 0
        return available_leave

    if _reserved_total(leave_request) > 0:
        leave_request.approved_available_days = leave_request.reserved_available_days
        leave_request.approved_carryforward_days = (
            leave_request.reserved_carryforward_days
        )
        leave_request.reserved_available_days = 0
        leave_request.reserved_carryforward_days = 0
        return available_leave

    if not has_sufficient_leave_balance(
        available_leave, leave_request.requested_days
    ):
        return None

    approved_available, approved_carryforward = deduct_leave_balance_fifo(
        available_leave, leave_request.requested_days
    )
    leave_request.approved_available_days = approved_available
    leave_request.approved_carryforward_days = approved_carryforward
    return available_leave


@transaction.atomic
def release_leave_balance(leave_request, clear_status=True):
    """Restore reserved or approved balance on reject/cancel/delete."""
    from leave.models import LeaveRequest

    available_leave = get_available_leave_record(leave_request, for_update=True)
    if not available_leave:
        return

    if _approved_total(leave_request) > 0:
        restore_leave_balance(
            available_leave,
            leave_request.approved_available_days,
            leave_request.approved_carryforward_days,
        )
        leave_request.approved_available_days = 0
        leave_request.approved_carryforward_days = 0
    elif _reserved_total(leave_request) > 0:
        restore_leave_balance(
            available_leave,
            leave_request.reserved_available_days,
            leave_request.reserved_carryforward_days,
        )
        leave_request.reserved_available_days = 0
        leave_request.reserved_carryforward_days = 0

    available_leave.save()
    if clear_status and leave_request.pk:
        LeaveRequest.objects.filter(pk=leave_request.pk).update(
            approved_available_days=leave_request.approved_available_days,
            approved_carryforward_days=leave_request.approved_carryforward_days,
            reserved_available_days=leave_request.reserved_available_days,
            reserved_carryforward_days=leave_request.reserved_carryforward_days,
        )


def reverse_allocation_days(available_leave, requested_days):
    """Reverse an approved allocation (available bucket first, then carryforward)."""
    requested = float(requested_days or 0)
    available = float(available_leave.available_days or 0)
    carryforward = float(available_leave.carryforward_days or 0)
    if available >= requested:
        available_leave.available_days = available - requested
    else:
        remainder = requested - available
        available_leave.available_days = 0.0
        available_leave.carryforward_days = max(0.0, carryforward - remainder)
    return available_leave


def deduct_encashment_days(available_leave, ad_days: float, cfd_days: float) -> bool:
    """Deduct encashment from available then carryforward buckets (FIFO-style)."""
    ad_days = float(ad_days or 0)
    cfd_days = float(cfd_days or 0)
    available = float(available_leave.available_days or 0)
    carryforward = float(available_leave.carryforward_days or 0)
    if available < ad_days or carryforward < cfd_days:
        return False
    available_leave.available_days = available - ad_days
    available_leave.carryforward_days = carryforward - cfd_days
    available_leave.save()
    return True


def restore_encashment_days(available_leave, ad_days: float, cfd_days: float):
    """Restore leave balance when encashment is rejected after approval."""
    available_leave.available_days = float(available_leave.available_days or 0) + float(
        ad_days or 0
    )
    available_leave.carryforward_days = float(
        available_leave.carryforward_days or 0
    ) + float(cfd_days or 0)
    available_leave.save()


def apply_auto_approve_deduction(leave_request, available_leave=None):
    """Immediate deduction when approval is not required."""
    if available_leave is None:
        available_leave = get_available_leave_record(leave_request, for_update=True)
    if not available_leave:
        return False
    result = confirm_leave_approval(leave_request, available_leave)
    if result is None:
        return False
    leave_request.status = "approved"
    available_leave.save()
    return True


def get_condition_display_choices():
    """
    Returns a dict of {condition_type: suggested value choices} for UI hints.
    """
    return {
        "gender": ["Male", "Female", "Other"],
        "marital_status": ["Single", "Married", "Divorced", "Widowed"],
        "department": [],
        "employment_type": [],
        "grade": [],
        "nationality": [],
        "once_per_employment": [],
    }


def _employee_off_days(employee, start_date, end_date):
    """Weekends, holidays, and company off-days in range."""
    from datetime import timedelta

    from leave.models import (
        CompanyLeaves,
        Holidays,
        company_leave_dates_list,
        holiday_dates_list,
    )

    holiday_qs = Holidays.objects.filter(Q(is_specific=False) | Q(employees=employee))
    holidays = set(holiday_dates_list(holiday_qs))
    company_leaves = set(
        company_leave_dates_list(CompanyLeaves.objects.all(), start_date)
    )
    off_days = set()
    current = start_date
    while current <= end_date:
        if current.weekday() >= 5 or current in holidays or current in company_leaves:
            off_days.add(current)
        current += timedelta(days=1)
    return off_days, holidays, company_leaves


def _leave_on_date(employee, day, exclude_pk=None):
    from leave.models import LeaveRequest

    qs = LeaveRequest.objects.filter(
        employee_id=employee,
        status__in=["requested", "approved"],
        start_date__lte=day,
        end_date__gte=day,
    )
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    return qs.exists()


def expand_sandwich_dates(start_date, end_date, employee, leave_type, exclude_pk=None):
    """Expand leave range when sandwich policy applies."""
    from datetime import timedelta

    if not leave_type or not leave_type.sandwich_policy:
        return start_date, end_date or start_date

    end_date = end_date or start_date
    scan_start = start_date - timedelta(days=14)
    scan_end = end_date + timedelta(days=14)
    off_days, _, _ = _employee_off_days(employee, scan_start, scan_end)

    cur = start_date
    while True:
        prev = cur - timedelta(days=1)
        if prev < scan_start:
            break
        if prev in off_days or _leave_on_date(employee, prev, exclude_pk):
            cur = prev
        else:
            break

    end = end_date
    while True:
        nxt = end + timedelta(days=1)
        if nxt > scan_end:
            break
        if nxt in off_days or _leave_on_date(employee, nxt, exclude_pk):
            end = nxt
        else:
            break

    return cur, end


def sandwich_adjusted_requested_days(
    start_date,
    end_date,
    start_breakdown,
    end_breakdown,
    employee,
    leave_type,
    base_days,
    exclude_pk=None,
):
    from leave.models import calculate_requested_days

    if not leave_type or not leave_type.sandwich_policy:
        return base_days

    exp_start, exp_end = expand_sandwich_dates(
        start_date, end_date, employee, leave_type, exclude_pk
    )
    if exp_start == start_date and exp_end == (end_date or start_date):
        return base_days

    return calculate_requested_days(
        exp_start, exp_end, start_breakdown, end_breakdown
    )


def expire_carryforward_days(available_leave, today_date=None):
    """
    Expire the carry-forward portion of a single AvailableLeave record.
    Saves the record and returns True if expiry was applied, False otherwise.
    """
    from datetime import date

    today_date = today_date or date.today()
    expired_date = available_leave.expired_date
    if not expired_date or expired_date > today_date:
        return False
    if available_leave.carryforward_days <= 0:
        # Nothing left to expire; just clear the date
        available_leave.expired_date = None
        available_leave.save(update_fields=["expired_date", "carryforward_days"])
        return False

    available_leave.carryforward_days = 0
    available_leave.expired_date = None
    available_leave.save(update_fields=["carryforward_days", "expired_date"])
    return True


def expire_all_carryforward_balances(today_date=None):
    """
    Run through every AvailableLeave with carryforward_type='carryforward expire'
    and expire CF that is past its expiry date.
    Returns a count of records updated.
    """
    from datetime import date

    from leave.models import AvailableLeave

    today_date = today_date or date.today()
    qs = AvailableLeave.objects.filter(
        leave_type_id__carryforward_type="carryforward expire",
        expired_date__lte=today_date,
        carryforward_days__gt=0,
    ).select_related("leave_type_id")
    count = 0
    for available_leave in qs:
        available_leave.carryforward_days = 0
        available_leave.expired_date = None
        available_leave.save(update_fields=["carryforward_days", "expired_date"])
        count += 1
    return count


def accrue_monthly_balances(today_date=None):
    """Monthly leave accrual with DOJ pro-rata for enabled leave types."""
    import calendar
    from datetime import date

    from leave.models import AvailableLeave

    today_date = today_date or date.today()
    month_key = (today_date.year, today_date.month)

    for available in AvailableLeave.objects.select_related(
        "leave_type_id", "employee_id", "employee_id__employee_work_info"
    ).filter(leave_type_id__is_active=True, employee_id__is_active=True):
        leave_type = available.leave_type_id
        if not leave_type or not leave_type.monthly_accrual:
            continue

        employee = available.employee_id
        # Re-check eligibility (e.g. CL requires confirmed)
        is_eligible, _ = evaluate_leave_type_conditions(
            leave_type, employee, for_assignment=False
        )
        if not is_eligible:
            continue

        if available.last_accrual_date:
            last_key = (
                available.last_accrual_date.year,
                available.last_accrual_date.month,
            )
            if last_key >= month_key:
                continue

        annual = resolve_annual_leave_days(leave_type, employee)
        monthly_rate = annual / 12.0
        if monthly_rate <= 0:
            continue

        work = getattr(employee, "employee_work_info", None)
        doj = getattr(work, "date_joining", None) if work else None
        if doj and (doj.year, doj.month) == month_key and doj.day > 1:
            days_in_month = calendar.monthrange(today_date.year, today_date.month)[1]
            monthly_rate *= (days_in_month - doj.day + 1) / days_in_month

        # Cap at annual entitlement within FY (no CF stack for monthly-accrual FY types)
        current = float(available.available_days or 0)
        if leave_type.carryforward_type == "no carryforward":
            cap = annual
        else:
            cap = annual
            if leave_type.carryforward_max:
                cap += float(leave_type.carryforward_max)

        available.available_days = min(current + monthly_rate, cap)
        available.last_accrual_date = today_date
        available.save(update_fields=["available_days", "last_accrual_date"])
