"""
lms/sidebar.py
"""

from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _

MENU = _("Learning")
IMG_SRC = "images/ui/lms.svg"

SUBMENUS = [
    {
        "menu": _("Courses"),
        "redirect": reverse_lazy("lms-course-list"),
    },
    {
        "menu": _("My Learning"),
        "redirect": reverse_lazy("lms-my-learning"),
    },
]


def lms_accessibility(request, menu, user_perms, *args, **kwargs):
    return True
