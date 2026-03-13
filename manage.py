#!/usr/bin/env python3
"""Django's command-line utility for administrative tasks."""
import os
import sys
import warnings

# Suppress requests dependency version warning (must be before requests is imported)
warnings.filterwarnings("ignore", message=".*doesn't match a supported version.*")


def main():
    """Run administrative tasks."""
    # On Windows, ensure gettext (msgfmt) is on PATH if installed in default location
    if sys.platform == "win32":
        gettext_bin = r"C:\Program Files\gettext-iconv\bin"
        if os.path.isdir(gettext_bin) and os.path.isfile(os.path.join(gettext_bin, "msgfmt.exe")):
            path = os.environ.get("PATH", "")
            if gettext_bin not in path:
                os.environ["PATH"] = gettext_bin + os.pathsep + path

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "horilla.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
