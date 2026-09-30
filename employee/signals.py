"""Employee app signals — access bootstrap when work info is saved."""

from django.db import transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from employee.models import EmployeeWorkInformation


@receiver(pre_save, sender=EmployeeWorkInformation)
def remember_previous_reporting_manager(sender, instance, **kwargs):
    if kwargs.get("raw") or not instance.pk:
        instance._previous_reporting_manager_id = None
        return
    instance._previous_reporting_manager_id = (
        EmployeeWorkInformation.objects.filter(pk=instance.pk)
        .values_list("reporting_manager_id", flat=True)
        .first()
    )


@receiver(post_save, sender=EmployeeWorkInformation)
def transfer_pending_on_reporting_manager_change(sender, instance, **kwargs):
    old_manager_id = getattr(instance, "_previous_reporting_manager_id", None)
    new_manager_id = instance.reporting_manager_id_id
    if kwargs.get("raw") or not old_manager_id or old_manager_id == new_manager_id:
        return

    from employee.methods.manager_transfer import transfer_pending_to_new_manager

    employee_id = instance.employee_id_id
    transaction.on_commit(
        lambda: transfer_pending_to_new_manager(
            employee_id, old_manager_id, new_manager_id
        )
    )


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
