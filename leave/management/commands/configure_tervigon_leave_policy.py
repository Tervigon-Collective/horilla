"""
Configure Tervigon leave policy (FY 2026-27).

- CL: 12/FY, confirmed only, 1/month accrual, FY-end lapse
- SL: 12/FY, all from DOJ, 1/month accrual, FY-end lapse
- No Earned Leave / Half-day leave types
- Eid, LWP, LOA, Voting, Maternity/Paternity/Adoption shells

Run: python manage.py configure_tervigon_leave_policy
"""

from __future__ import annotations

from datetime import date

from dateutil.relativedelta import relativedelta
from django.core.management.base import BaseCommand
from django.db import transaction

from base.models import Company
from employee.models import Employee
from horilla.horilla_middlewares import _thread_locals
from leave.models import AvailableLeave, LeaveType, LeaveTypeCondition

COMPANY_NAME = "Tervigon Collective Private Limited"
FY_START_MONTH = 4  # Indian FY


def _mock_request():
    mock_user = type(
        "MockUser", (), {"is_authenticated": False, "is_anonymous": True}
    )()
    return type(
        "MockRequest",
        (),
        {"session": {"selected_company": "all"}, "user": mock_user},
    )()


def _fy_start_for(today: date) -> date:
    year = today.year if today.month >= FY_START_MONTH else today.year - 1
    return date(year, FY_START_MONTH, 1)


def _next_fy_reset(today: date) -> date:
    start = _fy_start_for(today)
    if today < start:
        return start
    return date(start.year + 1, FY_START_MONTH, 1)


def _completed_months(from_date: date, to_date: date) -> int:
    """Unused helper retained for clarity — prefer _months_accrued_in_fy."""
    if not from_date or to_date < from_date:
        return 0
    months = (to_date.year - from_date.year) * 12 + (to_date.month - from_date.month)
    if to_date.day < from_date.day:
        months -= 1
    return max(0, min(12, months))


def _months_accrued_in_fy(anchor: date | None, today: date) -> int:
    """
    Completed calendar months in the current FY that earn 1 day each.

    Counts month boundaries from max(FY start, first accrual month) up to
    (but not including) the current month — i.e. only completed months.
    Mid-month join/confirm starts accruing from the following month.
    """
    fy0 = _fy_start_for(today)
    if anchor:
        if anchor.day > 1:
            start = date(anchor.year, anchor.month, 1) + relativedelta(months=1)
        else:
            start = date(anchor.year, anchor.month, 1)
        if start < fy0:
            start = fy0
    else:
        # Missing DOJ/confirm date: accrue from FY start until HR fills the date
        start = fy0
    if start > today:
        return 0
    end_boundary = date(today.year, today.month, 1)
    months = (end_boundary.year - start.year) * 12 + (end_boundary.month - start.month)
    return max(0, min(12, months))


