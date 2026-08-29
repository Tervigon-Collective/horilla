"""
Recalculate existing payslips so pay_head_data includes India statutory lines.

Use after enabling Indian statutory settings so Form 16 / challan exports
reflect PF, ESI, PT, and TDS on historical payslips.
"""

import json

from django.core.management.base import BaseCommand

from payroll.methods.methods import calculate_employer_contribution, save_payslip
from payroll.models.models import Payslip
from payroll.views.component_views import payroll_calculation


class Command(BaseCommand):
    help = (
        "Recalculate payslips to refresh pay head data (including India statutory)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--company",
            type=int,
            help="Limit to employees in this company id.",
        )
        parser.add_argument(
            "--status",
            nargs="+",
            default=["confirmed", "paid", "draft"],
            help="Payslip statuses to regenerate (default: confirmed paid draft).",
        )
        parser.add_argument(
            "--limit",
            type=int,
            help="Maximum number of payslips to process.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Count matching payslips without saving changes.",
        )

    def handle(self, *args, **options):
        company_id = options.get("company")
        statuses = options["status"]
        limit = options.get("limit")
        dry_run = options["dry_run"]

        qs = Payslip.objects.filter(status__in=statuses).select_related("employee_id")
        if company_id:
            qs = qs.filter(
                employee_id__employee_work_info__company_id_id=company_id
            ).distinct()
        # Never silently overwrite locked / frozen payroll snapshots
        qs = qs.filter(snapshot_frozen=False).exclude(
            payroll_run__status__in=["locked", "paid", "published"]
        )
        if limit:
            qs = qs[:limit]

        total = qs.count()
        updated = 0
        skipped = 0

        for payslip in qs.iterator():
            employee = payslip.employee_id
            payslip_data = payroll_calculation(
                employee, payslip.start_date, payslip.end_date
            )
            if not payslip_data:
                skipped += 1
                continue
            if dry_run:
                updated += 1
                continue

            data = {
                "employee": employee,
                "start_date": payslip_data["start_date"],
                "end_date": payslip_data["end_date"],
                "status": payslip.status,
                "contract_wage": payslip_data["contract_wage"],
                "basic_pay": payslip_data["basic_pay"],
                "gross_pay": payslip_data["gross_pay"],
                "deduction": payslip_data["total_deductions"],
                "net_pay": payslip_data["net_pay"],
                "pay_data": json.loads(payslip_data["json_data"]),
                "installments": payslip_data["installments"],
            }
            calculate_employer_contribution(data)
            try:
                from payroll.methods.payroll_run_engine import PayrollRunLockedError

                save_payslip(**data)
            except PayrollRunLockedError as exc:
                self.stdout.write(self.style.WARNING(str(exc)))
                skipped += 1
                continue
            updated += 1

        mode = "Would update" if dry_run else "Updated"
        self.stdout.write(
            self.style.SUCCESS(
                f"{mode} {updated} of {total} payslip(s); skipped {skipped}."
            )
        )
