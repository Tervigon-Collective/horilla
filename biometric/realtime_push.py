"""
Realtime Biometric (K7 firmware, "FK" web-push protocol) receiver.

The device POSTs to the configured "Web Server URL" with headers
``request_code`` (realtime_glog = a punch, realtime_enroll_data = a user record,
receive_cmd = "any commands for me?") and ``dev_id`` (its serial number). The
body is a 4-byte little-endian length followed by JSON, optionally followed by
binary blocks (photos/templates, which are ignored and never stored). The
device retries a message until the reply carries ``response_code: OK``.

Each punch is stored once in RealtimePunchLog and applied to attendance:
an open punch for the employee -> check-out, otherwise check-in (the device
doesn't report direction). Only punches made after the device was registered
in Horilla are applied, so its stored history can't collide with attendance
already recorded through the Check-in button and requests.
"""

import json
import logging
import struct
from datetime import datetime, timedelta

from django.db import IntegrityError, close_old_connections
from django.utils import timezone

logger = logging.getLogger(__name__)

DOUBLE_TAP = timedelta(minutes=2)


def parse_body(body):
    """JSON payload of a push message (length-prefixed), or {}."""
    if len(body) < 4:
        return {}
    length = struct.unpack("<I", body[:4])[0]
    try:
        return json.loads(body[4 : 4 + length].decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return {}


def find_device(serial):
    from biometric.models import BiometricDevices

    if not serial:
        return None
    return BiometricDevices._base_manager.filter(
        machine_type="realtime", serial_number=serial, is_active=True
    ).first()


def record_punch(device, payload):
    """Store one punch (idempotent). Returns the log row, or None if unparseable/duplicate."""
    from biometric.models import RealtimePunchLog

    user_id = str(payload.get("user_id") or "").strip()
    raw_time = str(payload.get("io_time") or "")
    try:
        punch_time = timezone.make_aware(datetime.strptime(raw_time, "%Y%m%d%H%M%S"))
    except ValueError:
        logger.warning("Realtime push: bad io_time %r from %s", raw_time, device)
        return None
    if not user_id:
        return None
    try:
        return RealtimePunchLog.objects.create(
            device_id=device,
            user_id=user_id,
            punch_time=punch_time,
            io_mode=payload.get("io_mode"),
            verify_mode=payload.get("verify_mode"),
        )
    except IntegrityError:
        return None  # the device re-sent a punch we already have


def apply_punch(log):
    """Turn a stored punch into a check-in/out. Leaves unmapped punches pending."""
    from attendance.methods.utils import Request
    from attendance.models import AttendanceActivity
    from attendance.views.clock_in_out import clock_in, clock_out
    from biometric.models import BiometricEmployees, RealtimePunchLog

    device = log.device_id
    if log.punch_time < device.created_at:
        log.processed, log.result = True, "history (before device go-live), stored only"
        log.save(update_fields=["processed", "result"])
        return log.result

    mapping = (
        BiometricEmployees.objects.filter(device_id=device, user_id=log.user_id)
        .select_related("employee_id__employee_user_id")
        .first()
    )
    if mapping is None or mapping.employee_id.employee_user_id is None:
        log.result = "pending: device user not linked to an employee"
        log.save(update_fields=["result"])
        return log.result

    employee = mapping.employee_id
    previous = (
        RealtimePunchLog.objects.filter(
            device_id=device, user_id=log.user_id, processed=True,
            punch_time__lt=log.punch_time,
        )
        .exclude(result__startswith="history")
        .order_by("-punch_time")
        .first()
    )
    if previous and log.punch_time - previous.punch_time < DOUBLE_TAP:
        log.processed, log.result = True, "ignored: double tap"
        log.save(update_fields=["processed", "result"])
        return log.result

    local = timezone.localtime(log.punch_time)
    request = Request(
        user=employee.employee_user_id,
        date=local.date(),
        time=local.time(),
        datetime=log.punch_time,
    )
    has_open_punch = AttendanceActivity.objects.filter(
        employee_id=employee, clock_out__isnull=True
    ).exists()
    try:
        (clock_out if has_open_punch else clock_in)(request)
        log.result = "check-out" if has_open_punch else "check-in"
    except Exception as exc:  # keep the receiver alive; the punch stays visible
        logger.exception("Realtime push: applying punch %s failed", log.pk)
        log.result = f"error: {exc}"[:200]
    log.processed = True
    log.save(update_fields=["processed", "result"])
    return log.result


def process_pending():
    """Apply punches that waited for an employee link (oldest first)."""
    from biometric.models import RealtimePunchLog

    close_old_connections()
    for log in RealtimePunchLog.objects.filter(processed=False).select_related(
        "device_id"
    ).order_by("punch_time"):
        apply_punch(log)


def handle_message(request_code, serial, body):
    """Process one push message; returns the response_code to send back."""
    close_old_connections()
    if request_code == "receive_cmd":
        return "ERROR_NO_CMD"
    device = find_device(serial)
    if device is None:
        # Acknowledge so an unregistered device doesn't flood us; nothing is stored.
        return "OK"
    if request_code == "realtime_glog":
        log = record_punch(device, parse_body(body))
        if log is not None:
            apply_punch(log)
    return "OK"
