import ipaddress

from django.conf import settings
from django.http import HttpResponseNotFound, HttpResponsePermanentRedirect
from django.http.request import split_domain_port, validate_host

LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "[::1]"}


def _is_public_ip(domain):
    try:
        return not ipaddress.ip_address(domain.strip("[]")).is_loopback
    except ValueError:
        return False


class CanonicalHostMiddleware:
    """
    Send requests for the server's bare IP to PRIMARY_HOST. Other hostnames
    that are not in ALLOWED_HOSTS belong to other services sharing this server
    (e.g. posthog.seleric.com) and get a plain 404 rather than being sent to
    HRMS. Runs before anything that calls request.get_host(), so neither case
    raises DisallowedHost.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        primary = getattr(settings, "PRIMARY_HOST", "")
        raw_host = request.META.get("HTTP_HOST", "")
        domain, _port = split_domain_port(raw_host)
        if domain and domain != primary and domain not in LOOPBACK_HOSTS:
            if _is_public_ip(domain):
                if primary:
                    return HttpResponsePermanentRedirect(
                        f"https://{primary}{request.get_full_path()}"
                    )
            elif not validate_host(domain, settings.ALLOWED_HOSTS):
                return HttpResponseNotFound(
                    b"Not found", content_type="text/plain"
                )
        return self.get_response(request)
