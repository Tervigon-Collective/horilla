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

from .base import DATABASES, INSTALLED_APPS

DATABASES["default"]["CONN_MAX_AGE"] = 60
DATABASES["default"]["CONN_HEALTH_CHECKS"] = True

if "geofencing" not in INSTALLED_APPS:
    INSTALLED_APPS.append("geofencing")
