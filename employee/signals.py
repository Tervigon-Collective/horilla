"""Employee app signals — access bootstrap when work info is saved."""

from django.db.models.signals import post_save
from django.dispatch import receiver

from employee.models import EmployeeWorkInformation


@receiver(post_save, sender=EmployeeWorkInformation)
def bootstrap_access_when_work_info_saved(sender, instance, **kwargs):
    """
    Assign/update default Employee role when company is set on work info.

    Covers recruitment conversion, onboarding portal, bulk import, and manual
    work-info updates that happen after the employee record is first created.
    """
    if kwargs.get("raw"):
        return
    if not instance.employee_id_id or not instance.company_id_id:
        return
    if not instance.employee_id.is_active:
        return

    from employee.methods.user_bootstrap import bootstrap_employee_access

    bootstrap_employee_access(instance.employee_id, skip_if_assigned=True)
