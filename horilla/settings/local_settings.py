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
