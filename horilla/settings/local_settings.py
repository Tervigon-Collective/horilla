"""
Tervigon Collective production overrides.
Imported last from horilla.settings.__init__ (after base + addons).
Do not use ``from .base import *`` here.
"""

DEBUG = False
ALLOWED_HOSTS = [
    "hrms.seleric.cloud",
    "hrms.seleric.com",
    "hrms.seleric.ai",
    "localhost",
    "127.0.0.1",
]
CSRF_TRUSTED_ORIGINS = [
    "https://hrms.seleric.cloud",
    "http://hrms.seleric.cloud",
    "https://hrms.seleric.com",
    "http://hrms.seleric.com",
    "https://hrms.seleric.ai",
    "http://hrms.seleric.ai",
]

from .base import DATABASES

DATABASES["default"]["CONN_MAX_AGE"] = 60
DATABASES["default"]["CONN_HEALTH_CHECKS"] = True

# Kill stuck PostgreSQL sessions server-side (idle in transaction / long SELECTs).
_db = DATABASES["default"]
if "postgresql" in _db.get("ENGINE", ""):
    _opts = _db.setdefault("OPTIONS", {})
    _pg_session = (
        "-c idle_in_transaction_session_timeout=60000 "
        "-c statement_timeout=120000 "
        "-c lock_timeout=30000"
    )
    _existing = _opts.get("options", "")
    _opts["options"] = f"{_existing} {_pg_session}".strip() if _existing else _pg_session
    _opts.setdefault("connect_timeout", 10)

WHITE_LABELLING = True
WHITE_LABEL_NAME = "Seleric HRMS"
DISABLE_AUTO_TOURS = True
DISABLE_SETUP_CHECKLIST = True

# Official 2.0 already registers geofencing from horilla_api.__init__.
# Do not append it again — Django rejects duplicate app labels.

# Expired login form -> fresh login page instead of a bare 403 (login only).
CSRF_FAILURE_VIEW = "horilla.csrf_failure.csrf_failure"

# Hashed + compressed static files so browsers can cache CSS/JS long-term
# (see horilla/static_storage.py).
from .base import STORAGES as _STORAGES

STORAGES = {
    **_STORAGES,
    "staticfiles": {
        "BACKEND": "horilla.static_storage.ForgivingManifestStaticFilesStorage"
    },
}

# Real client IP for django-axes lockouts and attendance IP rules. nginx sets
# X-Real-IP to $remote_addr (overwriting any client value) and gunicorn only
# listens on 127.0.0.1, so it can't be spoofed. Don't use AXES_PROXY_COUNT:
# nginx appends to X-Forwarded-For, which made the client-supplied (spoofable)
# entry win and returned no IP for normal visitors.
AXES_IPWARE_PROXY_COUNT = None
AXES_IPWARE_META_PRECEDENCE_ORDER = ["HTTP_X_REAL_IP", "REMOTE_ADDR"]

# Seleric's payroll/attendance month runs 26th -> 25th (horilla/payroll_cycle.py).
PAYROLL_CYCLE_START_DAY = 26
