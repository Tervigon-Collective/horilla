"""
Database connection helpers for background jobs and threads.

APScheduler jobs and worker threads do not get Django's per-request connection
cleanup. Without explicit cleanup, PostgreSQL sessions can remain idle in
transaction and hold server resources.
"""

from __future__ import annotations

import functools
import threading
from collections.abc import Callable
from typing import Any, ParamSpec, TypeVar

from apscheduler.schedulers.background import BackgroundScheduler
from django.db import close_old_connections

P = ParamSpec("P")
R = TypeVar("R")


def close_db_connections() -> None:
    """Close stale DB connections for the current thread."""
    close_old_connections()


def scheduled_job(func: Callable[P, R]) -> Callable[P, R]:
    """Wrap a scheduled job so DB connections are always cleaned up."""

    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        close_old_connections()
        try:
            return func(*args, **kwargs)
        finally:
            close_old_connections()

    return wrapper


class SafeBackgroundScheduler(BackgroundScheduler):
    """APScheduler that wraps every job with DB connection cleanup."""

    def add_job(self, func, *args, **kwargs):
        return super().add_job(scheduled_job(func), *args, **kwargs)


def run_in_db_thread(target: Callable[P, R], *args: P.args, **kwargs: P.kwargs) -> threading.Thread:
    """Start a thread that cleans up DB connections when finished."""

    @scheduled_job
    def _target() -> R:
        return target(*args, **kwargs)

    return threading.Thread(target=_target, daemon=kwargs.pop("daemon", False))
