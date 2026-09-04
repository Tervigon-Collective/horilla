# Gunicorn configuration for Horilla-HR
# This file provides advanced configuration options for the WSGI server

import multiprocessing
import os

# Bind settings
bind = f"0.0.0.0:{os.environ.get('PORT', '8000')}"
host = "0.0.0.0"
port = int(os.environ.get("PORT", "8000"))

# Worker settings
workers = int(
    os.environ.get(
        "GUNICORN_WORKERS", max(2, min(multiprocessing.cpu_count() * 2 + 1, 8))
    )
)
worker_class = "gthread"
threads = 4
worker_connections = 1000
# Higher recycle threshold: notification polling + dashboard fan-out was
# recycling workers often enough to surface as nginx 502 / connection resets.
max_requests = int(os.environ.get("GUNICORN_MAX_REQUESTS", "5000"))
max_requests_jitter = int(os.environ.get("GUNICORN_MAX_REQUESTS_JITTER", "200"))
# preload_app is disabled with gthread workers to avoid ORM connection issues
preload_app = False

# Timeout settings
timeout = int(os.environ.get("GUNICORN_TIMEOUT", "120"))
graceful_timeout = int(os.environ.get("GUNICORN_GRACEFUL_TIMEOUT", "30"))
keepalive = 5

# Logging
accesslog = "-"
errorlog = "-"
loglevel = os.environ.get("GUNICORN_LOG_LEVEL", "info")
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process naming
proc_name = "horilla-hrms"

# Server mechanics
pidfile = "/tmp/gunicorn.pid"
user = None  # Run as current user in container
group = None
tmp_upload_dir = None

# Development settings
reload = os.environ.get("GUNICORN_RELOAD", "false").lower() == "true"

# SSL settings (if needed)
# ssl_keyfile = os.environ.get('SSL_KEYFILE')
# ssl_certfile = os.environ.get('SSL_CERTFILE')
