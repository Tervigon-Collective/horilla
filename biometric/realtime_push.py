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
COMMAND_TIMEOUT = timedelta(minutes=5)


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

    # The device pushes ids zero-padded ("00000022") but shows them as "22";
    # accept a link stored either way.
    device_user = log.user_id.lstrip("0") or "0"
    mapping = (
        BiometricEmployees.objects.filter(
            device_id=device, user_id__in={log.user_id, device_user}
        )
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


def frame_json(data):
    """A command body: length-prefixed, NUL-terminated JSON (the device's own framing)."""
    raw = json.dumps(data).encode("utf-8") + b"\x00"
    return struct.pack("<I", len(raw)) + raw


def queue_command(device, cmd_code, params):
    from biometric.models import RealtimeDeviceCommand

    return RealtimeDeviceCommand.objects.create(
        device_id=device, cmd_code=cmd_code, params=params
    )


def next_command(device):
    """The oldest waiting command for this poll, marked sent. Commands go one at
    a time: the next is handed out only once the previous reported back (or
    timed out), so the device never has two user writes in flight."""
    from biometric.models import RealtimeDeviceCommand

    commands = RealtimeDeviceCommand.objects.filter(device_id=device)
    commands.filter(
        status="sent", updated_at__lt=timezone.now() - COMMAND_TIMEOUT
    ).update(status="error", result="no reply from device", updated_at=timezone.now())
    if commands.filter(status="sent").exists():
        return None
    command = commands.filter(status="waiting").order_by("pk").first()
    if command:
        command.status = "sent"
        command.save(update_fields=["status", "updated_at"])
    return command


_result_blocks = {}  # (serial, trans_id) -> {blk_no: bytes}; results come in blocks N..1, then 0


def record_result(device, headers, body):
    from biometric.models import RealtimeDeviceCommand

    trans_id = headers.get("trans_id", "")
    blk_no = int(headers.get("blk_no") or 0)
    key = (device.serial_number, trans_id)
    if blk_no:
        _result_blocks.setdefault(key, {})[blk_no] = body
        return
    parts = _result_blocks.pop(key, {})
    body = b"".join(parts[n] for n in sorted(parts)) + body
    if not trans_id.isdigit():
        return
    command = RealtimeDeviceCommand.objects.filter(
        device_id=device, pk=int(trans_id)
    ).first()
    if command is None:
        return
    return_code = headers.get("cmd_return_code", "OK")
    command.return_code = return_code[:40]
    command.status = "ok" if return_code == "OK" else "error"
    payload = parse_body(body)
    command.result = json.dumps(payload)[:20000] if payload else ""
    command.save(update_fields=["return_code", "status", "result", "updated_at"])


def handle_message(request_code, serial, body, headers=None):
    """Process one push message; returns (response_code, extra headers, body)."""
    headers = headers or {}
    close_old_connections()
    device = find_device(serial)
    if device is None:
        # Acknowledge so an unregistered device doesn't flood us; nothing is stored.
        return "OK", {}, b""
    if request_code == "receive_cmd":
        command = next_command(device)
        if command is None:
            # Plain OK = "nothing to do"; the device keeps polling (~10 s).
            return "OK", {}, b""
        return (
            "OK",
            {"trans_id": str(command.pk), "cmd_code": command.cmd_code},
            frame_json(command.params),
        )
    if request_code == "send_cmd_result":
        record_result(device, headers, body)
        return "OK", {"trans_id": headers.get("trans_id", "")}, b""
    if request_code == "realtime_glog":
        log = record_punch(device, parse_body(body))
        if log is not None:
            apply_punch(log)
    return "OK", {}, b""
