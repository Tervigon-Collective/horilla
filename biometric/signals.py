"""
Keep Realtime (web push) devices in step with Horilla employees.

- A new employee is linked to every active Realtime device under their badge
  number (PEP0031 -> device user 31) and created on the device.
- A first-name change renames them on the device.
- Deactivating an employee removes them from the device so they can't punch;
  their face stays saved in Horilla (BiometricFaceData). Reactivating creates
  them again and the saved face goes back with them.

Commands are queued; the device collects them when it polls. Faces themselves
can only be captured on the device (enrolment), after which they're saved.
"""

import logging
import re

from django.db import transaction
from django.db.models.signals import post_save, pre_delete, pre_save
from django.dispatch import receiver

from employee.models import Employee

logger = logging.getLogger(__name__)


def badge_user_id(employee):
    """Device user id from the badge number ("PEP0031" -> "31"), or None."""
    match = re.search(r"(\d+)\s*$", employee.badge_id or "")
    return str(int(match.group(1))) if match else None


def realtime_devices():
    from biometric.models import BiometricDevices

    return BiometricDevices._base_manager.filter(machine_type="realtime", is_active=True)


def sync_employee(employee_pk, old):
    from biometric.models import BiometricEmployees, BiometricFaceData
    from biometric.realtime_push import normalize_user_id, queue_command
    from biometric.views import realtime_device_name

    # _base_manager: inside a request the default manager hides inactive
    # employees, which made deactivations invisible here.
    employee = Employee._base_manager.filter(pk=employee_pk).first()
    if employee is None:
        return
    name = realtime_device_name(employee)
    user_id = badge_user_id(employee)
    for device in realtime_devices():
        link = BiometricEmployees.objects.filter(
            device_id=device, employee_id=employee
        ).first()
        if not employee.is_active:
            if link and old.get("is_active"):
                queue_command(device, "DELETE_USER", {"user_id": link.user_id})
            continue
        if link and user_id and normalize_user_id(link.user_id) != user_id:
            # Badge number changed: the person moves to the new device id.
            if BiometricEmployees.objects.filter(device_id=device, user_id=user_id).exists():
                logger.warning(
                    "Biometric: device user %s already linked; %s keeps %s",
                    user_id, employee, link.user_id,
                )
            else:
                queue_command(device, "DELETE_USER", {"user_id": link.user_id})
                if not BiometricFaceData.objects.filter(device_user_id=user_id).exists():
                    BiometricFaceData.objects.filter(
                        device_user_id=normalize_user_id(link.user_id)
                    ).update(device_user_id=user_id)
                link.user_id, link.ref_user_id = user_id, int(user_id)
                link.save(update_fields=["user_id", "ref_user_id"])
                old = {}  # recreate below
        if link is None:
            if user_id is None:
                continue
            if BiometricEmployees.objects.filter(device_id=device, user_id=user_id).exists():
                logger.warning(
                    "Biometric: device user %s already linked; %s not linked",
                    user_id, employee,
                )
                continue
            link = BiometricEmployees.objects.create(
                device_id=device, employee_id=employee, user_id=user_id,
                ref_user_id=int(user_id),
            )
        elif old.get("is_active") and old.get("name") == name:
            continue  # nothing the device shows has changed
        # Always SET_USER_NAME first: it renames an existing user without
        # touching their face. A user the device lacks (new, reactivated, new
        # badge) answers ERROR_NOT_EXIST, and realtime_push.follow_up then
        # creates them with SET_USER_INFO and sends their saved face.
        queue_command(
            device, "SET_USER_NAME", {"user_id": link.user_id, "user_name": name}
        )


@receiver(pre_save, sender=Employee)
def remember_device_fields(sender, instance, **kwargs):
    from biometric.views import realtime_device_name

    previous = (
        Employee._base_manager.filter(pk=instance.pk).first() if instance.pk else None
    )
    instance._biometric_old = (
        {"is_active": previous.is_active, "name": realtime_device_name(previous)}
        if previous
        else {}
    )


@receiver(post_save, sender=Employee)
def push_employee_to_devices(sender, instance, created, **kwargs):
    old = getattr(instance, "_biometric_old", {})

    def run():
        try:
            sync_employee(instance.pk, old)
        except Exception:  # never let a device problem break saving an employee
            logger.exception("Biometric: syncing %s to devices failed", instance.pk)

    transaction.on_commit(run)


@receiver(pre_delete, sender=Employee)
def remove_employee_from_devices(sender, instance, **kwargs):
    from biometric.models import BiometricEmployees
    from biometric.realtime_push import queue_command

    try:
        for link in BiometricEmployees.objects.filter(
            employee_id=instance, device_id__in=realtime_devices()
        ).select_related("device_id"):
            queue_command(link.device_id, "DELETE_USER", {"user_id": link.user_id})
    except Exception:
        logger.exception("Biometric: removing %s from devices failed", instance.pk)
