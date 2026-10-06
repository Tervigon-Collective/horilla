"""
Receive punches pushed by Realtime Biometric devices (FK web-push protocol),
and hand them queued commands (e.g. pushing employee names) when they poll.

Run as its own service with the device's "Web Server URL" pointing here:

    python manage.py run_realtime_push_server --port 2024

See biometric/realtime_push.py for the protocol and how punches are applied.
"""

import logging
import socket
import threading
import time

from django.core.management.base import BaseCommand

from biometric.realtime_push import handle_message, process_pending

logger = logging.getLogger(__name__)

MAX_BODY = 4 * 1024 * 1024  # enroll messages carry photos; never buffer more


def _read_request(conn):
    conn.settimeout(20)
    data = b""
    while b"\r\n\r\n" not in data:
        chunk = conn.recv(4096)
        if not chunk:
            return None, b""
        data += chunk
        if len(data) > 65536:
            return None, b""
    head, _, body = data.partition(b"\r\n\r\n")
    headers = {}
    for line in head.split(b"\r\n")[1:]:
        key, _, value = line.decode("latin-1").partition(":")
        headers[key.strip().lower()] = value.strip()
    length = min(int(headers.get("content-length") or 0), MAX_BODY)
    while len(body) < length:
        chunk = conn.recv(65536)
        if not chunk:
            break
        body += chunk
    return headers, body[:length]


def _serve(conn):
    try:
        headers, body = _read_request(conn)
        if headers is None:
            return
        code = headers.get("request_code", "")
        if code != "receive_cmd":
            logger.warning("Realtime push: %s from %s", code, headers.get("dev_id"))
        response_code, extra, payload = handle_message(
            code, headers.get("dev_id", ""), body, headers
        )
        if "trans_id" not in extra and headers.get("trans_id"):
            extra["trans_id"] = headers["trans_id"]
        lines = "".join(f"{k}: {v}\r\n" for k, v in extra.items() if v)
        conn.sendall(
            (
                f"HTTP/1.0 200 OK\r\nresponse_code: {response_code}\r\n{lines}"
                "Content-Type: application/octet-stream\r\n"
                f"Content-Length: {len(payload)}\r\nConnection: close\r\n\r\n"
            ).encode()
            + payload
        )
    except Exception:
        logger.exception("Realtime push: request failed")
    finally:
        conn.close()


class Command(BaseCommand):
    help = "Receive punches pushed by Realtime Biometric devices."

    def add_arguments(self, parser):
        parser.add_argument("--port", type=int, default=2024)

    def handle(self, *args, port, **options):
        def pending_loop():
            while True:
                try:
                    process_pending()
                except Exception:
                    logger.exception("Realtime push: pending punches failed")
                time.sleep(10)

        threading.Thread(target=pending_loop, daemon=True).start()
        server = socket.socket()
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(("0.0.0.0", port))
        server.listen(64)
        self.stdout.write(f"Realtime push receiver listening on :{port}")
        while True:
            conn, _ = server.accept()
            threading.Thread(target=_serve, args=(conn,), daemon=True).start()
