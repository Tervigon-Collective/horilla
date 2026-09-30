"""
Static files storage for production: hashed filenames + pre-compressed copies.

WhiteNoise serves hashed files with a one-year immutable Cache-Control, so
browsers stop re-downloading CSS/JS on every page (the plain storage only
allowed max-age=60). Filenames change with content, so a deploy can't leave
users on stale assets.

Vendored bundles reference files we don't ship (source maps, glyphicon fonts
in bootstrap.min.css). Those references are left untouched instead of failing
collectstatic, and templates asking for an unknown file fall back to the
unhashed URL instead of raising. Leading slashes in {% static %} are ignored,
as they were with the plain storage.
"""

from django.contrib.staticfiles.storage import StaticFilesStorage
from django.core.exceptions import SuspiciousFileOperation
from whitenoise.storage import CompressedManifestStaticFilesStorage


class ForgivingManifestStaticFilesStorage(CompressedManifestStaticFilesStorage):
    manifest_strict = False

    patterns = tuple(
        (ext, tuple(p for p in pats if "sourceMappingURL" not in str(p)))
        for ext, pats in CompressedManifestStaticFilesStorage.patterns
    )

    def url(self, name, force=False):
        # ~180 templates write {% static '/x.js' %}. Plain storage tolerated
        # the leading slash; manifest lookup raises SuspiciousFileOperation.
        name = name.lstrip("/") if name else name
        try:
            return super().url(name, force)
        except (ValueError, SuspiciousFileOperation):
            # Never 500 a page over an asset URL; serve it unhashed instead.
            return StaticFilesStorage.url(self, name)

    def hashed_name(self, name, content=None, filename=None):
        try:
            return super().hashed_name(name, content, filename)
        except ValueError as exc:
            if content is None and "could not be found" in str(exc):
                return name
            raise
