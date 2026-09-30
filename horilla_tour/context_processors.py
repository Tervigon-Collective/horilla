"""
Global template context for the tour engine.

Exposes a lightweight flag so the base template can render the "Help / Take a
tour" launcher (and an optional "pending" dot) without each page having to
know about tours. The heavy lifting — resolving which tour/steps apply — is
done lazily by the JS controller via the ``tour-active`` API.
"""

import logging

logger = logging.getLogger(__name__)


def pending_tours_flag(request):
    """Return launcher availability + whether the user has an unfinished tour."""
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return {"tour_launcher_enabled": False, "tour_has_pending": False}

    def load():
        try:
            from horilla_tour.models import Tour, TourProgress

            published = Tour.objects.filter(is_active=True, is_published=True)
            if not published.exists():
                return False
            done_ids = set(
                TourProgress.objects.filter(
                    user=user, status__in=["completed", "skipped"]
                ).values_list("tour_id", flat=True)
            )
            return (
                published.filter(trigger="auto_once").exclude(id__in=done_ids).exists()
            )
        except Exception as exc:  # never let the launcher break a page render
            logger.debug("pending_tours_flag skipped: %s", exc)
            return False

    from django.core.cache import cache

    key = f"horilla:tour-pending:{user.pk}"
    has_pending = cache.get(key)
    if has_pending is None:
        has_pending = load()
        cache.set(key, has_pending, 90)

    return {"tour_launcher_enabled": True, "tour_has_pending": has_pending}
