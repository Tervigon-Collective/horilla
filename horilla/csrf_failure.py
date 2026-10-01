"""
CSRF failure handling.

A login form left open past its token's lifetime (or after signing in from
another tab) failed with Django's bare 403 page, which employees read as the
site being broken and retried several times. For the login page only, send
them back to a fresh login form with a message; every other CSRF failure keeps
the default 403.
"""

from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.csrf import csrf_failure as default_csrf_failure


def csrf_failure(request, reason=""):
    try:
        login_path = reverse("login")
    except Exception:
        login_path = "/login/"
    if request.method == "POST" and request.path == login_path:
        messages.info(
            request, _("Your login page had expired. Please sign in again.")
        )
        next_url = request.GET.get("next")
        target = login_path + (f"?next={next_url}" if next_url else "")
        return redirect(target)
    return default_csrf_failure(request, reason=reason)
