from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class LmsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "lms"
    verbose_name = _("Learning")

    def ready(self):
        from django.conf import settings
        from django.urls import include, path

        from horilla.urls import urlpatterns

        if "lms" not in settings.APPS:
            settings.APPS.append("lms")
        urlpatterns.append(path("lms/", include("lms.urls")))
        super().ready()