class Command(BaseCommand):
    help = "Configure Tervigon leave policy (CL/SL FY rules + related types)"

    def handle(self, *args, **options):
        _thread_locals.request = _mock_request()
        try:
            company = Company.objects.filter(company=COMPANY_NAME).first()
            if not company:
                self.stderr.write(self.style.ERROR(f"{COMPANY_NAME} not found"))
                return
            with transaction.atomic():
                self._deactivate_excluded(company)
                cl = self._configure_cl_sl(company, "Casual Leave", confirmed_only=True)
                sl = self._configure_cl_sl(company, "Sick Leave", confirmed_only=False)
                self._ensure_other_types(company)
                self._assign_balances(company, cl, sl)
                self._backfill_probation_dates(company)
            self.stdout.write(self.style.SUCCESS("Tervigon leave policy configured"))
        finally:
            try:
                delattr(_thread_locals, "request")
            except AttributeError:
                pass

    def _deactivate_excluded(self, company):
        patterns = [
            "earned",
            "privilege",
            "half day",
            "half-day",
            "halfday",
        ]
        qs = LeaveType.objects.filter(company_id=company)
        for lt in qs:
            name = (lt.name or "").lower()
            if any(p in name for p in patterns):
                lt.is_active = False
                lt.save(update_fields=["is_active"])
                self.stdout.write(f"Deactivated excluded leave type: {lt.name}")

    def _configure_cl_sl(self, company, name: str, confirmed_only: bool) -> LeaveType:
        lt, created = LeaveType.objects.get_or_create(
            name=name,
            company_id=company,
            defaults={
                "payment": "paid",
                "payment_type": "paid",
                "total_days": 12,
                "limit_leave": True,
                "reset": True,
                "reset_based": "yearly",
                "reset_month": "4",
                "reset_day": "1",
                "carryforward_type": "no carryforward",
                "carryforward_max": None,
                "monthly_accrual": True,
                "require_approval": "yes",
                "require_attachment": "no",
                "exclude_company_leave": "yes",
                "exclude_holiday": "yes",
                "is_encashable": False,
            },
        )
        lt.payment = "paid"
        lt.payment_type = "paid"
        lt.total_days = 12
        lt.limit_leave = True
        lt.reset = True
        lt.reset_based = "yearly"
        lt.reset_month = "4"
        lt.reset_day = "1"
        lt.carryforward_type = "no carryforward"
        lt.carryforward_max = None
        lt.monthly_accrual = True
        lt.require_approval = "yes"
        lt.is_encashable = False
        lt.is_active = True
        lt.save()

        # Clear old conditions then set confirmed-only for CL
        lt.conditions.clear()
        if confirmed_only:
            cond, _ = LeaveTypeCondition.objects.get_or_create(
                condition_type="employment_status",
                value="confirmed",
            )
            lt.conditions.add(cond)
            self.stdout.write(f"{name}: employment_status=confirmed")
        action = "Created" if created else "Updated"
        self.stdout.write(
            f"{action} {name}: 12/FY monthly accrual, FY reset Apr 1, no FY carry"
        )
        return lt

    def _ensure_type(self, company, name, **kwargs) -> LeaveType:
        lt, created = LeaveType.objects.get_or_create(
            name=name, company_id=company, defaults=kwargs
        )
        if not created:
            for k, v in kwargs.items():
                setattr(lt, k, v)
            lt.is_active = True
            lt.save()
            self.stdout.write(f"Updated {name}")
        else:
            self.stdout.write(self.style.SUCCESS(f"Created {name}"))
        return lt

    def _ensure_other_types(self, company):
        # Eid already seeded; refresh settings
        eid = self._ensure_type(
            company,
            "Eid Holiday",
            payment="paid",
            payment_type="paid",
            total_days=2,
            limit_leave=True,
            reset=True,
            reset_based="yearly",
            reset_month="4",
            reset_day="1",
            carryforward_type="no carryforward",
            monthly_accrual=False,
            require_approval="yes",
            is_encashable=False,
        )

        self._ensure_type(
            company,
            "Leave Without Pay",
            payment="unpaid",
            payment_type="unpaid",
            total_days=0,
            limit_leave=False,
            reset=False,
            carryforward_type="no carryforward",
            monthly_accrual=False,
            require_approval="yes",
            is_encashable=False,
        )

        loa = self._ensure_type(
            company,
            "Leave of Absence",
            payment="unpaid",
            payment_type="unpaid",
            total_days=15,
            limit_leave=True,
            reset=True,
            reset_based="yearly",
            reset_month="4",
            reset_day="1",
            carryforward_type="no carryforward",
            monthly_accrual=False,
            require_approval="yes",
            is_encashable=False,
        )
        loa.conditions.clear()
        sd, _ = LeaveTypeCondition.objects.get_or_create(
            condition_type="service_duration", value="2"
        )
        loa.conditions.add(sd)

        self._ensure_type(
            company,
            "Voting Leave",
            payment="paid",
            payment_type="paid",
            total_days=0.5,
            limit_leave=True,
            reset=True,
            reset_based="yearly",
            reset_month="4",
            reset_day="1",
            carryforward_type="no carryforward",
            monthly_accrual=False,
            require_approval="yes",
            is_encashable=False,
        )

        # Statutory shells — durations editable by HR (not hard-locked in code)
        for name, days, gender in [
            ("Maternity Leave", 182, "female"),
            ("Paternity Leave", 15, "male"),
            ("Adoption Leave", 84, None),
        ]:
            lt = self._ensure_type(
                company,
                name,
                payment="paid",
                payment_type="paid",
                total_days=days,
                limit_leave=True,
                reset=False,
                carryforward_type="no carryforward",
                monthly_accrual=False,
                require_approval="yes",
                require_attachment="yes",
                is_encashable=False,
            )
            lt.conditions.clear()
            once, _ = LeaveTypeCondition.objects.get_or_create(
                condition_type="once_per_employment", value=""
            )
            lt.conditions.add(once)
            if gender:
                g, _ = LeaveTypeCondition.objects.get_or_create(
                    condition_type="gender", value=gender
                )
                lt.conditions.add(g)

        return eid

    def _assign_balances(self, company, cl: LeaveType, sl: LeaveType):
        today = date.today()
        reset_date = _next_fy_reset(today)
        employees = Employee.objects.filter(
            is_active=True, employee_work_info__company_id=company
        ).select_related("employee_work_info")

        for emp in employees:
            wi = getattr(emp, "employee_work_info", None)
            doj = getattr(wi, "date_joining", None) if wi else None
            status = (getattr(wi, "employment_status", None) or "confirmed") if wi else "confirmed"
            probation_end = getattr(wi, "probation_end", None) if wi else None

            # Sick Leave — all employees from DOJ
            sl_months = _months_accrued_in_fy(doj, today)
            sl_bal, _ = AvailableLeave.objects.get_or_create(
                employee_id=emp,
                leave_type_id=sl,
                defaults={"available_days": 0, "carryforward_days": 0},
            )
            taken = float(sl_bal.leave_taken() or 0)
            sl_bal.available_days = max(0.0, float(sl_months) - taken)
            sl_bal.carryforward_days = 0
            sl_bal.reset_date = reset_date
            sl_bal.last_accrual_date = date(today.year, today.month, 1)
            sl_bal.save()

            # Casual Leave — confirmed only
            if status == "confirmed":
                # Accrual after confirmation: use probation_end or DOJ as proxy
                anchor = probation_end or doj
                cl_months = _months_accrued_in_fy(anchor, today)
                cl_bal, _ = AvailableLeave.objects.get_or_create(
                    employee_id=emp,
                    leave_type_id=cl,
                    defaults={"available_days": 0, "carryforward_days": 0},
                )
                taken = float(cl_bal.leave_taken() or 0)
                cl_bal.available_days = max(0.0, float(cl_months) - taken)
                cl_bal.carryforward_days = 0
                cl_bal.reset_date = reset_date
                cl_bal.last_accrual_date = date(today.year, today.month, 1)
                cl_bal.save()
            else:
                # Probation: remove CL balance / do not credit
                AvailableLeave.objects.filter(
                    employee_id=emp, leave_type_id=cl
                ).delete()

        self.stdout.write(
            f"Assigned SL to {employees.count()} employees; "
            f"CL only for confirmed (FY accrual through {_fy_start_for(today)})"
        )

        # Shared unpaid / voting shells — assign so employees can request
        for type_name in ("Leave Without Pay", "Voting Leave"):
            lt = LeaveType.objects.filter(name=type_name, company_id=company).first()
            if not lt:
                continue
            for emp in employees:
                AvailableLeave.objects.get_or_create(
                    employee_id=emp,
                    leave_type_id=lt,
                    defaults={
                        "available_days": float(lt.total_days or 0),
                        "carryforward_days": 0,
                        "reset_date": reset_date if lt.reset else None,
                    },
                )
            self.stdout.write(f"Assigned {type_name} to active employees")

        # Eid already assigned by holiday seed; ensure still present
        eid = LeaveType.objects.filter(name="Eid Holiday", company_id=company).first()
        if eid:
            for emp in employees:
                AvailableLeave.objects.get_or_create(
                    employee_id=emp,
                    leave_type_id=eid,
                    defaults={"available_days": 2, "carryforward_days": 0, "reset_date": reset_date},
                )

    def _backfill_probation_dates(self, company):
        from employee.models import EmployeeWorkInformation

        updated = 0
        for wi in EmployeeWorkInformation.objects.filter(
            company_id=company, date_joining__isnull=False, probation_end__isnull=True
        ):
            wi.probation_end = wi.date_joining + relativedelta(months=6)
            wi.save(update_fields=["probation_end"])
            updated += 1
        self.stdout.write(f"Backfilled probation_end (DOJ+6m) on {updated} work info rows")
