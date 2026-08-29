"""Auto-provision login user and default ESS permissions for new employees."""

from __future__ import annotations

import logging
import secrets

from django.contrib.auth.models import Group, Permission
from django.db import transaction

logger = logging.getLogger(__name__)

DEFAULT_EMPLOYEE_GROUP = "Employee"

# Self-service permissions for regular employees (not managers/admins).
# Do NOT include org-wide change/delete on leave/attendance/tickets — those let
# any ESS user pass manager_can_enter / has_perm gates for other people's records.
ESS_PERMISSION_CODENAMES = (
    "view_ownprofile",
    "change_ownprofile",
    "view_employee",
    "view_employeebankdetails",
    "add_leaverequest",
    "view_leaverequest",
    "view_availableleave",
    "view_leavetype",
    "view_holiday",
    "view_companyleave",
    "add_attendance",
    "view_attendance",
    "view_attendancelatecomeearlyout",
    "view_workrecords",
    "view_attendanceovertime",
    "view_payslip",
    "view_reimbursement",
    "add_reimbursement",
    # No change_reimbursement — that is approve/reject (HR/payroll only)
    "view_loanaccount",
    # No add/change_loanaccount — create/edit loans is HR/payroll only
    "add_ticket",
    "view_ticket",
    "add_assetrequest",
    "view_assetrequest",
    "view_employeeobjective",
    # No change_employeeobjective — edit others' OKRs is manager/HR only
    "view_announcement",
    "view_rotatingworktypeassign",
    "view_rotatingshiftassign",
    "view_shiftrequest",
    "add_shiftrequest",
    "view_worktyperequest",
    "add_worktyperequest",
    # Project self-service (lists stay scoped to own/team; Admin/HR/PM see all)
    "view_project",
    "add_project",
    "view_task",
    "add_task",
    "view_timesheet",
    "add_timesheet",
    "change_timesheet",
)


def sync_employee_group_permissions(group: Group) -> None:
    """Keep only ESS permissions on the Employee role (no HR work-info edits)."""
    ess_perms = list(Permission.objects.filter(codename__in=ESS_PERMISSION_CODENAMES))
    # Replace the full set so removed ESS privileges are revoked on next sync.
    group.permissions.set(ess_perms)


def ensure_employee_group() -> Group | None:
    group, _created = Group.objects.get_or_create(name=DEFAULT_EMPLOYEE_GROUP)
    sync_employee_group_permissions(group)
    return group


def _resolve_username(employee) -> str | None:
    email = (employee.email or "").strip()
    if email:
        return email
    badge = (employee.badge_id or "").strip()
    if badge:
        return badge
    if employee.pk:
        return f"employee_{employee.pk}"
    return None


def _apply_profile_permissions(user) -> None:
    for codename in ("view_ownprofile", "change_ownprofile"):
        perm = Permission.objects.filter(
            codename=codename, content_type__app_label="employee"
        ).first()
        if perm:
            user.user_permissions.add(perm)


def ensure_employee_user(employee):
    """
    Create HorillaUser for employee if missing.
    Returns the linked user (existing or newly created).
    """
    from horilla_auth.models import HorillaUser

    if employee.employee_user_id_id:
        user = employee.employee_user_id
        _apply_profile_permissions(user)
        return user

    username = _resolve_username(employee)
    if not username:
        logger.warning(
            "Cannot create user for employee %s: no email or badge", employee.pk
        )
        return None

    password = secrets.token_urlsafe(12)
    user = HorillaUser.objects.filter(username=username).first()
    if not user:
        email = (employee.email or "").strip()
        if email:
            user = HorillaUser.objects.filter(email=email).first()

    if not user:
        user = HorillaUser.objects.create_user(
            username=username,
            email=(employee.email or username),
            password=password,
            is_new_employee=True,
        )
    _apply_profile_permissions(user)

    employee.employee_user_id = user
    return user


def _employee_company(employee):
    from base.models import Company

    try:
        work = getattr(employee, "employee_work_info", None)
        if work and work.company_id_id:
            return work.company_id
    except Exception:
        pass
    return Company.objects.filter(hq=True).first() or Company.objects.first()


def _has_non_employee_role(user, employee_group: Group) -> bool:
    from base.models import CompanyGroupAssignment

    return (
        CompanyGroupAssignment.objects.filter(user=user)
        .exclude(group=employee_group)
        .exists()
    )


def bootstrap_employee_access(employee, *, skip_if_assigned: bool = True) -> bool:
    """
    Ensure user exists and assign default Employee role for the work company.

    Skips users who already have manager/admin roles (non-Employee groups).
    Updates Employee group company when work info changes.
    """
    from base.models import CompanyGroupAssignment

    user = ensure_employee_user(employee)
    if not user:
        return False

    group = ensure_employee_group()
    if not group:
        return False

    company = _employee_company(employee)
    if not company:
        return False

    if skip_if_assigned and _has_non_employee_role(user, group):
        return False

    with transaction.atomic():
        CompanyGroupAssignment.objects.filter(user=user, group=group).exclude(
            company=company
        ).delete()
        CompanyGroupAssignment.objects.get_or_create(
            user=user,
            group=group,
            company=company,
        )
        CompanyGroupAssignment.sync_user_group_membership(user, group)

    return True


def bootstrap_employees_queryset(queryset, *, skip_if_assigned: bool = True) -> int:
    count = 0
    for employee in queryset.select_related("employee_user_id", "employee_work_info"):
        if bootstrap_employee_access(employee, skip_if_assigned=skip_if_assigned):
            count += 1
    return count


def repair_orphan_employee_users() -> int:
    """
    Link HorillaUser rows that match employee email but are not connected.
    """
    from horilla_auth.models import HorillaUser

    from employee.models import Employee

    fixed = 0
    for employee in Employee.objects.filter(
        employee_user_id__isnull=True, is_active=True
    ).exclude(email__isnull=True).exclude(email=""):
        user = HorillaUser.objects.filter(username=employee.email).first()
        if not user:
            user = HorillaUser.objects.filter(email=employee.email).first()
        if user:
            employee.employee_user_id = user
            employee.save(update_fields=["employee_user_id"])
            bootstrap_employee_access(employee, skip_if_assigned=True)
            fixed += 1
    return fixed
