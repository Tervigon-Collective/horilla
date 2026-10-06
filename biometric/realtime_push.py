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
from attendance.methods.effective_shift import resolve_effective_shift
from attendance.methods.utils import shift_schedule_today
from django.utils import timezone
from django.utils.translation import gettext as _

logger = logging.getLogger(__name__)

DOUBLE_TAP = timedelta(minutes=2)
COMMAND_TIMEOUT = timedelta(minutes=5)
MAX_MESSAGE = 4 * 1024 * 1024
CONTACT_EVERY = timedelta(seconds=30)
OFFLINE_AFTER = timedelta(minutes=30)
# Web + device for the same action (check in on the phone, then the door).
SAME_ACTION = timedelta(minutes=10)
# A face enrolment logs a punch; its upload arrives within seconds of it.
ENROLMENT_WINDOW = timedelta(seconds=90)
# Punches wait this long before applying, so the enrolment upload can arrive.
APPLY_AFTER = timedelta(seconds=30)
PARTIAL_TTL = timedelta(minutes=5)


def parse_body(body):
    """JSON payload of a push message (length-prefixed), or {}."""
    if len(body) < 4:
        return {}
    length = struct.unpack("<I", body[:4])[0]
    try:
        return json.loads(body[4 : 4 + length].decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return {}


def split_blocks(body):
    """The length-prefixed blocks of a message: [JSON, BIN_1, BIN_2, ...]."""
    blocks, offset = [], 0
    while offset + 4 <= len(body):
        length = struct.unpack("<I", body[offset : offset + 4])[0]
        offset += 4
        if length == 0 or offset + length > len(body):
            break
        blocks.append(body[offset : offset + length])
        offset += length
    return blocks


def normalize_user_id(user_id):
    """Device ids arrive zero-padded ("00000022"); store them as shown ("22")."""
    return str(user_id or "").strip().lstrip("0") or "0"


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


DEVICE_POINT = {
    "ip": "132.154.65.28",
    "address": "Office - Realtime Pro T304 Mini (132.154.65.28)",
}


def attendance_day(employee, punch_local):
    """(attendance_date, EmployeeShiftDay, shift, minimum_hour, start_sec, end_sec)
    for a punch. As with the web Check-in, a night shift's morning punches
    belong to the previous day."""
    from base.models import EmployeeShiftDay

    shift = resolve_effective_shift(employee, punch_local)
    date_today = punch_local.date()
    day = EmployeeShiftDay.objects.filter(day=punch_local.strftime("%A").lower()).first()
    minimum_hour, start_sec, end_sec = (
        shift_schedule_today(day=day, shift=shift) if shift and day else ("00:00", 0, 0)
    )
    if start_sec > end_sec and punch_local.hour < 12:
        yesterday = date_today - timedelta(days=1)
        day = EmployeeShiftDay.objects.filter(day=yesterday.strftime("%A").lower()).first()
        if day:
            minimum_hour, start_sec, end_sec = shift_schedule_today(day=day, shift=shift)
        date_today = yesterday
    return date_today, day, shift, minimum_hour, start_sec, end_sec


def _at(day, time):
    return timezone.make_aware(datetime.combine(day, time))


def is_enrolment_punch(log):
    """The device logs a punch whenever someone enrolls a face (it verifies the
    new face). Those aren't check-ins or check-outs."""
    from biometric.models import BiometricFaceData

    enrolled = BiometricFaceData.objects.filter(
        device_user_id=normalize_user_id(log.user_id)
    ).values_list("updated_at", flat=True)
    return any(
        min(abs(at - log.received_at), abs(at - log.punch_time)) <= ENROLMENT_WINDOW
        for at in enrolled
    )


def tag_location(instance, key):
    meta = dict(instance.punch_location or {})
    meta[key] = DEVICE_POINT
    type(instance).objects.filter(pk=instance.pk).update(punch_location=meta)


def apply_punch(log):
    """
    Turn a stored punch into a check-in/out. The device doesn't say which, and
    people also use the web Check-in button (WFH, or before reaching the
    device), so the punch is read against the employee's last action from
    either source:
      - checked in less than SAME_ACTION ago, or checked out less than
        SAME_ACTION ago -> the same action done twice (web + device): ignored;
      - checked in (today)  -> check-out;
      - otherwise           -> check-in (a check-in left open on an earlier
        day is not closed at today's time).
    Punches from face enrolment are ignored. Unmapped punches stay pending.
    """
    from attendance.models import Attendance, AttendanceActivity
    from attendance.views.clock_in_out import (
        clock_in_attendance_and_activity,
        clock_out_attendance_and_activity,
    )
    from biometric.models import BiometricEmployees

    def done(result):
        log.processed, log.result = True, result[:200]
        log.save(update_fields=["processed", "result"])
        return log.result

    device = log.device_id
    if log.punch_time < device.created_at:
        return done("history (before device go-live), stored only")

    # The device pushes ids zero-padded ("00000022") but shows them as "22";
    # accept a link stored either way.
    mapping = (
        BiometricEmployees.objects.filter(
            device_id=device,
            user_id__in={log.user_id, normalize_user_id(log.user_id)},
        )
        .select_related("employee_id__employee_user_id")
        .first()
    )
    if mapping is None or mapping.employee_id.employee_user_id is None:
        log.result = "pending: device user not linked to an employee"
        log.save(update_fields=["result"])
        return log.result
    if is_enrolment_punch(log):
        return done("ignored: face enrolment")

    employee = mapping.employee_id
    punch = timezone.localtime(log.punch_time)
    attendance_date, day, shift, minimum_hour, start_sec, end_sec = attendance_day(
        employee, punch
    )
    hhmm = punch.strftime("%H:%M")

    open_activity = (
        AttendanceActivity.objects.filter(employee_id=employee, clock_out__isnull=True)
        .order_by("-attendance_date", "-id")
        .first()
    )
    if open_activity and open_activity.attendance_date < attendance_date:
        open_activity = None  # forgotten check-out on an earlier day: leave it
    try:
        if open_activity:
            opened = _at(open_activity.clock_in_date, open_activity.clock_in)
            if timedelta(0) <= log.punch_time - opened < SAME_ACTION:
                return done(f"ignored: already checked in at {opened:%H:%M}")
            if log.punch_time < opened:
                return done("ignored: older than the current check-in")
            clock_out_attendance_and_activity(
                employee=employee, date_today=punch.date(), now=hhmm,
                out_datetime=punch,
            )
            tag_location(AttendanceActivity.objects.get(pk=open_activity.pk), "out")
            result = "check-out"
        else:
            last = (
                AttendanceActivity.objects.filter(
                    employee_id=employee, attendance_date=attendance_date,
                    clock_out__isnull=False,
                )
                .order_by("-clock_out_date", "-clock_out")
                .first()
            )
            if last:
                closed = _at(last.clock_out_date, last.clock_out)
                if timedelta(0) <= log.punch_time - closed < SAME_ACTION:
                    return done(f"ignored: already checked out at {closed:%H:%M}")
                if log.punch_time < closed:
                    return done("ignored: older than the last check-out")
            clock_in_attendance_and_activity(
                employee=employee, date_today=punch.date(),
                attendance_date=attendance_date, day=day, now=hhmm, shift=shift,
                minimum_hour=minimum_hour, start_time=start_sec, end_time=end_sec,
                in_datetime=punch,
            )
            created = (
                AttendanceActivity.objects.filter(employee_id=employee, clock_out__isnull=True)
                .order_by("-id")
                .first()
            )
            if created:
                tag_location(created, "in")
            result = "check-in"
        attendance = Attendance.objects.filter(
            employee_id=employee, attendance_date=attendance_date
        ).first()
        first_in = result == "check-in" and not AttendanceActivity.objects.filter(
            employee_id=employee, attendance_date=attendance_date
        ).exclude(clock_out__isnull=True).exists()
        if attendance and (result == "check-out" or first_in):
            # The day's check-in location is where the day started.
            tag_location(attendance, "out" if result == "check-out" else "in")
    except Exception as exc:  # keep the receiver alive; the punch stays visible
        logger.exception("Realtime push: applying punch %s failed", log.pk)
        result = f"error: {exc}"
    return done(result)


def process_pending():
    """Apply stored punches, oldest first, once they've waited APPLY_AFTER
    (so a face enrolment's upload can arrive) -- also ones that waited for an
    employee link."""
    from biometric.models import RealtimePunchLog

    close_old_connections()
    for log in (
        RealtimePunchLog.objects.filter(
            processed=False, received_at__lte=timezone.now() - APPLY_AFTER
        )
        .select_related("device_id")
        .order_by("punch_time")
    ):
        apply_punch(log)


def frame_json(data, binary=None):
    """A command body: length-prefixed, NUL-terminated JSON (the device's own
    framing), then the binary the JSON calls "BIN_1" as its own block."""
    raw = json.dumps(data).encode("utf-8") + b"\x00"
    body = struct.pack("<I", len(raw)) + raw
    if binary:
        body += struct.pack("<I", len(binary)) + bytes(binary)
    return body


def queue_command(device, cmd_code, params, binary=None):
    from biometric.models import RealtimeDeviceCommand

    # The same command already waiting (e.g. Push pressed twice): don't repeat
    # it -- unless something else for that user was queued after it (rename,
    # delete, rename again must all reach the device, in that order).
    latest = (
        RealtimeDeviceCommand.objects.filter(
            device_id=device, params__user_id=params.get("user_id"),
            status__in=["waiting", "sent"],
        )
        .order_by("-pk")
        .first()
        if params.get("user_id")
        else None
    )
    if (
        latest and not binary and latest.cmd_code == cmd_code
        and latest.params == params
    ):
        return None

    return RealtimeDeviceCommand.objects.create(
        device_id=device, cmd_code=cmd_code, params=params, binary=binary
    )


def save_enrollment(device, body):
    """Keep the face data and photo a device sent when someone enrolled: the
    templates go to BiometricFaceData, the photo becomes the linked employee's
    avatar."""
    from biometric.models import BiometricEmployees, BiometricFaceData

    blocks = split_blocks(body)
    try:
        info = json.loads(blocks[0].rstrip(b"\x00").decode("utf-8"))
    except (IndexError, ValueError, UnicodeDecodeError):
        return

    def binary(ref):
        ref = str(ref or "")
        if ref.startswith("BIN_") and ref[4:].isdigit() and int(ref[4:]) < len(blocks):
            return blocks[int(ref[4:])]
        return None

    raw_id = str(info.get("user_id") or "").strip()
    if not raw_id:
        return
    user_id = normalize_user_id(raw_id)
    link = (
        BiometricEmployees.objects.filter(
            device_id=device, user_id__in={raw_id, user_id}
        )
        .select_related("employee_id")
        .first()
    )
    employee = link.employee_id if link else None
    for entry in info.get("enroll_data_array") or []:
        data = binary(entry.get("enroll_data"))
        if data is None or entry.get("backup_number") is None:
            continue
        BiometricFaceData.objects.update_or_create(
            device_user_id=user_id,
            backup_number=int(entry["backup_number"]),
            defaults={"data": data, "employee_id": employee, "source_device": device},
        )
    photo = binary(info.get("user_photo"))
    if employee and photo:
        set_avatar(employee, photo)
    logger.warning(
        "Realtime push: saved enrolment of device user %s (%s)", user_id, employee
    )


def set_avatar(employee, photo):
    """Use the device's enrolment photo as the employee's Horilla avatar."""
    import io

    from django.core.files.base import ContentFile
    from PIL import Image

    from employee.models import Employee

    try:
        Image.open(io.BytesIO(photo)).verify()
    except Exception:
        return
    field = employee.employee_profile
    field.save(f"biometric-{employee.pk}.jpg", ContentFile(photo), save=False)
    # update() skips Employee.save()'s side effects; only the picture changes.
    Employee.objects.filter(pk=employee.pk).update(employee_profile=field.name)


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


# Large messages (photos, templates) arrive in parts: blk_no 1, 2, ... then the
# last part with blk_no 0. (serial, request_code, trans_id) -> (first seen, {blk_no: bytes})
_partial = {}


def assemble(serial, request_code, headers, body):
    """The whole message once its last part arrives, else None."""
    blk_no = int(headers.get("blk_no") or 0)
    key = (serial, request_code, headers.get("trans_id", ""))
    if blk_no:
        now = timezone.now()
        # A message whose last part never came (device rebooted) is dropped.
        for stale in [k for k, (started, _) in _partial.items() if now - started > PARTIAL_TTL]:
            _partial.pop(stale, None)
        started, parts = _partial.setdefault(key, (now, {}))
        if sum(map(len, parts.values())) + len(body) <= MAX_MESSAGE:
            parts[blk_no] = body
        return None
    _, parts = _partial.pop(key, (None, {}))
    return b"".join(parts[n] for n in sorted(parts)) + body


def record_result(device, headers, body):
    from biometric.models import RealtimeDeviceCommand

    trans_id = headers.get("trans_id", "")
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
    follow_up(device, command)


def follow_up(device, command):
    """Next step of pushing a user. SET_USER_NAME only renames on this
    firmware, so a user the device doesn't have is created with SET_USER_INFO
    (safe: SET_USER_INFO is only dangerous on a user who already has a face).
    Once the user exists, saved faces are sent with SET_ENROLL_DATA, which
    only fills an empty slot."""
    from biometric.models import BiometricFaceData

    params = command.params or {}
    if command.cmd_code == "SET_USER_NAME" and command.return_code == "ERROR_NOT_EXIST":
        queue_command(
            device,
            "SET_USER_INFO",
            {
                "user_id": params["user_id"],
                "user_name": params.get("user_name", ""),
                "user_privilege": "USER",
                "enroll_data_array": [],
            },
        )
    elif command.cmd_code in ("SET_USER_NAME", "SET_USER_INFO") and command.status == "ok":
        for face in BiometricFaceData.objects.filter(
            device_user_id=normalize_user_id(params.get("user_id"))
        ):
            queue_command(
                device,
                "SET_ENROLL_DATA",
                {
                    "user_id": params["user_id"],
                    "backup_number": face.backup_number,
                    "enroll_data": "BIN_1",
                },
                binary=bytes(face.data),
            )


_last_noted = {}


def note_contact(device):
    """Record when the device last called in (at most every 30 s)."""
    from biometric.models import BiometricDevices

    now = timezone.now()
    if now - _last_noted.get(device.pk, now - CONTACT_EVERY * 2) >= CONTACT_EVERY:
        _last_noted[device.pk] = now
        BiometricDevices._base_manager.filter(pk=device.pk).update(last_contact=now)


def device_status(device):
    """(online, message) for the Test Connection / Fetch Logs buttons."""
    from biometric.models import RealtimeDeviceCommand, RealtimePunchLog

    process_pending()
    if device.last_contact is None:
        return False, _("The device has not contacted Horilla yet. Check its Web Server URL.")
    ago = timezone.now() - device.last_contact
    seen = timezone.localtime(device.last_contact).strftime("%d %b %H:%M:%S")
    today = timezone.localtime().date()
    punches = RealtimePunchLog.objects.filter(
        device_id=device, punch_time__date=today
    ).count()
    pending = RealtimeDeviceCommand.objects.filter(
        device_id=device, status__in=["waiting", "sent"]
    ).count()
    unlinked = (
        RealtimePunchLog.objects.filter(device_id=device, processed=False)
        .values("user_id").distinct().count()
    )
    details = _(
        "Last contact {seen}. Punches today: {punches}. Commands waiting: "
        "{pending}. Unlinked device users with punches: {unlinked}. "
        "Punches arrive automatically; nothing needs fetching."
    ).format(seen=seen, punches=punches, pending=pending, unlinked=unlinked)
    return ago <= OFFLINE_AFTER, details


def handle_message(request_code, serial, body, headers=None):
    """Process one push message; returns (response_code, extra headers, body)."""
    headers = headers or {}
    close_old_connections()
    device = find_device(serial)
    if device is None:
        # Acknowledge so an unregistered device doesn't flood us; nothing is stored.
        return "OK", {}, b""
    note_contact(device)
    if request_code != "receive_cmd":
        body = assemble(serial, request_code, headers, body)
        if body is None:
            return "OK", {}, b""  # more parts to come
    if request_code == "receive_cmd":
        command = next_command(device)
        if command is None:
            # Plain OK = "nothing to do"; the device keeps polling (~10 s).
            return "OK", {}, b""
        return (
            "OK",
            {"trans_id": str(command.pk), "cmd_code": command.cmd_code},
            frame_json(command.params, command.binary),
        )
    if request_code == "realtime_enroll_data":
        save_enrollment(device, body)
        return "OK", {}, b""
    if request_code == "send_cmd_result":
        record_result(device, headers, body)
        return "OK", {"trans_id": headers.get("trans_id", "")}, b""
    if request_code == "realtime_glog":
        # Stored now, applied by process_pending after APPLY_AFTER.
        record_punch(device, parse_body(body))
    return "OK", {}, b""
