"""
Tell superusers when a newer Horilla release has been published.

The GitHub lookup is cached and only ever made from the background request the
notice loads with, so a slow or unreachable GitHub never delays a page.
"""

import json
import logging
import re
import urllib.request

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse
from django.shortcuts import render

from horilla.__version__ import __version__
from horilla.decorators import login_required

logger = logging.getLogger(__name__)

CACHE_KEY = "horilla:latest_release"
SUCCESS_TTL = 6 * 60 * 60
# A failed lookup is remembered too, so an outage is not retried on every page.
FAILURE_TTL = 60 * 60
_NO_RELEASE = "none"


def parse_version(tag):
    """'v2.1.10' -> (2, 1, 10). Non-numeric suffixes are ignored."""
    return tuple(int(part) for part in re.findall(r"\d+", str(tag or ""))[:4])


def latest_release():
    cached = cache.get(CACHE_KEY)
    if cached is not None:
        return None if cached == _NO_RELEASE else cached

    release = None
    try:
        req = urllib.request.Request(
            settings.HORILLA_RELEASES_API,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": f"horilla/{__version__}",
            },
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.load(resp)
        if data.get("tag_name") and not data.get("draft") and not data.get("prerelease"):
            release = {
                "tag": data["tag_name"],
                "name": data.get("name") or data["tag_name"],
                "url": data.get("html_url") or "",
                "published_at": (data.get("published_at") or "")[:10],
            }
    except Exception as exc:
        logger.info("Release check failed: %s", exc)

    cache.set(
        CACHE_KEY,
        release or _NO_RELEASE,
        SUCCESS_TTL if release else FAILURE_TTL,
    )
    return release


def available_update():
    """The latest release if it is newer than the running version, else None."""
    if not settings.HORILLA_RELEASE_CHECK:
        return None
    release = latest_release()
    if release and parse_version(release["tag"]) > parse_version(__version__):
        return release
    return None


@login_required
def release_update_notice(request):
    if not request.user.is_superuser:
        return HttpResponse("")
    release = available_update()
    if not release:
        return HttpResponse("")
    return render(
        request,
        "base/release_update_notice.html",
        {"release": release, "current_version": __version__},
    )
