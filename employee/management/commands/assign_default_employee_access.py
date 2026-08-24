"""Assign default Employee role and ESS permissions to staff without roles."""

from django.core.management.base import BaseCommand

from employee.methods.user_bootstrap import (
    bootstrap_employees_queryset,
    ensure_employee_group,
    repair_orphan_employee_users,
)
from employee.models import Employee


class Command(BaseCommand):
    help = (
        "Assign the default Employee group and ESS permissions to active employees "
        "who have no manager role yet. Also links orphan login users."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--all",
            action="store_true",
            help="Re-run bootstrap even if the user already has the Employee role.",
        )
        parser.add_argument(
            "--employee-id",
            type=int,
            help="Bootstrap a single employee by id.",
        )
        parser.add_argument(
            "--repair-orphans",
            action="store_true",
            help="Link users that match employee email but are not connected.",
        )

    def handle(self, *args, **options):
        ensure_employee_group()
        skip_if_assigned = not options["all"]

        if options["repair_orphans"]:
            linked = repair_orphan_employee_users()
            self.stdout.write(
                self.style.SUCCESS(f"Linked {linked} orphan user(s) to employees.")
            )

        if options["employee_id"]:
            qs = Employee.objects.filter(pk=options["employee_id"], is_active=True)
        else:
            qs = Employee.objects.filter(is_active=True)

        count = bootstrap_employees_queryset(qs, skip_if_assigned=skip_if_assigned)
        self.stdout.write(
            self.style.SUCCESS(f"Bootstrapped access for {count} employee(s).")
        )
