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


def badge_user_id_from_str(badge_id):
    """Extract numeric suffix from badge string ("PEP0031" -> "31"), or None."""
    if not badge_id:
        return None
    match = re.search(r"(\d+)\s*$", badge_id)
    return str(int(match.group(1))) if match else None


def badge_user_id(employee):
    """Device user id from the badge number ("PEP0031" -> "31"), or None."""
    match = re.search(r"(\d+)\s*$", employee.badge_id or "")
    return str(int(match.group(1))) if match else None


def realtime_devices():
    from biometric.models import BiometricDevices

    return BiometricDevices._base_manager.filter(machine_type="realtime", is_active=True)


def sync_employee(employee_pk, old):
    from biometric.models import BiometricEmployees
    from biometric.realtime_push import queue_command
    from biometric.views import realtime_device_name

    employee = Employee.objects.filter(pk=employee_pk).first()
    if employee is None:
        return
    name = realtime_device_name(employee)
    for device in realtime_devices():
        link = BiometricEmployees.objects.filter(
            device_id=device, employee_id=employee
        ).first()
        if not employee.is_active:
            if link and old.get("is_active"):
                queue_command(device, "DELETE_USER", {"user_id": link.user_id})
            continue
        if link is None:
            user_id = badge_user_id(employee)
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
        elif old.get("is_active", True) and old.get("name") == name and old.get("badge_id") == employee.badge_id:
            continue  # nothing the device shows has changed

        # Badge ID changed -> device user ID must change
        old_badge_id = old.get("badge_id")
        new_user_id = badge_user_id(employee)
        if old_badge_id and new_user_id and badge_user_id_from_str(old_badge_id) != new_user_id:
            # Delete old device user
            if link:
                queue_command(device, "DELETE_USER", {"user_id": link.user_id})
            # Create new device user with new ID
            link = BiometricEmployees.objects.update_or_create(
                device_id=device, employee_id=employee,
                defaults={"user_id": new_user_id, "ref_user_id": int(new_user_id)}
            )[0]
            queue_command(
                device,
                "SET_USER_INFO",
                {"user_id": new_user_id, "user_name": name, "user_privilege": "USER", "enroll_data_array": []},
            )
        # Reactivation after deactivation: device user was deleted, so use
        # SET_USER_INFO to create (follow_up will then push saved faces).
        elif not old.get("is_active", True) and employee.is_active:
            queue_command(
                device,
                "SET_USER_INFO",
                {"user_id": link.user_id, "user_name": name, "user_privilege": "USER", "enroll_data_array": []},
            )
        else:
            queue_command(device, "SET_USER_NAME", {"user_id": link.user_id, "user_name": name})


@receiver(pre_save, sender=Employee)
def remember_device_fields(sender, instance, **kwargs):
    from biometric.views import realtime_device_name

    previous = Employee.objects.filter(pk=instance.pk).first() if instance.pk else None
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
